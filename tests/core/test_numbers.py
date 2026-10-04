"""Tests of reading a number the way people write or say it, and of writing one for the ledger.

Every amount here is invented. Each kind of wording has a section of its own.
"""

from __future__ import annotations

import decimal
import itertools
import random
import re
from decimal import Decimal

import pytest

from ledger_hand.core.numbers import (
    Caution,
    Doubt,
    NotANumber,
    Recognised,
    Unsure,
    read_number,
    write_number,
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
    assert reading.unit is None
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
        "5.万",
        "8,万",
        "1.,5",
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


# --- units and currency words -----------------------------------------------


@pytest.mark.parametrize(
    ("text", "value", "unit"),
    [
        ("50美金", "50", "美金"),
        ("0.5个", "0.5", "个"),
        ("2 USDT", "2", "USDT"),
        ("$50", "50", "$"),
        ("50u", "50", "u"),
        ("50U", "50", "U"),
        ("0.02BTC", "0.02", "BTC"),
        ("0.02 btc", "0.02", "btc"),
        ("100 dollars", "100", "dollars"),
        ("94,900刀", "94900", "刀"),
        ("3个比特币", "3", "个比特币"),
        ("5" + "X" * 32, "5", "X" * 32),
        ("0.02 个 BTC", "0.02", "个 BTC"),
        ("3个 比特币", "3", "个 比特币"),
        ("2 US dollars", "2", "US dollars"),
        ("两万三 个 USDT", "23000", "个 USDT"),
        ("50$", "50", "$"),
        ("50 €", "50", "€"),
        ("¥700", "700", "¥"),
        ("£5", "5", "£"),
        ("$ 50", "50", "$"),
        (" 2  USDT ", "2", "USDT"),
        ("50\N{IDEOGRAPHIC SPACE}美金", "50", "美金"),
    ],
)
def test_unit_or_currency_word_is_split_off_and_handed_back(
    text: str, value: str, unit: str
) -> None:
    reading = recognised(text)

    assert format(reading.value, "f") == value
    assert reading.unit == unit


@pytest.mark.parametrize(
    ("text", "unit"),
    [("＄５０", "＄"), ("５０Ｕ", "Ｕ"), ("５０ｕｓｄｔ", "ｕｓｄｔ"), ("￥７００", "￥")],
)
def test_unit_is_handed_back_exactly_as_it_was_written(text: str, unit: str) -> None:
    assert recognised(text).unit == unit


def test_caution_survives_next_to_a_unit() -> None:
    reading = recognised("94.900刀")

    assert reading.unit == "刀"
    assert reading.cautions == (Caution.POINT_MAY_BE_THOUSANDS_SEPARATOR,)


def test_doubt_about_the_number_is_reported_whatever_its_unit() -> None:
    assert read_number("1,5个") == Unsure(Doubt.AMBIGUOUS_SEPARATOR)
    assert read_number("$1.234.567") == Unsure(Doubt.AMBIGUOUS_SEPARATOR)
    assert read_number("50 1INCH") == Unsure(Doubt.AMBIGUOUS_SEPARATOR)


@pytest.mark.parametrize(
    "text",
    [
        "$",
        "USDT",
        "个",
        "$50u",
        "$50 USDT",
        "$$50",
        "50$$",
        "50 US dollars cash",
        "0.02 个 BTC 现货",
        "5 " + "X" * 16 + " " + "X" * 16,
        "50$\N{YEN SIGN}",
        "50 $ u",
        "50u5",
        "50#",
        "50_",
        "50-",
        "u50",
        "美金50",
        "5" + "X" * 33,
    ],
)
def test_anything_beyond_one_number_and_one_unit_is_not_a_number(text: str) -> None:
    assert read_number(text) == NotANumber()


@pytest.mark.parametrize("text", ["3个亿", "0.5个二饼", "3仟", "5块3", "2佰", "3萬", "5点", "2俩"])
def test_word_holding_a_number_word_is_never_taken_for_a_unit(text: str) -> None:
    # Taking "个亿" for a unit would turn three hundred million into three.
    assert not isinstance(read_number(text), Recognised)


# --- multipliers after written digits ---------------------------------------


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("1.2k", "1200"),
        ("3w", "30000"),
        ("8万", "80000"),
        ("8.5万", "85000"),
        ("2亿", "200000000"),
        ("1.2K", "1200"),
        ("3W", "30000"),
        ("5k", "5000"),
        ("0.5k", "500"),
        ("1.25w", "12500"),
        ("3千", "3000"),
        ("3千万", "30000000"),
        ("1.5亿", "150000000"),
        ("2.5百万", "2500000"),
        ("5十万", "500000"),
        ("1.2万亿", "1200000000000"),
        ("12000万", "120000000"),
        ("1,200万", "12000000"),
        ("8 万", "80000"),
        ("８．５万", "85000"),
        ("３ｗ", "30000"),
    ],
)
def test_multiplier_after_written_digits_is_applied(text: str, value: str) -> None:
    reading = recognised(text)

    assert format(reading.value, "f") == value
    assert reading.unit is None


@pytest.mark.parametrize(
    ("text", "value"),
    [("1.50万", "15000"), ("0.00015万", "1.5"), ("1.2345678k", "1234.5678"), ("0.0010k", "1")],
)
def test_multiplying_leaves_no_zeros_behind_after_the_point(text: str, value: str) -> None:
    assert written(text) == value


@pytest.mark.parametrize(
    ("text", "value", "unit"),
    [
        ("8万刀", "80000", "刀"),
        ("8 万刀", "80000", "刀"),
        ("3w刀", "30000", "刀"),
        ("3w usdt", "30000", "usdt"),
        ("1.2k美金", "1200", "美金"),
        ("1.2k u", "1200", "u"),
        ("$1.2k", "1200", "$"),
        ("2亿个", "200000000", "个"),
        ("5千 USDT", "5000", "USDT"),
    ],
)
def test_multiplier_and_unit_can_both_follow_the_digits(text: str, value: str, unit: str) -> None:
    reading = recognised(text)

    assert format(reading.value, "f") == value
    assert reading.unit == unit


