"""The small fixed word lists an answer is read against, and how an answer is tidied first.

An answer to a follow-up question is first read by rules. Where the answer
is a word rather than a number, a time or a coin (buy or sell, yes or no,
"no fee", skip this trade, drop the whole passage, which of several cells,
and the commands once every trade is settled), it is looked up in one of
the lists below, and only what a list holds is taken. Nothing is guessed
from a word that is not listed; such an answer goes on to be copied from by
the model, or is asked again.

Before it is looked up, an answer is tidied: full-width and other
compatibility forms become ordinary characters, letter case does not count,
runs of whitespace count as one space, whitespace at either end is dropped,
and so is one full stop or exclamation mark at the very end ("skip." is
"skip"). Nothing else is changed.

The lists hold their words already tidied.

Names defined here: ``tidy``, ``SIDE_WORDS``, ``YES_WORDS``, ``NO_WORDS``,
``NO_FEE_WORDS``, ``NOTHING_WORDS``, ``NOT_SAID_WORDS``, ``SKIP_WORDS``,
``CANCEL_WORDS``, ``DONE_WORDS``, ``REMOVE_WORDS``, ``FIRST_WORDS``,
``SECOND_WORDS``, ``CELL_WORDS`` and ``CONNECTING_WORDS``.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Mapping

from ledger_hand.core.followup import Cell
from ledger_hand.core.trade import Side

_ENDING_MARKS = ".。!！"


def tidy(answer: str) -> str:
    """``answer`` as the lists are looked up with."""
    text = " ".join(unicodedata.normalize("NFKC", answer).casefold().split())
    if text and text[-1] in _ENDING_MARKS:
        text = text[:-1].rstrip()
    return text


SIDE_WORDS: Mapping[str, Side] = {
    **dict.fromkeys(("buy", "bought", "买", "买了", "买入", "买的", "买进"), Side.BUY),
    **dict.fromkeys(("sell", "sold", "卖", "卖了", "卖出", "卖的", "卖掉"), Side.SELL),
}

YES_WORDS = frozenset(
    {"yes", "y", "yeah", "yep", "correct", "right", "是", "是的", "对", "对的", "没错", "确认"}
)
NO_WORDS = frozenset({"no", "n", "nope", "wrong", "不", "不是", "不对", "错", "错了"})

# Said for the fee: there was none, so it is zero.
NO_FEE_WORDS = frozenset(
    {
        "no",
        "none",
        "no fee",
        "zero",
        "free",
        "没有",
        "没",
        "无",
        "没有手续费",
        "无手续费",
        "免手续费",
        "免费",
    }
)

# Said for the platform or the note: leave it out.
NOTHING_WORDS = frozenset({"none", "nothing", "no", "leave it out", "没有", "无", "不填", "不要"})

# Said of one of several cells: the passage did not give it. Found anywhere
# in the answer, so that "the price was not said" and "价格原话没说" count.
NOT_SAID_WORDS = (
    "not said",
    "wasn't said",
    "not given",
    "not stated",
    "原话没说",
    "原话没有",
    "没说",
    "没有说",
    "没写",
)

SKIP_WORDS = frozenset(
    {
        "skip",
        "skip it",
        "skip this",
        "skip this trade",
        "跳过",
        "跳过这笔",
        "这笔跳过",
        "这笔不记",
        "不记这笔",
    }
)
CANCEL_WORDS = frozenset(
    {
        "cancel",
        "cancel all",
        "abandon",
        "discard",
        "取消",
        "取消整段",
        "放弃",
        "放弃整段",
        "都不记",
        "全部不记",
    }
)
DONE_WORDS = frozenset({"done", "finish", "finished", "ok", "完成", "好了", "就这样"})
# Followed by the trade's number: "remove 2", "去掉第 2 笔".
REMOVE_WORDS = ("remove", "drop", "delete", "去掉", "删掉", "删除", "拿掉")

# Which of two moments the clocks showed the same time at.
FIRST_WORDS = frozenset(
    {"1", "first", "the first", "earlier", "the earlier", "第一个", "第一", "前一个", "早的那个"}
)
SECOND_WORDS = frozenset(
    {"2", "second", "the second", "later", "the later", "第二个", "第二", "后一个", "晚的那个"}
)

# The words that name a cell, when the answer has to say which cell is wrong.
CELL_WORDS: Mapping[Cell, tuple[str, ...]] = {
    Cell.QUANTITY: ("quantity", "qty", "数量", "个数"),
    Cell.PRICE: ("unit price", "price", "价格", "单价", "价"),
    Cell.TOTAL: ("total", "总额", "总价", "总共", "一共", "合计", "总金额"),
    Cell.FEE: ("fee", "手续费"),
}

# Words that may stand between a cell's name and its value: "price is 94900".
CONNECTING_WORDS = (
    "should be",
    "is",
    "was",
    "=",
    ":",
    "应该是",
    "应为",
    "改成",
    "改为",
    "是",
    "为",
)
