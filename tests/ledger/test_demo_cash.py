"""Tests of the demo ledger with cash: the demo book as it is, and opening cash its trades move.

The page and the try-out script use it; ``demo_ledger`` itself still has no
tool for cash, as every test written before it expects. Every figure is
invented.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ledger_hand.core.ledger_records import NO_CASH_TOOL, TradeFilter
from ledger_hand.ledger.demo_book import DEMO_TRADES, demo_ledger
from ledger_hand.ledger.demo_cash import DEMO_OPENING_CASH, demo_ledger_with_cash
from ledger_hand.ports import LedgerError
from tests.ledger.test_fake_ledger_cash import buy


def test_it_is_the_demo_book_with_cash_and_the_demo_ledger_has_none() -> None:
    with_cash, without = demo_ledger_with_cash(), demo_ledger()

    assert with_cash.list_assets() == without.list_assets()
    assert with_cash.list_trades(TradeFilter()) == without.list_trades(TradeFilter())
    with pytest.raises(LedgerError) as raised:
        without.cash_balances()
    assert raised.value.code == NO_CASH_TOOL


def test_every_balance_is_the_opening_amount_moved_by_every_trade_and_none_is_below_zero() -> None:
    rows = {row.code: row.balance for row in demo_ledger_with_cash().cash_balances().balances}

    assert rows == {"USDT": Decimal("140080.18724"), "USD": Decimal("17093.94")}
    assert all(balance > 0 for balance in rows.values())
    assert set(rows) == set(DEMO_OPENING_CASH)


def test_the_august_buys_alone_take_about_what_the_file_says() -> None:
    august = [facts for _, facts in DEMO_TRADES if facts.occurred.month == 8]
    by_money: dict[str, Decimal] = {}
    for facts in august:
        by_money[facts.quote] = by_money.get(facts.quote, Decimal(0)) + facts.total + facts.fee

    assert by_money == {"USDT": Decimal("107707.6"), "USD": Decimal("42105")}


def test_a_trade_saved_in_the_demo_moves_its_cash() -> None:
    ledger = demo_ledger_with_cash()
    (check,) = ledger.propose_add((buy("BTC", "100", "USDT", "1", "USDT"),), "invented").checks
    assert check.proposal_id is not None

    ledger.save(check.proposal_id)

    usdt = ledger.cash_balances().balances[0]
    assert (usdt.code, usdt.balance) == ("USDT", Decimal("139979.18724"))