def test_caution_and_doubt_about_the_digits_survive_a_multiplier() -> None:
    cautious = recognised("1.234k")

    assert format(cautious.value, "f") == "1234"
    assert cautious.cautions == (Caution.POINT_MAY_BE_THOUSANDS_SEPARATOR,)
    assert read_number("1,5k") == Unsure(Doubt.AMBIGUOUS_SEPARATOR)
    assert read_number("1,5万") == Unsure(Doubt.AMBIGUOUS_SEPARATOR)


@pytest.mark.parametrize(
    "text",
    [
        # m is a million to some and a thousandth (as in mBTC) to others.
        "5m",
        "5M",
        "2b",
        "2B",
        "3t",
        "2bn",
        "5kk",
        "1kw",
        "1ku",
        "1wu",
        "5kas",
        "3wif",
        "5 k",
        "5 w",
        "5 m",
        "5 million",
        "5million",
        "2 thousand",
        "2thousand",
        "3 billion",
        "1 mil",
        "3 hundred",
        "5 dozen",
        "5 million dollars",
        "2 k usdt",
        "3 usdt k",
        "5 million dollars in cash",
        "8万k",
        "8万 w",
    ],
)
def test_letters_that_may_or_may_not_multiply_are_not_guessed(text: str) -> None:
    assert read_number(text) == Unsure(Doubt.UNCLEAR_MULTIPLIER)


@pytest.mark.parametrize(
    ("text", "value", "unit"),
    [
        ("50matic", "50", "matic"),
        ("5mBTC", "5", "mBTC"),
        ("0.5btc", "0.5", "btc"),
        ("2ton", "2", "ton"),
        ("3trx", "3", "trx"),
        ("5bnb", "5", "bnb"),
        ("5 kas", "5", "kas"),
        ("5 wif", "5", "wif"),
    ],
)
def test_unit_that_does_not_read_as_a_multiplier_stays_a_unit(
    text: str, value: str, unit: str
) -> None:
    reading = recognised(text)

    assert format(reading.value, "f") == value
    assert reading.unit == unit


@pytest.mark.parametrize("text", ["3k万", "3kw刀", "1k5", "3w5", "k", "w", "万", "$k"])
def test_multiplier_out_of_place_never_yields_a_number(text: str) -> None:
    assert not isinstance(read_number(text), Recognised)


# --- numbers said in Chinese number words -----------------------------------


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("九万四千九", "94900"),
        ("两万三", "23000"),
        ("三千五", "3500"),
        ("一百二", "120"),
        ("两千零五", "2005"),
        ("十二", "12"),
        ("五千", "5000"),
        ("零", "0"),
        ("一", "1"),
        ("两", "2"),
        ("九", "9"),
        ("十", "10"),
        ("十一", "11"),
        ("一十二", "12"),
        ("二十", "20"),
        ("二十三", "23"),
        ("九十九", "99"),
        ("一百", "100"),
        ("二百", "200"),
        ("两百", "200"),
        ("一百零五", "105"),
        ("一百一十", "110"),
        ("一百二十三", "123"),
        ("三百零五", "305"),
        ("三百五十", "350"),
        ("一千", "1000"),
        ("一千零一十", "1010"),
        ("一千零五十", "1050"),
        ("两千零五十", "2050"),
        ("两千两百", "2200"),
        ("九千九百九十九", "9999"),
        ("一万", "10000"),
        ("一万零五", "10005"),
        ("一万零五百", "10500"),
        ("一万五千", "15000"),
        ("九万四千九百", "94900"),
        ("十万", "100000"),
        ("十二万三千", "123000"),
        ("二十万", "200000"),
        ("一百万", "1000000"),
        ("一百万五千", "1005000"),
        ("一百万零五千", "1005000"),
        ("一百零五万", "1050000"),
        ("一百二十万", "1200000"),
        ("两千万", "20000000"),
        ("三千五百万", "35000000"),
        ("一亿", "100000000"),
        ("一亿五千万", "150000000"),
        ("一亿零五千", "100005000"),
        ("十亿", "1000000000"),
        ("一万亿", "1000000000000"),
        ("一万二千亿", "1200000000000"),
        ("两 万 三", "23000"),
    ],
)
def test_number_said_in_chinese_number_words_is_read(text: str, value: str) -> None:
    reading = recognised(text)

    assert format(reading.value, "f") == value
    assert reading.unit is None
    assert reading.cautions == ()


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("三百五", "350"),
        ("一百一", "110"),
        ("一千一", "1100"),
        ("两千五", "2500"),
        ("一万五", "15000"),
        ("三万五千二", "35200"),
        ("十万五", "105000"),
        ("二十万五", "205000"),
        ("一百二十万五", "1205000"),
        ("十亿五", "1050000000"),
        ("十二万三", "123000"),
        ("三十五万六", "356000"),
        ("一亿五", "150000000"),
    ],
)
def test_last_digit_without_a_unit_takes_the_unit_just_below_the_one_before_it(
    text: str, value: str
) -> None:
    assert written(text) == value


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("零点五", "0.5"),
        ("零点零五", "0.05"),
        ("三点一四", "3.14"),
        ("两点五", "2.5"),
        ("十二点五", "12.5"),
        ("一百二十点五", "120.5"),
        ("零点五零", "0.50"),
        ("一点五亿", "150000000"),
        ("二点五千万", "25000000"),
        ("一点二五万", "12500"),
    ],
)
def test_number_said_with_a_decimal_point_is_read(text: str, value: str) -> None:
    assert written(text) == value


@pytest.mark.parametrize(
    ("text", "value", "unit"),
    [
        ("五千个", "5000", "个"),
        ("两万三刀", "23000", "刀"),
        ("一百美金", "100", "美金"),
        ("十个", "10", "个"),
        ("两个", "2", "个"),
        ("零点五个", "0.5", "个"),
        ("三千块", "3000", "块"),
        ("九万四千九 USDT", "94900", "USDT"),
        ("两万三u", "23000", "u"),
    ],
)
def test_number_said_in_chinese_number_words_may_carry_a_unit(
    text: str, value: str, unit: str
) -> None:
    reading = recognised(text)

    assert format(reading.value, "f") == value
    assert reading.unit == unit


