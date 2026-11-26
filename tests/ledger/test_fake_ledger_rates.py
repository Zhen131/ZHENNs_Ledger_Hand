"""Tests of the fake ledger's check of a trade paid in another money: the ledger's own rule.

For an asset whose own money the book names: paid in another money a
trade needs its rate, paid in its own money it takes none, and a rate is
above 0. An asset whose own money the book does not name is not checked.
A card with an empty cell is taken all the same, the mismatch said as what
its cells show. Every figure is invented.
"""

from __future__ import annotations

import dataclasses
from decimal import Decimal

from ledger_hand.core.ledger_records import TradeFilter
from ledger_hand.core.proposals import CheckOutcome
from ledger_hand.core.trade_card import card_of
from ledger_hand.ledger.fake_ledger import FakeLedger
from tests.flows import paid_apart_books as books

PAID_IN_EUROS = books.bought("KO", "EUR", (2026, 11, 24, 15, 30), "64", rate="1.0859375")


def _one(ledger: FakeLedger, rate: Decimal | None, quote: str = "EUR") -> tuple[str | None, bool]:
    facts = dataclasses.replace(PAID_IN_EUROS, cost_rate=rate, quote=quote, fee_asset=quote)
    (check,) = ledger.propose_add((facts,), "invented").checks
    return check.code, check.outcome is CheckOutcome.PASSED


def test_paid_in_another_money_with_its_rate_is_taken() -> None:
    assert _one(books.jia(), Decimal("1.0859375")) == (None, True)


def test_paid_in_another_money_with_no_rate_is_turned_down() -> None:
    assert _one(books.jia(), None) == ("CURRENCY_MISMATCH", False)


def test_paid_in_its_own_money_with_a_rate_is_turned_down() -> None:
    assert _one(books.jia(), Decimal("1"), quote="USD") == ("CURRENCY_MISMATCH", False)


def test_a_rate_of_zero_is_turned_down() -> None:
    assert _one(books.jia(), Decimal(0)) == ("VALUE_MUST_BE_POSITIVE", False)


def test_an_asset_whose_own_money_is_not_named_is_not_checked() -> None:
    assert _one(books.ding(), None) == (None, True)
    assert _one(books.ding(), Decimal("1.0859375"), quote="USD") == (None, True)


def test_a_card_with_an_empty_cell_and_no_rate_is_taken_with_the_mismatch_said() -> None:
    card = dataclasses.replace(
        card_of(dataclasses.replace(PAID_IN_EUROS, cost_rate=None)), fee=None
    )

    (check,) = books.jia().propose_cards((card,), "invented").checks

    assert check.outcome is CheckOutcome.PASSED and check.ready is False
    assert check.problem is not None and check.problem.code == "CURRENCY_MISMATCH"


def test_a_trade_listed_comes_back_with_the_rate_it_was_sent_with() -> None:
    ledger = books.jia()

    (aapl,) = [
        trade for trade in ledger.list_trades(TradeFilter()).trades if trade.id == "t-aapl-eur"
    ]

    assert aapl.facts.cost_rate == Decimal("1.0859")
