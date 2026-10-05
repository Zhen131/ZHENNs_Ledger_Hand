"""Tests of reading a number the way people write or say it, and of writing one for the ledger.

Every amount here is invented. Each kind of wording has a section of its own.
"""

from __future__ import annotations

import decimal
import itertools
import random
import re
import sys
import time
import unicodedata
from decimal import Decimal

import pytest

from ledger_hand.core.coins import BUILT_IN_COINS, USDT_WORDS
from ledger_hand.core.numbers import (
    Caution,
    Doubt,
    NotANumber,
    Reading,
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


def in_another_form(text: str, capital_a: str, small_a: str) -> str:
    """``text`` with its ordinary letters replaced by those of an alphabet listed in order."""
    return "".join(
        chr(ord(capital_a) + ord(letter) - ord("A"))
        if "A" <= letter <= "Z"
        else chr(ord(small_a) + ord(letter) - ord("a"))
        if "a" <= letter <= "z"
        else letter
        for letter in text
    )


def in_bold(text: str) -> str:
    return in_another_form(text, "\N{MATHEMATICAL BOLD CAPITAL A}", "\N{MATHEMATICAL BOLD SMALL A}")


def in_sans_serif(text: str) -> str:
    return in_another_form(
        text, "\N{MATHEMATICAL SANS-SERIF CAPITAL A}", "\N{MATHEMATICAL SANS-SERIF SMALL A}"
    )


def in_monospace(text: str) -> str:
    return in_another_form(
        text, "\N{MATHEMATICAL MONOSPACE CAPITAL A}", "\N{MATHEMATICAL MONOSPACE SMALL A}"
    )


USDT_IN_SUPERSCRIPT = (
    "\N{MODIFIER LETTER CAPITAL U}\N{MODIFIER LETTER SMALL S}"
    "\N{MODIFIER LETTER CAPITAL D}\N{MODIFIER LETTER CAPITAL T}"
)


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
        ("0.02 个 BTC", "0.02", "个 BTC"),
        ("3个 比特币", "3", "个 比特币"),
        ("两万三 个 USDT", "23000", "个 USDT"),
        ("50$", "50", "$"),
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
    [("＄５０", "＄"), ("５０Ｕ", "Ｕ"), ("５０ｕｓｄｔ", "ｕｓｄｔ")],
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


# --- only units this program knows are handed back --------------------------

ONE_WORD_NAMES_OF_COINS = sorted(
    form
    for coin in BUILT_IN_COINS
    for form in (coin.symbol, coin.name, *coin.aliases)
    # A name of two words is two blocks, and 二饼 begins with a number word.
    if " " not in form and form != "二饼"
)

NAMES_OF_SEVERAL_WORDS = sorted(
    form
    for coin in BUILT_IN_COINS
    for form in (coin.symbol, coin.name, *coin.aliases)
    if " " in form
)

COUNTERS = ["个", "個", "枚", "颗", "顆", "coin", "coins", "token", "tokens"]


@pytest.mark.parametrize("word", sorted(USDT_WORDS))
def test_every_word_for_usdt_is_a_unit_this_program_knows(word: str) -> None:
    for written_as in (word, word.lower(), word.capitalize()):
        reading = recognised(f"5 {written_as}")

        assert reading.value == 5
        assert reading.unit == written_as


@pytest.mark.parametrize("name", ONE_WORD_NAMES_OF_COINS)
def test_every_one_word_name_of_a_built_in_coin_is_a_unit_this_program_knows(name: str) -> None:
    for written_as in (name, name.lower(), name.upper()):
        reading = recognised(f"5 {written_as}")

        assert reading.value == 5
        assert reading.unit == written_as


def test_the_built_in_table_has_names_of_several_words() -> None:
    assert "Bitcoin Cash" in NAMES_OF_SEVERAL_WORDS
    assert len(NAMES_OF_SEVERAL_WORDS) >= 5


@pytest.mark.parametrize("name", NAMES_OF_SEVERAL_WORDS)
def test_every_name_of_several_words_of_a_built_in_coin_is_a_unit_as_a_whole(name: str) -> None:
    for written_as in (name, name.lower(), name.upper()):
        reading = recognised(f"5 {written_as}")

        assert reading.value == 5
        assert reading.unit == written_as


@pytest.mark.parametrize(
    ("text", "value", "unit"),
    [
        ("5 Bitcoin Cash", "5", "Bitcoin Cash"),
        ("0.02 Ethereum Classic", "0.02", "Ethereum Classic"),
        ("5 NEAR Protocol", "5", "NEAR Protocol"),
        ("两万三 Shiba Inu", "23000", "Shiba Inu"),
        ("1.2k Bitcoin Cash", "1200", "Bitcoin Cash"),
        ("5Bitcoin Cash", "5", "Bitcoin Cash"),
        ("5 Bitcoin  Cash", "5", "Bitcoin  Cash"),
        (
            "5 Ｂｉｔｃｏｉｎ\N{IDEOGRAPHIC SPACE}Ｃａｓｈ",
            "5",
            "Ｂｉｔｃｏｉｎ\N{IDEOGRAPHIC SPACE}Ｃａｓｈ",
        ),
    ],
)
def test_name_of_several_words_is_handed_back_whole_and_as_written(
    text: str, value: str, unit: str
) -> None:
    reading = recognised(text)

    assert format(reading.value, "f") == value
    assert reading.unit == unit


@pytest.mark.parametrize(
    "text",
    [
        # Only part of a name, or a name with something added.
        "5 Cash",
        "5 Inu",
        "5 Classic",
        "5 Protocol",
        "5 Cash Bitcoin",
        "5 Bitcoin Cashs",
        "5 Bitcoin Cashk",
        "5 kBitcoin Cash",
        "5 Shiba Inus",
        "5 Ethereum Classics",
        "5 BitcoinCash",
        "0.5个Bitcoin Cash",
        "5 Bitcoin Cash个",
        # A known word and a word that is not known.
        "5 Bitcoin Gold",
        "5 Bitcoin SV",
        "5 Ethereum PoW",
        "5 Bitcoin Foo",
    ],
)
def test_part_of_a_name_or_a_known_word_with_an_unknown_one_is_not_a_known_unit(
    text: str,
) -> None:
    assert read_number(text) == Unsure(Doubt.UNKNOWN_UNIT)


@pytest.mark.parametrize("text", ["5 Bitcoin Cash coins", "5 个 Bitcoin Cash", "5 Shiba Inu USDT"])
def test_name_of_several_words_with_a_further_word_is_not_a_number(text: str) -> None:
    assert read_number(text) == NotANumber()


@pytest.mark.parametrize("counter", COUNTERS)
def test_every_counter_is_a_unit_this_program_knows(counter: str) -> None:
    assert recognised(f"5 {counter}").unit == counter
    assert recognised(f"0.5{counter}").value == Decimal("0.5")


@pytest.mark.parametrize(
    ("text", "value", "unit"),
    [
        ("0.02 个 BTC", "0.02", "个 BTC"),
        ("0.02个BTC", "0.02", "个BTC"),
        ("3个 比特币", "3", "个 比特币"),
        ("3枚ETH", "3", "枚ETH"),
        ("2个u", "2", "个u"),
        ("两万三 个 USDT", "23000", "个 USDT"),
        ("5 BTC USDT", "5", "BTC USDT"),
        ("5 tokens BTC", "5", "tokens BTC"),
        ("８万\N{IDEOGRAPHIC SPACE}刀", "80000", "刀"),
        ("5 ＢＴＣ", "5", "ＢＴＣ"),
        # Two known names side by side stay two blocks: they are not put
        # together and searched for a multiplier ("bn" in BNB, "shi" in SHIB).
        ("5 USDT BNB", "5", "USDT BNB"),
        ("5 BNB u", "5", "BNB u"),
        ("5 SHIB BTC", "5", "SHIB BTC"),
        ("两万三 Aave SHIB", "23000", "Aave SHIB"),
    ],
)
def test_unit_made_of_known_blocks_is_handed_back_as_written(
    text: str, value: str, unit: str
) -> None:
    reading = recognised(text)

    assert format(reading.value, "f") == value
    assert reading.unit == unit


@pytest.mark.parametrize(
    "text",
    [
        # Coins and tokens that are not in the built-in table.
        "500 BONK",
        "5 WIF",
        "5 kas",
        "50matic",
        "5 mSOL",
        "5 wstETH",
        "5 bbSOL",
        "5 BTCB",
        # Known words written together with something else, or in the plural.
        "5 BTCUSDT",
        "5 BTCs",
        "5 USDTs",
        "5 kBONK",
        "5个币",
        "5 个 BONK",
        # Other money, and words that are not money at all.
        "50 €",
        "¥700",
        "£5",
        "￥７００",
        "100块",
        "100元",
        "5块钱",
        "2 US dollars",
        "5 bucks",
        "5 units",
        "1手",
        "3张",
        "三天",
        "3号",
        "2026年",
        "两万吧",
        "两万都不止",
        "一下",
        "8万成交",
        "3个成交",
        "8万 成交",
        "5" + "X" * 32,
        # Names of things in which nothing looks like a multiplier.
        "5 wif",
        "5 wld",
        "5 ksm",
        "5 waves",
        "5 kava",
        "5 wax",
        "5 milk",
        "5 gigachad",
        "5 millennium",
        "5 bittensor",
        "5 centrifuge",
        "3 gas",
        "3 kg",
        "3 bitcoins",
        "3 btcs",
        "3个币",
        "五块",
        "三千块",
        "5 mETH",
        "5 tBTC",
        "5 bETH",
        "5mSOL",
        "5 SOLm",
        "5 ggAVAX",
        "5 UST",
        "5 GBP",
        "5 MNT",
        "5 GMT",
    ],
)
def test_unit_with_a_block_this_program_does_not_know_is_not_handed_back(text: str) -> None:
    assert read_number(text) == Unsure(Doubt.UNKNOWN_UNIT)


# --- Chinese characters written without gaps --------------------------------


@pytest.mark.parametrize(
    ("text", "value", "unit"),
    [
        ("3个比特币", "3", "个比特币"),
        ("0.5个以太坊", "0.5", "个以太坊"),
        ("100个狗狗币", "100", "个狗狗币"),
        ("两万三枚比特币", "23000", "枚比特币"),
        ("3千个比特币", "3000", "个比特币"),
        ("3 个比特币", "3", "个比特币"),
        ("5个刀", "5", "个刀"),
        ("5个美金", "5", "个美金"),
        # 以太 is a name too, and so is 比特币: the longer names are found all the same.
        ("3个以太币", "3", "个以太币"),
        ("0.5个比特币现金", "0.5", "个比特币现金"),
        ("0.5个比特现金", "0.5", "个比特现金"),
        ("2颗大饼", "2", "颗大饼"),
        ("0.5個以太坊", "0.5", "個以太坊"),
        ("0.5个以太坊ETH", "0.5", "个以太坊ETH"),
        ("2 BTC个比特币", "2", "BTC个比特币"),
    ],
)
def test_run_of_chinese_characters_made_of_known_words_is_a_known_unit(
    text: str, value: str, unit: str
) -> None:
    reading = recognised(text)

    assert format(reading.value, "f") == value
    assert reading.unit == unit


@pytest.mark.parametrize(
    "text",
    [
        # A character is left over at the end, at the start or in the middle.
        "3个比特",
        "3个比特币们",
        "3个比特币的",
        "3们个比特币",
        "3个的比特币",
        "5个比特币现",
        "3个以太坊币",
        "3个币",
        "3个比特币币",
        # A known word next to one that would change the number.
        "5个聪",
        "5个毛",
        "3个打比特币",
        "3个比特币对",
        "3双比特币",
        "5个比特币手",
        # Known words in letters are not put together the same way.
        "5 BTCUSDT",
        "5 个btcusdt",
    ],
)
def test_run_of_chinese_characters_with_a_character_left_over_is_not_a_known_unit(
    text: str,
) -> None:
    assert read_number(text) == Unsure(Doubt.UNKNOWN_UNIT)


@pytest.mark.parametrize(
    "text",
    [
        "3个亿",
        "3个万",
        "3个千比特币",
        "3个比特币万",
        "3个兆比特币",
        "3个比特币京",
        "3个萬比特币",
        "3个比特币两",
        "3个比特币仨",
        "0.5个二饼",
    ],
)
def test_run_of_chinese_characters_holding_a_number_character_is_never_cut(text: str) -> None:
    assert read_number(text) == NotANumber()


def test_word_the_caller_allows_counts_in_a_run_of_chinese_characters() -> None:
    assert read_number("500个邦克") == Unsure(Doubt.UNKNOWN_UNIT)
    assert recognised_with("500个邦克", "邦克") == Recognised(Decimal("500"), "个邦克")
    assert recognised_with("500枚邦克比特币", "邦克").unit == "枚邦克比特币"
    assert read_number("500个邦克们", extra_units=["邦克"]) == Unsure(Doubt.UNKNOWN_UNIT)
    assert read_number("500个邦", extra_units=["邦克"]) == Unsure(Doubt.UNKNOWN_UNIT)


def test_long_run_of_one_known_word_after_another_is_read_without_delay() -> None:
    assert recognised("5" + "个" * 32).unit == "个" * 32
    assert read_number("5" + "个" * 31 + "们", extra_units=["个个"]) == Unsure(Doubt.UNKNOWN_UNIT)


# --- letters that are not Chinese characters, whatever they look like --------

LETTERS_WRITTEN_TOGETHER_IN_A_FORM_OF_THEIR_OWN = [
    "5 " + in_bold("BTCUSDT"),
    "5 " + in_sans_serif("BTCETH"),
    "5 " + in_monospace("BTCUSDT"),
    "5 BTC" + USDT_IN_SUPERSCRIPT,
    "5 " + in_bold("UU"),
    "5 " + in_bold("TOKENU"),
    "5 OP\N{MODIFIER LETTER SMALL U}",
    "5coin" + in_bold("U"),
    "5 " + in_bold("BTC") + "USDT",
    "5 " + in_bold("u") + "u",
    "5 u" + in_bold("u"),
    "5 " + in_bold("BTC") + in_sans_serif("ETH"),
    "5 个" + in_bold("BTCUSDT"),
    "5 " + in_bold("Bitcoin") + "Cash",
    "5 BTC\N{FULLWIDTH LATIN CAPITAL LETTER U}",
    "5 u\N{LATIN SUBSCRIPT SMALL LETTER U}",
    "5 u\N{FEMININE ORDINAL INDICATOR}da",
]


@pytest.mark.parametrize("text", LETTERS_WRITTEN_TOGETHER_IN_A_FORM_OF_THEIR_OWN)
def test_known_words_run_together_are_no_unit_in_whatever_form_the_letters_are(text: str) -> None:
    assert read_number(text) == Unsure(Doubt.UNKNOWN_UNIT)
    # The same text in ordinary letters is turned away for the same reason.
    assert read_number(in_ordinary_characters(text)) == Unsure(Doubt.UNKNOWN_UNIT)


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("5 " + in_bold("BTC"), "5"),
        ("5 " + in_sans_serif("usdt"), "5"),
        ("5 " + USDT_IN_SUPERSCRIPT, "5"),
        ("5 \N{MODIFIER LETTER SMALL U}", "5"),
        ("5 个" + in_bold("BTC"), "5"),
        ("5 " + in_bold("BTC") + "个", "5"),
        ("5 " + in_bold("BTC") + " " + in_monospace("usdt"), "5"),
        ("5 " + in_bold("Bitcoin Cash"), "5"),
        ("5k " + in_bold("u"), "5000"),
        ("3w刀" + in_bold("u"), "30000"),
    ],
)
def test_known_word_in_a_form_of_its_own_is_read_like_the_ordinary_word(
    text: str, value: str
) -> None:
    reading = recognised(text)
    ordinary = recognised(in_ordinary_characters(text))

    assert format(reading.value, "f") == value == format(ordinary.value, "f")
    assert reading.unit == text.split(None, 1)[1] if " " in text else True
    assert in_ordinary_characters(reading.unit or "") == ordinary.unit


