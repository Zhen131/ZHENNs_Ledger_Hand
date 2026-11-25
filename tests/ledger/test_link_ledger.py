"""Tests of the real ledger's plug, against what the ledger really answered.

Every answer comes from ``tests/ledger/samples/``, the ledger's own answers
captured on 2026-11-25 (68C), handed back by a stand-in that plays them in
order and keeps what the plug asked. A few answers the capture did not
reach are written from the ledger's ``assistant-link/README.md`` and say
so where they are made. Every figure is invented.
"""

from __future__ import annotations

import copy
import dataclasses
import json
from collections.abc import Mapping
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from ledger_hand.assistant.lookups import when_text
from ledger_hand.core.ledger_records import (
    MOST_TRADES_LISTED,
    AssetKind,
    LedgerTrade,
    MoneyAmount,
    NotWorkedOut,
    PeriodRequest,
    Pricing,
    TradeFacts,
    TradeFilter,
)
from ledger_hand.core.proposals import TARGET_NOT_FOUND, CheckOutcome, ProposalStatus
from ledger_hand.core.trade import Side
from ledger_hand.ledger.link_client import AnswerKind, LedgerLink, ToolAnswer
from ledger_hand.ledger.link_failures import LedgerLinkError, LinkFailure
from ledger_hand.ledger.link_ledger import (
    ALL_TIME_START,
    CALL_FAILURES,
    TRADE_REFUSALS,
    LinkLedger,
    codes_on_no_table,
)
from ledger_hand.ports import LedgerError, LedgerErrorKind
from tests.ledger.test_link_client import ledger_folder, node, setup

__all__ = ["ledger_folder", "node"]  # the stand-in link's fixtures, used below

SAMPLES = Path(__file__).resolve().parent / "samples"
TODAY = date(2026, 11, 25)
MODEL = "qwen2.5:7b"
SAID = "今天10:15买了0.01 BTC，价格60000 USDT，手续费0"


def sample(name: str) -> ToolAnswer:
    answer = json.loads((SAMPLES / f"{name}.json").read_text(encoding="utf-8"))["answer"]
    return ToolAnswer(kind=AnswerKind(answer["kind"]), content=answer["content"])


def written_from_the_readme(code: str, message: str) -> ToolAnswer:
    """An error the capture did not reach, in the shape the ledger's README gives every error."""
    return ToolAnswer(
        kind=AnswerKind.ERROR,
        content={"code": code, "category": "temporarily-unavailable", "message": message},
    )


class SampleLink:
    """Plays the ledger's answers in order; each must be asked by the tool it answers."""

    def __init__(self, *script: tuple[str, ToolAnswer | Exception]) -> None:
        self.script = list(script)
        self.asked: list[tuple[str, dict[str, Any]]] = []

    def call(self, name: str, arguments: Mapping[str, Any]) -> ToolAnswer:
        self.asked.append((name, copy.deepcopy(dict(arguments))))
        assert self.script, f"nothing left to answer {name}"
        tool, answer = self.script.pop(0)
        assert tool == name, f"asked {name}, the script answers {tool}"
        if isinstance(answer, Exception):
            raise answer
        return answer

    def names(self) -> list[str]:
        return [name for name, _ in self.asked]


def plug(*script: tuple[str, ToolAnswer | Exception]) -> tuple[LinkLedger, SampleLink]:
    link = SampleLink(*script)
    return LinkLedger(link, model_name=MODEL, today=lambda: TODAY), link


ASSETS = ("list_assets", sample("list-assets"))


# --- assets -------------------------------------------------------------------


def test_assets_carry_their_kind_whether_they_price_a_trade_and_their_own_money() -> None:
    ledger, _ = plug(ASSETS)

    assets = {asset.code: asset for asset in ledger.list_assets()}

    assert (assets["BTC"].id, assets["BTC"].kind, assets["BTC"].price_currency) == (
        "asset-btc",
        AssetKind.CRYPTO,
        "USDT",
    )
    assert (assets["NVDA"].kind, assets["NVDA"].price_currency) == (AssetKind.STOCK, "USD")
    assert assets["CNY"].kind is AssetKind.CASH
    assert {code for code, a in assets.items() if a.pricing is Pricing.CAN_PRICE} == {
        "USDT",
        "USD",
        "CNY",
    }


