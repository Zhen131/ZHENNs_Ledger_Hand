"""Tests of finding the numbers written in a text.

The rule leans towards finding too much: anything that could be a number is
one. Every text below is invented.
"""

from __future__ import annotations

import pytest

from ledger_hand.extraction.passage_numbers import CHINESE_COUNTERS, number_runs, number_spans


def numbers_in(text: str) -> list[str]:
    return [text[start:end] for start, end in number_spans(text)]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("bought 0.02 BTC at 94,900", ["0.02", "94,900"]),
        ("1.2k", ["1.2k"]),
        ("3w", ["3w"]),
        ("5K and 2W", ["5K", "2W"]),
        ("8万刀", ["8万"]),
        ("两万三", ["两万三"]),
        ("九万四千九", ["九万四千九"]),
        ("9万4900", ["9万4900"]),
        ("1亿5000万", ["1亿5000万"]),
        ("零点五", ["零点五"]),
        ("9点40", ["9点40"]),
        ("三点五", ["三点五"]),
        ("壹万贰仟", ["壹万贰仟"]),
        ("兩萬", ["兩萬"]),
        ("二〇二六年", ["二〇二六"]),
        ("94.900", ["94.900"]),
        ("1,5", ["1,5"]),
        ("1,234,567.89", ["1,234,567.89"]),
    ],
)
def test_one_number_is_one_run(text: str, expected: list[str]) -> None:
    assert numbers_in(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("9:40", ["9", "40"]),
        ("2026-10-03", ["2026", "10", "03"]),
        ("10/2", ["10", "2"]),
        ("94, 900", ["94", "900"]),
        ("price 94900.", ["94900"]),
        ("94,900,", ["94,900"]),
        ("9 点 40", ["9", "40"]),
        ("10 月 2 号", ["10", "2"]),
        ("0.5 BTC 和 2 ETH", ["0.5", "2"]),
    ],
)
def test_separate_numbers_are_separate_runs(text: str, expected: list[str]) -> None:
    assert numbers_in(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("5ku", ["5"]),
        ("50u", ["50"]),
        ("5kBONK", ["5"]),
        ("5k个", ["5k"]),
        ("5k,", ["5k"]),
        ("k5", ["5"]),
    ],
)
def test_a_k_or_w_belongs_to_the_number_only_when_no_letter_follows(
    text: str, expected: list[str]
) -> None:
    assert numbers_in(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("一下", ["一"]),
        ("十分", ["十"]),
        ("万一", ["一"]),
        ("一点", ["一"]),
        ("两笔", ["两"]),
        ("二饼", ["二"]),
    ],
)
def test_chinese_number_characters_count_even_inside_other_words(
    text: str, expected: list[str]
) -> None:
    assert numbers_in(text) == expected


def test_digits_of_other_scripts_count() -> None:
    assert numbers_in("\N{ARABIC-INDIC DIGIT THREE}\N{ARABIC-INDIC DIGIT FIVE} coins") == [
        "\N{ARABIC-INDIC DIGIT THREE}\N{ARABIC-INDIC DIGIT FIVE}"
    ]


def test_a_place_word_alone_does_not_begin_a_number() -> None:
    assert numbers_in("百分之 万 千") == []


def test_a_text_without_numbers_has_none() -> None:
    assert numbers_in("") == []
    assert numbers_in("今天行情好无聊 nothing traded") == []


def test_a_long_text_is_read_in_one_pass() -> None:
    text = "买了 0.1 BTC，" * 2000

    assert len(numbers_in(text)) == 2000
    assert numbers_in("9" * 100_000) == ["9" * 100_000]


# --- "so much a piece": the one place a run is cut ------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("3000一个", ["3000", "一"]),
        ("13.2一个", ["13.2", "一"]),
        ("150一枚", ["150", "一"]),
        ("94900一个BTC", ["94900", "一"]),
        ("0.42一个", ["0.42", "一"]),
        ("3点5一个", ["3点5", "一"]),
        ("1,234一个", ["1,234", "一"]),
        ("1千零5一个", ["1千零5", "一"]),
        ("3000一颗", ["3000", "一"]),
        ("3000一個", ["3000", "一"]),
    ],
)
def test_a_number_ending_in_a_digit_then_one_and_a_counter_is_cut_before_the_one(
    text: str, expected: list[str]
) -> None:
    assert numbers_in(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1千零5", ["1千零5"]),
        ("2万零3百", ["2万零3百"]),
        ("1亿零5万", ["1亿零5万"]),
        ("3万零5", ["3万零5"]),
        ("1,234两个", ["1,234两"]),
        ("3零5", ["3零5"]),
        ("两万三0", ["两万三0"]),
        ("第一3000", ["一3000"]),
        ("3000壹", ["3000壹"]),
        ("3000一", ["3000一"]),
        ("3000一千", ["3000一千"]),
        ("3000一万个", ["3000一万"]),
        ("30万一个", ["30万一"]),
        ("2三千", ["2三千"]),
        ("3四十个", ["3四十"]),
        ("两3千", ["两3千"]),
        ("3000壹个", ["3000壹"]),
        ("2 USDT一笔", ["2", "一"]),
    ],
)
def test_every_other_mixture_of_the_two_writings_stays_one_run(
    text: str, expected: list[str]
) -> None:
    assert numbers_in(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "9万4",
        "30万一",
        "5十",
        "3十5",
        "3点五",
        "三点5",
        "1亿5000万",
        "3万五",
        "9千9",
        "12万3",
        "2拾",
    ],
)
def test_the_two_writings_still_join_through_a_place_or_a_point(text: str) -> None:
    assert numbers_in(text) == [text]


@pytest.mark.parametrize(
    "text", ["两三千", "一亿五千", "三四十", "九万四千九", "零点五", "二〇二六"]
)
def test_a_run_of_chinese_number_characters_alone_stays_one_number(text: str) -> None:
    assert numbers_in(text) == [text]


@pytest.mark.parametrize("text", ["94900", "94,900", "1.25", "1,234", "1,5", "94.900", "1.2k"])
def test_a_run_of_decimal_digits_alone_stays_one_number(text: str) -> None:
    assert numbers_in(text) == [text]


def test_the_counters_are_the_number_readers_chinese_ones() -> None:
    assert set(CHINESE_COUNTERS) == {"个", "個", "枚", "颗", "顆"}


def test_the_runs_are_the_numbers_before_anything_is_cut_off() -> None:
    assert number_runs("3000一个") == [(0, 5)]
    assert number_spans("3000一个") == [(0, 4), (4, 5)]