@pytest.mark.parametrize(
    "text",
    [
        "5k" + in_bold("u"),
        "5K" + in_bold("usdt"),
        "5w" + in_bold("BTC"),
        "5k" + USDT_IN_SUPERSCRIPT,
        "5k\N{MODIFIER LETTER SMALL U}个",
        "5w\N{FULLWIDTH LATIN SMALL LETTER U}",
    ],
)
def test_multiplier_letter_with_a_known_word_right_behind_it_in_another_form_is_a_doubt(
    text: str,
) -> None:
    assert read_number(text) == Unsure(Doubt.UNCLEAR_MULTIPLIER)
    assert read_number(in_ordinary_characters(text)) == Unsure(Doubt.UNCLEAR_MULTIPLIER)


@pytest.mark.parametrize(
    "text",
    [
        "5" + in_bold("k"),
        "5" + in_bold("w"),
        "5" + in_bold("K") + " USDT",
        "5\N{MODIFIER LETTER SMALL K}",
        "5\N{MODIFIER LETTER SMALL K}BTC",
        "5\N{KELVIN SIGN}",
        "5 " + in_bold("k"),
        "5 " + in_bold("k") + "BTC",
        "5 " + in_bold("BTC") + in_bold("k"),
        "5 " + in_bold("ks") + "BTC",
        "5 " + in_bold("m") + "BTC",
        "5 BTC\N{MODIFIER LETTER SMALL K}",
        "5 \N{CYRILLIC SMALL LETTER KA}BTC",
        "5 \N{GREEK SMALL LETTER KAPPA}BTC",
        "5\N{CYRILLIC SMALL LETTER KA}",
        "5k\N{CYRILLIC SMALL LETTER KA}",
        "5 个\N{CYRILLIC SMALL LETTER KA}",
    ],
)
def test_multiplier_letter_in_a_form_of_its_own_is_neither_applied_nor_a_unit(text: str) -> None:
    assert isinstance(read_number(text), Unsure)


RAISED_B_AND_T = "\N{MODIFIER LETTER CAPITAL B}\N{MODIFIER LETTER CAPITAL T}"


@pytest.mark.parametrize(
    "text",
    [
        f"5 u {RAISED_B_AND_T}C",
        f"5 {RAISED_B_AND_T}C u",
        f"5 个{RAISED_B_AND_T}C",
        f"5 {RAISED_B_AND_T}C个",
        "5 BT" + in_bold("C") + " u",
        "5 个" + in_bold("B") + "TC",
        "5 个" + in_bold("us") + "dt",
        "5 个\N{FEMININE ORDINAL INDICATOR}DA",
        "5 USDT \N{FEMININE ORDINAL INDICATOR}DA",
        # The whole unit is such a block.
        f"5 {RAISED_B_AND_T}C",
        f"5{RAISED_B_AND_T}C",
        "5 \N{FEMININE ORDINAL INDICATOR}DA",
        "5 BT" + in_bold("C"),
        "5 \N{DOUBLE-STRUCK CAPITAL C}OIN",
        "5 Bitcoin " + in_bold("C") + "ash",
    ],
)
def test_block_that_mixes_letters_with_and_without_capitals_is_no_known_word(text: str) -> None:
    assert read_number(text) == Unsure(Doubt.UNKNOWN_UNIT)


