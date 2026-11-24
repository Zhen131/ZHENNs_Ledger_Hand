"""Tests of telling a period cut out of a longer time the user said from a fair copy."""

from __future__ import annotations

import pytest

from ledger_hand.assistant.judging import MisstepKind
from ledger_hand.assistant.period_cuts import cut_misstep, is_cut
from ledger_hand.ledger.invented_book import INVENTED_NOW, INVENTED_ZONE


def cut(words: str, *said: str) -> bool:
    return is_cut(words, said, INVENTED_NOW, INVENTED_ZONE)


@pytest.mark.parametrize(
    ("words", "said"),
    [
        ("9月", "把9月13号那笔BTC的时间改成9月13号上午10点15分"),
        ("9月", "把9月30号那笔BTC删掉"),
        ("11月", "把11月4号那笔ADA删掉"),
        ("10月1号", "10月1号到10月15号我买了什么"),
        ("10月15号", "10月1号到10月15号我买了什么"),
        ("October 1", "What did I buy from October 1 to October 15?"),
        ("12月", "2025年12月我买了什么"),
        ("10月", "10月6号那天我都做了什么交易"),
    ],
)
def test_words_cut_out_of_a_longer_time_are_cut(words: str, said: str) -> None:
    assert cut(words, said)


@pytest.mark.parametrize(
    ("words", "said"),
    [
        ("10月", "10月份我买了什么"),
        ("10月", "今年10月我买了什么"),
        ("9月25号", "把9月25号那笔ADA删掉"),
        ("October 6", "Delete the trade from October 6"),
        ("上个月", "上个月我卖了什么"),
        ("this year", "How much ETH did I buy this year?"),
    ],
)
def test_a_whole_time_is_not_cut(words: str, said: str) -> None:
    assert not cut(words, said)


def test_words_found_once_on_their_own_are_a_fair_copy() -> None:
    assert not cut("9月", "9月13号那笔和9月的那些都看看")


def test_words_found_on_their_own_in_an_earlier_sentence_are_a_fair_copy() -> None:
    assert not cut("9月", "9月我买了什么", "把9月13号那笔删掉")


def test_words_found_nowhere_are_left_to_the_copy_check() -> None:
    assert not cut("2023-09-25", "把9月25号那笔ADA删掉")


def test_the_wrong_step_is_worded_as_a_period_not_copied() -> None:
    misstep = cut_misstep("9月")
    assert misstep.kind is MisstepKind.NOT_COPIED
    assert misstep.detail.startswith("'period' is '9月'")
