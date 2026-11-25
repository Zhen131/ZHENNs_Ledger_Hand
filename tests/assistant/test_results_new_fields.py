"""Tests of the fields added to what the model is handed (68B2, part 11): only added, never renamed.

The real ledger hands back things the invented book never holds: a trade
known only to its day, one dated after today, a profit given but not
reliable, a sum it could not add up, cost taken out by a transfer, a cost
not reliable, a proposal that became void. Each comes to the model as a
field of its own, beside the fields that were there, which keep their names
and their values. The figures are invented, in the shapes of the ledger's
samples of 2026-11-25.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal

from ledger_hand.assistant.lookups import when_text
from ledger_hand.assistant.results import (
    ledger_error_text,
    positions_text,
    status_text,
    summary_text,
    trades_text,
)
from ledger_hand.core.ledger_records import (
    AssetRealized,
    CurrencyTotals,
    LedgerTrade,
    MoneyAmount,
    NotWorkedOut,
    PeriodRequest,
    PeriodSummary,
    Position,
    TradeFacts,
)
from ledger_hand.core.proposals import ProposalState, ProposalStatus
from ledger_hand.core.trade import Side
from ledger_hand.ports import LedgerError, LedgerErrorKind


def usd(amount: str) -> MoneyAmount:
    return MoneyAmount(currency="USD", amount=Decimal(amount))


def nvda(*, date_only: bool) -> TradeFacts:
    occurred = (
        datetime(2026, 11, 14, tzinfo=timezone.utc)
        if date_only
        else datetime(2026, 11, 14, 15, 30, tzinfo=timezone.utc)
    )
    return TradeFacts(
        occurred=occurred,
        side=Side.SELL,
        asset="NVDA",
        quantity=Decimal("10"),
        price=Decimal("180"),
        total=Decimal("1800"),
        quote="USD",
        fee=Decimal("1"),
        fee_asset="USD",
        platform="",
        note="",
        raw_text=None,
        zone=None,
        date_only=date_only,
        cost_rate=None,
    )


def test_a_trade_known_only_to_its_day_is_its_day_alone_never_midnight() -> None:
    trade = LedgerTrade(
        id="t-1",
        facts=nvda(date_only=True),
        realized=usd("48"),
        realized_unreliable="a fee was paid in BNB",
        dated_after_today=True,
    )

    (entry,) = json.loads(trades_text((trade,)))["trades"]

    assert entry["time"] == "2026-11-14"
    assert "00:00" not in json.dumps(entry)
    assert entry["date_only"] is True
    assert entry["dated_after_today"] is True
    assert entry["realized_profit"] == {"amount": "48", "currency": "USD"}
    assert entry["realized_profit_not_reliable"] == "a fee was paid in BNB"
    assert when_text(trade.facts) == "2026-11-14"


def test_a_trade_with_its_time_has_none_of_the_added_fields() -> None:
    trade = LedgerTrade(
        id="t-1",
        facts=nvda(date_only=False),
        realized=usd("48"),
        realized_unreliable=None,
        dated_after_today=False,
    )

    (entry,) = json.loads(trades_text((trade,)))["trades"]

    assert entry["time"] == "2026-11-14T15:30:00+00:00"
    assert not {"date_only", "dated_after_today", "realized_profit_not_reliable"} & set(entry)
    assert when_text(trade.facts) == "2026-11-14 15:30"


def group(**changed: object) -> CurrencyTotals:
    fields: dict[str, object] = {
        "currency": "USD",
        "buy_count": 2,
        "sell_count": 1,
        "spent": usd("2952"),
        "received": usd("1199"),
        "fees": (usd("3"),),
        "realized": usd("48"),
        "realized_from_sells": usd("48"),
        "realized_from_transfers": usd("0"),
        "by_asset": (AssetRealized(asset="AAPL", realized=usd("48"), unreliable=None),),
    }
    fields.update(changed)
    return CurrencyTotals(**fields)  # type: ignore[arg-type]


def test_one_group_is_handed_as_before() -> None:
    summary = PeriodSummary(request=PeriodRequest(), by_currency=(group(),))

    assert json.loads(summary_text(summary)) == {
        "trade_count": 3,
        "by_currency": [
            {
                "currency": "USD",
                "spent_on_buys": "2952",
                "received_from_sells": "1199",
                "realized_profit": {"amount": "48", "currency": "USD"},
            }
        ],
        "fees": [{"amount": "3", "currency": "USD"}],
    }


def test_two_groups_say_their_own_counts_and_fees_and_a_sum_not_added_says_why() -> None:
    usdt = group(
        currency="USDT",
        buy_count=3,
        sell_count=1,
        spent=NotWorkedOut(reason="一笔买入算不出花了多少"),
        received=MoneyAmount(currency="USDT", amount=Decimal("2797")),
        fees=(MoneyAmount(currency="USDT", amount=Decimal("10.5")),),
        realized=MoneyAmount(currency="USDT", amount=Decimal("135")),
        realized_from_sells=MoneyAmount(currency="USDT", amount=Decimal("195")),
        realized_from_transfers=MoneyAmount(currency="USDT", amount=Decimal("-60")),
        by_asset=(
            AssetRealized(
                asset="BTC",
                realized=MoneyAmount(currency="USDT", amount=Decimal("135")),
                unreliable="a fee of BTC was paid in BNB",
            ),
        ),
    )
    summary = PeriodSummary(request=PeriodRequest(), by_currency=(group(), usdt))

    handed = json.loads(summary_text(summary))

    assert handed["trade_count"] == 7
    first, second = handed["by_currency"]
    assert (first["buy_count"], first["sell_count"], second["buy_count"]) == (2, 1, 3)
    assert first["fees"] == [{"amount": "3", "currency": "USD"}]
    assert second["spent_on_buys"] == {"not_worked_out": "一笔买入算不出花了多少"}
    assert second["received_from_sells"] == "2797"
    assert second["realized_from_sells"] == {"amount": "195", "currency": "USDT"}
    assert second["cost_taken_out_by_transfers"] == {"amount": "-60", "currency": "USDT"}
    assert second["realized_not_reliable"] == [
        {
            "asset": "BTC",
            "realized_profit": {"amount": "135", "currency": "USDT"},
            "why": "a fee of BTC was paid in BNB",
        }
    ]
    assert "cost_taken_out_by_transfers" not in first
    assert not any(key.startswith("partial") for key in json.dumps(handed))


def test_a_holding_keeps_bought_with_for_its_own_money_and_says_a_cost_not_reliable() -> None:
    holding = Position(
        asset="NVDA",
        currency="USD",
        quantity=Decimal("10"),
        cost=usd("1801"),
        cost_unreliable="a fee was paid in another asset",
        unrealized=NotWorkedOut(reason="没有能用的市场价，算不出市值和浮动盈亏"),
    )

    (entry,) = json.loads(positions_text((holding,)))["positions"]

    assert entry == {
        "asset": "NVDA",
        "bought_with": "USD",
        "quantity": "10",
        "cost": {"amount": "1801", "currency": "USD"},
        "unrealized_profit": {"not_worked_out": "没有能用的市场价，算不出市值和浮动盈亏"},
        "cost_not_reliable": "a fee was paid in another asset",
    }


def test_one_proposal_is_handed_as_before_and_a_void_one_says_why() -> None:
    pending = ProposalState(proposal_id="p-1", status=ProposalStatus.PENDING)
    void = ProposalState(
        proposal_id="p-2",
        status=ProposalStatus.VOID,
        reason="ASSISTANT_DISCONNECTED",
        message="已断开和助手的连接。",
    )

    assert json.loads(status_text((pending,))) == {"proposal": "p-1", "status": "pending"}
    assert json.loads(status_text((void,))) == {
        "proposal": "p-2",
        "status": "void",
        "void_reason": "ASSISTANT_DISCONNECTED",
        "message": "已断开和助手的连接。",
    }
    both = json.loads(status_text((pending, void)))
    assert (both["proposal"], both["status"]) == ("p-1", "mixed")
    assert [one["status"] for one in both["proposals"]] == ["pending", "void"]


def test_a_timeout_and_a_forgotten_proposal_say_what_they_mean_and_others_do_not() -> None:
    late = LedgerError(LedgerErrorKind.TIMED_OUT, "LEDGER_PAGE_TIMEOUT", "Too late.")
    forgotten = LedgerError(LedgerErrorKind.RESULT_UNKNOWN, "PROPOSAL_NOT_FOUND", "找不到。")
    plain = LedgerError(LedgerErrorKind.UNKNOWN_ASSET, "ASSET_NOT_FOUND", "No such asset.")

    assert "do not send it again" in json.loads(ledger_error_text(late))["what_it_means"]
    assert "not mean it was not saved" in json.loads(ledger_error_text(forgotten))["what_it_means"]
    assert json.loads(ledger_error_text(plain)) == {
        "status": "ledger_error",
        "code": "ASSET_NOT_FOUND",
        "message": "No such asset.",
    }