@pytest.mark.parametrize(
    "text",
    [
        # Two digits side by side: "two or three thousand", or digits read out one by one.
        "两三千",
        "一二三",
        "七八",
        # 两 belongs before 百, 千, 万 or 亿, or stands alone; elsewhere it may be the weight.
        "三两",
        "十两",
        "两十",
        "三万两",
        # A place is skipped without 零, so the digit could belong to either place.
        "一千五十",
        "两万三百",
        "一亿五千",
        # 零 where nothing is skipped, or with nothing after it.
        "三千零五百",
        "二十零五",
        "二十零",
        "零五",
        "两千零零五",
        # A shortened ending in the middle of the number.
        "三千五万",
        # After 百万 or 千万 the last digit could count thousands or the unit below those.
        "一百万五",
        "三千万五",
        "两千五百万三",
        "一百亿五",
        # Units with nothing to count, or out of order.
        "万",
        "千",
        "百万",
        "千万",
        "万一",
        "一百十二",
        "三百五千",
        "一万二万",
        "一亿二亿",
        "一万万",
        "一亿亿",
        "万三",
        "万五千",
        "亿五",
        "亿三千万",
        # A point with nothing, or with units, on one side: this is how clock times are said.
        "点五",
        "五点",
        "九点四十",
        "零点",
        "一点两",
        # A shortened ending before the point.
        "两万三点五",
        "一百二点五",
        # A multiplier this short is not said after a decimal.
        "一点五百",
        "一点五十",
    ],
)
def test_number_words_without_a_single_reading_are_not_guessed(text: str) -> None:
    assert read_number(text) == Unsure(Doubt.UNCLEAR_WORDING)


def test_letter_multiplier_after_number_words_is_not_guessed() -> None:
    assert read_number("五千k") == Unsure(Doubt.UNCLEAR_MULTIPLIER)
    assert read_number("两w") == Unsure(Doubt.UNCLEAR_MULTIPLIER)


# --- digits and Chinese number words mixed ----------------------------------


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("9万4", "94000"),
        ("2万3", "23000"),
        ("一点二万", "12000"),
        ("9万4千", "94000"),
        ("9万4千9", "94900"),
        ("9万4千9百", "94900"),
        ("3千5", "3500"),
        ("3千5百", "3500"),
        ("5百", "500"),
        ("1百2", "120"),
        ("2千零5", "2005"),
        ("2万零5", "20005"),
        ("12万3", "123000"),
        ("12万3千", "123000"),
        ("50万3千", "503000"),
        ("120万3", "1203000"),
        ("120万零5百", "1200500"),
        ("9万4900", "94900"),
        ("9万4000", "94000"),
        ("1亿5千万", "150000000"),
        ("1亿5000万", "150000000"),
        ("9万四", "94000"),
        ("两万3", "23000"),
        ("9 万 4", "94000"),
        ("8 万 5", "85000"),
        ("12千", "12000"),
        ("９万４", "94000"),
    ],
)
def test_digits_mixed_with_chinese_number_words_are_read(text: str, value: str) -> None:
    reading = recognised(text)

    assert format(reading.value, "f") == value
    assert reading.unit is None


@pytest.mark.parametrize(
    ("text", "value", "unit"),
    [("9万4刀", "94000", "刀"), ("2万3 USDT", "23000", "USDT"), ("$9万4", "94000", "$")],
)
def test_mixed_number_may_carry_a_unit(text: str, value: str, unit: str) -> None:
    reading = recognised(text)

    assert format(reading.value, "f") == value
    assert reading.unit == unit


@pytest.mark.parametrize(
    "text",
    [
        # Is 9万49 ninety thousand and forty-nine, or ninety-four thousand nine hundred?
        "9万49",
        "9万490",
        "9万40",
        "9万05",
        "9万0400",
        "2万05",
        "1亿500万",
        "1亿5千",
        "1亿5000",
        "100万3",
        "3千万5",
        # Several digits in front of a small unit.
        "50百",
        "12百5",
        "3千500",
        # A decimal or grouped number cannot be continued with more places.
        "8.5万3",
        "1,200万5",
        "9万4.5",
        # Digits around 点 are how a clock time is written.
        "3点5",
        "0点5",
        "1点2万",
        "9点40",
        "4万4万",
        "1.5百",
    ],
)
def test_mixed_wording_without_a_single_reading_is_not_guessed(text: str) -> None:
    assert read_number(text) == Unsure(Doubt.UNCLEAR_WORDING)


# --- more digits than the ledger holds --------------------------------------

EIGHTEEN_PLACES = "0.123456789012345678"
NINETEEN_PLACES = "0.1234567890123456789"
FORTY_DIGITS = "1234567890" * 4


@pytest.mark.parametrize(
    "text",
    [
        NINETEEN_PLACES,
        "1.0000000000000000000",
        "0.0000000000000000001",
        NINETEEN_PLACES + " BTC",
        "$" + NINETEEN_PLACES,
        "0." + "0" * 199 + "1",
        "0." + "0" * 17 + "12345k",
    ],
)
def test_more_decimal_places_than_the_ledger_holds_are_not_rounded_away(text: str) -> None:
    assert read_number(text) == Unsure(Doubt.TOO_MANY_DECIMAL_PLACES)


@pytest.mark.parametrize(
    "text",
    [
        FORTY_DIGITS + "1",
        "9" * 23 + "." + "9" * 18,
        "1" * 200,
        "1" * 200 + "k",
        FORTY_DIGITS[:37] + "万",
        FORTY_DIGITS + "k",
        "1" * 30 + "." + "1" * 30,
    ],
)
def test_more_digits_than_the_ledger_holds_are_not_cut_off(text: str) -> None:
    assert read_number(text) == Unsure(Doubt.TOO_MANY_DIGITS)


@pytest.mark.parametrize(
    "text",
    [
        EIGHTEEN_PLACES,
        "0.000000000000000001",
        FORTY_DIGITS,
        "9" * 22 + "." + "9" * 18,
    ],
)
def test_number_right_at_the_ledger_s_digit_limits_is_read_in_full(text: str) -> None:
    assert written(text) == text


