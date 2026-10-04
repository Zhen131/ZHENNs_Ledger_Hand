"""Tests of reading a number the way people write or say it.

Every amount here is invented. Each kind of wording has a section of its own.
"""

from __future__ import annotations

import pytest

from ledger_hand.core.numbers import NotANumber, Recognised, read_number


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
    assert written(text) == text


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
