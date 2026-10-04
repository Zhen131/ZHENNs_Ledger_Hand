"""Tests of the ledger's limits and of the yardsticks that measure against them.

The expected values are written out by hand from the ledger's validation
code, so a limit that drifts here fails a test.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ledger_hand.core import ledger_limits
from ledger_hand.core.ledger_limits import (
    decimal_places,
    fits_digit_limits,
    is_symbol,
    significant_digits,
    text_length,
    trim,
)

# --- the limits themselves --------------------------------------------------


def test_limits_match_the_ledger() -> None:
    assert ledger_limits.QUOTE_CURRENCY == "USDT"
    assert ledger_limits.SYMBOL_MAX_LENGTH == 32
    assert ledger_limits.COIN_NAME_MAX_LENGTH == 128
    assert ledger_limits.MARKET_PAIR_MAX_LENGTH == 32
    assert ledger_limits.MAX_DECIMAL_PLACES == 18
    assert ledger_limits.MAX_SIGNIFICANT_DIGITS == 40
    assert Decimal("0.01") == ledger_limits.TOTAL_TOLERANCE
    assert ledger_limits.ARITHMETIC_PRECISION == 40
    assert ledger_limits.PLATFORM_MAX_LENGTH == 128
    assert ledger_limits.NOTE_MAX_LENGTH == 4096
    assert ledger_limits.RAW_TEXT_MAX_LENGTH == 16384


# --- text length ------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "length"),
    [
        ("", 0),
        ("abc", 3),
        ("买了 0.02 BTC", 11),
        ("\N{GRINNING FACE}", 2),
        ("up \N{ROCKET} again", 11),
        ("e\N{COMBINING ACUTE ACCENT}", 2),
        ("\ud83d", 1),
    ],
)
def test_text_length_counts_utf16_code_units(text: str, length: int) -> None:
    assert text_length(text) == length


# --- surrounding whitespace -------------------------------------------------


@pytest.mark.parametrize(
    ("text", "trimmed"),
    [
        ("OKX", "OKX"),
        ("  OKX\t\n", "OKX"),
        ("\N{IDEOGRAPHIC SPACE}币安\N{IDEOGRAPHIC SPACE}", "币安"),
        ("\N{NO-BREAK SPACE}OKX\N{ZERO WIDTH NO-BREAK SPACE}", "OKX"),
        ("\N{LINE SEPARATOR}OKX\N{PARAGRAPH SEPARATOR}", "OKX"),
        ("Gate io", "Gate io"),
        (" \t\r\n", ""),
    ],
)
def test_trim_removes_what_the_ledger_calls_whitespace(text: str, trimmed: str) -> None:
    assert trim(text) == trimmed


def test_trim_keeps_characters_the_ledger_does_not_call_whitespace() -> None:
    # The ledger's trim leaves these control characters alone, so trimming them
    # here would make this program disagree with the ledger about a text.
    assert trim("\x1cOKX\x85") == "\x1cOKX\x85"


# --- symbols ----------------------------------------------------------------


@pytest.mark.parametrize("text", ["BTC", "ETH", "1INCH", "A", "USDC", "X" * 32])
def test_well_formed_symbol_is_accepted(text: str) -> None:
    assert is_symbol(text)


@pytest.mark.parametrize(
    "text",
    [
        "",
        "btc",
        "Btc",
        "BT-C",
        "BT C",
        "BTC ",
        "BTC\n",
        "比特币",
        "\N{FULLWIDTH LATIN CAPITAL LETTER B}TC",
        "X" * 33,
    ],
)
def test_malformed_symbol_is_refused(text: str) -> None:
    assert not is_symbol(text)


def test_the_quote_currency_is_not_a_coin_symbol() -> None:
    assert not is_symbol("USDT")


# --- the digits of a number -------------------------------------------------


@pytest.mark.parametrize(
    ("value", "significant", "places"),
    [
        ("0.02", 1, 2),
        ("94900", 5, 0),
        ("1000", 4, 0),
        ("100.50", 5, 2),
        ("0", 1, 0),
        ("0.000", 1, 3),
        ("0.020", 2, 3),
        ("1E+3", 4, 0),
        ("1.5E-7", 2, 8),
        ("-12.5", 3, 1),
        ("123456789.123456789", 18, 9),
    ],
)
def test_digits_are_counted_as_the_ledger_counts_them(
    value: str, significant: int, places: int
) -> None:
    number = Decimal(value)

    assert significant_digits(number) == significant
    assert decimal_places(number) == places


@pytest.mark.parametrize(
    "value",
    [
        "1",
        "0.02",
        "0." + "0" * 17 + "1",
        "1." + "1" * 18,
        "9" * 40,
        "9" * 22 + "." + "9" * 18,
    ],
)
def test_number_within_the_digit_limits_fits(value: str) -> None:
    assert fits_digit_limits(Decimal(value))


@pytest.mark.parametrize(
    "value",
    [
        "0." + "0" * 18 + "1",
        "1." + "1" * 19,
        "9" * 41,
        "9" * 23 + "." + "9" * 18,
        "1E+40",
    ],
)
def test_number_beyond_the_digit_limits_does_not_fit(value: str) -> None:
    assert not fits_digit_limits(Decimal(value))