@pytest.mark.parametrize(
    "text",
    [
        "5 u " + in_bold("BTC"),
        "5 个" + in_bold("BTC"),
        "5 个\N{FULLWIDTH LATIN CAPITAL LETTER B}TC",
        "5 u \N{FULLWIDTH LATIN CAPITAL LETTER B}tc",
        "5 个" + USDT_IN_SUPERSCRIPT,
    ],
)
def test_block_in_one_kind_of_letters_is_read_like_the_ordinary_word(text: str) -> None:
    reading = recognised(text)
    ordinary = recognised(in_ordinary_characters(text))

    assert reading.value == ordinary.value == 5
    assert in_ordinary_characters(reading.unit or "") == ordinary.unit


def test_only_chinese_characters_are_cut_into_known_words_not_other_writing_without_gaps() -> None:
    doru = "\N{KATAKANA LETTER DO}\N{KATAKANA LETTER RU}"
    won = "\N{HANGUL SYLLABLE WEON}"
    ka = "\N{CYRILLIC SMALL LETTER KA}"

    # A word the caller allows is one block next to Chinese characters ...
    assert recognised_with(f"5個{doru}", doru) == Recognised(Decimal("5"), f"個{doru}")
    assert recognised_with(f"5 {won}个", won).unit == f"{won}个"
    # ... but a run of such words is not cut the way Chinese is.
    assert read_number(f"5 {doru}{doru}", extra_units=[doru]) == Unsure(Doubt.UNKNOWN_UNIT)
    assert read_number(f"5 {won}{won}", extra_units=[won]) == Unsure(Doubt.UNKNOWN_UNIT)
    assert read_number(f"5 {ka}{ka}", extra_units=[ka]) == Unsure(Doubt.UNKNOWN_UNIT)
    assert read_number(f"5 BTC{doru}", extra_units=[doru]) == Unsure(Doubt.UNKNOWN_UNIT)
    assert read_number("5 " + in_bold("uu"), extra_units=["u"]) == Unsure(Doubt.UNKNOWN_UNIT)
    assert recognised_with("5 邦克邦克", "邦克").unit == "邦克邦克"


def test_letters_in_another_alphabet_after_a_multiplier_letter_carry_on_the_word() -> None:
    ore = "\N{LATIN SMALL LETTER O WITH DIAERESIS}re"

    assert read_number(f"5k{ore}", extra_units=[ore]) == Unsure(Doubt.UNCLEAR_MULTIPLIER)
    assert read_number(f"5k{ore}", extra_units=[ore, f"k{ore}"]) == Unsure(Doubt.UNCLEAR_MULTIPLIER)
    assert recognised_with(f"5k{ore}", f"k{ore}") == Recognised(Decimal("5"), f"k{ore}")
    assert recognised_with(f"5k {ore}", ore) == Recognised(Decimal("5000"), ore)


@pytest.mark.parametrize(
    "character",
    [
        "\N{CJK COMPATIBILITY IDEOGRAPH-F978}",  # a copy of 兩
        "\N{CJK COMPATIBILITY IDEOGRAPH-F9B2}",  # a copy of 零
        "\N{CJK COMPATIBILITY IDEOGRAPH-F9D3}",  # a copy of 陸
        "\N{CJK COMPATIBILITY IDEOGRAPH-F96B}",  # a copy of 參
    ],
)
def test_copy_of_a_number_character_is_a_number_character(character: str) -> None:
    assert in_ordinary_characters(character) != character
    for text in (f"5 {character}", f"5{character}", f"3个{character}", f"5 BTC{character}"):
        assert read_number(text) == NotANumber()
        assert read_number(text, extra_units=[character]) == NotANumber()


def every_character_that_is_not_ordinary(*, letters: bool) -> list[str]:
    """Every character Unicode lists outside ASCII that is, or is not, a letter.

    Chinese characters are left out, and so are gaps and what has no meaning
    of its own (private use, surrogates, code points not given out).
    """
    return [
        character
        for character in map(chr, range(0x80, sys.maxunicode + 1))
        if character.isalpha() == letters
        and not character.isspace()
        and not is_an_ideograph(character)
        and unicodedata.category(character) not in {"Co", "Cs", "Cn"}
    ]


def is_read_like_the_same_text_in_ordinary_characters(text: str, reading: Reading) -> bool:
    """Whether ``text`` is either not recognised, or read just as its ordinary spelling is.

    A recognised unit must also be made of known words, by the rule of this file.
    """
    if not isinstance(reading, Recognised):
        return True
    ordinary = read_number(in_ordinary_characters(text))
    return (
        isinstance(ordinary, Recognised)
        and ordinary.value == reading.value
        and in_ordinary_characters(reading.unit or "") == (ordinary.unit or "")
        and (reading.unit is None or blocks_outside(reading.unit, frozenset()) == [])
    )


PLACES_FOR_A_LETTER_OF_ANY_WRITING = [
    "5 {}",
    "5{}",
    "5 BTC{}",
    "5 {}BTC",
    "5 个{}",
    "5 BTC {}",
    "5k{}",
    "5 {0}{0}",
]


def test_no_letter_of_any_writing_gets_a_unit_recognised_that_ordinary_letters_would_not() -> None:
    letters = every_character_that_is_not_ordinary(letters=True)
    wrong = []
    recognised_at_all = 0
    for letter in letters:
        # A letter that is already in its ordinary form can only make a word
        # no table knows; three places are enough for it.
        is_a_form_of_another = in_ordinary_characters(letter) != letter
        places = (
            PLACES_FOR_A_LETTER_OF_ANY_WRITING
            if is_a_form_of_another
            else ["5 {}", "5 BTC{}", "5k{}"]
        )
        for place in places:
            text = place.format(letter)
            reading = read_number(text)
            recognised_at_all += isinstance(reading, Recognised)
            if not is_read_like_the_same_text_in_ordinary_characters(text, reading):
                wrong.append(text)

    assert wrong == []
    # Mathematical, superscript and full-width forms of u, U and the like are read.
    assert recognised_at_all > 100
    assert len(letters) > 30_000


def test_no_mark_sign_or_unseen_character_gets_a_unit_recognised() -> None:
    others = every_character_that_is_not_ordinary(letters=False)
    wrong = []
    for character in others:
        for place in ("5 BTC{}", "5 {}BTC", "5 个{}", "5 u {}", "5 B{}TC", "5k{}"):
            text = place.format(character)
            if not is_read_like_the_same_text_in_ordinary_characters(text, read_number(text)):
                wrong.append(text)

    assert wrong == []
    assert "\N{ZERO WIDTH SPACE}" in others
    assert "\N{COMBINING ACUTE ACCENT}" in others
    assert "\N{CIRCLED LATIN SMALL LETTER K}" in others
    assert "\N{SMALL ROMAN NUMERAL ONE THOUSAND}" in others
    assert len(others) > 10_000


def test_only_a_chinese_character_is_cut_from_its_neighbour_when_the_caller_allows_it() -> None:
    # With a character allowed as a word, the same character twice is two
    # known words only where the writing is cut between them: in Chinese.
    cut = []
    chinese_left_whole = []
    others_left_whole = 0
    for character in map(chr, range(0x80, sys.maxunicode + 1)):
        if not character.isalpha():
            continue
        # One ideograph in sixteen, and every one at the edges of the block in use.
        if (
            is_an_ideograph(character)
            and ord(character) % 16
            and all(is_a_chinese_character(chr(ord(character) + step)) for step in (-1, 1))
        ):
            continue
        reading = read_number(f"5 {character}{character}", extra_units=[character])
        if isinstance(reading, Recognised):
            cut.append(character)
        elif is_a_chinese_character(character):
            chinese_left_whole.append((character, reading))
        else:
            others_left_whole += 1

    # Nothing is cut but the Chinese characters of the one block listed for them.
    assert [character for character in cut if not is_a_chinese_character(character)] == []
    # A Chinese character is cut unless it says a number, or makes the amount a vague one.
    assert [
        character
        for character, reading in chinese_left_whole
        if reading == Unsure(Doubt.UNKNOWN_UNIT)
    ] == []
    assert len(cut) > 1_000
    assert others_left_whole > 30_000


RARE_AND_COMPATIBILITY_IDEOGRAPHS = [
    "\N{CJK UNIFIED IDEOGRAPH-3400}",
    "\N{CJK UNIFIED IDEOGRAPH-4DBF}",
    "\N{CJK UNIFIED IDEOGRAPH-20000}",
    "\N{CJK UNIFIED IDEOGRAPH-2A6DF}",
    "\N{CJK UNIFIED IDEOGRAPH-2B740}",
    "\N{CJK UNIFIED IDEOGRAPH-30000}",
    "\N{CJK UNIFIED IDEOGRAPH-323AF}",
    "\N{CJK COMPATIBILITY IDEOGRAPH-F90A}",  # a copy of 金
    "\N{CJK COMPATIBILITY IDEOGRAPH-FA0E}",
    "\N{CJK COMPATIBILITY IDEOGRAPH-2F800}",
]


