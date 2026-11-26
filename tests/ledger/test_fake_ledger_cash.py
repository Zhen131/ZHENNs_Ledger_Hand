"""Tests of the fake ledger's cash balances: none by default, as given, or moved by its trades.

By default the fake ledger has no tool for cash balances, as an older
ledger has none: asked, it says so with its own code and names no call.
Handed ``cash``, it hands those balances back as the ledger would: one row
for each cash asset, in its list's order, 0 for one not named. Handed
``opening_cash``, each balance is moved by every trade of its book, the
ledger's way. Every figure is invented.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest

from ledger_hand.core.ledger_records import (
    NO_CASH_TOOL,
    Asset,
    AssetKind,
    CashBalance,
    CashBalances,
    Pricing,
    TradeFacts,
)
from ledger_hand.core.trade import Side
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ledger.invented_book import INVENTED_ASSETS, INVENTED_NOW, INVENTED_ZONE
from ledger_hand.ports import LedgerError, LedgerErrorKind


def cash_asset(code: str, name: str) -> Asset:
    return Asset(
        id=f"asset-{code.lower()}",
        code=code,
        name=name,
        kind=AssetKind.CASH,
        pricing=Pricing.CAN_PRICE,
    )


YUAN = cash_asset("CNY", "Chinese yuan")
EURO = cash_asset("EUR", "Euro")


def buy(asset: str, total: str, quote: str, fee: str, fee_asset: str, side: Side = Side.BUY):
    """One invented trade of 1 unit, on 1 November 2026."""
    return TradeFacts(
        occurred=datetime(2026, 11, 1, 10, 0, tzinfo=INVENTED_NOW.tzinfo),
        side=side,
        asset=asset,
        quantity=Decimal(1),
        price=Decimal(total),
        total=Decimal(total),
        quote=quote,
        fee=Decimal(fee),
        fee_asset=fee_asset,
        platform="",
        note="",
        raw_text=None,
        zone=INVENTED_ZONE,
        date_only=False,
        cost_rate=None,
    )


def test_by_default_it_has_no_tool_and_names_no_call() -> None:
    ledger = FakeLedger()

    with pytest.raises(LedgerError) as raised:
        ledger.cash_balances()

    assert raised.value.code == NO_CASH_TOOL
    assert raised.value.kind is LedgerErrorKind.OTHER
    assert ledger.calls == []


def test_balances_given_are_handed_back_as_they_are_one_row_a_cash_asset_in_order() -> None:
    ledger = FakeLedger(
        assets=(*INVENTED_ASSETS, YUAN, EURO),
        cash={"USDT": Decimal("1200.5"), "USD": Decimal("830"), "EUR": Decimal("250")},
    )

    balances = ledger.cash_balances()

    assert [(row.code, row.name, row.balance) for row in balances.balances] == [
        ("USDT", "Tether", Decimal("1200.5")),
        ("USD", "US dollar", Decimal("830")),
        ("CNY", "Chinese yuan", Decimal("0")),
        ("EUR", "Euro", Decimal("250")),
    ]
    assert balances.day == date(2026, 11, 24)
    assert ledger.calls == ["cash_balances"]


def test_balances_given_are_not_moved_by_its_trades() -> None:
    ledger = FakeLedger(cash={"USDT": Decimal("-30")})

    rows = ledger.cash_balances().balances

    assert [(row.code, row.balance) for row in rows] == [
        ("USDT", Decimal("-30")),
        ("USD", Decimal("0")),
    ]


def test_opening_amounts_are_moved_by_every_trade_the_ledgers_way() -> None:
    # USDT: 1000 - (100 + 1) for a buy with a fee in USDT, + (50 - 2) for a sell
    # = 947; a buy whose fee is paid in BTC moves no cash for its fee: - 10 = 937.
    # USD: 500 - 20, the fee of 3 paid in USDT moving no US dollar = 480.
    trades = (
        ("t-1", buy("BTC", "100", "USDT", "1", "USDT")),
        ("t-2", buy("BTC", "50", "USDT", "2", "USDT", side=Side.SELL)),
        ("t-3", buy("BTC", "10", "USDT", "0.001", "BTC")),
        ("t-4", buy("MSFT", "20", "USD", "3", "USDT")),
    )
    ledger = FakeLedger(
        trades=trades, opening_cash={"USDT": Decimal("1000"), "USD": Decimal("500")}
    )

    rows = ledger.cash_balances().balances

    assert [(row.code, row.balance) for row in rows] == [
        ("USDT", Decimal("937")),
        ("USD", Decimal("480")),
    ]


def test_a_trade_saved_shows_in_the_balances_next_asked_for() -> None:
    ledger = FakeLedger(trades=(), opening_cash={"USDT": Decimal("1000")})
    (check,) = ledger.propose_add((buy("BTC", "100", "USDT", "1", "USDT"),), "invented").checks
    assert check.proposal_id is not None

    before = ledger.cash_balances().balances[0].balance
    ledger.save(check.proposal_id)
    after = ledger.cash_balances().balances[0].balance

    assert (before, after) == (Decimal("1000"), Decimal("899"))


def test_a_ledger_with_no_cash_asset_hands_back_no_row() -> None:
    coins_only = tuple(asset for asset in INVENTED_ASSETS if asset.kind is not AssetKind.CASH)

    balances = FakeLedger(assets=coins_only, trades=(), cash={}).cash_balances()

    assert balances.balances == ()


def test_a_failing_ledger_fails_the_call_for_cash_too() -> None:
    failure = LedgerError(LedgerErrorKind.UNREACHABLE, "X", "gone")
    ledger = FakeLedger(failure=failure, cash={"USDT": Decimal("1")})

    with pytest.raises(LedgerError) as raised:
        ledger.cash_balances()

    assert raised.value is failure


@pytest.mark.parametrize(
    "made",
    [
        {"cash": {"BTC": Decimal("1")}},
        {"opening_cash": {"EUR": Decimal("1")}},
        {"cash": {"USDT": Decimal("1")}, "opening_cash": {"USDT": Decimal("1")}},
    ],
    ids=["a coin", "a money it lacks", "both kinds"],
)
def test_cash_of_an_asset_that_is_not_its_cash_or_given_twice_is_refused(
    made: dict[str, dict[str, Decimal]],
) -> None:
    with pytest.raises(ValueError):
        FakeLedger(**made)  # type: ignore[arg-type]


def test_the_shapes_refuse_two_rows_of_one_money_and_keep_a_balance_below_zero() -> None:
    row = CashBalance(code="USD", name="US dollar", balance=Decimal("-30"))
    assert row.balance == Decimal("-30")
    with pytest.raises(ValueError):
        CashBalances(day=date(2026, 11, 24), balances=(row, row))
    with pytest.raises(ValueError):
        CashBalance(code=" ", name="US dollar", balance=Decimal(0))
