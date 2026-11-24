"""Tests of the ledger port, run against every plug: so far the fake ledger alone.

A plug that reaches the real ledger is added to ``PLUGS`` and must pass the
same tests, given the same invented book. Each test starts from the book as
invented: assets, trades and market prices that copy nothing real.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from ledger_hand.core.ledger_records import (
    MoneyAmount,
    NotWorkedOut,
    PeriodRequest,
    Pricing,
    TradeFacts,
    TradeFilter,
)
from ledger_hand.core.proposals import CheckOutcome, ProposalStatus
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
    start = datetime(year, month, number, tzinfo=BUDAPEST)
    return TradeFilter(start=start, end=start + timedelta(days=1))


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
    trades = ledger.list_trades(day(2026, 10, 6))

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
    trades = ledger.list_trades(day(2026, 9, 25))

    assert [(trade.facts.asset, trade.facts.side) for trade in trades] == [("ADA", Side.BUY)]


def test_a_filter_by_asset_and_side_narrows_the_list(ledger: LedgerPort) -> None:
    sells = ledger.list_trades(TradeFilter(asset="ETH", side=Side.SELL))

    assert [trade.facts.asset for trade in sells] == ["ETH"]
    assert all(trade.facts.side is Side.SELL for trade in sells)


def test_a_sell_carries_its_profit_by_the_moving_average(ledger: LedgerPort) -> None:
    (sell,) = ledger.list_trades(TradeFilter(asset="ETH", side=Side.SELL))

    # 0.42 ETH for 960.54 + 0.96054 USDT, then 0.15 for 366.9 + 0.3669: 0.57 cost
    # 1328.76744. Selling 0.2 takes out 1328.76744 x 0.2 / 0.57 = 466.23418947 and
    # brings in 523.6 - 0.5236 = 523.0764, so the profit is 56.84221053 USDT.
    assert sell.realized == MoneyAmount(currency="USDT", amount=Decimal("56.84221053"))


def test_a_stock_bought_with_dollars_is_summed_apart_from_the_coins(ledger: LedgerPort) -> None:
    start = datetime(2026, 10, 1, tzinfo=BUDAPEST)
    summary = ledger.period_summary(
        PeriodRequest(start=start, end=datetime(2026, 11, 1, tzinfo=BUDAPEST))
    )

    totals = {totals.currency: totals for totals in summary.by_currency}
    assert summary.trade_count == 5
    assert set(totals) == {"USD", "USDT"}
    assert (totals["USD"].spent, totals["USD"].received) == (Decimal("1237.11"), Decimal(0))
    assert totals["USDT"].spent == Decimal("874.808")
    assert totals["USDT"].received == Decimal("920.32")
    assert isinstance(totals["USDT"].realized, MoneyAmount)


def test_a_holding_with_no_market_price_gives_a_reason_not_a_figure(ledger: LedgerPort) -> None:
    held = {position.asset: position for position in ledger.positions()}

    assert set(held) == {"ADA", "BTC", "ETH", "MSFT"}
    assert isinstance(held["ADA"].unrealized, NotWorkedOut)
    assert "market price" in held["ADA"].unrealized.reason
    assert isinstance(held["BTC"].unrealized, MoneyAmount)
    assert held["MSFT"].quote == "USD"
    assert held["MSFT"].cost.currency == "USD"


def test_an_asset_the_ledger_does_not_know_is_an_error_when_listing(ledger: LedgerPort) -> None:
    with pytest.raises(LedgerError) as caught:
        ledger.list_trades(TradeFilter(asset="DOGE"))

    assert caught.value.kind is LedgerErrorKind.UNKNOWN_ASSET
    assert caught.value.code == "unknown_asset"


# --- proposing ---------------------------------------------------------------


def test_a_pending_proposal_changes_nothing_until_it_is_saved() -> None:
    ledger = FakeLedger()
    before = (ledger.list_trades(TradeFilter()), ledger.positions())

    result = ledger.propose_add((facts(Side.BUY, "BTC", "0.01"),))

    assert result.all_passed
    assert result.proposal_id is not None
    assert (ledger.list_trades(TradeFilter()), ledger.positions()) == before
    assert ledger.proposal_status(result.proposal_id) is ProposalStatus.PENDING

    ledger.save(result.proposal_id)

    assert len(ledger.list_trades(TradeFilter())) == len(before[0]) + 1
    assert ledger.positions() != before[1]
    assert ledger.proposal_status(result.proposal_id) is ProposalStatus.SAVED


def test_a_rejected_proposal_changes_nothing() -> None:
    ledger = FakeLedger()
    before = ledger.list_trades(TradeFilter())
    result = ledger.propose_delete(before[0].id)
    assert result.proposal_id is not None

    ledger.reject(result.proposal_id)

    assert ledger.proposal_status(result.proposal_id) is ProposalStatus.REJECTED
    assert ledger.list_trades(TradeFilter()) == before


def test_saving_one_proposal_voids_the_others_still_pending() -> None:
    ledger = FakeLedger()
    first = ledger.propose_add((facts(Side.BUY, "BTC", "0.01"),)).proposal_id
    second = ledger.propose_add((facts(Side.BUY, "ETH", "0.01"),)).proposal_id
    assert first is not None and second is not None

    ledger.save(first)

    assert ledger.proposal_status(second) is ProposalStatus.VOID


def test_two_trades_one_with_an_unknown_asset_give_two_checks_and_no_proposal(
    ledger: LedgerPort,
) -> None:
    result = ledger.propose_add((facts(Side.BUY, "BTC", "0.01"), facts(Side.BUY, "DOGE", "5")))

    assert [check.outcome for check in result.checks] == [
        CheckOutcome.PASSED,
        CheckOutcome.FAILED,
    ]
    assert result.checks[1].code == "unknown_asset"
    assert result.checks[1].message
    assert result.proposal_id is None
    with pytest.raises(LedgerError):
        ledger.proposal_status("proposal-1")


def test_selling_more_than_is_held_fails_the_check(ledger: LedgerPort) -> None:
    result = ledger.propose_add((facts(Side.SELL, "BTC", "5"),))

    assert result.checks[0].outcome is CheckOutcome.FAILED
    assert result.checks[0].code == "sells_more_than_held"
    assert result.proposal_id is None


def test_a_money_that_cannot_price_a_trade_fails_the_check(ledger: LedgerPort) -> None:
    result = ledger.propose_add((facts(Side.BUY, "ETH", "0.01", quote="BTC"),))

    assert result.checks[0].code == "cannot_price"


def test_a_change_or_a_deletion_that_leaves_a_later_sell_short_fails_the_check() -> None:
    ledger = FakeLedger()
    september, october = ledger.list_trades(
        TradeFilter(asset="BTC", side=Side.BUY, end=datetime(2026, 10, 7, tzinfo=BUDAPEST))
    )
    # With the September buy gone, the October buy alone still covers the
    # 0.006 BTC sold on 21 October; moved after that sell, or deleted, it does not.
    first = ledger.propose_delete(september.id).proposal_id
    assert first is not None
    ledger.save(first)
    moved = dataclasses.replace(october.facts, occurred=datetime(2026, 10, 22, tzinfo=BUDAPEST))

    changed = ledger.propose_update(october.id, moved)
    deleted = ledger.propose_delete(october.id)

    for result in (changed, deleted):
        assert result.checks[0].code == "sells_more_than_held"
        assert result.proposal_id is None


def test_a_change_or_deletion_of_a_trade_not_in_the_ledger_is_not_found(
    ledger: LedgerPort,
) -> None:
    for propose in (
        lambda: ledger.propose_delete("t-99"),
        lambda: ledger.propose_update("t-99", facts(Side.BUY, "BTC", "0.01")),
    ):
        with pytest.raises(LedgerError) as caught:
            propose()
        assert caught.value.kind is LedgerErrorKind.NOT_FOUND
        assert caught.value.code == "trade_not_found"


def test_a_failing_ledger_raises_its_failure_on_every_call() -> None:
    failure = LedgerError(LedgerErrorKind.UNREACHABLE, "offline", "The ledger is not open.")
    ledger = FakeLedger(failure=failure)

    with pytest.raises(LedgerError) as caught:
        ledger.positions()

    assert caught.value is failure
    assert ledger.calls == ["positions"]
