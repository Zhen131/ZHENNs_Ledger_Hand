"""Tests of reading a number the way people write or say it.

Every amount here is invented. Each kind of wording has a section of its own.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ledger_hand.core.numbers import (
    Caution,
    Doubt,
    NotANumber,
    Recognised,
    Unsure,
    read_number,
)


def recognised(text: str) -> Recognised:
    reading = read_number(text)
    assert isinstance(reading, Recognised), f"{text!r} was read as {reading!r}"
    return reading


def written(text: str) -> str:
    """The value read from ``text``, written out in full."""
    return format(recognised(text).value, "f")


# --- ordinary writing -------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "0.02",
        "94900",
        "0",
        "7",
        "0.0",
        "1898.50",
        "0.020",
        "100000000",
        "0.000000033",
        "123456789.000000001",
    ],
)
def test_ordinary_number_is_read_exactly_as_written(text: str) -> None:
    reading = recognised(text)

    assert format(reading.value, "f") == text
    assert reading.cautions == ()


@pytest.mark.parametrize(
    "text",
    [
        " 94900",
        "94900 ",
        "\t94900\n",
        "\N{NO-BREAK SPACE}94900\N{NO-BREAK SPACE}",
        "\N{IDEOGRAPHIC SPACE}94900",
    ],
)
def test_whitespace_around_a_number_is_ignored(text: str) -> None:
    assert written(text) == "94900"


# --- commas between groups of three digits ----------------------------------


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("94,900", "94900"),
        ("1,234,567.89", "1234567.89"),
        ("1,000", "1000"),
        ("12,345", "12345"),
        ("999,999", "999999"),
        ("1,000,000,000", "1000000000"),
        ("1,234.5", "1234.5"),
        ("1,234.567", "1234.567"),
        ("100,000.00", "100000.00"),
    ],
)
def test_commas_between_groups_of_three_digits_are_dropped(text: str, value: str) -> None:
    reading = recognised(text)

    assert format(reading.value, "f") == value
    assert reading.cautions == ()


# --- separators that can be read more than one way --------------------------


@pytest.mark.parametrize(
    "text",
    [
        "1,5",
        "1.234.567",
        "94.900,50",
        "0,5",
        "0,500",
        "1,23",
        "1,2345",
        "1234,567",
        "12,34,567",
        "1,234,56",
        "1.234,567",
        "1,,234",
        "1,234.567.8",
        "94 900",
        "1 234 567",
        "94\N{NARROW NO-BREAK SPACE}900",
        "94, 900",
        "0.5 0.6",
    ],
)
def test_separators_with_more_than_one_reading_are_not_guessed(text: str) -> None:
    assert read_number(text) == Unsure(Doubt.AMBIGUOUS_SEPARATOR)


# --- a point that may have been meant to group thousands --------------------


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("94.900", "94.900"),
        ("1.234", "1.234"),
        ("999.999", "999.999"),
        ("100.000", "100.000"),
        ("1.500", "1.500"),
    ],
)
def test_point_before_exactly_three_digits_is_read_as_decimal_with_a_caution(
    text: str, value: str
) -> None:
    reading = recognised(text)

    assert format(reading.value, "f") == value
    assert reading.cautions == (Caution.POINT_MAY_BE_THOUSANDS_SEPARATOR,)


def test_the_decimal_reading_of_such_a_point_is_the_smaller_number() -> None:
    assert recognised("94.900").value == Decimal("94.9")


@pytest.mark.parametrize(
    "text", ["0.900", "0.123", "1234.567", "94.90", "94.9000", "94900.123", "1,234.567"]
)
def test_point_that_cannot_be_grouping_thousands_carries_no_caution(text: str) -> None:
    assert recognised(text).cautions == ()


# --- full-width characters --------------------------------------------------


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("９４９００", "94900"),
        ("０．０２", "0.02"),
        ("９４，９００", "94900"),
        ("9４900", "94900"),
        ("１，２３４，５６７．８９", "1234567.89"),
        ("\N{IDEOGRAPHIC SPACE}９４９００\N{IDEOGRAPHIC SPACE}", "94900"),
    ],
)
def test_full_width_characters_are_read_as_their_ordinary_forms(text: str, value: str) -> None:
    assert written(text) == value


def test_full_width_separators_are_judged_like_ordinary_ones() -> None:
    assert read_number("１，５") == Unsure(Doubt.AMBIGUOUS_SEPARATOR)
    assert read_number("９４\N{IDEOGRAPHIC SPACE}９００") == Unsure(Doubt.AMBIGUOUS_SEPARATOR)
    assert recognised("９４．９００").cautions == (Caution.POINT_MAY_BE_THOUSANDS_SEPARATOR,)


@pytest.mark.parametrize("text", ["－５", "１ｅ５", "１＿０００", "ＮａＮ", "０。５", "００７"])
def test_full_width_spelling_does_not_let_a_refused_form_through(text: str) -> None:
    assert read_number(text) == NotANumber()


# --- what is not a number ---------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "",
        " ",
        "\n",
        "NaN",
        "nan",
        "sNaN",
        "Infinity",
        "-Infinity",
        "inf",
        "1e5",
        "1E5",
        "1e-5",
        "1.5e3",
        "1_000",
        "-5",
        "+5",
        "\N{MINUS SIGN}5",
        "(5)",
        "很多",
        "abc",
        "BTC",
        "007",
        "00.5",
        "01,234",
        "0x10",
        ".5",
        "5.",
        "5,",
        "\N{ARABIC-INDIC DIGIT ONE}\N{ARABIC-INDIC DIGIT TWO}",
        "\N{DEVANAGARI DIGIT ONE}\N{DEVANAGARI DIGIT TWO}",
        "\N{CIRCLED DIGIT ONE}",
        "5\N{SUPERSCRIPT TWO}",
        "1\N{ZERO WIDTH SPACE}000",
    ],
)
def test_text_that_is_not_a_number_is_called_that(text: str) -> None:
    assert read_number(text) == NotANumber()