@pytest.mark.parametrize(
    ("text", "value"),
    [
        # Nineteen places as written, fifteen once multiplied.
        (NINETEEN_PLACES + "万", "1234.567890123456789"),
        ("0.0000000000000000015k", "0.0000000000000015"),
        (FORTY_DIGITS[:36] + "万", FORTY_DIGITS[:36] + "0000"),
    ],
)
def test_digit_limits_apply_to_the_number_after_its_multiplier(text: str, value: str) -> None:
    assert written(text) == value


# --- ranges, approximate amounts, halves and shares -------------------------


@pytest.mark.parametrize(
    "text",
    [
        "8 万到 8 万 5",
        "8万到8万5",
        "8万-8万5",
        "100~200",
        "100-200",
        "100\N{EN DASH}200",
        "100\N{EM DASH}200",
        "１００～２００",
        "2到3个",
        "100u-200u",
        "0.5至1",
        "2 to 3",
        "九万到十万",
        "8万刀到9万刀",
        "$100-$200",
    ],
)
def test_range_is_not_one_number(text: str) -> None:
    assert read_number(text) == Unsure(Doubt.RANGE)


@pytest.mark.parametrize(
    "text",
    [
        "大概两万",
        "大约50",
        "约50",
        "差不多100",
        "两万左右",
        "两万上下",
        "两万多",
        "两万多刀",
        "三千来块",
        "十几个",
        "几千",
        "几个",
        "一些",
        "一百出头",
        "不到100",
        "100以上",
        "100+",
        "~100",
        "\N{ALMOST EQUAL TO}100",
        "<100",
        "about 50",
        "around 2k",
        "50 or so",
        "50ish",
        "nearly 3 BTC",
        "2 ETH maybe",
        "5 or more",
        "5 at most",
        "100 USDT approx",
        "两万 左右",
    ],
)
def test_approximate_amount_is_not_an_exact_number(text: str) -> None:
    assert read_number(text) == Unsure(Doubt.APPROXIMATE)


@pytest.mark.parametrize(
    "text",
    [
        "半个",
        "一半",
        "两个半",
        "一个半",
        "半",
        "半仓",
        "30%",
        "0.1%",
        "５０％",
        "50 percent",
        "50pct",
        "三成",
        "3倍",
        "8折",
        "1/2",
        "三分之一",
        "一部分",
    ],
)
def test_half_share_or_multiple_is_not_a_plain_amount(text: str) -> None:
    assert read_number(text) == Unsure(Doubt.HALF_OR_SHARE)


def test_doubt_about_the_number_itself_is_reported_before_doubt_about_its_wording() -> None:
    assert read_number("十点半") == Unsure(Doubt.UNCLEAR_WORDING)
    assert read_number("1,5左右") == Unsure(Doubt.AMBIGUOUS_SEPARATOR)


@pytest.mark.parametrize("text", ["5m BTC", "5 million dollars", "2 k usdt", "1k5", "3k万"])
def test_stray_magnitude_word_is_named_as_the_reason(text: str) -> None:
    assert read_number(text) == Unsure(Doubt.UNCLEAR_MULTIPLIER)


@pytest.mark.parametrize("text", ["很多", "好多", "多少", "大概", "左右", "about", "~", "to", "k"])
def test_vague_word_without_any_number_is_not_a_number(text: str) -> None:
    assert read_number(text) == NotANumber()


@pytest.mark.parametrize(
    ("text", "unit"),
    [("2ton", "ton"), ("3 atom", "atom"), ("5 dot", "dot"), ("8万成交", "成交")],
)
def test_unit_that_only_resembles_a_vague_word_stays_a_unit(text: str, unit: str) -> None:
    assert recognised(text).unit == unit


# --- units that would change the number -------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        # A multiplier letter written into the unit, next to other characters.
        "3个w",
        "三个w",
        "3 个w",
        "两个w",
        "九个w",
        "1.5个w",
        "3个k",
        "3个W",
        "３个ｗ",
        "3个w刀",
        "3个w U",
        "3 个k刀",
        "3 w刀",
        "3 W刀",
        "3 k刀",
        "3刀k",
        "3个w币",
        "三个k刀",
        "3个m",
        "3个b",
        "3个t",
        "$3 w",
        # A multiplier letter glued to the front of a currency word or a coin.
        "3 wu",
        "3 WU",
        "3 ku",
        "3个wu",
        "3个ku",
        "5 kusdt",
        "5 wUSDT",
        "5 kusd",
        "2 kbtc",
        "2 wbtc",
        "5 weth",
        "5 个 kU",
        # Any other single letter: letters are how multipliers and small units are abbreviated.
        "5g",
        "5 G",
        "5x",
        "5e",
        "5E",
        "5c",
        "5 p",
        "5 个 x",
        "5\N{CYRILLIC SMALL LETTER KA}",
    ],
)
def test_multiplier_letter_inside_a_unit_is_never_handed_back_as_a_unit(text: str) -> None:
    # "3个w" handed back as three with the unit "个w" would turn thirty thousand into three.
    assert read_number(text) == Unsure(Doubt.UNCLEAR_MULTIPLIER)


