"""Tests of the ledger port, run against every plug: so far the fake ledger alone.

A plug that reaches the real ledger is added to ``PLUGS`` and must pass the
same tests, given the same invented book. Each test starts from the book as
invented: assets, trades and market prices that copy nothing real.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from ledger_hand.core.ledger_records import (
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
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ledger.invented_book import INVENTED_ZONE
from ledger_hand.ports import LedgerError, LedgerErrorKind, LedgerPort

BUDAPEST = ZoneInfo(INVENTED_ZONE)
PLUGS: dict[str, Callable[[], LedgerPort]] = {"fake": FakeLedger}


@pytest.fixture(params=sorted(PLUGS))
def ledger(request: pytest.FixtureRequest) -> LedgerPort:
    return PLUGS[request.param]()


def day(year: int, month: int, number: int) -> TradeFilter:
    one = date(year, month, number)
    return TradeFilter(first_day=one, last_day=one)


def listed(ledger: LedgerPort, trade_filter: TradeFilter) -> tuple[LedgerTrade, ...]:
    found = ledger.list_trades(trade_filter)
    assert not found.cut
    return found.trades


def facts(
    side: Side, asset: str, quantity: str, *, quote: str = "USDT", when: int = 23
) -> TradeFacts:
    return TradeFacts(
        occurred=datetime(2026, 11, when, 12, 0, tzinfo=BUDAPEST),
        side=side,
        asset=asset,
        quantity=Decimal(quantity),
        price=Decimal("10"),
        total=Decimal(quantity) * 10,
        quote=quote,
        fee=Decimal("0.1"),
        fee_asset=quote,
        platform="OKX",
        note="",
        raw_text=f"Bought {quantity} {asset} at 10 on OKX.",
        zone=None,
        date_only=False,
        cost_rate=None,
    )


# --- reading -----------------------------------------------------------------


def test_the_assets_include_two_moneys_that_can_price_a_trade(ledger: LedgerPort) -> None:
    assets = {asset.code: asset for asset in ledger.list_assets()}

    assert {"USDT", "USD", "BTC", "ETH", "ADA"} <= set(assets)
    pricing = {code for code, asset in assets.items() if asset.pricing is Pricing.CAN_PRICE}
    assert pricing == {"USDT", "USD"}


def test_6_october_holds_exactly_a_btc_buy_and_an_eth_buy_each_naming_its_money_and_fee(
    ledger: LedgerPort,
) -> None:
    trades = listed(ledger, day(2026, 10, 6))

    assert [(trade.facts.asset, trade.facts.side) for trade in trades] == [
        ("BTC", Side.BUY),
        ("ETH", Side.BUY),
    ]
    for trade in trades:
        assert trade.facts.quote == "USDT"
        assert trade.facts.fee_asset in {"BTC", "ETH", "USDT"}
        assert trade.realized is None
    assert len({trade.id for trade in trades}) == 2


def test_25_september_holds_exactly_one_ada_buy(ledger: LedgerPort) -> None:
    trades = listed(ledger, day(2026, 9, 25))

    assert [(trade.facts.asset, trade.facts.side) for trade in trades] == [("ADA", Side.BUY)]


def test_a_filter_by_asset_and_side_narrows_the_list(ledger: LedgerPort) -> None:
    sells = listed(ledger, TradeFilter(asset="ETH", side=Side.SELL))

    assert [trade.facts.asset for trade in sells] == ["ETH"]
    assert all(trade.facts.side is Side.SELL for trade in sells)


def test_a_sell_carries_its_profit_by_the_moving_average(ledger: LedgerPort) -> None:
    (sell,) = listed(ledger, TradeFilter(asset="ETH", side=Side.SELL))

    # 0.42 ETH for 960.54 + 0.96054 USDT, then 0.15 for 366.9 + 0.3669: 0.57 cost
    # 1328.76744. Selling 0.2 takes out 1328.76744 x 0.2 / 0.57 = 466.23418947 and
    # brings in 523.6 - 0.5236 = 523.0764, so the profit is 56.84221053 USDT.
    assert sell.realized == MoneyAmount(currency="USDT", amount=Decimal("56.84221053"))


def test_a_stock_bought_with_dollars_is_summed_apart_from_the_coins(ledger: LedgerPort) -> None:
    summary = ledger.period_summary(
        PeriodRequest(first_day=date(2026, 10, 1), last_day=date(2026, 10, 31))
    )

    totals = {totals.currency: totals for totals in summary.by_currency}
    assert summary.trade_count == 5
    assert set(totals) == {"USD", "USDT"}
    usd, usdt = totals["USD"], totals["USDT"]
    assert (usd.spent, usd.received) == (
        MoneyAmount(currency="USD", amount=Decimal("1237.11")),
        MoneyAmount(currency="USD", amount=Decimal(0)),
    )
    assert usdt.spent == MoneyAmount(currency="USDT", amount=Decimal("874.808"))
    assert usdt.received == MoneyAmount(currency="USDT", amount=Decimal("920.32"))
    assert isinstance(usdt.realized, MoneyAmount)
    # Each group counts its own buys and sells; the summary's count is all of them.
    assert (usd.buy_count, usd.sell_count, usdt.buy_count, usdt.sell_count) == (1, 0, 2, 2)
    assert usdt.realized_from_sells == usdt.realized
    assert usdt.realized_from_transfers == MoneyAmount(currency="USDT", amount=Decimal(0))


def test_a_holding_with_no_market_price_gives_a_reason_not_a_figure(ledger: LedgerPort) -> None:
    held = {position.asset: position for position in ledger.positions()}

    assert set(held) == {"ADA", "BTC", "ETH", "MSFT"}
    assert isinstance(held["ADA"].unrealized, NotWorkedOut)
    assert "market price" in held["ADA"].unrealized.reason
    assert isinstance(held["BTC"].unrealized, MoneyAmount)
    assert held["MSFT"].currency == "USD"
    assert held["MSFT"].cost.currency == "USD"


def test_an_asset_the_ledger_does_not_know_is_an_error_when_listing(ledger: LedgerPort) -> None:
    with pytest.raises(LedgerError) as caught:
        ledger.list_trades(TradeFilter(asset="DOGE"))

    assert caught.value.kind is LedgerErrorKind.UNKNOWN_ASSET
    assert caught.value.code == "unknown_asset"


def test_a_day_counts_both_its_ends_on_the_trades_own_clock() -> None:
    # Invented: two buys in the last minute of 30 November, one in Shanghai and
    # one in New York. Each falls on 30 November on its own clock, though the
    # New York one is 1 December in UTC; 1 December alone holds neither.
    shanghai = dataclasses.replace(
        facts(Side.BUY, "BTC", "0.01"),
        occurred=datetime(2026, 11, 30, 23, 59, tzinfo=ZoneInfo("Asia/Shanghai")),
    )
    new_york = dataclasses.replace(
        facts(Side.BUY, "ETH", "0.02"),
        occurred=datetime(2026, 11, 30, 23, 59, tzinfo=ZoneInfo("America/New_York")),
    )
    ledger = FakeLedger(trades=(("t-a", shanghai), ("t-b", new_york)))

    last_of_november = listed(ledger, day(2026, 11, 30))
    first_of_december = listed(ledger, day(2026, 12, 1))
    both_ends = listed(
        ledger, TradeFilter(first_day=date(2026, 11, 30), last_day=date(2026, 11, 30))
    )

    assert [trade.id for trade in last_of_november] == ["t-b", "t-a"] or [
        trade.id for trade in last_of_november
    ] == ["t-a", "t-b"]
    assert first_of_december == ()
    assert {trade.id for trade in both_ends} == {"t-a", "t-b"}
    summary = ledger.period_summary(
        PeriodRequest(first_day=date(2026, 11, 30), last_day=date(2026, 11, 30))
    )
    assert summary.trade_count == 2


def test_a_list_longer_than_the_most_listed_keeps_the_latest_and_says_it_was_cut() -> None:
    ledger = FakeLedger(most_listed=4)

    found = ledger.list_trades(TradeFilter())

    # The invented book holds 11 trades; the latest four are t-08 to t-11.
    assert found.cut
    assert [trade.id for trade in found.trades] == ["t-08", "t-09", "t-10", "t-11"]
    assert not ledger.list_trades(day(2026, 10, 6)).cut


# --- proposing ---------------------------------------------------------------

SAID = "Bought 0.01 BTC and 5 DOGE at 10 on OKX."


def test_a_pending_proposal_changes_nothing_until_it_is_saved() -> None:
    ledger = FakeLedger()
    before = (listed(ledger, TradeFilter()), ledger.positions())

    result = ledger.propose_add((facts(Side.BUY, "BTC", "0.01"),), SAID)

    assert result.all_passed
    (proposal,) = result.proposal_ids
    assert (listed(ledger, TradeFilter()), ledger.positions()) == before
    assert ledger.proposal_status(proposal).status is ProposalStatus.PENDING

    ledger.save(proposal)

    assert len(listed(ledger, TradeFilter())) == len(before[0]) + 1
    assert ledger.positions() != before[1]
    state = ledger.proposal_status(proposal)
    assert state.status is ProposalStatus.SAVED
    assert state.trade_id == "t-12"
    assert ledger.said == [SAID]


def test_every_trade_comes_back_with_the_words_it_was_recorded_from() -> None:
    ledger = FakeLedger()
    said = "  Bought 0.01 BTC at 10 on OKX.\n"
    proposed = dataclasses.replace(facts(Side.BUY, "BTC", "0.01"), raw_text=said)

    assert all(trade.facts.raw_text for trade in listed(ledger, TradeFilter()))
    (proposal,) = ledger.propose_add((proposed,), said).proposal_ids
    ledger.save(proposal)

    (added,) = [t for t in listed(ledger, TradeFilter()) if t.facts == proposed]
    assert added.facts.raw_text == said


def test_a_rejected_proposal_changes_nothing() -> None:
    ledger = FakeLedger()
    before = listed(ledger, TradeFilter())
    (proposal,) = ledger.propose_delete(before[0].id, "delete the first one").proposal_ids

    ledger.reject(proposal)

    assert ledger.proposal_status(proposal).status is ProposalStatus.REJECTED
    assert listed(ledger, TradeFilter()) == before


def test_saving_one_proposal_leaves_the_others_that_still_fit_pending() -> None:
    ledger = FakeLedger()
    (first,) = ledger.propose_add((facts(Side.BUY, "BTC", "0.01"),), SAID).proposal_ids
    (second,) = ledger.propose_add((facts(Side.BUY, "ETH", "0.01"),), SAID).proposal_ids

    ledger.save(first)

    assert ledger.proposal_status(second).status is ProposalStatus.PENDING


def test_saving_one_voids_the_others_it_spoils_and_says_why() -> None:
    ledger = FakeLedger()
    trades = listed(ledger, TradeFilter(asset="ETH", side=Side.SELL))
    (sell,) = trades
    (delete,) = ledger.propose_delete(sell.id, "delete the ETH sell").proposal_ids
    changed = dataclasses.replace(sell.facts, fee=Decimal("0.4"))
    (change,) = ledger.propose_update(sell.id, changed, "fee 0.4").proposal_ids

    ledger.save(delete)

    state = ledger.proposal_status(change)
    assert state.status is ProposalStatus.VOID
    assert state.reason == "TARGET_CHANGED" and state.message


def test_two_trades_one_with_an_unknown_asset_wait_one_and_turn_one_down(
    ledger: LedgerPort,
) -> None:
    result = ledger.propose_add(
        (facts(Side.BUY, "BTC", "0.01"), facts(Side.BUY, "DOGE", "5")), SAID
    )

    assert [check.outcome for check in result.checks] == [
        CheckOutcome.PASSED,
        CheckOutcome.FAILED,
    ]
    assert result.checks[0].proposal_id == "proposal-1"
    assert result.checks[1].proposal_id is None
    assert result.checks[1].code == "unknown_asset"
    assert result.checks[1].message
    assert result.proposal_ids == ("proposal-1",)
    assert not result.all_passed and not result.none_passed
    assert ledger.proposal_status("proposal-1").status is ProposalStatus.PENDING


def test_three_trades_taken_wait_under_three_identifiers(ledger: LedgerPort) -> None:
    result = ledger.propose_add(
        (
            facts(Side.BUY, "BTC", "0.01"),
            facts(Side.BUY, "ETH", "0.2"),
            facts(Side.BUY, "ADA", "30"),
        ),
        SAID,
    )

    assert result.proposal_ids == ("proposal-1", "proposal-2", "proposal-3")


def test_selling_more_than_is_held_fails_the_check(ledger: LedgerPort) -> None:
    result = ledger.propose_add((facts(Side.SELL, "BTC", "5"),), SAID)

    assert result.checks[0].outcome is CheckOutcome.FAILED
    assert result.checks[0].code == "sells_more_than_held"
    assert result.none_passed and result.proposal_ids == ()


def test_a_money_that_cannot_price_a_trade_fails_the_check(ledger: LedgerPort) -> None:
    result = ledger.propose_add((facts(Side.BUY, "ETH", "0.01", quote="BTC"),), SAID)

    assert result.checks[0].code == "cannot_price"


def test_a_change_or_a_deletion_that_leaves_a_later_sell_short_fails_the_check() -> None:
    ledger = FakeLedger()
    september, october = listed(
        ledger, TradeFilter(asset="BTC", side=Side.BUY, last_day=date(2026, 10, 6))
    )
    # With the September buy gone, the October buy alone still covers the
    # 0.006 BTC sold on 21 October; moved after that sell, or deleted, it does not.
    (first,) = ledger.propose_delete(september.id, "delete it").proposal_ids
    ledger.save(first)
    moved = dataclasses.replace(october.facts, occurred=datetime(2026, 10, 22, tzinfo=BUDAPEST))

    changed = ledger.propose_update(october.id, moved, "move it")
    deleted = ledger.propose_delete(october.id, "delete it")

    for result in (changed, deleted):
        assert result.checks[0].code == "sells_more_than_held"
        assert result.proposal_ids == ()


def test_a_change_or_deletion_of_a_trade_not_in_the_ledger_fails_its_check(
    ledger: LedgerPort,
) -> None:
    for result in (
        ledger.propose_delete("t-99", "delete it"),
        ledger.propose_update("t-99", facts(Side.BUY, "BTC", "0.01"), "change it"),
    ):
        (check,) = result.checks
        assert check.outcome is CheckOutcome.FAILED
        assert check.code == TARGET_NOT_FOUND


def test_a_failing_ledger_raises_its_failure_on_every_call() -> None:
    failure = LedgerError(LedgerErrorKind.UNREACHABLE, "offline", "The ledger is not open.")
    ledger = FakeLedger(failure=failure)

    with pytest.raises(LedgerError) as caught:
        ledger.positions()

    assert caught.value is failure
    assert ledger.calls == ["positions"]
