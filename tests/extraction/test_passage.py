"""Tests of finding a copied phrase in the passage.

The tidying on both sides is only about width and whitespace; nothing that
changes what a character says is ever tidied away. Every passage below is
invented.
"""

from __future__ import annotations

import pytest

from ledger_hand.extraction.passage import MAX_PLACES_TRIED, Passage, Piece, PieceMiss

PASSAGE = "昨天晚上 9 点 40 在币安买了 0.02 个比特币，价格 94,900，手续费 1.2 USDT，感觉还会涨"


def piece(passage: str, phrase: str) -> Piece:
    found = Passage(passage).find(phrase)
    assert isinstance(found, Piece), found
    return found


def miss(passage: str, phrase: str) -> PieceMiss:
    found = Passage(passage).find(phrase)
    assert isinstance(found, PieceMiss), found
    return found


@pytest.mark.parametrize(
    "phrase", ["比特币", "0.02 个比特币", "94,900", "9 点 40", "1.2 USDT", "感觉还会涨", "币安"]
)
def test_a_phrase_written_as_in_the_passage_is_a_piece(phrase: str) -> None:
    assert piece(PASSAGE, phrase).text == phrase


@pytest.mark.parametrize(
    ("phrase", "expected"),
    [
        ("  比特币  ", "比特币"),
        ("0.02  个比特币", "0.02 个比特币"),
        ("0.02\t个比特币", "0.02 个比特币"),
        ("9\n点\N{IDEOGRAPHIC SPACE}40", "9 点 40"),
        ("９４，９００", "94,900"),
        ("１.２ ＵＳＤＴ", "1.2 USDT"),
        ("94，900 ", "94,900"),
    ],
)
def test_width_and_whitespace_are_tidied_on_the_phrase(phrase: str, expected: str) -> None:
    assert piece(PASSAGE, phrase).text == expected


def test_the_piece_is_the_passages_own_text() -> None:
    passage = "买了 ０.５  ＥＴＨ，\n价格　3,420"

    assert piece(passage, "0.5 ETH").text == "０.５  ＥＴＨ"
    assert piece(passage, "价格 3,420").text == "价格　3,420"
    assert piece(passage, "， 价格").text == "，\n价格"
    assert miss(passage, "，价格") is PieceMiss.NOT_IN_PASSAGE


@pytest.mark.parametrize(
    "phrase",
    [
        "btc",
        "BTC",
        "0.02个比特币",
        "94900",
        "9点40",
        "感觉要涨",
        "\N{ZERO WIDTH SPACE}比特币",
        "比特币\N{ZERO WIDTH JOINER}",
        "𝟗𝟒,𝟗𝟎𝟎",
        "Ⅰ",
        "比特币。",
        "1.2 usdt",
        PASSAGE + "。",
    ],
)
def test_anything_else_that_differs_is_not_a_piece(phrase: str) -> None:
    assert miss(PASSAGE, phrase) is PieceMiss.NOT_IN_PASSAGE


def test_any_piece_of_the_passage_counts_even_part_of_a_word() -> None:
    assert piece(PASSAGE, "比特").text == "比特"
    assert piece("sold 2 ETHW", "ETH").text == "ETH"


def test_letter_case_counts() -> None:
    assert piece("sold 2 ETH", "ETH").text == "ETH"
    assert miss("sold 2 ETH", "eth") is PieceMiss.NOT_IN_PASSAGE
    assert miss("sold 2 eth", "ETH") is PieceMiss.NOT_IN_PASSAGE


def test_a_full_width_passage_matches_an_ordinary_phrase_and_back() -> None:
    assert piece("ｓｏｌｄ ２ ＥＴＨ", "2 ETH").text == "２ ＥＴＨ"
    assert piece("sold 2 ETH", "２ ＥＴＨ").text == "2 ETH"


def test_half_width_katakana_matches_its_full_width_form() -> None:
    assert piece("ｶﾀｶﾅ で買った", "カタカナ").text == "ｶﾀｶﾅ"


@pytest.mark.parametrize(
    ("passage", "phrase"),
    [
        ("price 94,900", "94"),
        ("price 94,900", "900"),
        ("price 94,900", "4,9"),
        ("1.2k USDT", "1.2"),
        ("8万刀", "8"),
        ("两万三", "两万"),
        ("零点五个", "零点"),
        ("9点40", "9点"),
        ("9点40", "40"),
        ("94.900", "94"),
        ("1,5", "5"),
    ],
)
def test_a_phrase_that_cuts_a_number_in_two_is_not_a_piece(passage: str, phrase: str) -> None:
    assert miss(passage, phrase) is PieceMiss.CUTS_A_NUMBER


def test_the_first_place_that_cuts_no_number_is_the_piece() -> None:
    passage = "先 94,900 后 94 收"

    found = piece(passage, "94")

    assert found.text == "94"
    assert found.numbers == ("94",)


def test_a_phrase_may_hold_several_numbers_and_whole_ones_only() -> None:
    found = piece(PASSAGE, "价格 94,900，手续费 1.2 USDT")

    assert found.numbers == ("94,900", "1.2")
    assert piece("8万刀", "8万刀").numbers == ("8万",)
    assert piece("8万刀", "刀").numbers == ()


def test_numbers_inside_a_piece_are_tidied() -> None:
    assert piece("买了 ０.５ ETH", "0.5 ETH").numbers == ("0.5",)


