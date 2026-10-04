"""Tests of the decimal contexts the core calculates in."""

from __future__ import annotations

import decimal
from collections.abc import Callable
from decimal import Decimal
from fractions import Fraction

import pytest

from ledger_hand.core.arithmetic import (
    WORKING_PRECISION,
    ledger_context,
    round_half_up,
    working_context,
)

FORTY_DIGITS = Decimal("1234567890123456789012.123456789012345678")
ANOTHER_FORTY = Decimal("9876543210987654321098.876543210987654321")


# --- the working context ----------------------------------------------------


def test_working_context_is_wide_and_rounds_half_up() -> None:
    context = working_context()

    assert WORKING_PRECISION == 150
    assert context.prec == WORKING_PRECISION
    assert context.rounding == decimal.ROUND_HALF_UP


def test_working_context_multiplies_two_full_length_numbers_exactly() -> None:
    product = working_context().multiply(FORTY_DIGITS, ANOTHER_FORTY)

    assert Fraction(product) == Fraction(FORTY_DIGITS) * Fraction(ANOTHER_FORTY)


def test_working_context_subtracts_a_full_length_number_from_such_a_product_exactly() -> None:
    context = working_context()
    whole = Decimal("9" * 40)

    difference = context.subtract(context.multiply(whole, whole), FORTY_DIGITS)

    assert Fraction(difference) == Fraction(whole) ** 2 - Fraction(FORTY_DIGITS)


def test_working_context_says_whether_a_division_came_out_even() -> None:
    even = working_context()
    uneven = working_context()

    assert even.divide(Decimal("1898"), Decimal("94900")) == Decimal("0.02")
    uneven.divide(Decimal("100"), Decimal("3"))

    assert not even.flags[decimal.Inexact]
    assert uneven.flags[decimal.Inexact]


@pytest.mark.parametrize("make", [working_context, ledger_context])
def test_every_call_gives_a_context_of_its_own(make: Callable[[], decimal.Context]) -> None:
    first = make()
    second = make()

    first.divide(Decimal("1"), Decimal("3"))

    assert first is not second
    assert first.flags[decimal.Inexact]
    assert not second.flags[decimal.Inexact]


@pytest.mark.parametrize("make", [working_context, ledger_context])
def test_impossible_operations_raise_instead_of_passing_a_marker_value_on(
    make: Callable[[], decimal.Context],
) -> None:
    context = make()

    with pytest.raises(decimal.DivisionByZero):
        context.divide(Decimal("1"), Decimal("0"))
    with pytest.raises(decimal.InvalidOperation):
        context.divide(Decimal("0"), Decimal("0"))


# --- the ledger's arithmetic ------------------------------------------------


def test_ledger_context_keeps_forty_significant_digits_and_rounds_half_up() -> None:
    context = ledger_context()

    assert context.prec == 40
    assert context.rounding == decimal.ROUND_HALF_UP


def test_ledger_context_rounds_a_long_product_the_way_the_ledger_does() -> None:
    product = ledger_context().multiply(
        Decimal("5"), Decimal("2000000000000000000000.001000000000000001")
    )

    assert product == Decimal("10000000000000000000000.00500000000000001")


# --- rounding ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "places", "rounded"),
    [
        ("0.125", 2, "0.13"),
        ("0.135", 2, "0.14"),
        ("2.5", 0, "3"),
        ("0.124999", 2, "0.12"),
        ("33.333333333333", 8, "33.33333333"),
        ("0.0000000000000000005", 18, "0.000000000000000001"),
        ("1898", 3, "1898.000"),
        ("-0.125", 2, "-0.13"),
    ],
)
def test_round_half_up_rounds_a_tie_away_from_zero(value: str, places: int, rounded: str) -> None:
    result = round_half_up(Decimal(value), places)

    assert format(result, "f") == rounded


def test_round_half_up_keeps_every_digit_of_a_long_number() -> None:
    long_number = Decimal("9" * 60 + ".123456789")

    assert round_half_up(long_number, 4) == Decimal("9" * 60 + ".1235")


# --- nothing leaks in from the caller ---------------------------------------


def test_results_do_not_depend_on_the_decimal_context_of_the_caller() -> None:
    hostile = decimal.Context(prec=3, rounding=decimal.ROUND_DOWN)
    hostile.traps[decimal.Inexact] = True
    hostile.traps[decimal.Rounded] = True

    with decimal.localcontext(hostile):
        product = working_context().multiply(FORTY_DIGITS, ANOTHER_FORTY)
        rounded = round_half_up(Decimal("33.333333333333"), 8)

    assert Fraction(product) == Fraction(FORTY_DIGITS) * Fraction(ANOTHER_FORTY)
    assert rounded == Decimal("33.33333333")