@pytest.mark.parametrize("character", RARE_AND_COMPATIBILITY_IDEOGRAPHS)
def test_rare_chinese_character_is_known_only_as_a_whole_unit(character: str) -> None:
    assert is_an_ideograph(character)
    assert not is_a_chinese_character(character)

    # Allowed by the caller, it is a unit when it is the whole unit ...
    assert recognised_with(f"5 {character}", character) == Recognised(Decimal("5"), character)
    assert recognised_with(f"5 {character}个", f"{character}个").unit == f"{character}个"
    # ... and neither a block next to others nor a word in a run of Chinese.
    for text in (
        f"5 个{character}",
        f"5 {character}个",
        f"5 {character}{character}",
        f"5 {character} BTC",
        f"5 BTC {character}",
        f"5 BTC{character}",
        f"5 个{character}个",
    ):
        assert read_number(text, extra_units=[character]) == Unsure(Doubt.UNKNOWN_UNIT)
    assert read_number(f"5k{character}", extra_units=[character]) != Recognised(
        Decimal("5"), f"k{character}"
    )


# --- units the caller allows for one call -----------------------------------


def test_coin_outside_the_table_is_read_only_when_the_caller_allows_its_name() -> None:
    assert read_number("500 BONK") == Unsure(Doubt.UNKNOWN_UNIT)
    assert read_number("5 kBONK") == Unsure(Doubt.UNKNOWN_UNIT)

    allowed = read_number("500 BONK", extra_units=("BONK",))

    assert allowed == Recognised(Decimal("500"), "BONK")
    assert read_number("5 kBONK", extra_units=("BONK",)) == Unsure(Doubt.UNKNOWN_UNIT)


@pytest.mark.parametrize(
    ("text", "extra"),
    [
        ("500 BONK", "bonk"),
        ("500 bonk", "BONK"),
        ("500 Bonk", " bonk "),
        ("500 ＢＯＮＫ", "BONK"),
        ("500 BONK", "ＢＯＮＫ"),
        ("500BONK", "BONK"),
        ("500 个 BONK", "BONK"),
        ("500个BONK", "BONK"),
        ("500 BONK USDT", "BONK"),
        ("三天", "天"),
    ],
)
def test_allowed_unit_is_matched_whatever_its_capitals_and_width(text: str, extra: str) -> None:
    reading = read_number(text, extra_units=[extra])

    assert isinstance(reading, Recognised)
    assert reading.value in (500, 3)


@pytest.mark.parametrize(
    "text",
    ["500 BONKS", "500 BONKk", "500 xBONK", "500 BON", "500 BONK币", "5 kBONK", "5 BONKUSDT"],
)
def test_allowed_unit_must_match_a_block_exactly(text: str) -> None:
    assert read_number(text, extra_units=("BONK",)) == Unsure(Doubt.UNKNOWN_UNIT)


def test_unit_allowed_for_one_call_is_not_remembered_for_the_next() -> None:
    read_number("500 BONK", extra_units=("BONK",))

    assert read_number("500 BONK") == Unsure(Doubt.UNKNOWN_UNIT)


def test_allowed_name_of_several_words_is_a_unit_as_a_whole() -> None:
    assert read_number("500 Baby Doge") == Unsure(Doubt.UNKNOWN_UNIT)

    assert recognised_with("500 Baby Doge", "Baby Doge") == Recognised(Decimal("500"), "Baby Doge")
    assert recognised_with("500 baby  doge", "BABY DOGE").unit == "baby  doge"
    assert recognised_with("500Baby Doge", "Baby Doge").unit == "Baby Doge"
    assert recognised_with("5k Baby Doge", "Baby Doge").value == 5000
    assert recognised_with("500 Book of Meme", "Book of Meme").unit == "Book of Meme"
    assert recognised_with("500 BONK币", "BONK币").unit == "BONK币"


@pytest.mark.parametrize(
    "text",
    [
        "500 Baby",
        "500 Doge Baby",
        "500 Baby Doges",
        "500 kBaby Doge",
        "500 BabyDoge",
        "500 个Baby Doge",
        "500 Book of",
        "500 of Meme",
    ],
)
def test_part_of_an_allowed_name_of_several_words_is_not_a_unit(text: str) -> None:
    extra_units = ["Baby Doge", "Book of Meme"]

    assert read_number(text, extra_units=extra_units) == Unsure(Doubt.UNKNOWN_UNIT)


@pytest.mark.parametrize(
    "text",
    ["500 Baby Doge coins", "500 个 Baby Doge", "500 Book of Memes", "500 Book of Meme coin"],
)
def test_more_than_two_words_that_are_not_one_allowed_name_are_not_a_number(text: str) -> None:
    extra_units = ["Baby Doge", "Book of Meme"]

    assert read_number(text, extra_units=extra_units) == NotANumber()


def test_allowed_name_that_starts_like_a_multiplier_is_read_when_nothing_else_fits() -> None:
    assert read_number("5Wrapped Bitcoin") == Unsure(Doubt.UNCLEAR_MULTIPLIER)

    allowed = recognised_with("5Wrapped Bitcoin", "Wrapped Bitcoin")

    assert allowed == Recognised(Decimal("5"), "Wrapped Bitcoin")
    # With "rapped Bitcoin" allowed as well, the w may be a multiplier.
    assert read_number(
        "5Wrapped Bitcoin", extra_units=["Wrapped Bitcoin", "rapped Bitcoin"]
    ) == Unsure(Doubt.UNCLEAR_MULTIPLIER)


@pytest.mark.parametrize(
    ("text", "extra"),
    [
        ("3兆", "兆"),
        ("3 京", "京"),
        ("3萬", "萬"),
        ("3个亿", "个亿"),
        ("3个 亿", "亿"),
        ("5 仨", "仨"),
        ("5块五", "块五"),
        ("0.5个 二饼", "二饼"),
        ("5 Baby 兆", "Baby 兆"),
        ("5 two 萬 coins", "two 萬 coins"),
    ],
)
def test_word_holding_a_number_character_is_no_unit_even_when_the_caller_allows_it(
    text: str, extra: str
) -> None:
    assert read_number(text, extra_units=[extra]) == NotANumber()


MULTIPLIERS_OF_THIS_PROGRAM_AS_A_CALLER_MIGHT_PASS_THEM = [
    "k",
    "K",
    "w",
    "W",
    " k ",
    "\N{FULLWIDTH LATIN SMALL LETTER K}",
    "\N{KELVIN SIGN}",
    "\N{MODIFIER LETTER SMALL K}",
    in_bold("k"),
    in_bold("W"),
    "k BONK",
    "BONK k",
    "个k",
    "w个",
    "千",
    "万",
    "十万",
    "亿",
    "个亿",
    "兩",
    "\N{CJK COMPATIBILITY IDEOGRAPH-F978}",
]


@pytest.mark.parametrize("word", MULTIPLIERS_OF_THIS_PROGRAM_AS_A_CALLER_MIGHT_PASS_THEM)
def test_multiplier_of_this_program_is_not_taken_from_a_caller_as_a_unit(word: str) -> None:
    plain = " ".join(in_ordinary_characters(word).split())
    texts = [
        f"5 {plain}",
        f"5{plain}",
        f"5 {word}",
        f"5 {plain} BTC",
        f"5 BTC {plain}",
        f"5 个{plain}",
        "5 k",
        "5 w",
        "5 K BTC",
        "5 BONK k",
        "5 k BONK",
        "5个万",
        "5 千",
        "5k",
        "3w",
        "500 BONK",
    ]

    for text in texts:
        assert read_number(text, extra_units=[word]) == read_number(text)
        assert read_number(text, extra_units=[word, "BONK"]) == read_number(
            text, extra_units=["BONK"]
        )


@pytest.mark.parametrize(
    "word",
    ["万", "千", "个亿", "ku万", "u万", "兩", "\N{CJK COMPATIBILITY IDEOGRAPH-F978}", "Baby 兆"],
)
def test_word_holding_a_number_character_is_as_good_as_not_passed(word: str) -> None:
    texts = [f"5 {word}", f"5{word}", f"5 个{word}", "5ku万", "5ku", "5 万", "5个万", "5 Baby 兆"]

    for text in texts:
        assert read_number(text, extra_units=[word]) == read_number(text)


@pytest.mark.parametrize(
    "letter",
    [
        "\N{GREEK YPOGEGRAMMENI}",
        "\N{ARABIC FATHA ISOLATED FORM}",
        "\N{ARABIC LIGATURE SHADDA WITH DAMMATAN ISOLATED FORM}",
        "\N{ARABIC LIGATURE SALLALLAHOU ALAYHE WASALLAM}",
    ],
)
def test_letter_that_comes_apart_into_gaps_and_marks_is_no_unit_even_when_allowed(
    letter: str,
) -> None:
    # In ordinary characters each of these is a gap and a mark, or several words.
    assert letter.isalpha()
    assert not in_ordinary_characters(letter).isalpha()

    for text in (f"5 {letter}", f"5 {letter}{letter}", f"5 个{letter}", f"5 {letter} BTC"):
        assert read_number(text, extra_units=[letter]) == Unsure(Doubt.UNKNOWN_UNIT)


def test_letter_that_comes_apart_is_no_unit_though_its_mark_is_a_letter_the_caller_allows() -> None:
    # The mark this one comes apart into is the small iota written under a
    # letter; in capitals it is the letter iota itself.
    iota = "\N{GREEK SMALL LETTER IOTA}"
    under = "\N{GREEK YPOGEGRAMMENI}"

    assert recognised_with(f"5 {iota}", iota) == Recognised(Decimal("5"), iota)
    for text in (f"5 {under}", f"5{under}", f"5 个{under}", f"5 {under} BTC", f"5 {under}{under}"):
        assert read_number(text, extra_units=[iota]) == Unsure(Doubt.UNKNOWN_UNIT)


