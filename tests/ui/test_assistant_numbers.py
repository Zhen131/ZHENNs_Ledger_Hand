"""Tests of how the assistant page writes a number: in full, with thousands marks, never changed.

Each figure shown is read back and must be the very decimal the result
held: every place kept, no rounding, no exponent. And every figure of a
table the page draws reads back to the figure of the trade it came from.
Every number is invented.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from ledger_hand.core.ledger_records import TradeFacts
from ledger_hand.core.trade import Side
from ledger_hand.ui.assistant_numbers import read_back, shown
from ledger_hand.ui.assistant_tables import proposed_rows

EXAMPLES = [
    ("0", "0"),
    ("94900", "94,900"),
    ("1898", "1,898"),
    ("0.02", "0.02"),
    ("0.00012345", "0.00012345"),
    ("0.000009", "0.000009"),
    ("1234567.891011121314", "1,234,567.891011121314"),
    ("62704.69135802", "62,704.69135802"),
    ("-1500.50", "-1,500.50"),
    ("1E+3", "1,000"),
    ("1.0E-7", "0.00000010"),
    ("410", "410"),
    ("999", "999"),
    ("1000", "1,000"),
]


@pytest.mark.parametrize(("value", "text"), EXAMPLES)
def test_a_number_is_written_in_full_with_thousands_marks(value: str, text: str) -> None:
    assert shown(Decimal(value)) == text


@pytest.mark.parametrize(("value", "_text"), EXAMPLES)
def test_what_is_shown_reads_back_to_the_same_value(value: str, _text: str) -> None:
    assert read_back(shown(Decimal(value))) == Decimal(value)


def test_many_numbers_read_back_unchanged() -> None:
    for whole in (0, 7, 42, 999, 1000, 123456, 10**15):
        for places in ("", ".5", ".05", ".123456789", ".000000000001"):
            value = Decimal(f"{whole}{places}")
            assert read_back(shown(value)) == value
            assert read_back(shown(-value)) == -value


def test_only_a_decimal_is_shown() -> None:
    with pytest.raises(TypeError):
        shown(0.1)  # type: ignore[arg-type]


def test_every_figure_of_the_proposal_table_reads_back_to_the_trade() -> None:
    facts = TradeFacts(
        occurred=datetime(2026, 11, 24, 15, 30, tzinfo=ZoneInfo("Europe/Budapest")),
        side=Side.BUY,
        asset="MSFT",
        quantity=Decimal("2"),
        price=Decimal("410.125"),
        total=Decimal("820.25"),
        quote="USD",
        fee=Decimal("1"),
        fee_asset="USD",
        platform="IBKR",
        note="",
        raw_text="invented",
        zone=None,
        date_only=False,
        cost_rate=None,
    )

    (cells,) = proposed_rows((1,), (facts,))

    assert read_back(cells["Quantity"]) == facts.quantity
    for name, value in (("Price", facts.price), ("Total", facts.total), ("Fee", facts.fee)):
        number, money = cells[name].split(" ")
        assert read_back(number) == value
        assert money == "USD"