@pytest.mark.parametrize(
    "text",
    [
        # More than one of a magnitude word.
        "2 thousands",
        "2 THOUSANDS",
        "2 thousands DOGE",
        "5 millions",
        "5 millions PEPE",
        "3 hundreds",
        "5 grands",
        "5 dozens",
        "5 billions",
        "3 trillions",
        "2thousands",
        "5millions",
        "5 ks",
        "3 ws",
        "2 mils",
        "2 thousands of dollars",
        # Short forms of magnitude words, and the same words in other languages.
        "5 mln",
        "5mln",
        "5 MLN",
        "2 bln",
        "2bln刀",
        "5 mill",
        "5 mio",
        "5 mia",
        "5 Mrd",
        "5 milliard",
        "5 tsd",
        "2 thou",
        "2 bil",
        "2 trn",
        "5 tril",
        "5 kilo",
        "5 kilos",
        "5 mega",
        "3 lakh",
        "3 lakhs",
        "3 lac",
        "3 crore",
        "3 crores",
        # The Chinese multipliers spelled in Latin letters.
        "3 wan",
        "3个wan",
        "3 个 wan",
        "3 WAN",
        "3 yi",
        "5 qian",
        "2 bai",
        # The same in everyday shorthand and in a few other languages.
        "5 doz",
        "5 hundos",
        "5 pairs",
        "5 pair",
        "5 ezer",
        "5 millió",
        "5 millio",
        "5 milliárd",
        "5 mille",
        "5 mila",
        "5 тыс",
        "5 млн",
        "5 млрд",
        # A magnitude letter or word glued to the front of a currency word.
        "3 mu",
        "3 mU",
        "3 musdt",
        "3 musd",
        "3 bU",
        "5 kiloUSDT",
        "5 megausdt",
        "3 mlnusdt",
        "3个mu",
        # A magnitude word glued to the front of a coin.
        "5 kilobtc",
        "5 megaeth",
        "2 kdoge",
        # With more around it than one unit.
        "$5 mln",
        "5 mln usdt in cash",
        "2 thousands usdt in cash",
    ],
)
def test_magnitude_word_in_any_common_form_is_never_handed_back_as_a_unit(text: str) -> None:
    assert read_number(text) == Unsure(Doubt.UNCLEAR_MULTIPLIER)


@pytest.mark.parametrize(
    "text",
    [
        # The small units of the yuan.
        "5毛",
        "五毛",
        "两毛",
        "5 毛",
        "5毛钱",
        "5角",
        "5角钱",
        "5分",
        "五分",
        "5分钱",
        "5厘",
        "十分",
        "5w毛",
        # An amount that runs on past its unit: three yuan and a half, not three.
        "三块五",
        "3块5",
        "5块3",
        "3块5毛",
        "三块五毛",
        "两毛五",
        "3元5角",
        "1元5",
        "十块零五毛",
        "3刀5",
        "三刀五",
        # The small units of other money, and of coins.
        "50 cents",
        "50 cent",
        "50cents",
        "50 CENTS",
        "5 pence",
        "5 penny",
        "5 pennies",
        "100 sats",
        "100 sat",
        "100sats",
        "100 sats BTC",
        "5000 satoshis",
        "1 satoshi",
        "5 gwei",
        "5 Gwei",
        "100 wei",
        "3 lamports",
        "5 mao",
        "5 jiao",
        "5 fen",
        "$5 cents",
        "50 cents for each one",
    ],
)
def test_amount_in_a_smaller_unit_of_money_is_never_handed_back_as_that_many_whole_units(
    text: str,
) -> None:
    # "5毛" handed back as five with the unit "毛" would turn half a yuan into five.
    assert read_number(text) == Unsure(Doubt.SMALLER_UNIT)


@pytest.mark.parametrize(
    "text",
    ["5毫", "5 仙", "5 finney", "5 szabo", "5 bits", "5 centavos", "5 centimes", "5 kopeks"],
)
def test_small_units_of_other_money_and_of_coins_are_doubted_too(text: str) -> None:
    assert read_number(text) == Unsure(Doubt.SMALLER_UNIT)


@pytest.mark.parametrize(
    "text",
    ["3打", "三打", "3 打", "3打币", "5双", "5 双", "5对", "5 对", "3 个 打", "3 u 打", "3 U 双"],
)
def test_dozen_or_pair_said_in_chinese_is_a_multiplier_too(text: str) -> None:
    assert read_number(text) == Unsure(Doubt.UNCLEAR_MULTIPLIER)


@pytest.mark.parametrize(
    "text",
    [
        "5 thousandths",
        "5 hundredths",
        "5 tenths",
        "5 halves",
        "5 quarters",
        "5 thirds",
        "5 milli",
        "5 micro",
        "5 nano",
        "3 times",
        "3 fold",
        "5 bp",
        "5 bps",
        "5bps",
        "25 bips",
    ],
)
def test_word_for_a_fraction_or_a_multiple_is_never_handed_back_as_a_unit(text: str) -> None:
    assert read_number(text) == Unsure(Doubt.HALF_OR_SHARE)


@pytest.mark.parametrize(
    ("text", "value", "unit"),
    [
        ("50u", "50", "u"),
        ("50 U", "50", "U"),
        ("5块钱", "5", "块钱"),
        ("五块", "5", "块"),
        ("5刀", "5", "刀"),
        ("1手", "1", "手"),
        ("5 coins", "5", "coins"),
        ("5 units", "5", "units"),
        ("5 bucks", "5", "bucks"),
        ("5 waves", "5", "waves"),
        ("5 kava", "5", "kava"),
        ("5 wax", "5", "wax"),
        ("5 tether", "5", "tether"),
        ("5 milk", "5", "milk"),
        ("3 gas", "3", "gas"),
        ("2 tokens", "2", "tokens"),
        ("3个u", "3", "个u"),
        ("3 个 U", "3", "个 U"),
        ("3w u", "30000", "u"),
        ("3w刀", "30000", "刀"),
        ("5K USDT", "5000", "USDT"),
        ("5k usdt", "5000", "usdt"),
        ("5 kas", "5", "kas"),
        ("5 wif", "5", "wif"),
        ("5 wld", "5", "wld"),
        ("5 ksm", "5", "ksm"),
        ("3 doge", "3", "doge"),
        ("3个币", "3", "个币"),
        ("3个BTC", "3", "个BTC"),
        ("100块", "100", "块"),
        ("100元", "100", "元"),
        ("3枚", "3", "枚"),
        ("5 USDC", "5", "USDC"),
        ("0.5 eth", "0.5", "eth"),
        ("5 op", "5", "op"),
    ],
)
def test_unit_with_nothing_in_it_that_changes_the_number_is_still_handed_back(
    text: str, value: str, unit: str
) -> None:
    reading = recognised(text)

    assert format(reading.value, "f") == value
    assert reading.unit == unit


MAGNITUDE_WORDS_IN_MANY_FORMS = [
    *("k", "K", "w", "W", "m", "M", "b", "B", "t", "g", "kk", "kw", "mm", "bn", "mn"),
    *("mil", "mill", "mln", "MLN", "mio", "mrd", "bln", "tsd", "wan", "WAN", "yi", "qian"),
    *("hundred", "hundreds", "thousand", "thousands", "Thousand", "million", "millions"),
    *("billion", "billions", "trillion", "grand", "grands", "dozen", "dozens", "lakh", "crore"),
]