# --- listing trades -----------------------------------------------------------


def test_trades_come_oldest_first_and_a_day_only_trade_is_its_day_alone() -> None:
    ledger, link = plug(("list_trades", sample("list-trades-no-filter")))

    listed = ledger.list_trades(TradeFilter())

    assert link.asked == [("list_trades", {})]
    assert not listed.cut
    # Oldest first: the ledger's own order (newest first, by the real moment) turned round.
    newest_first = [row["tradeId"] for row in sample("list-trades-no-filter").content["trades"]]
    assert [trade.id for trade in listed.trades] == newest_first[::-1]
    nvda = next(trade for trade in listed.trades if trade.facts.asset == "NVDA")
    assert nvda.facts.date_only and nvda.facts.day == date(2026, 11, 14)
    assert when_text(nvda.facts) == "2026-11-14"
    assert nvda.facts.zone is None
    sell = next(t for t in listed.trades if t.facts.asset == "BTC" and t.facts.side is Side.SELL)
    assert sell.facts.occurred == datetime(2026, 11, 16, 3, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    assert sell.facts.zone == "Asia/Shanghai"
    assert sell.realized == MoneyAmount(currency="USDT", amount=Decimal("195"))
    assert sell.realized_unreliable is None
    assert (sell.facts.platform, sell.facts.note) == ("", "")


def test_the_ledgers_own_machine_text_is_never_taken_for_the_users_words() -> None:
    ledger, _ = plug(("list_trades", sample("list-trades-no-filter")))

    listed = ledger.list_trades(TradeFilter())

    assert all(trade.facts.raw_text is None for trade in listed.trades)
    (zoned,) = ledger_with_zoned_trade()
    assert zoned.facts.raw_text == "Ledger Hand sample capture: invented trades only"


def ledger_with_zoned_trade() -> tuple[Any, ...]:
    ledger, _ = plug(("list_trades", sample("list-trades-on-2026-11-20-after-zoned-save")))
    day = date(2026, 11, 20)
    return ledger.list_trades(TradeFilter(first_day=day, last_day=day)).trades


def test_a_day_is_asked_as_both_its_ends_and_a_trade_falls_on_its_own_clock() -> None:
    ledger, link = plug(("list_trades", sample("list-trades-on-2026-11-20-after-zoned-save")))

    (trade,) = ledger.list_trades(
        TradeFilter(first_day=date(2026, 11, 20), last_day=date(2026, 11, 20))
    ).trades

    assert link.asked == [("list_trades", {"startDate": "2026-11-20", "endDate": "2026-11-20"})]
    # 22:30 in New York on 20 November is 03:30 on the 21st in UTC: it counts on the 20th.
    assert trade.facts.day == date(2026, 11, 20)
    assert trade.facts.occurred.astimezone(timezone.utc).day == 21


def test_every_page_is_read_and_the_second_asks_with_the_first_pages_token() -> None:
    first = sample("list-trades-page-1")
    ledger, link = plug(("list_trades", first), ("list_trades", sample("list-trades-page-2")))

    listed = ledger.list_trades(TradeFilter())

    assert len(listed.trades) == 50 + 17
    assert not listed.cut
    assert link.asked[1] == ("list_trades", {"pageToken": first.content["nextPageToken"]})


def test_a_ledger_changed_in_between_starts_again_and_never_mixes_two_runs() -> None:
    changed = written_from_the_readme(
        "LEDGER_CHANGED_START_FROM_FIRST_PAGE", "The ledger changed since the previous page."
    )
    ledger, link = plug(
        ("list_trades", sample("list-trades-page-1")),
        ("list_trades", changed),
        ("list_trades", sample("list-trades-page-1")),
        ("list_trades", sample("list-trades-page-2")),
    )

    listed = ledger.list_trades(TradeFilter())

    assert len(listed.trades) == 67
    assert len({trade.id for trade in listed.trades}) == 67
    assert link.asked[2] == ("list_trades", {})


def test_a_ledger_that_keeps_changing_is_given_up_on_after_three_new_starts() -> None:
    changed = written_from_the_readme("INVALID_PAGE_TOKEN", "Start again.")
    script = [("list_trades", sample("list-trades-page-1")), ("list_trades", changed)] * 4
    ledger, link = plug(*script)

    with pytest.raises(LedgerError) as caught:
        ledger.list_trades(TradeFilter())

    assert caught.value.code == "LEDGER_CHANGED_START_FROM_FIRST_PAGE"
    assert len(link.asked) == 8


def test_more_than_two_thousand_trades_keep_the_latest_two_thousand_and_say_so() -> None:
    page = sample("list-trades-page-1")
    pages = MOST_TRADES_LISTED // 50 + 1
    ledger, link = plug(*[("list_trades", page)] * pages)

    listed = ledger.list_trades(TradeFilter())

    assert listed.cut
    assert len(listed.trades) == MOST_TRADES_LISTED == 2000
    assert len(link.asked) == 41


def test_trades_of_one_asset_are_asked_by_its_identifier() -> None:
    ledger, link = plug(ASSETS, ("list_trades", sample("list-trades-asset")))

    listed = ledger.list_trades(TradeFilter(asset="BTC", side=Side.BUY))

    assert link.asked[1] == ("list_trades", {"assetId": "asset-btc", "side": "buy"})
    assert [trade.facts.asset for trade in listed.trades] == ["BTC", "BTC"]


def test_trades_asked_by_a_money_are_told_apart_with_the_ledgers_own_sentence() -> None:
    ledger, _ = plug(ASSETS, ("list_trades", sample("list-trades-asset-is-currency")))

    with pytest.raises(LedgerError) as caught:
        ledger.list_trades(TradeFilter(asset="USDT"))

    assert caught.value.kind is LedgerErrorKind.ASSET_IS_CURRENCY
    assert caught.value.message.startswith("这个编号是现金货币")


def twin_assets() -> ToolAnswer:
    """The ledger's list with a stock that shares the code BTC: made from the sample, as the
    README says a coin and a stock may share one code; the capture had none."""
    answer = sample("list-assets")
    content = copy.deepcopy(dict(answer.content))
    content["assets"].append(
        {
            "assetId": "asset-stock-btc",
            "assetCode": "BTC",
            "assetName": "Invented BTC Holdings",
            "assetKind": "stock",
            "stockMarket": "US",
            "priceCurrencyAssetId": "asset-usd",
            "priceCurrencyCode": "USD",
            "canBeTradeCurrency": False,
        }
    )
    return ToolAnswer(kind=AnswerKind.RESULT, content=content)


def test_a_code_two_assets_share_is_never_picked_from() -> None:
    ledger, link = plug(("list_assets", twin_assets()))

    with pytest.raises(LedgerError) as caught:
        ledger.list_trades(TradeFilter(asset="BTC"))

    assert caught.value.code == "HAND_SAME_CODE"
    assert "Bitcoin (crypto) and Invented BTC Holdings (stock)" in caught.value.message
    assert link.names() == ["list_assets"]


# --- sums ---------------------------------------------------------------------


def test_all_time_runs_from_1970_to_today_and_each_money_is_a_group_of_its_own() -> None:
    ledger, link = plug(("get_period_summary", sample("period-summary-all-time")))

    summary = ledger.period_summary(PeriodRequest())

    assert link.asked == [
        ("get_period_summary", {"startDate": "1970-01-01", "endDate": "2026-11-25"})
    ]
    assert date(1970, 1, 1) == ALL_TIME_START
    usd, usdt = summary.by_currency
    assert (usd.currency, usd.buy_count, usd.sell_count) == ("USD", 2, 1)
    assert usd.spent == MoneyAmount(currency="USD", amount=Decimal("2952"))
    assert usd.received == MoneyAmount(currency="USD", amount=Decimal("1199"))
    assert usd.fees == (MoneyAmount(currency="USD", amount=Decimal("3")),)
    assert usd.realized == MoneyAmount(currency="USD", amount=Decimal("48"))
    assert usd.realized_from_transfers == MoneyAmount(currency="USD", amount=Decimal("0"))
    assert [(row.asset, row.realized.amount) for row in usd.by_asset] == [("AAPL", Decimal("48"))]
    assert (usdt.buy_count, usdt.sell_count) == (3, 1)
    assert summary.trade_count == 2 + 1 + 3 + 1


def test_a_sum_the_ledger_could_not_add_up_is_its_reason_never_the_partial_number() -> None:
    answer = sample("period-summary-all-time")
    content = copy.deepcopy(dict(answer.content))
    # Made from the sample with the README's fields for a buy that could not be counted.
    group = content["currencyGroups"][1]
    group["buyTotalSpent"] = None
    group["buyTotalSpentMissingReasons"] = ["一笔买入算不出花了多少"]
    group["partialBuyTotalSpent"] = "6505"
    group["partialBuyTotalSpentLeftOutTradeCount"] = 1
    ledger, _ = plug(("get_period_summary", ToolAnswer(kind=AnswerKind.RESULT, content=content)))

    usdt = ledger.period_summary(PeriodRequest()).by_currency[1]

    assert usdt.spent == NotWorkedOut(reason="一笔买入算不出花了多少")
    assert "6505" not in repr(usdt)


def test_one_assets_sums_add_its_trades_money_here_and_take_its_profit_from_the_ledger() -> None:
    ledger, link = plug(
        ("get_period_summary", sample("period-summary-all-time")),
        ASSETS,
        ("list_trades", sample("list-trades-asset")),
    )

    summary = ledger.period_summary(PeriodRequest(asset="BTC"))

    assert link.asked[2] == (
        "list_trades",
        {"startDate": "1970-01-01", "endDate": "2026-11-25", "assetId": "asset-btc"},
    )
    (usdt,) = summary.by_currency
    # The buy paid 6505 USDT and the sell brought in 2797 USDT (fees inside);
    # the fees were 5 and 3 USDT; the ledger's own row for BTC is 195 USDT.
    assert (usdt.currency, usdt.buy_count, usdt.sell_count) == ("USDT", 1, 1)
    assert usdt.spent == MoneyAmount(currency="USDT", amount=Decimal("6505"))
    assert usdt.received == MoneyAmount(currency="USDT", amount=Decimal("2797"))
    assert usdt.fees == (MoneyAmount(currency="USDT", amount=Decimal("8")),)
    assert usdt.realized == MoneyAmount(currency="USDT", amount=Decimal("195"))
    assert isinstance(usdt.realized_from_transfers, NotWorkedOut)


def test_one_trade_whose_money_the_ledger_could_not_work_out_leaves_its_sum_not_worked_out() -> (
    None
):
    answer = sample("list-trades-asset")
    content = copy.deepcopy(dict(answer.content))
    # Made from the sample with the README's fields for money that cannot be computed.
    content["trades"][1]["cashSpentOrReceived"] = None
    content["trades"][1]["cashSpentOrReceivedMissingReason"] = "手续费的币没有市场价"
    future = copy.deepcopy(content["trades"][0])
    future["tradeId"], future["isDatedAfterToday"] = "trade-later", True
    content["trades"].insert(0, future)
    ledger, _ = plug(
        ("get_period_summary", sample("period-summary-all-time")),
        ASSETS,
        ("list_trades", ToolAnswer(kind=AnswerKind.RESULT, content=content)),
    )

    (usdt,) = ledger.period_summary(PeriodRequest(asset="BTC")).by_currency

    assert usdt.spent == NotWorkedOut(reason="手续费的币没有市场价")
    # The sell dated after today is in no sum: one sell, 2797, as before.
    assert (usdt.sell_count, usdt.received) == (
        1,
        MoneyAmount(currency="USDT", amount=Decimal("2797")),
    )


# --- holdings -----------------------------------------------------------------


def test_holdings_leave_the_sold_out_out_and_are_in_each_assets_own_money() -> None:
    ledger, _ = plug(("get_positions", sample("positions")))

    held = {position.asset: position for position in ledger.positions()}

    assert set(held) == {"BTC", "ETH", "NVDA", "ADA"}
    nvda = held["NVDA"]
    assert (nvda.currency, nvda.quantity, nvda.cost) == (
        "USD",
        Decimal("10"),
        MoneyAmount(currency="USD", amount=Decimal("1801")),
    )
    assert nvda.unrealized == NotWorkedOut(reason="没有能用的市场价，算不出市值和浮动盈亏")
    assert nvda.cost_unreliable is None


# --- recording ----------------------------------------------------------------

BUDAPEST = ZoneInfo("Europe/Budapest")


def facts(**changed: object) -> TradeFacts:
    fields: dict[str, object] = {
        "occurred": datetime(2026, 11, 24, 10, 15, tzinfo=BUDAPEST),
        "side": Side.BUY,
        "asset": "BTC",
        "quantity": Decimal("0.01"),
        "price": Decimal("60000"),
        "total": Decimal("600"),
        "quote": "USDT",
        "fee": Decimal("0"),
        "fee_asset": "BTC",
        "platform": "",
        "note": "",
        "raw_text": SAID,
        "zone": "Europe/Budapest",
        "date_only": False,
        "cost_rate": None,
    }
    fields.update(changed)
    return TradeFacts(**fields)  # type: ignore[arg-type]


def test_two_trades_sent_at_once_come_back_one_check_each_in_their_order() -> None:
    sell = facts(side=Side.SELL, quantity=Decimal("50"), total=Decimal("3000000"))
    ledger, link = plug(ASSETS, ("propose_trade_add", sample("propose-add-one-refused")))

    result = ledger.propose_add((sell, facts(platform="Binance")), SAID)

    first, second = result.checks
    assert (first.outcome, first.code, first.message) == (
        CheckOutcome.FAILED,
        "INSUFFICIENT_HOLDINGS",
        "卖出数量超过该时间点的可用持仓",
    )
    assert (second.outcome, second.proposal_id) == (
        CheckOutcome.PASSED,
        "b43937bc-74c9-4b94-be1f-9a7c4ab2f1ed",
    )
    _, sent = link.asked[1]
    assert sent["sourceText"] == SAID and sent["modelName"] == MODEL
    assert sent["trades"][1] == {
        "type": "buy",
        "assetId": "asset-btc",
        "quantity": "0.01",
        "price": "60000",
        "totalValue": "600",
        "quoteAssetId": "asset-usdt",
        "fee": "0",
        # A fee of 0 is taken in the money traded.
        "feeAssetId": "asset-usdt",
        "costRate": None,
        "platform": "Binance",
        "note": None,
        "occurredDate": "2026-11-24",
        "occurredTime": "10:15",
        "occurredTimeZone": "Europe/Budapest",
    }


def test_a_time_with_seconds_and_a_trade_in_another_money_are_not_sent_and_the_rest_are() -> None:
    seconds = facts(occurred=datetime(2026, 11, 24, 10, 15, 30, tzinfo=BUDAPEST))
    dollars = facts(quote="USD", fee=Decimal("1"), fee_asset="USD")
    ledger, link = plug(ASSETS, ("propose_trade_add", sample("propose-add-time-with-zone")))

    result = ledger.propose_add((seconds, dollars, facts()), SAID)

    assert [check.code for check in result.checks] == [
        "HAND_TIME_HAS_SECONDS",
        "HAND_NEEDS_COST_RATE",
        None,
    ]
    assert result.checks[2].proposal_id == "968a2b6e-1bb9-4f30-bc2a-2b72e0ddd80c"
    _, sent = link.asked[1]
    assert len(sent["trades"]) == 1


def test_nothing_is_sent_when_every_trade_is_one_this_program_does_not_send() -> None:
    ledger, link = plug(ASSETS)

    result = ledger.propose_add((facts(zone=None),), SAID)

    assert result.checks[0].code == "HAND_NO_TIME_ZONE"
    assert link.names() == ["list_assets"]


def listed_then(
    *script: tuple[str, ToolAnswer | Exception],
) -> tuple[LinkLedger, SampleLink, dict[str, LedgerTrade]]:
    """The plug after it listed every trade once, as a change always follows a listing."""
    ledger, link = plug(("list_trades", sample("list-trades-no-filter")), *script)
    listed = ledger.list_trades(TradeFilter()).trades
    return ledger, link, {trade.id: trade for trade in listed}


def test_a_fee_changed_alone_sends_the_whole_trade_its_time_left_out_the_rest_as_listed() -> None:
    ledger, link, listed = listed_then(
        ASSETS, ("propose_trade_update", sample("propose-update-fee-only"))
    )
    eth = "dc36a1d6-6022-4020-acd5-20f08e3786d0"
    changed = dataclasses.replace(listed[eth].facts, fee=Decimal("1.5"))

    result = ledger.propose_update(eth, changed, "把11月12号那笔ETH手续费改成1.5")

    (check,) = result.checks
    assert check.proposal_id == "d3289b8e-ac48-4866-aabb-3bb03612bfe2"
    assert link.asked[-1] == (
        "propose_trade_update",
        {
            "tradeId": eth,
            "trade": {
                "type": "buy",
                "assetId": "asset-eth",
                "quantity": "2",
                "price": "3000",
                "totalValue": "6000",
                "quoteAssetId": "asset-usdt",
                "fee": "1.5",
                "feeAssetId": "asset-usdt",
                "costRate": None,
                "platform": None,
                "note": None,
            },
            "sourceText": "把11月12号那笔ETH手续费改成1.5",
            "modelName": MODEL,
        },
    )


def test_a_change_keeps_the_listed_platform_and_note_and_a_new_time_sends_all_three() -> None:
    ledger, link, listed = listed_then(
        ASSETS, ("propose_trade_update", sample("propose-update-fee-only"))
    )
    (bought,) = [trade for trade in listed.values() if trade.facts.platform == "Binance"]
    moved = dataclasses.replace(
        bought.facts, occurred=datetime(2026, 11, 10, 11, 45, tzinfo=BUDAPEST)
    )

    ledger.propose_update(bought.id, moved, "时间改成11:45")

    trade = link.asked[-1][1]["trade"]
    assert (trade["platform"], trade["note"]) == ("Binance", "invented: first BTC buy")
    assert (trade["occurredDate"], trade["occurredTime"], trade["occurredTimeZone"]) == (
        "2026-11-10",
        "11:45",
        "Europe/Budapest",
    )


def test_a_change_or_deletion_of_a_trade_gone_is_a_failed_check_saying_so() -> None:
    ledger, _ = plug(("propose_trade_delete", sample("propose-update-not-found")))

    (check,) = ledger.propose_delete("trade-does-not-exist", "删掉那笔").checks

    assert check.code == TARGET_NOT_FOUND
    assert check.message == "账本里找不到要改或要删的那一笔"


def test_a_trade_not_listed_in_this_session_is_not_changed() -> None:
    ledger, link = plug()

    (check,) = ledger.propose_update("t-unknown", facts(), "改一下").checks

    assert check.code == "HAND_TRADE_NOT_LISTED"
    assert link.asked == []


# --- where a proposal stands --------------------------------------------------


@pytest.mark.parametrize(
    ("name", "status"),
    [
        ("status-pending", ProposalStatus.PENDING),
        ("status-saved", ProposalStatus.SAVED),
        ("status-rejected", ProposalStatus.REJECTED),
        ("status-void", ProposalStatus.VOID),
    ],
)
def test_each_status_comes_back_with_what_the_ledger_said(
    name: str, status: ProposalStatus
) -> None:
    ledger, link = plug(("get_proposal_status", sample(name)))

    state = ledger.proposal_status("p-asked")

    assert state.status is status
    assert link.asked == [("get_proposal_status", {"proposalId": "p-asked"})]
    if status is ProposalStatus.SAVED:
        assert state.trade_id == "f5b5b78b-9691-40b8-b12d-6d274a9e0ecf"
    if status is ProposalStatus.VOID:
        assert state.reason == "ASSISTANT_DISCONNECTED"
        assert state.message == "和助手的连接断开了，这一轮的提议都作废了"


def test_a_proposal_forgotten_after_a_reload_is_unknown_never_unsaved() -> None:
    ledger, _ = plug(("get_proposal_status", sample("status-not-found-after-reload")))

    with pytest.raises(LedgerError) as caught:
        ledger.proposal_status("p-1")

    assert caught.value.kind is LedgerErrorKind.RESULT_UNKNOWN
    assert caught.value.message == "没有这个编号的提议"


# --- failing ------------------------------------------------------------------


@pytest.mark.parametrize("name", ["page-not-connected", "page-disconnected-call"])
def test_a_page_not_connected_is_unreachable_with_the_ledgers_words(name: str) -> None:
    ledger, _ = plug(("get_positions", sample(name)))

    with pytest.raises(LedgerError) as caught:
        ledger.positions()

    assert caught.value.kind is LedgerErrorKind.UNREACHABLE
    assert caught.value.message == sample(name).content["message"]


def test_a_proposal_the_page_did_not_answer_in_time_is_timed_out_and_asked_once() -> None:
    late = written_from_the_readme("LEDGER_PAGE_TIMEOUT", "The ledger page did not answer in time.")
    ledger, link = plug(ASSETS, ("propose_trade_add", late))

    with pytest.raises(LedgerError) as caught:
        ledger.propose_add((facts(),), SAID)

    assert caught.value.kind is LedgerErrorKind.TIMED_OUT
    assert link.names().count("propose_trade_add") == 1


@pytest.mark.parametrize(
    ("failure", "kind"),
    [
        (LinkFailure.TIMED_OUT, LedgerErrorKind.TIMED_OUT),
        (LinkFailure.LINK_GONE, LedgerErrorKind.UNREACHABLE),
        (LinkFailure.PORT_IN_USE, LedgerErrorKind.UNREACHABLE),
        (LinkFailure.HANDSHAKE_REFUSED, LedgerErrorKind.UNREACHABLE),
        (LinkFailure.NOT_STARTED, LedgerErrorKind.UNREACHABLE),
        (LinkFailure.REPLY_NOT_JSON, LedgerErrorKind.OTHER),
    ],
)
def test_a_link_that_fails_is_sorted_into_a_ledger_failure(
    failure: LinkFailure, kind: LedgerErrorKind
) -> None:
    ledger, _ = plug(("list_assets", LedgerLinkError(failure)))

    with pytest.raises(LedgerError) as caught:
        ledger.list_assets()

    assert caught.value.kind is kind


# Every code of the error table at the end of the ledger's assistant-link/README.md
# at dev@a6ba639; the ledger tier compares the list with the README itself.
README_CODES = [
    "INVALID_ARGUMENTS",
    "UNKNOWN_TOOL",
    "LEDGER_NOT_READY",
    "TOO_MANY_TRADES",
    "INVALID_DATE",
    "START_DATE_AFTER_END_DATE",
    "ASSET_NOT_FOUND",
    "ASSET_IS_CURRENCY",
    "INVALID_PAGE_TOKEN",
    "LEDGER_CHANGED_START_FROM_FIRST_PAGE",
    "LEDGER_RECORDS_CONTRADICT",
    "UNEXPECTED_PROGRAM_ERROR",
    "PROPOSAL_PROPOSER_INVALID",
    "PROPOSAL_LIST_FULL",
    "PROPOSAL_ID_UNAVAILABLE",
    "PROPOSAL_TARGET_NOT_FOUND",
    "PROPOSAL_TARGET_ALREADY_PENDING",
    "PROPOSAL_TARGET_CHANGED",
    "PROPOSAL_NO_CHANGE",
    "PROPOSAL_NOT_FOUND",
    "PROPOSAL_NOT_PENDING",
    "PROPOSAL_TIME_INVALID",
    "PROPOSAL_TIME_ZONE_MISSING",
    "PROPOSAL_TIME_ZONE_WITHOUT_TIME",
    "PROPOSAL_TIME_ZONE_UNKNOWN",
    "PROPOSAL_TIME_NONEXISTENT",
    "PROPOSAL_TIME_AMBIGUOUS",
    "INVALID_DECIMAL",
    "VALUE_MUST_BE_POSITIVE",
    "FEE_MUST_BE_NON_NEGATIVE",
    "ASSET_FEE_MUST_BE_LESS_THAN_QUANTITY",
    "TOTAL_VALUE_MISMATCH",
    "INSUFFICIENT_HOLDINGS",
    "CURRENCY_MISMATCH",
    "FEE_CURRENCY_MISMATCH",
    "FUTURE_FACT",
    "TRADE_UPDATE_BREAKS_LEDGER_TIMELINE",
    "TRADE_REMOVAL_BREAKS_LEDGER_TIMELINE",
    "TRADE_ID_GENERATION_EXHAUSTED",
    "TRADE_DEPENDENCY_FAILURE",
    "LEDGER_PAGE_NOT_CONNECTED",
    "LEDGER_PAGE_TIMEOUT",
    "LEDGER_PAGE_DISCONNECTED",
    "LEDGER_PAGE_REPLY_INVALID",
]


def test_every_code_of_the_ledger_is_on_one_of_the_two_tables() -> None:
    assert len(README_CODES) == 44
    missing = [code for code in README_CODES if code not in CALL_FAILURES | TRADE_REFUSALS]
    assert missing == []
    assert CALL_FAILURES["LEDGER_PAGE_TIMEOUT"] is LedgerErrorKind.TIMED_OUT
    assert CALL_FAILURES["PROPOSAL_NOT_FOUND"] is LedgerErrorKind.RESULT_UNKNOWN
    unused = [code for code in CALL_FAILURES | TRADE_REFUSALS if code not in README_CODES]
    assert unused == []


# --- through the link client, with the stand-in link playing the samples ----------


def test_the_plug_over_the_real_client_reads_the_samples_and_fails_as_they_say(
    ledger_folder: Path, node: str, tmp_path: Path
) -> None:
    played = tmp_path / "played.json"
    answers = [
        json.loads((SAMPLES / f"{name}.json").read_text(encoding="utf-8"))["answer"]
        for name in ("list-assets", "list-trades-asset", "page-disconnected-call")
    ]
    played.write_text(json.dumps(answers), encoding="utf-8")
    the_setup = setup(ledger_folder, node, "samples", FAKE_LINK_SAMPLES=str(played))

    with LedgerLink(the_setup) as link:
        ledger = LinkLedger(link, model_name=MODEL, today=lambda: TODAY)
        listed = ledger.list_trades(TradeFilter(asset="BTC"))
        with pytest.raises(LedgerError) as caught:
            ledger.positions()

    assert [trade.facts.side for trade in listed.trades] == [Side.BUY, Side.SELL]
    assert caught.value.kind is LedgerErrorKind.UNREACHABLE
    assert caught.value.code == "LEDGER_PAGE_NOT_CONNECTED"  # what the page said, after it left


def test_a_code_the_readme_adds_is_found_on_no_table() -> None:
    readme = (
        "# Assistant link\n\n## Error codes\n\n| Code | Category |\n| --- | --- |\n"
        "| `LEDGER_PAGE_TIMEOUT` | temporarily-unavailable |\n"
        "| `INVENTED_NEW_CODE` | check-failed |\n"
    )

    assert codes_on_no_table(readme) == ["INVENTED_NEW_CODE"]
    assert codes_on_no_table("# no table") == ["(the README has no heading 'Error codes')"]