@pytest.mark.parametrize(
    "name",
    [
        "",
        "   ",
        "USD.e",
        "BTC-PERP",
        "1000SATS",
        "u2",
        "BONK!",
        "\N{GREEK YPOGEGRAMMENI}",
        "\N{ARABIC FATHA ISOLATED FORM}",
        "BTC \N{GREEK YPOGEGRAMMENI}",
        "\N{COMBINING GREEK YPOGEGRAMMENI}",
        "\N{ZERO WIDTH SPACE}",
        "u\N{ZERO WIDTH SPACE}",
        "\N{CIRCLED LATIN SMALL LETTER U}",
    ],
)
def test_name_that_is_not_made_of_words_of_letters_is_not_taken_from_a_caller(name: str) -> None:
    iota = "\N{GREEK SMALL LETTER IOTA}"
    texts = [
        f"5 {name}",
        f"5{name}",
        f"5 个{name}",
        f"5 {iota}",
        f"5 {iota.upper()}",
        f"5 个{iota}",
        "5 USD",
        "5 USD e",
        "5 USDe",
        "5 u",
        "5 SATS",
        "5 BONK",
        "5 e",
        "5 2",
    ]

    for text in texts:
        assert read_number(text, extra_units=[name]) == read_number(text)


def test_currency_sign_is_taken_from_a_caller() -> None:
    assert read_number("\N{YEN SIGN}700") == Unsure(Doubt.UNKNOWN_UNIT)
    assert recognised_with("\N{YEN SIGN}700", "\N{YEN SIGN}") == Recognised(
        Decimal("700"), "\N{YEN SIGN}"
    )
    assert recognised_with("\N{FULLWIDTH YEN SIGN}700", "\N{YEN SIGN}").value == 700
    assert recognised_with("50 \N{EURO SIGN}", " \N{EURO SIGN} ").unit == "\N{EURO SIGN}"


def test_multiplier_letter_is_applied_or_doubted_the_same_whatever_the_caller_allows() -> None:
    assert read_number("5 k", extra_units=["k"]) == Unsure(Doubt.UNKNOWN_UNIT)
    assert read_number("5 k BTC", extra_units=["k"]) == Unsure(Doubt.UNKNOWN_UNIT)
    assert read_number("5 w", extra_units=["W"]) == Unsure(Doubt.UNKNOWN_UNIT)
    assert recognised_with("5k", "k") == Recognised(Decimal("5000"))
    assert recognised_with("3w", "w") == Recognised(Decimal("30000"))
    assert recognised_with("5k BONK", "k", "BONK") == Recognised(Decimal("5000"), "BONK")
    assert read_number("5 kBTC", extra_units=["k"]) == Unsure(Doubt.UNKNOWN_UNIT)


def test_name_that_only_holds_a_multiplier_letter_is_still_taken_from_a_caller() -> None:
    assert recognised_with("5 kBONK", "kBONK") == Recognised(Decimal("5"), "kBONK")
    assert recognised_with("5 wif", "wif") == Recognised(Decimal("5"), "wif")
    assert recognised_with("5 ks", "ks") == Recognised(Decimal("5"), "ks")
    assert recognised_with("5 kk", "kk") == Recognised(Decimal("5"), "kk")


def test_allowed_units_given_as_one_string_are_refused() -> None:
    with pytest.raises(TypeError, match="collection"):
        read_number("500 BONK", extra_units="BONK")


def recognised_with(text: str, *extra_units: str) -> Recognised:
    reading = read_number(text, extra_units=extra_units)
    assert isinstance(reading, Recognised), f"{text!r} was read as {reading!r}"
    return reading


# --- letters right after the digits: a multiplier, a unit, or a doubt -------


def test_multiplier_letter_alone_is_applied_and_known_units_may_follow() -> None:
    assert recognised("5k").value == 5000
    assert recognised("5k刀") == Recognised(Decimal("5000"), "刀")
    assert recognised("5k USDT") == Recognised(Decimal("5000"), "USDT")
    assert recognised_with("5k BONK", "BONK") == Recognised(Decimal("5000"), "BONK")


@pytest.mark.parametrize("text", ["5ku", "5wu", "5kusdt", "5wBTC", "5kU", "3w刀刀k"])
def test_multiplier_letter_glued_to_a_known_word_is_not_applied(text: str) -> None:
    assert not isinstance(read_number(text), Recognised)


def test_letters_that_read_both_as_multiplier_and_word_and_as_one_word_are_a_doubt() -> None:
    assert read_number("5wu", extra_units=("wu",)) == Unsure(Doubt.UNCLEAR_MULTIPLIER)
    assert read_number("5kBONK", extra_units=("BONK",)) == Unsure(Doubt.UNCLEAR_MULTIPLIER)
    assert read_number("5kBONK", extra_units=("BONK", "kBONK")) == Unsure(Doubt.UNCLEAR_MULTIPLIER)


def test_letters_that_only_read_as_one_allowed_word_are_a_unit() -> None:
    assert read_number("5kas") == Unsure(Doubt.UNCLEAR_MULTIPLIER)
    assert recognised_with("5kas", "kas") == Recognised(Decimal("5"), "kas")
    assert recognised_with("5 kas", "KAS") == Recognised(Decimal("5"), "kas")


# --- whatever is recognised carries only known units: random texts ----------

# The list of unit words is written out a second time here, from the two
# tables it is made of and the counters above, and the unit is cut into blocks
# by a rule of this file's own: at gaps, and wherever Chinese characters meet
# anything else.
EVERY_UNIT_WORD_THIS_PROGRAM_KNOWS = frozenset(
    unicodedata.normalize("NFKC", word).upper()
    for word in (
        *USDT_WORDS,
        *COUNTERS,
        *(form for coin in BUILT_IN_COINS for form in (coin.symbol, coin.name, *coin.aliases)),
    )
)


def is_a_chinese_character(character: str) -> bool:
    """Whether ``character`` is in the block of the Chinese characters in use."""
    return "\N{CJK UNIFIED IDEOGRAPH-4E00}" <= character <= "\N{CJK UNIFIED IDEOGRAPH-9FFF}"


def is_an_ideograph(character: str) -> bool:
    """Whether Unicode names ``character`` an ideograph: the rare ones and the copies as well."""
    name = unicodedata.name(character, "")
    return name.startswith(("CJK UNIFIED IDEOGRAPH-", "CJK COMPATIBILITY IDEOGRAPH-"))


def in_ordinary_characters(text: str) -> str:
    """``text`` the way Unicode writes it out for comparison: 𝐁 as B, ｕ as u, ᵘ as u."""
    return unicodedata.normalize("NFKC", text)


def blocks_of(unit: str) -> list[tuple[bool, str]]:
    """The blocks of the unit, each in ordinary characters and marked Chinese or not.

    The unit is cut at gaps, and wherever Chinese meets anything else. Where
    the line around "a Chinese character" lies can be drawn narrowly or
    widely, so the unit is cut both ways and the blocks of both are given:
    first as written with only the characters in use counted as Chinese, then
    in ordinary characters with every ideograph counted.
    """
    narrowly = [
        (is_chinese, in_ordinary_characters("".join(run)))
        for word in unit.split()
        for is_chinese, run in itertools.groupby(word, key=is_a_chinese_character)
    ]
    widely = [
        (is_chinese, "".join(run))
        for word in in_ordinary_characters(unit).split()
        for is_chinese, run in itertools.groupby(word, key=is_an_ideograph)
    ]
    return narrowly + widely


NUMBERS_FOR_RANDOM_TEXTS = [
    "5",
    "0.5",
    "94,900",
    "1.2k",
    "3w",
    "8万",
    "两万三",
    "9万4",
    "三千",
    "$5",
    "５",
    "5K",
    "12.5W",
]
KNOWN_WORDS_FOR_RANDOM_TEXTS = [
    "USDT",
    "usdt",
    "u",
    "U",
    "ｕ",
    "刀",
    "美金",
    "美元",
    "dollars",
    "Tether",
    "BTC",
    "btc",
    "Eth",
    "sol",
    "DOGE",
    "ＢＴＣ",
    "比特币",
    "以太坊",
    "个",
    "個",
    "枚",
    "颗",
    "coins",
    "Token",
    "Bitcoin Cash",
    "shiba inu",
    in_bold("BTC"),
    in_bold("U"),
    in_bold("usdt"),
    USDT_IN_SUPERSCRIPT,
    "\N{MODIFIER LETTER SMALL U}",
]
UNKNOWN_WORDS_FOR_RANDOM_TEXTS = [
    "k",
    "K",
    "w",
    "W",
    "m",
    "b",
    "t",
    "g",
    "s",
    "x",
    "ks",
    "ws",
    "ms",
    "mm",
    "us",
    "千",
    "万",
    "亿",
    "兆",
    "萬",
    "million",
    "millions",
    "thousand",
    "mln",
    "wan",
    "kilo",
    "milli",
    "half",
    "sat",
    "sats",
    "wei",
    "gwei",
    "cents",
    "毛",
    "分",
    "聪",
    "成",
    "倍",
    "打",
    "块",
    "元",
    "币",
    "天",
    "тыс",
    "к",
    "μ",
    "BONK",
    "bonk",
    "WIF",
    "kas",
    "手",
    "张",
    "Cash",
    "Inu",
    "Baby",
    "们",
    in_bold("k"),
    in_bold("W"),
    in_bold("s"),
    "\N{MODIFIER LETTER SMALL K}",
    "\N{CYRILLIC SMALL LETTER KA}",
    "\N{GREEK SMALL LETTER KAPPA}",
    "\N{KATAKANA LETTER DO}\N{KATAKANA LETTER RU}",
    "\N{CJK COMPATIBILITY IDEOGRAPH-F978}",
]
WORDS_A_CALLER_MAY_ALLOW = ["BONK", "wif", "KAS", "手", "张", "Baby Doge"]
# Words this program reads as part of the number, and so does not take from a caller.
WORDS_NOT_TAKEN_FROM_A_CALLER = ["k", "W", "万"]
GAPS_FOR_RANDOM_TEXTS = ["", "", " ", "\N{IDEOGRAPHIC SPACE}"]


