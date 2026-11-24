"""Tests of reading which listed trade the user picks, and which amount follows."""

from __future__ import annotations

import pytest

from ledger_hand.assistant.picking import (
    NotPicked,
    Picked,
    is_cancel,
    read_follower,
    read_pick,
)
from ledger_hand.core.trade import Amount


@pytest.mark.parametrize(
    "answer",
    [
        "2",
        "#2",
        "No. 2",
        "第二笔",
        "第2个",
        "第二",
        "选第二个",
        "第 2 笔",
        "second",
        "the second one",
        "the 2nd",
        "2nd",
        "the second trade",
        "２",
        "第二笔。",
    ],
)
def test_ways_of_saying_the_second(answer: str) -> None:
    assert read_pick(answer, 3) == Picked(number=2)


@pytest.mark.parametrize("answer", ["最后一笔", "最后那笔", "the last one", "Last", "最后"])
def test_ways_of_saying_the_last(answer: str) -> None:
    assert read_pick(answer, 4) == Picked(number=4)


@pytest.mark.parametrize("answer", ["3", "第三笔", "third", "0", "第十笔"])
def test_a_number_outside_the_list_is_not_taken(answer: str) -> None:
    picked = read_pick(answer, 2)
    assert isinstance(picked, NotPicked)
    assert "runs from 1 to 2" in picked.why


@pytest.mark.parametrize(
    "answer",
    ["BTC那笔", "早上那笔", "两笔都删", "2笔", "第二笔和第一笔", "", "the second and first"],
)
def test_anything_else_is_not_read(answer: str) -> None:
    picked = read_pick(answer, 3)
    assert isinstance(picked, NotPicked)
    assert "could not read" in picked.why


OFFERED = (Amount.TOTAL, Amount.PRICE)


@pytest.mark.parametrize(
    ("answer", "follows"),
    [
        ("1", Amount.TOTAL),
        ("第一种", Amount.TOTAL),
        ("the first one", Amount.TOTAL),
        ("总额", Amount.TOTAL),
        ("总额跟着变", Amount.TOTAL),
        ("让总额跟着变", Amount.TOTAL),
        ("total", Amount.TOTAL),
        ("2", Amount.PRICE),
        ("第二种", Amount.PRICE),
        ("成交价", Amount.PRICE),
        ("price", Amount.PRICE),
        ("单价跟着变", Amount.PRICE),
    ],
)
def test_which_amount_follows(answer: str, follows: Amount) -> None:
    assert read_follower(answer, OFFERED) is follows


@pytest.mark.parametrize("answer", ["3", "数量", "quantity", "随便", "都行", ""])
def test_an_amount_not_offered_or_no_amount_is_not_taken(answer: str) -> None:
    assert read_follower(answer, OFFERED) is None


def test_cancel_takes_the_recording_flows_words() -> None:
    assert is_cancel("cancel")
    assert is_cancel("取消")
    assert not is_cancel("算了吧")