def test_the_passage_lists_its_numbers_as_written_and_tidied() -> None:
    passage = Passage("买 ０.５ ETH 和 1.2ｋ U，两笔")

    assert passage.numbers == (("０.５", "0.5"), ("1.2ｋ", "1.2k"), ("两", "两"))


@pytest.mark.parametrize("phrase", ["", " ", "\N{IDEOGRAPHIC SPACE}\n"])
def test_an_empty_phrase_is_not_a_piece(phrase: str) -> None:
    assert miss(PASSAGE, phrase) is PieceMiss.NOT_IN_PASSAGE


def test_a_phrase_longer_than_the_passage_is_not_a_piece() -> None:
    assert miss("BTC", "BTC" * 100_000) is PieceMiss.NOT_IN_PASSAGE


def test_a_long_passage_and_many_phrases_are_found_quickly() -> None:
    passage = Passage("买了 0.1 BTC，价格 6万；" * 1500)

    for _ in range(2000):
        assert isinstance(passage.find("0.1 BTC"), Piece)
    assert isinstance(passage.find("买了 0.1 BTC，价格 6万；" * 3), Piece)
    assert Passage("1" * 16_000).find("1") is PieceMiss.CUTS_A_NUMBER


def test_a_phrase_is_looked_for_in_a_bounded_number_of_places() -> None:
    within = "12 " * (MAX_PLACES_TRIED - 1) + "1"
    beyond = "12 " * (MAX_PLACES_TRIED + 1) + "1"

    assert piece(within, "1").text == "1"
    assert miss(beyond, "1") is PieceMiss.CUTS_A_NUMBER


def test_a_phrase_looked_up_twice_gives_the_same_answer() -> None:
    passage = Passage(PASSAGE)

    assert passage.find("比特币") is passage.find(" 比特币 ")
    assert passage.find("btc") is passage.find("btc")


@pytest.mark.parametrize(
    ("passage", "phrase"),
    [
        ("ETH 3000一个，买了 2 个", "3000"),
        ("13.2一个买了 10 个 SOL", "13.2"),
        ("150一枚，卖了 3 枚", "150"),
        ("0.42 一个", "0.42"),
        ("0.42一个", "0.42"),
        ("价格 94900一个BTC", "94900"),
        ("手续费 2 USDT一笔", "2 USDT"),
        ("3000 each", "3000"),
        ("3000 apiece", "3000"),
        ("3点5一个", "3点5"),
        ("1,234一个", "1,234"),
        ("买了 1千零5一个", "1千零5"),
    ],
)
def test_a_number_then_so_much_a_piece_is_whole(passage: str, phrase: str) -> None:
    assert piece(passage, phrase).text == phrase


@pytest.mark.parametrize(
    ("passage", "phrase"),
    [
        ("94900", "9490"),
        ("94900", "4900"),
        ("3万5", "3万"),
        ("九万四千九", "九万四"),
        ("1.25", "1.2"),
        ("1,234", "1,23"),
        ("两三千", "两"),
        ("两三千", "三千"),
        ("一亿五千", "一亿五"),
        ("一亿五千", "五千"),
        ("三四十个", "三"),
        ("1,5", "1"),
        ("9万4", "9万"),
        ("5十个", "5"),
    ],
)
def test_a_number_written_in_one_kind_of_writing_is_still_not_cut(
    passage: str, phrase: str
) -> None:
    assert miss(passage, phrase) is PieceMiss.CUTS_A_NUMBER


def test_a_leading_point_is_not_a_piece_of_a_number() -> None:
    # ".02" cuts "0.02" between the zero and the point.
    assert miss("0.02 BTC", ".02") is PieceMiss.CUTS_A_NUMBER


def test_a_place_followed_by_one_still_reads_as_one_number_a_known_limit() -> None:
    # The core reads "30万一" as 301000, so "30万" is taken as cutting it.
    assert miss("30万一个", "30万") is PieceMiss.CUTS_A_NUMBER


@pytest.mark.parametrize(
    ("passage", "phrase"),
    [
        ("1千零5", "5"),
        ("买了 1千零5 个 DOGE", "5 个"),
        ("2万零3百", "3百"),
        ("1亿零5万", "5万"),
        ("3万零5", "5"),
        ("两千零5", "5"),
        ("一万零5", "5"),
        ("1千〇5", "5"),
        ("2三千", "三千"),
        ("2三千", "2"),
        ("3四十个", "四十个"),
        ("3四十个", "3"),
        ("两3千", "3千"),
        ("两3千", "两"),
        ("3零5", "5"),
        ("3零5", "3"),
        ("第一3000一个", "3000"),
        ("3000一个", "一个"),
        ("3000一个", "一"),
        ("3000一千", "3000"),
        ("3000一", "3000"),
        ("3000壹个", "3000"),
    ],
)
def test_any_other_mixture_of_the_two_writings_is_cut(passage: str, phrase: str) -> None:
    assert miss(passage, phrase) is PieceMiss.CUTS_A_NUMBER


def test_the_numbers_inside_a_piece_split_off_one_and_a_counter() -> None:
    assert piece("3000一个", "3000一个").numbers == ("3000", "一")
    assert piece("ETH 3000一个", "3000").numbers == ("3000",)