def blocks_outside(unit: str, allowed: frozenset[str]) -> list[str]:
    """The blocks of ``unit`` that are neither known to this program nor in ``allowed``.

    There are none when the whole unit is one known or allowed name. A block
    of Chinese characters is also inside when it is known words one after
    another. That is asked of a pattern made of those words, not of the way
    the module under test cuts such a block.
    """
    known = EVERY_UNIT_WORD_THIS_PROGRAM_KNOWS | allowed
    if " ".join(in_ordinary_characters(unit).upper().split()) in known:
        return []
    chinese_words = sorted(word for word in known if all(map(is_an_ideograph, word)))
    row_of_known_words = "(?:" + "|".join(map(re.escape, chinese_words)) + ")+"
    outside = [
        block
        for is_chinese, block in blocks_of(unit)
        if block.upper() not in known
        and not (is_chinese and re.fullmatch(row_of_known_words, block))
    ]
    return list(dict.fromkeys(outside))


def test_the_rule_used_to_judge_units_cuts_them_at_gaps_and_between_scripts() -> None:
    nothing = frozenset[str]()

    assert blocks_outside("个 BTC", nothing) == []
    assert blocks_outside("个BTC刀", nothing) == []
    assert blocks_outside("＄", nothing) == []
    assert blocks_outside("个w刀", nothing) == ["w"]
    assert blocks_outside("BTCks", nothing) == ["BTCks"]
    assert blocks_outside("个比特币", nothing) == []
    assert blocks_outside("个比特币现金", nothing) == []
    assert blocks_outside("个比特", nothing) == ["个比特"]
    assert blocks_outside("个比特币们", nothing) == ["个比特币们"]
    assert blocks_outside("个币 BTC", nothing) == ["个币"]
    assert blocks_outside("个邦克", frozenset({"邦克"})) == []
    assert blocks_outside("BTCUSDT", nothing) == ["BTCUSDT"]
    assert blocks_outside("Bitcoin Cash", nothing) == []
    assert blocks_outside("bitcoin  cash", nothing) == []
    assert blocks_outside("Bitcoin Cashs", nothing) == ["Cashs"]
    assert blocks_outside("Cash", nothing) == ["Cash"]
    assert blocks_outside("Baby Doge", nothing) == ["Baby"]
    assert blocks_outside("Baby Doge", frozenset({"BABY DOGE"})) == []
    assert blocks_outside("Baby", frozenset({"BABY DOGE"})) == ["Baby"]
    # Letters in a form of their own are judged as the ordinary letters they stand for.
    assert blocks_outside(in_bold("BTC"), nothing) == []
    assert blocks_outside("个" + in_bold("BTC"), nothing) == []
    assert blocks_outside(in_bold("BTCUSDT"), nothing) == ["BTCUSDT"]
    assert blocks_outside("BTC" + in_bold("U"), nothing) == ["BTCU"]
    assert blocks_outside(in_bold("UU"), nothing) == ["UU"]
    assert blocks_outside("kBONK 个", frozenset({"BONK"})) == ["kBONK"]
    assert blocks_outside("BONK 个", frozenset({"BONK"})) == []


def test_the_rule_used_to_judge_units_holds_however_rare_characters_are_counted() -> None:
    nothing = frozenset[str]()
    doru = "\N{KATAKANA LETTER DO}\N{KATAKANA LETTER RU}"
    rare = "\N{CJK UNIFIED IDEOGRAPH-3400}"

    assert set(blocks_outside(f"{doru}个", nothing)) == {doru}
    # A rare Chinese character is Chinese to some and a letter to others;
    # the unit is cut both ways, and every block of both must be known.
    assert blocks_outside(f"个{rare}", frozenset({rare})) == []
    assert set(blocks_outside(f"{rare}{rare}", frozenset({rare}))) == {f"{rare}{rare}"}
    # Counted as a letter, the rare character makes one known word with the x;
    # counted as Chinese, it is cut from the x and neither half is known.
    assert set(blocks_outside(f"个{rare}x", frozenset({f"{rare}X"}))) == {f"个{rare}", "x"}


def test_every_unit_handed_back_for_a_random_text_is_made_of_known_or_allowed_words() -> None:
    dice = random.Random(63)
    # Known words come up most often, or hardly any unit would be handed back.
    kinds_of_words = [
        KNOWN_WORDS_FOR_RANDOM_TEXTS,
        KNOWN_WORDS_FOR_RANDOM_TEXTS,
        KNOWN_WORDS_FOR_RANDOM_TEXTS,
        WORDS_A_CALLER_MAY_ALLOW,
        UNKNOWN_WORDS_FOR_RANDOM_TEXTS,
    ]
    with_a_unit = 0
    with_an_allowed_word = 0
    turned_away = 0
    offending = []
    for _ in range(40_000):
        words = [dice.choice(dice.choice(kinds_of_words)) for _ in range(dice.randint(1, 3))]
        text = dice.choice(NUMBERS_FOR_RANDOM_TEXTS) + "".join(
            dice.choice(GAPS_FOR_RANDOM_TEXTS) + word for word in words
        )
        extra_units = dice.sample(WORDS_A_CALLER_MAY_ALLOW, dice.randint(0, 2))
        allowed = frozenset(word.upper() for word in extra_units)
        # Passed along with the rest, and expected to make no difference.
        extra_units += dice.sample(WORDS_NOT_TAKEN_FROM_A_CALLER, dice.randint(0, 1))

        reading = read_number(text, extra_units=extra_units)

        if not isinstance(reading, Recognised):
            turned_away += 1
        elif reading.unit is not None:
            with_a_unit += 1
            with_an_allowed_word += any(
                block.upper() in allowed for _, block in blocks_of(reading.unit)
            )
            if blocks_outside(reading.unit, allowed):
                offending.append((text, extra_units, reading.unit))

    assert offending == []
    # The texts must be of all three kinds, or the check above says nothing.
    assert with_a_unit > 5_000
    assert with_an_allowed_word > 500
    assert turned_away > 5_000


def test_every_unit_handed_back_for_random_characters_is_made_of_known_words() -> None:
    dice = random.Random(64)
    alphabet = (
        "0123456789.,kKwWmusdtUSDTbcBCeh个枚刀美金元币万千亿兆聪毛块 $¥\N{IDEOGRAPHIC SPACE}ｕｋ５"
    )
    with_a_unit = 0
    offending = []
    for _ in range(60_000):
        text = dice.choice("123456789") + "".join(
            dice.choice(alphabet) for _ in range(dice.randint(1, 6))
        )

        reading = read_number(text)

        if isinstance(reading, Recognised) and reading.unit is not None:
            with_a_unit += 1
            if blocks_outside(reading.unit, frozenset()):
                offending.append((text, reading.unit))

    assert offending == []
    assert with_a_unit > 1_000


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
    ("text", "reason"),
    [
        # m is a million to some and a thousandth (as in mBTC) to others.
        ("5m", Doubt.UNKNOWN_UNIT),
        ("5M", Doubt.UNKNOWN_UNIT),
        ("2b", Doubt.UNKNOWN_UNIT),
        ("2B", Doubt.UNKNOWN_UNIT),
        ("3t", Doubt.UNKNOWN_UNIT),
        ("2bn", Doubt.UNKNOWN_UNIT),
        ("5kk", Doubt.UNCLEAR_MULTIPLIER),
        ("1kw", Doubt.UNCLEAR_MULTIPLIER),
        ("1ku", Doubt.UNCLEAR_MULTIPLIER),
        ("1wu", Doubt.UNCLEAR_MULTIPLIER),
        ("5kas", Doubt.UNCLEAR_MULTIPLIER),
        ("3wif", Doubt.UNCLEAR_MULTIPLIER),
        ("5 k", Doubt.UNKNOWN_UNIT),
        ("5 w", Doubt.UNKNOWN_UNIT),
        ("5 m", Doubt.UNKNOWN_UNIT),
        ("5 million", Doubt.UNKNOWN_UNIT),
        ("5million", Doubt.UNKNOWN_UNIT),
        ("2 thousand", Doubt.UNKNOWN_UNIT),
        ("2thousand", Doubt.UNKNOWN_UNIT),
        ("3 billion", Doubt.UNKNOWN_UNIT),
        ("1 mil", Doubt.UNKNOWN_UNIT),
        ("3 hundred", Doubt.UNKNOWN_UNIT),
        ("5 dozen", Doubt.UNKNOWN_UNIT),
        ("5 million dollars", Doubt.UNKNOWN_UNIT),
        ("2 k usdt", Doubt.UNKNOWN_UNIT),
        ("3 usdt k", Doubt.UNKNOWN_UNIT),
        ("8万k", Doubt.UNCLEAR_MULTIPLIER),
        ("8万 w", Doubt.UNKNOWN_UNIT),
    ],
)
def test_letters_that_may_or_may_not_multiply_are_not_guessed(text: str, reason: Doubt) -> None:
    # A letter glued to the digits that may be a multiplier is named as such;
    # anywhere else it is simply a unit this program does not know.
    assert read_number(text) == Unsure(reason)


