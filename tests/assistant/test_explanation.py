"""Tests of checking the model's words beside a table, and its answer without one."""

from __future__ import annotations

import pytest

from ledger_hand.assistant.explanation import (
    LONGEST_EXPLANATION,
    check_explanation,
    check_plain_answer,
    numbers_in,
)

HEADER = ("Time: 2026-10-01 to 2026-10-31", "Asset: all assets", "Trades in this time: 2")
RESULT = '{"by_currency":[{"currency":"USDT","spent_on_buys":"61940"}]}'
SAID = "我10月一共买了多少钱的币"
AGAINST = (*HEADER, RESULT, SAID)


def test_only_arabic_digits_count_with_their_point_and_thousands_commas() -> None:
    assert numbers_in("你10月一共买入了两笔，共 61,940 USDT，0.0081 个") == (
        "10",
        "61,940",
        "0.0081",
    )
    assert numbers_in("2026-10-06") == ("2026", "10", "06")
    assert numbers_in("共２笔") == ("2",)
    assert numbers_in("一共两笔") == ()


def test_a_comma_between_two_numbers_is_not_a_thousands_comma() -> None:
    assert numbers_in("2,61940") == ("2", "61940")
    assert numbers_in("1,2") == ("1", "2")


def test_words_whose_every_number_is_in_the_table_pass() -> None:
    assert check_explanation("你10月一共买入了两笔，共 61,940 USDT", AGAINST) is None


def test_one_number_not_in_the_table_withholds_the_words() -> None:
    withheld = check_explanation("你10月一共买入了两笔，共 61,950 USDT", AGAINST)

    assert withheld is not None
    assert withheld.reason == "61,950 is not in what the ledger returned"


def test_numbers_are_compared_by_value() -> None:
    against = ('{"total":"1000.5"}',)

    assert check_explanation("1000.50", against) is None
    assert check_explanation("1,000.5", against) is None
    assert check_explanation("1000.5000", against) is None


def test_a_number_rounded_is_not_the_number() -> None:
    withheld = check_explanation("about 281.39", ('{"total":"281.394"}',))

    assert withheld is not None


def test_a_date_counts_as_its_parts() -> None:
    against = ("Time: 2026-10-06",)

    assert check_explanation("On 10/6 there were trades", against) is None
    assert check_explanation("10月6号", against) is None
    assert check_explanation("10月7号", against) is not None


def test_numbers_the_user_said_may_be_said_back() -> None:
    assert check_explanation("最近7天没有交易", ("Trades: 0", "最近7天我买了什么")) is None


def test_words_too_long_are_withheld() -> None:
    withheld = check_explanation("好" * (LONGEST_EXPLANATION + 1), AGAINST)

    assert withheld is not None
    assert "longer than" in withheld.reason


@pytest.mark.parametrize(
    "words",
    ["比特币明天大概 61000", "可能涨到 65,000", "现在价格 0.5", "2026年会涨"],
)
def test_an_answer_with_no_lookup_holds_no_amount(words: str) -> None:
    withheld = check_plain_answer(words)

    assert withheld is not None
    assert "looks like an amount" in withheld.reason


@pytest.mark.parametrize(
    "words",
    ["你可以问我 10 月的交易", "我能答四样：交易、汇总、持仓、资产", "I can't tell you that."],
)
def test_an_answer_with_no_lookup_and_no_amount_passes(words: str) -> None:
    assert check_plain_answer(words) is None