PLACES_FOR_A_WORD_AWAY_FROM_THE_DIGITS = [
    "3 {}",
    "3个{}",
    "3 个{}",
    "3 个 {}",
    "三个{}",
    "两个{}",
    "1.5个{}",
    "３个{}",
    "3 {}刀",
    "3个{}刀",
    "3 {} USDT",
    "3 USDT {}",
    "3个{} U",
    "3刀{}",
    "3 {} 个",
    "$3 {}",
]

PLACES_FOR_A_WORD_RIGHT_AFTER_THE_DIGITS = ["3{}", "3{}刀", "3{} USDT", "3{}个", "$3{}"]

SMALLER_UNITS_IN_MANY_FORMS = [
    *("毛", "角", "分", "厘", "毫", "仙", "毛钱", "分钱"),
    *("cent", "cents", "Cents", "pence", "sat", "sats", "SATS", "satoshi", "satoshis"),
    *("gwei", "wei", "lamports", "mao", "fen"),
]

PLACES_FOR_A_SMALLER_UNIT = [
    "5{}",
    "5 {}",
    "五{}",
    "$5 {}",
    "5 {} BTC",
    "5 BTC {}",
    "5k{}",
    "5 个{}",
]


@pytest.mark.parametrize("place", PLACES_FOR_A_WORD_AWAY_FROM_THE_DIGITS)
@pytest.mark.parametrize("word", MAGNITUDE_WORDS_IN_MANY_FORMS)
def test_magnitude_word_anywhere_in_a_unit_never_yields_a_number(word: str, place: str) -> None:
    assert not isinstance(read_number(place.format(word)), Recognised)


@pytest.mark.parametrize("place", PLACES_FOR_A_WORD_RIGHT_AFTER_THE_DIGITS)
@pytest.mark.parametrize("word", MAGNITUDE_WORDS_IN_MANY_FORMS)
def test_magnitude_word_right_after_the_digits_is_applied_or_doubted_never_dropped(
    word: str, place: str
) -> None:
    reading = read_number(place.format(word))

    assert not (isinstance(reading, Recognised) and reading.value == 3)


def test_only_k_and_w_right_after_the_digits_are_applied() -> None:
    applied = {
        word: recognised(f"3{word}").value
        for word in MAGNITUDE_WORDS_IN_MANY_FORMS
        if isinstance(read_number(f"3{word}"), Recognised)
    }

    assert applied == {"k": 3000, "K": 3000, "w": 30000, "W": 30000}


@pytest.mark.parametrize("place", PLACES_FOR_A_SMALLER_UNIT)
@pytest.mark.parametrize("unit", SMALLER_UNITS_IN_MANY_FORMS)
def test_smaller_unit_anywhere_in_a_unit_never_yields_a_number(unit: str, place: str) -> None:
    assert not isinstance(read_number(place.format(unit)), Recognised)


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


# --- writing a number for the ledger ----------------------------------------

