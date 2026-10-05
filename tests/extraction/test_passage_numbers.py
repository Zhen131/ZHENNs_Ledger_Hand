"""Tests of finding the numbers written in a text.

The rule leans towards finding too much: anything that could be a number is
one. Every text below is invented.
"""

from __future__ import annotations

import pytest

from ledger_hand.extraction.passage_numbers import number_spans


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