def test_magnitude_word_among_more_words_than_a_unit_has_is_not_a_number() -> None:
    assert read_number("5 million dollars in cash") == NotANumber()


@pytest.mark.parametrize(
    ("text", "value", "unit"),
    [
        ("0.5btc", "0.5", "btc"),
        ("2ton", "2", "ton"),
        ("3trx", "3", "trx"),
        ("5bnb", "5", "bnb"),
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
def test_stray_magnitude_word_never_yields_a_number(text: str) -> None:
    assert not isinstance(read_number(text), Recognised)


@pytest.mark.parametrize("text", ["很多", "好多", "多少", "大概", "左右", "about", "~", "to", "k"])
def test_vague_word_without_any_number_is_not_a_number(text: str) -> None:
    assert read_number(text) == NotANumber()


@pytest.mark.parametrize(
    ("text", "unit"),
    [("2ton", "ton"), ("3 atom", "atom"), ("5 dot", "dot")],
)
def test_unit_that_only_resembles_a_vague_word_stays_a_unit(text: str, unit: str) -> None:
    assert recognised(text).unit == unit


# --- once doubted, never recognised ------------------------------------------
#
# In each of these the unit holds a multiplier, a smaller unit or a share,
# glued on or set apart, in front or behind, in one form or another. None of
# their units is on the list of units this program knows, so none is read.

ONCE_DOUBTED = [
    # A multiplier letter written into the unit, glued to a known word, or standing alone.
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
    "5g",
    "5 G",
    "5x",
    "5e",
    "5E",
    "5c",
    "5 p",
    "5 个 x",
    "5к",
    "5 mmETH",
    "5 ETHmm",
    "5 mmBTC",
    "5 kkETH",
    "5 mnSOL",
    "5 kmusdt",
    "5 mkusdt",
    "5 kkkusdt",
    "5 kilomusdt",
    "5 usdtkm",
    "5 mkbtc",
    "5 btcmk",
    "5 millikbtc",
    "100 satskm",
    "$3 times",
    "5 tenths of one btc",
    "5 kusdts",
    "5 kbtcs",
    "5 pico",
    "5 picoBTC",
    "5 μusdt",
    "5 μETH",
    "5 \N{MICRO SIGN}eth",
    # A magnitude word in the plural, shortened, or in another language.
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
    "3 wan",
    "3个wan",
    "3 个 wan",
    "3 WAN",
    "3 yi",
    "5 qian",
    "2 bai",
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
    "3 Gs",
    "3 gs",
    "3 ts",
    "$3 t",
    "3 large",
    "3 shi",
    "3 millón",
    "3 millones",
    "3 tausend",
    "3个达不溜",
    "3 达不溜",
    "3 millionen",
    "3 milliarden",
    "3 thousandish",
    "3 milliontokens",
    "3 hundredfold",
    "3 dogethousand",
    "3 pepemillions",
    "3个XYZmillion",
    "3 mu",
    "3 mU",
    "3 musdt",
    "3 musd",
    "3 bU",
    "5 kiloUSDT",
    "5 megausdt",
    "3 mlnusdt",
    "3个mu",
    "5 kilobtc",
    "5 megaeth",
    "2 kdoge",
    "3 Uk",
    "3 uw",
    "3 USDTk",
    "3 usdtw",
    "3 usdm",
    "3 USDTwan",
    "3 btck",
    "3 BTCmln",
    "3 BTCthousand",
    "3 BTCthousands",
    "3个Uk",
    "$5 mln",
    "5 mln usdt in cash",
    "2 thousands usdt in cash",
    "3打",
    "三打",
    "3 打",
    "3打币",
    "5双",
    "5 双",
    "5对",
    "5 对",
    "3 个 打",
    "3 u 打",
    "3 U 双",
    # An amount in a smaller unit of money or of a coin.
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
    "5mBTC",
    "5 mBTC",
    "5mbtc",
    "5 MBTC",
    "5 mBTCs",
    "5个mBTC",
    "5uBTC",
    "5 uBTC",
    "5 UBTC",
    "5μBTC",
    "5 μBTC",
    "5 \N{MICRO SIGN}BTC",
    "$5 mBTC",
    "100sat",
    "100 SATS",
    "100 Sats",
    "1satoshi",
    "5000satoshis",
    "5000 Satoshis",
    "100聪",
    "100 聪",
    "一百聪",
    "5gwei",
    "5 GWEI",
    "100wei",
    "100 WEI",
    "5毫",
    "5 仙",
    "3个聪",
    "50便士",
    "50美分",
    "50 欧分",
    "5 finney",
    "5 szabo",
    "5 bits",
    "5 centavos",
    "5 centimes",
    "5 kopeks",
    "5kopek",
    "5kopeks",
    "5 centBTC",
    "5 BTCcent",
    "5 BTCcents",
    "5 satsBTC",
    "5 BTCsats",
    "5 Ucents",
    "5个BTCsats",
    "100 ksats",
    "21 ksats",
    "100 KSATS",
    "100 Ksat",
    "100 kSats",
    "100 ｋｓａｔｓ",
    "100个ksats",
    "100 ksat BTC",
    "100 kilosats",
    "100 kilosatoshi",
    "100 ksatoshis",
    "100 msat",
    "100 msats",
    "100 MSAT",
    "100 Msats",
    "100msat",
    "100 millisats",
    "100 millisatoshis",
    "100 megasats",
    "100 nanosats",
    "5 kwei",
    "5 Kwei",
    "5 KWEI",
    "5 mwei",
    "5 Mwei",
    "5 MWEI",
    "5mwei",
    "5 kgwei",
    "5 kGwei",
    "5 Mgwei",
    "5 microwei",
    "5 gigawei",
    "5 megagwei",
    "5 kcents",
    "5 mcent",
    "5 kpence",
    "5 klamports",
    "5 kmBTC",
    "5 mmbtc",
    "100 xyzsats",
    "5 abcwei",
    "5 个 qqqcents",
    "100 satsk",
    "100 satk",
    "5 weim",
    "5 gweik",
    "5 centkilo",
    "100 satsmilli",
    # A fraction, a share or a multiple.
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
    "5层",
    "5层仓",
    "5 bp",
    "5 bps",
    "5bps",
    "25 bips",
    "3 BTC倍",
    "3 U成",
    "3 U 成",
    "3 USDT折",
    "3 USDTpct",
    "3 pctUSDT",
    "3 btcbps",
    # A number character outside the ones this program reads, and further forms of the above.
    "3兆",
    "3 兆",
    "三兆",
    "两兆",
    "一兆",
    "1.5兆",
    "3兆刀",
    "3兆U",
    "3 兆 USDT",
    "3兆个",
    "3个兆",
    "3万兆",
    "3京",
    "3京U",
    "3个京",
    "3垓",
    "3 U兆",
    "3 USDT 兆",
    "3個萬",
    "3个點",
    "3个幺",
    "3卌",
    "3个陌",
    "3 阡",
    "3个壱",
    "3 弐",
    "3个打",
    "3 个双",
    "3个对",
    "3 U个打",
    "3个成",
    "3 个倍",
    "3个折",
    "3 个层",
    "3 BTC个倍",
    "3个仓位成",
    "5 tera",
    "5 peta",
    "5 teraBTC",
    "5 centi",
    "5 deciBTC",
    "5 femto",
    "5 attoFIL",
    "5 lovelace",
    "5 lovelaces",
    "5 drops",
    "5 kdrops",
    "5 kkk",
    "5 KKKK",
    "5 ww",
    "5 wk",
    "5个kkw",
    "$5 kk",
    "$5 kw",
    "3 達不溜",
    "3個雙",
    "3 對",
    "3層",
    "100聰",
    "5釐",
]


@pytest.mark.parametrize("text", ONCE_DOUBTED)
def test_text_once_doubted_for_its_unit_is_never_recognised(text: str) -> None:
    assert not isinstance(read_number(text), Recognised)


@pytest.mark.parametrize(
    ("text", "value", "unit"),
    [
        ("50u", "50", "u"),
        ("50 U", "50", "U"),
        ("5刀", "5", "刀"),
        ("5 coins", "5", "coins"),
        ("5 tether", "5", "tether"),
        ("3 bitcoin", "3", "bitcoin"),
        ("3 usdc", "3", "usdc"),
        ("3 USDT", "3", "USDT"),
        ("2 tokens", "2", "tokens"),
        ("3个u", "3", "个u"),
        ("3 个 U", "3", "个 U"),
        ("3w u", "30000", "u"),
        ("3w刀", "30000", "刀"),
        ("5K USDT", "5000", "USDT"),
        ("5k usdt", "5000", "usdt"),
        ("3 doge", "3", "doge"),
        ("3个BTC", "3", "个BTC"),
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


NUMBER_CHARACTERS = (
    "零〇一二三四五六七八九十百千万亿兆京垓秭穰沟涧正载极"
    "两俩仨廿卅卌皕半几幺点"
    "壹贰叁肆伍陆柒捌玖拾佰仟陌阡弌弍弎"
    "萬億兩倆貳參叄参陸溝澗載極點幾壱弐"
)

PLACES_FOR_A_NUMBER_CHARACTER = [
    "3{}",
    "3 {}",
    "3个{}",
    "3 个 {}",
    "3{}个",
    "3{}刀",
    "3{}U",
    "3 U{}",
    "3 U {}",
    "3 USDT{}",
    "3刀{}",
    "$3 {}",
    "三个{}",
]


@pytest.mark.parametrize("place", PLACES_FOR_A_NUMBER_CHARACTER)
@pytest.mark.parametrize("character", NUMBER_CHARACTERS)
def test_number_character_in_a_unit_never_leaves_the_bare_number(
    character: str, place: str
) -> None:
    # Where this program reads the character it changes the number ("3万" is
    # thirty thousand); everywhere else the answer is not a number at all.
    reading = read_number(place.format(character))

    assert not (isinstance(reading, Recognised) and reading.value == 3)


# The second written form of 廿, twenty. It is tried on its own, and with the
# caller allowing it as a word, so that the list above stays as it was.
SECOND_FORM_OF_TWENTY = "卄"


@pytest.mark.parametrize("place", PLACES_FOR_A_NUMBER_CHARACTER)
@pytest.mark.parametrize("allowed", [(), (SECOND_FORM_OF_TWENTY,)])
def test_second_form_of_twenty_is_a_number_character_and_never_a_unit(
    place: str, allowed: tuple[str, ...]
) -> None:
    reading = read_number(place.format(SECOND_FORM_OF_TWENTY), extra_units=allowed)

    assert not isinstance(reading, Recognised)


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
    *("毛", "角", "分", "厘", "毫", "仙", "聪", "便士", "毛钱", "分钱", "美分"),
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


# Python refuses to turn more than a few thousand digits into a whole number.
MORE_DIGITS_THAN_PYTHON_TURNS_INTO_A_WHOLE_NUMBER = "4" * (sys.get_int_max_str_digits() + 700)


@pytest.mark.parametrize(
    ("place", "reason"),
    [
        ("9万{}", Doubt.UNCLEAR_WORDING),
        ("一万{}", Doubt.UNCLEAR_WORDING),
        ("1亿{}万", Doubt.UNCLEAR_WORDING),
        ("{}万三", Doubt.TOO_MANY_DIGITS),
        ("{}亿5000万", Doubt.TOO_MANY_DIGITS),
        ("{}万零五", Doubt.TOO_MANY_DIGITS),
        ("{}", Doubt.TOO_MANY_DIGITS),
        ("{}万", Doubt.TOO_MANY_DIGITS),
        ("0.{}", Doubt.TOO_MANY_DIGITS),
    ],
)
def test_count_of_thousands_of_digits_is_a_doubt_and_not_an_error(
    place: str, reason: Doubt
) -> None:
    text = place.format(MORE_DIGITS_THAN_PYTHON_TURNS_INTO_A_WHOLE_NUMBER)

    assert read_number(text) == Unsure(reason)


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("5" * 36 + "万三", "5" * 36 + "3000"),
        ("12345万3", "123453000"),
        ("1亿12345678", "112345678"),
        ("1" + "0" * 35 + "万零五", "1" + "0" * 38 + "5"),
    ],
)
def test_long_count_that_the_ledger_can_hold_is_still_added_up(text: str, value: str) -> None:
    assert written(text) == value


@pytest.mark.parametrize(
    "text",
    ["5" * 37 + "万三", "5" * 41 + "万三", "1" + "0" * 45 + "万零五", "1" + "0" * 40 + "万零三"],
)
def test_long_count_that_the_ledger_cannot_hold_has_too_many_digits(text: str) -> None:
    assert read_number(text) == Unsure(Doubt.TOO_MANY_DIGITS)


VERY_LONG = 50_000

# What each very long text is read as. None of them may take long: where the
# work grows with the length of the text these take a few hundredths of a
# second, and where it grows with its square or its cube, minutes or hours.
VERY_LONG_TEXTS: dict[str, tuple[str, type]] = {
    "counters after letters that may hold a multiplier": ("5ku" + "个" * VERY_LONG, Unsure),
    "counters after a multiplier letter": ("5k" + "个" * VERY_LONG, NotANumber),
    "counters after a gap": ("5 " + "个" * VERY_LONG, NotANumber),
    "counters right after the number": ("5" + "个" * VERY_LONG, NotANumber),
    "known names one after another": ("5个" + "比特币现金" * (VERY_LONG // 5), NotANumber),
    "names that begin like other names": ("5w" + "以太坊以太" * (VERY_LONG // 5), NotANumber),
    "names with one character left over": ("5个" + "以太" * (VERY_LONG // 2) + "们", NotANumber),
    "letters after a multiplier letter": ("5k" + "u" * VERY_LONG, Unsure),
    "mathematical letters after a multiplier letter": (
        "5k" + in_bold("u") * VERY_LONG,
        Unsure,
    ),
    "mathematical letters": ("5 " + in_bold("u") * VERY_LONG, NotANumber),
    "letters and Chinese characters in turn": ("5ku" + "个u" * (VERY_LONG // 2), Unsure),
    "words": ("5 " + "u " * (VERY_LONG // 2), NotANumber),
    "gaps before a unit": ("5" + " " * VERY_LONG + "u", Recognised),
    "wide gaps before a unit": ("5" + "\N{IDEOGRAPHIC SPACE}" * VERY_LONG + "u", Recognised),
    "tabs and line breaks before a unit": ("5" + "\t\n" * (VERY_LONG // 2) + "u", Recognised),
    "gaps after the number": ("5" + " " * VERY_LONG, Recognised),
    "gaps before the number": (" " * VERY_LONG + "5", Recognised),
    "gaps and no number": (" " * VERY_LONG + "x", NotANumber),
    "gaps around a sign and no number": (
        " " * VERY_LONG + "$" + " " * VERY_LONG + "x",
        NotANumber,
    ),
    "gaps before something that is no unit": ("5" + " " * VERY_LONG + "#", NotANumber),
    "gaps around a word for a range": (
        "5" + " " * VERY_LONG + "to" + " " * VERY_LONG + "x",
        NotANumber,
    ),
    "gaps around a dash and a sign": (
        "5" + " " * VERY_LONG + "-" + " " * VERY_LONG + "$" + " " * VERY_LONG + "x",
        NotANumber,
    ),
    "gaps around a slash": ("5" + " " * VERY_LONG + "/" + " " * VERY_LONG + "x", NotANumber),
    "gaps before a share": ("5" + " " * VERY_LONG + "x成", Unsure),
    "numbers with gaps after each": (("5" + " " * 200) * (VERY_LONG // 201) + "x", Unsure),
    "number words with gaps after each": (
        ("五" + " " * 300) * (VERY_LONG // 301) + "#",
        NotANumber,
    ),
    "digits": ("5" * VERY_LONG, Unsure),
    "decimal places": ("0." + "5" * VERY_LONG, Unsure),
    "digits in groups of three": ("1" + ",000" * (VERY_LONG // 4), Unsure),
    "digits and a multiplier letter": ("5" * VERY_LONG + "k u", Unsure),
    "a count inside a number said in words": ("9万" + "4" * VERY_LONG, Unsure),
    "a count before a number said in words": ("5" * VERY_LONG + "万三", Unsure),
    "a count between 亿 and 万": ("1亿" + "5" * VERY_LONG + "万", Unsure),
    "the same number word": ("一" * VERY_LONG, Unsure),
    "thousands said again and again": ("九千" * (VERY_LONG // 2), Unsure),
    "a number said in full again and again": ("一万二千三百四十五" * (VERY_LONG // 9), Unsure),
    "zeros said": ("一" + "零" * VERY_LONG + "五", Unsure),
    "decimal places said": ("一点" + "五" * VERY_LONG, Unsure),
    "commas": ("5," * (VERY_LONG // 2), NotANumber),
    "ranges": ("5到" * (VERY_LONG // 2), Unsure),
    "vague words": ("大概" * (VERY_LONG // 2) + "5", Unsure),
    "marks on a letter": ("5 u" + "\N{COMBINING ACUTE ACCENT}" * VERY_LONG, NotANumber),
    "characters that are not seen": ("5" + "\N{ZERO WIDTH SPACE}" * VERY_LONG + "u", NotANumber),
    "letters that come apart into words": (
        "5 " + "\N{ARABIC LIGATURE SALLALLAHOU ALAYHE WASALLAM}" * VERY_LONG,
        NotANumber,
    ),
}


@pytest.mark.parametrize("name", VERY_LONG_TEXTS)
def test_very_long_text_is_answered_at_once(name: str) -> None:
    text, kind = VERY_LONG_TEXTS[name]
    started = time.perf_counter()

    reading = read_number(text)

    seconds = time.perf_counter() - started
    assert isinstance(reading, kind)
    assert seconds < 2


def test_long_run_of_known_chinese_words_is_cut_in_time_that_grows_with_its_length() -> None:
    # Thirty-two characters is all a unit may have, so this asks the words
    # the caller allows: a hundred of them, each a beginning of the next.
    words = ["邦" * size for size in range(1, 33)]

    assert recognised_with("5" + "邦" * 32, *words).unit == "邦" * 32
    assert read_number("5" + "邦" * 31 + "们", extra_units=words) == Unsure(Doubt.UNKNOWN_UNIT)
    assert read_number("5" + "邦" * 33, extra_units=words) == NotANumber()


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