LEDGER_NUMBER = re.compile(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?")


def is_written_as_the_ledger_requires(text: str) -> bool:
    """The ledger's rule for a number, restated here independently of the code under test.

    Digits and at most one point; no exponent and no sign; no needless zero in
    front; at most 18 digits after the point and 40 significant digits, where
    zeros at the end count as significant.
    """
    if LEDGER_NUMBER.fullmatch(text) is None:
        return False
    whole, _, fraction = text.partition(".")
    significant = len((whole + fraction).lstrip("0")) or 1
    return len(fraction) <= 18 and significant <= 40


@pytest.mark.parametrize(
    "text",
    ["0", "7", "94900", "0.02", "1898.50", "0.000000033", "9" * 40, "0." + "0" * 17 + "1"],
)
def test_the_rule_used_to_judge_written_numbers_accepts_what_the_ledger_accepts(text: str) -> None:
    assert is_written_as_the_ledger_requires(text)


@pytest.mark.parametrize(
    "text",
    [
        "1e3",
        "1E+3",
        "3.3E-8",
        "007",
        "00.5",
        ".5",
        "5.",
        "-5",
        "-0",
        "+5",
        "1,000",
        " 5",
        "5 ",
        "",
        "NaN",
        "Infinity",
        "５",
        "0." + "0" * 18 + "1",
        "9" * 41,
    ],
)
def test_the_rule_used_to_judge_written_numbers_refuses_what_the_ledger_refuses(text: str) -> None:
    assert not is_written_as_the_ledger_requires(text)


VALUES_THE_LEDGER_CAN_HOLD = [
    # whole numbers
    "0",
    "1",
    "7",
    "10",
    "94900",
    "1000000",
    # decimals
    "0.02",
    "0.5",
    "1898.5",
    "123456789.123456789",
    # zeros at the end
    "1898.50",
    "0.020",
    "100.000",
    "1.0",
    "0.0",
    # very large
    "1234567890" * 4,
    "9" * 22 + "." + "9" * 18,
    "1E+39",
    # very small
    "0.000000033",
    "3.3E-8",
    "1E-7",
    "1E-18",
    "0.000000000000000001",
    # held with an exponent inside
    "1E+3",
    "1.5E+4",
    "0E-7",
    "0E+3",
    # zero with a sign
    "-0",
    "-0.00",
]


@pytest.mark.parametrize("value", VALUES_THE_LEDGER_CAN_HOLD)
def test_written_number_has_the_form_the_ledger_requires(value: str) -> None:
    assert is_written_as_the_ledger_requires(write_number(Decimal(value)))


@pytest.mark.parametrize("value", VALUES_THE_LEDGER_CAN_HOLD)
def test_written_number_reads_back_as_the_same_value(value: str) -> None:
    text = write_number(Decimal(value))

    assert Decimal(text) == Decimal(value)
    assert recognised(text).value == Decimal(value)
    assert recognised(text).unit is None


@pytest.mark.parametrize("value", VALUES_THE_LEDGER_CAN_HOLD)
def test_writing_what_was_read_back_gives_the_same_text(value: str) -> None:
    text = write_number(Decimal(value))

    assert write_number(recognised(text).value) == text


@pytest.mark.parametrize(
    ("value", "text"),
    [
        ("94900", "94900"),
        ("0.02", "0.02"),
        ("1898.50", "1898.50"),
        ("0.020", "0.020"),
        ("1E+3", "1000"),
        ("1.5E+4", "15000"),
        ("3.3E-8", "0.000000033"),
        ("1E-18", "0.000000000000000001"),
        ("0E-7", "0.0000000"),
        ("0E+3", "0"),
        ("-0", "0"),
        ("-0.00", "0.00"),
        ("1E+39", "1" + "0" * 39),
    ],
)
def test_number_is_written_in_plain_digits_with_its_zeros_kept(value: str, text: str) -> None:
    assert write_number(Decimal(value)) == text


def test_python_s_own_text_for_a_small_number_is_not_what_the_ledger_takes() -> None:
    small = Decimal("0.000000033")

    assert not is_written_as_the_ledger_requires(str(small))
    assert write_number(small) == "0.000000033"


@pytest.mark.parametrize(
    "value",
    [
        "NaN",
        "sNaN",
        "Infinity",
        "-Infinity",
        "-5",
        "-0.01",
        "0." + "0" * 18 + "1",
        "1." + "1" * 19,
        "9" * 41,
        "1E+40",
    ],
)
def test_number_the_ledger_cannot_hold_is_refused_instead_of_written(value: str) -> None:
    with pytest.raises(ValueError, match="ledger"):
        write_number(Decimal(value))


def test_writing_does_not_depend_on_the_decimal_context_of_the_caller() -> None:
    hostile = decimal.Context(prec=3, rounding=decimal.ROUND_DOWN)
    hostile.traps[decimal.Inexact] = True
    hostile.traps[decimal.Rounded] = True
    long_number = Decimal("9" * 22 + "." + "9" * 18)

    with decimal.localcontext(hostile):
        text = write_number(long_number)

    assert text == "9" * 22 + "." + "9" * 18


# --- promises that hold for every input -------------------------------------

EVERY_KIND_OF_INPUT = [
    "0.02",
    "94,900",
    "1,5",
    "94.900",
    "９４９００",
    "8万刀",
    "$50",
    "1.2k",
    "5m",
    "九万四千九",
    "两三千",
    "9万4",
    "一点二万",
    NINETEEN_PLACES,
    FORTY_DIGITS + "1",
    "8万到8万5",
    "大概两万",
    "半个",
    "NaN",
    "1e5",
    "-5",
    "",
    "很多",
]

TEXT_THAT_IS_NOT_AN_AMOUNT = [
    "\x00",
    "5\x00",
    "\ud83d",
    "5\udc00",
    "\N{GRINNING FACE}",
    "5\N{ROCKET}",
    "\N{RIGHT-TO-LEFT OVERRIDE}5",
    "5\N{COMBINING ACUTE ACCENT}",
    "e\N{COMBINING ACUTE ACCENT}5",
    "\N{ROMAN NUMERAL FOUR}",
    "\N{VULGAR FRACTION ONE HALF}",
    "5\N{VULGAR FRACTION ONE HALF}",
    "\N{HANGZHOU NUMERAL FIVE}",
    "\N{IDEOGRAPHIC NUMBER ZERO}",
    "\N{CJK UNIFIED IDEOGRAPH-58F9}万",
    "bought 0.02 BTC at 94,900 at 9:40, fee 2 USDT",
    "昨天晚上 9 点 40 买了 0.02 个比特币",
    "\n\n\n",
    "1\n2",
    "0b101",
    "0o17",
    "1__0",
    "1\N{ARABIC DECIMAL SEPARATOR}5",
    "1\N{ARABIC THOUSANDS SEPARATOR}000",
    "二〇二六",
    "..",
    ",,",
    "$,",
    "k万点",
    pytest.param("\x00" * 50 + "5", id="many null characters"),
    pytest.param("1" * 20_000, id="twenty thousand digits"),
    pytest.param("1" * 20_000 + "万", id="twenty thousand digits and a multiplier"),
    pytest.param("9," * 10_000 + "9", id="ten thousand commas"),
    pytest.param("万" * 20_000, id="twenty thousand units"),
    pytest.param("一" * 20_000, id="twenty thousand number words"),
    pytest.param("零点" + "零" * 20_000 + "一", id="twenty thousand decimal places said"),
    pytest.param("5" + "u" * 20_000, id="a unit twenty thousand letters long"),
    pytest.param("5 " * 10_000, id="ten thousand separate digits"),
    pytest.param("到" * 5_000 + "5", id="five thousand range words"),
    pytest.param("5" + "到" * 5_000 + "5", id="five thousand range words between digits"),
    pytest.param("$" * 5_000, id="five thousand currency signs"),
]


@pytest.mark.parametrize("text", EVERY_KIND_OF_INPUT)
def test_same_text_always_gives_the_same_reading(text: str) -> None:
    first = read_number(text)
    for other in EVERY_KIND_OF_INPUT:
        read_number(other)

    assert read_number(text) == first


@pytest.mark.parametrize("text", EVERY_KIND_OF_INPUT)
def test_reading_does_not_depend_on_the_decimal_context_of_the_caller(text: str) -> None:
    hostile = decimal.Context(prec=3, rounding=decimal.ROUND_DOWN)
    hostile.traps[decimal.Inexact] = True
    hostile.traps[decimal.Rounded] = True

    with decimal.localcontext(hostile):
        reading = read_number(text)

    assert reading == read_number(text)


def test_long_number_is_multiplied_exactly_whatever_the_context_of_the_caller() -> None:
    hostile = decimal.Context(prec=3, rounding=decimal.ROUND_DOWN)

    with decimal.localcontext(hostile):
        reading = read_number(FORTY_DIGITS[:36] + "." + "5万")

    assert reading == Recognised(Decimal(FORTY_DIGITS[:36] + "5000"))


def is_a_sound_reading(reading: object) -> bool:
    """Whether a reading is one of the three results, and a recognised value fits the ledger."""
    if isinstance(reading, Recognised):
        text = write_number(reading.value)
        return is_written_as_the_ledger_requires(text) and Decimal(text) == reading.value
    if isinstance(reading, Unsure):
        return isinstance(reading.reason, Doubt)
    return reading == NotANumber()


@pytest.mark.parametrize("text", [*EVERY_KIND_OF_INPUT, *TEXT_THAT_IS_NOT_AN_AMOUNT])
def test_no_text_makes_the_reader_raise(text: str) -> None:
    assert is_a_sound_reading(read_number(text))


@pytest.mark.parametrize("text", TEXT_THAT_IS_NOT_AN_AMOUNT)
def test_text_that_is_not_an_amount_never_becomes_a_number(text: str) -> None:
    assert not isinstance(read_number(text), Recognised)


def test_every_short_string_of_number_characters_gets_a_sound_reading() -> None:
    alphabet = "015., \N{IDEOGRAPHIC SPACE}万千十零两点kw$刀半-~e"
    texts = (
        "".join(letters)
        for size in (1, 2, 3)
        for letters in itertools.product(alphabet, repeat=size)
    )

    unsound = [text for text in texts if not is_a_sound_reading(read_number(text))]

    assert unsound == []


def test_recognised_number_survives_being_written_and_read_again() -> None:
    alphabet = "0159.,万千百十零一二两五点kw"
    texts = (
        "".join(letters)
        for size in (1, 2, 3, 4)
        for letters in itertools.product(alphabet, repeat=size)
    )
    changed = []
    for text in texts:
        reading = read_number(text)
        if isinstance(reading, Recognised):
            again = read_number(write_number(reading.value))
            if not isinstance(again, Recognised) or again.value != reading.value:
                changed.append(text)

    assert changed == []


# --- checked against an independent way of saying numbers -------------------

SAID_DIGITS = "零一二三四五六七八九"


def said_below_ten_thousand(number: int) -> str:
    """A number from 1 to 9999 the way it is properly said, 零 included."""
    words = ""
    skipped = False
    for size, unit in ((1000, "千"), (100, "百"), (10, "十"), (1, "")):
        digit, number = divmod(number, size)
        if digit == 0:
            skipped = bool(words)
            continue
        words += ("零" if skipped else "") + SAID_DIGITS[digit] + unit
        skipped = False
    return words


def said(number: int) -> str:
    """A whole number below a trillion the way it is properly said."""
    if number == 0:
        return "零"
    words = ""
    skipped = False
    sections = ((number // 10**8, "亿"), (number // 10**4 % 10**4, "万"), (number % 10**4, ""))
    for section, unit in sections:
        if section == 0:
            skipped = bool(words)
            continue
        needs_zero = bool(words) and (skipped or section < 1000)
        words += ("零" if needs_zero else "") + said_below_ten_thousand(section) + unit
        skipped = False
    return words.removeprefix("一") if words.startswith("一十") else words


def spread_of_whole_numbers() -> list[int]:
    """Every number up to 12000, and a fixed spread of larger ones of every length."""
    dice = random.Random(0)
    larger = [dice.randrange(10**size) for size in range(5, 13) for _ in range(1500)]
    rounder = [dice.randrange(1, 10**4) * 10 ** dice.randrange(1, 9) for _ in range(3000)]
    return [*range(12001), *larger, *rounder]


@pytest.mark.parametrize(
    ("number", "words"),
    [
        (0, "零"),
        (10, "十"),
        (12, "十二"),
        (110, "一百一十"),
        (2005, "二千零五"),
        (10500, "一万零五百"),
        (100500, "十万零五百"),
        (1005000, "一百万五千"),
        (100005000, "一亿零五千"),
        (150000000, "一亿五千万"),
        (999999999999, "九千九百九十九亿九千九百九十九万九千九百九十九"),
    ],
)
def test_the_independent_way_of_saying_numbers_says_them_properly(number: int, words: str) -> None:
    assert said(number) == words


def test_every_properly_said_whole_number_is_read_back_as_itself() -> None:
    misread = [
        number
        for number in spread_of_whole_numbers()
        if read_number(said(number)) != Recognised(Decimal(number))
    ]

    assert misread == []


def test_saying_two_as_liang_before_a_unit_changes_nothing() -> None:
    misread = []
    for number in spread_of_whole_numbers():
        words = re.sub(r"二(?=[百千万亿])", "两", said(number))
        if read_number(words) != Recognised(Decimal(number)):
            misread.append(number)

    assert misread == []


def test_dropping_the_last_unit_gives_the_same_number_or_a_doubt_never_another_number() -> None:
    wrong = []
    read = 0
    for number in spread_of_whole_numbers():
        words = said(number)
        if re.search(r"[百千万亿][一二三四五六七八九][十百千]$", words) is None:
            continue
        reading = read_number(words[:-1])
        if isinstance(reading, Recognised):
            read += 1
            if reading.value != number:
                wrong.append(number)
        elif not isinstance(reading, Unsure):
            wrong.append(number)

    assert wrong == []
    assert read > 100


def test_sections_written_in_digits_give_the_same_number_or_a_doubt() -> None:
    wrong = []
    read = 0
    for number in spread_of_whole_numbers():
        yi, wan, rest = number // 10**8, number // 10**4 % 10**4, number % 10**4
        if yi == 0 and wan == 0:
            continue
        # The last section is written with all four of its digits, as in "9万4900":
        # fewer would be the short form, where "1万1" is eleven thousand.
        text = (f"{yi}亿" if yi else "") + (f"{wan}万" if wan else "") + f"{rest:04d}" * bool(rest)
        reading = read_number(text)
        if isinstance(reading, Recognised):
            read += 1
            if reading.value != number:
                wrong.append(number)
        elif not isinstance(reading, Unsure):
            wrong.append(number)

    assert wrong == []
    assert read > 100


def test_whole_number_written_with_thousands_commas_is_read_back_as_itself() -> None:
    misread = [
        number
        for number in spread_of_whole_numbers()
        if read_number(f"{number:,}") != Recognised(Decimal(number))
    ]

    assert misread == []
