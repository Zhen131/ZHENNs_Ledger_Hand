"""Reading the user's answer when the program asks which trade, or which amount follows.

When more than one trade matches a change or a deletion, the program lists
them, numbered from 1 in time order, and asks which one; when a change to
the quantity, the price or the total leaves the three out of step, it asks
which of the other two follows. The user's next words are the answer, and
they are read here, by rules, never by the model.

``read_pick`` reads a number among the listed trades. Taken, after the
answer is tidied (``extraction.answer_words.tidy``), and with nothing
else in the answer:

- a number written in digits: "2", "#2", "no. 2";
- "第" and a number, in digits or Chinese ("第二", "第2"), with or
  without "笔", "个", "条" or "项" after it, and "选" or "要" before it;
- an English ordinal: "second", "2nd", "the second", "the second one",
  "the second trade", up to the tenth;
- the last one: "最后一笔", "最后一个", "最后那笔", "最后", "last",
  "the last one", "the last trade".

A number outside the list is not taken (``NotPicked`` says why), and
nothing is guessed from anything else.

``read_follower`` reads which of two amounts follows: "1" or "2" and the
same ordinal words ("第一种", "the first one"), or the amount's name
("总额", "total", "成交价", "price", "数量", "quantity"), alone or with
"跟着变" and the like around it. A name not among the two offered is not
taken.

Names defined here: ``MOST_LISTED``, ``Picked``, ``NotPicked``,
``read_pick``, ``read_follower`` and ``is_cancel``.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from ledger_hand.core.followup import Cell
from ledger_hand.core.trade import Amount
from ledger_hand.extraction.answer_words import CANCEL_WORDS, CELL_WORDS, tidy

# How many matching trades the program lists and asks about. More than this
# is not read at a glance; the program then asks the user to say more. This
# is a guess, to be checked against how the person reads the list.
MOST_LISTED = 10

_CHINESE = {
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}
_ENGLISH = {
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
    "sixth": 6,
    "seventh": 7,
    "eighth": 8,
    "ninth": 9,
    "tenth": 10,
}
_DIGITS = re.compile(r"^(?:#|no\.? ?)?(?P<n>[0-9]{1,2})$")
_DI = re.compile(
    r"^(?:选|要)?第 ?(?P<n>[0-9]{1,2}|[一二三四五六七八九十]) ?(?:笔|个|条|项|种)?(?:交易)?$"
)
_ORDINAL = re.compile(
    r"^(?:the )?(?:(?P<word>[a-z]+)|(?P<n>[0-9]{1,2})(?:st|nd|rd|th))(?: one| trade)?$"
)
_LAST = frozenset(
    {
        "最后一笔",
        "最后一个",
        "最后一条",
        "最后那笔",
        "最后那个",
        "最后",
        "last",
        "the last",
        "last one",
        "the last one",
        "the last trade",
    }
)


@dataclass(frozen=True)
class Picked:
    """The trade picked: its number in the list, from 1."""

    number: int


@dataclass(frozen=True)
class NotPicked:
    """No trade was picked, and why, in one sentence for the user."""

    why: str


def is_cancel(answer: str) -> bool:
    """Whether the answer drops what is waiting, with the recording flow's own words."""
    return tidy(answer) in CANCEL_WORDS


def _number(answer: str, last: int) -> int | None:
    """The number an answer says, by the rules above; ``None`` when it says none."""
    text = tidy(answer)
    if text in _LAST:
        return last
    for pattern in (_DIGITS, _DI):
        found = pattern.fullmatch(text)
        if found is not None:
            n = found.group("n")
            return int(n) if n.isdigit() else _CHINESE[n]
    found = _ORDINAL.fullmatch(text)
    if found is None:
        return None
    if found.group("n") is not None:
        return int(found.group("n"))
    return _ENGLISH.get(found.group("word"))


def read_pick(answer: str, count: int) -> Picked | NotPicked:
    """Which of ``count`` listed trades the answer picks."""
    number = _number(answer, count)
    if number is None:
        return NotPicked(why=f"I could not read {answer.strip()!r} as the number of a trade.")
    if not 1 <= number <= count:
        return NotPicked(why=f"There is no trade {number} in the list; it runs from 1 to {count}.")
    return Picked(number=number)


# The names of the three amounts, beside the recording flow's words for them.
_NAMES: dict[Amount, tuple[str, ...]] = {
    Amount.QUANTITY: CELL_WORDS[Cell.QUANTITY],
    Amount.PRICE: (*CELL_WORDS[Cell.PRICE], "成交价", "成交价格", "均价"),
    Amount.TOTAL: (*CELL_WORDS[Cell.TOTAL], "总价格"),
}
_AROUND = re.compile(r"^(?:让|改)?(?P<name>.+?) ?(?:跟着变|跟着改|跟着走|变|改|follows|changes)?$")


def read_follower(answer: str, offered: Sequence[Amount]) -> Amount | None:
    """Which of the ``offered`` amounts the answer says follows; ``None`` when it says none."""
    number = _number(answer, len(offered))
    if number is not None:
        return offered[number - 1] if 1 <= number <= len(offered) else None
    found = _AROUND.fullmatch(tidy(answer))
    name = found.group("name") if found is not None else ""
    named = [amount for amount in offered if name in _NAMES[amount]]
    return named[0] if len(named) == 1 else None
