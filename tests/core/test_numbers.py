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
        "50 US dollars",
        "50u5",
        "50#",
        "50_",
        "50-",
        "u50",
        "美金50",
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
