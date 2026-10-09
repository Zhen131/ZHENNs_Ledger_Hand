"""Tests of reading the model's reply to a split: the pieces of each trade, or why it is unreadable.

Every reply below is invented. Nothing is sent to a model.
"""

from __future__ import annotations

import json

import pytest

from ledger_hand.extraction.prompting import PROBLEM_MARK
from ledger_hand.extraction.split_table import (
    MAX_PIECES,
    MAX_SPLIT_REPLY_CHARACTERS,
    MAX_SPLIT_TRADES,
    SPLIT_TABLE,
    SplitExample,
    SplitProblem,
    SplitPromptVersion,
    SplitUnreadable,
    example_split_reply,
    read_split_reply,
)
from ledger_hand.ports import FinishReason, ModelReply, ReplyRecord


def reply(text: str, finish: FinishReason = FinishReason.STOPPED) -> ModelReply:
    record = ReplyRecord(
        model="scripted", elapsed_seconds=0.0, prompt_tokens=None, reply_tokens=None, finish=finish
    )
    return ModelReply(text=text, record=record)


def test_the_pieces_of_each_trade_are_read_in_order_as_written() -> None:
    text = json.dumps(
        {"trades": [{"pieces": ["今天在 OKX", "买了 1 ETH"]}, {"pieces": [" 卖了 2 SOL "]}]},
        ensure_ascii=False,
    )

    assert read_split_reply(reply(text)) == (("今天在 OKX", "买了 1 ETH"), (" 卖了 2 SOL ",))


def test_no_trade_and_a_trade_with_no_piece_are_read() -> None:
    assert read_split_reply(reply('{"trades": []}')) == ()
    assert read_split_reply(reply('{"trades": [{"pieces": []}]}')) == ((),)


def test_keys_the_table_does_not_have_are_ignored() -> None:
    text = '{"note": 1, "trades": [{"pieces": ["a"], "why": "x"}]}'

    assert read_split_reply(reply(text)) == (("a",),)


@pytest.mark.parametrize(
    ("text", "problem"),
    [
        ("not json", SplitProblem.NOT_JSON),
        ('{"trades": [{"pieces": [NaN]}]}', SplitProblem.NOT_JSON),
        ('{"trades": [], "trades": []}', SplitProblem.REPEATED_KEY),
        ('{"rows": []}', SplitProblem.NO_TRADES_LIST),
        ("[]", SplitProblem.NO_TRADES_LIST),
        ('{"trades": {}}', SplitProblem.NO_TRADES_LIST),
        ('{"trades": ["a"]}', SplitProblem.TRADE_NOT_AN_OBJECT),
        ('{"trades": [{}]}', SplitProblem.NO_PIECES_LIST),
        ('{"trades": [{"pieces": "a"}]}', SplitProblem.NO_PIECES_LIST),
        ('{"trades": [{"pieces": [1]}]}', SplitProblem.PIECE_NOT_TEXT),
        ('{"trades": [{"pieces": ["\\ud800"]}]}', SplitProblem.PIECE_NOT_TEXT),
    ],
)
def test_a_reply_that_misses_the_shape_says_which_part(text: str, problem: SplitProblem) -> None:
    assert read_split_reply(reply(text)) == SplitUnreadable(problem)


def test_a_reply_cut_off_at_the_length_limit_is_not_read() -> None:
    whole = '{"trades": []}'

    assert read_split_reply(reply(whole, FinishReason.LENGTH_LIMIT)) == SplitUnreadable(
        SplitProblem.CUT_OFF
    )


def test_too_long_too_many_trades_and_too_many_pieces_are_refused() -> None:
    too_long = '{"trades": []}' + " " * MAX_SPLIT_REPLY_CHARACTERS
    many_trades = json.dumps({"trades": [{"pieces": []}] * (MAX_SPLIT_TRADES + 1)})
    many_pieces = json.dumps({"trades": [{"pieces": ["a"] * (MAX_PIECES + 1)}]})

    assert read_split_reply(reply(too_long)) == SplitUnreadable(SplitProblem.TOO_LONG)
    assert read_split_reply(reply(many_trades)) == SplitUnreadable(SplitProblem.TOO_MANY_TRADES)
    assert read_split_reply(reply(many_pieces)) == SplitUnreadable(SplitProblem.TOO_MANY_PIECES)


def test_an_example_is_written_as_the_table_and_reads_back() -> None:
    example = SplitExample("x", (("a", "b"), ()))

    written = example_split_reply(example)

    assert json.loads(written) == {"trades": [{"pieces": ["a", "b"]}, {"pieces": []}]}
    assert read_split_reply(reply(written)) == example.trades


def test_the_table_asks_for_a_list_of_trades_each_with_a_list_of_pieces() -> None:
    trades = SPLIT_TABLE["properties"]["trades"]  # type: ignore[index]

    assert SPLIT_TABLE["required"] == ["trades"]
    assert trades["items"]["required"] == ["pieces"]
    assert trades["items"]["properties"]["pieces"]["items"] == {"type": "string"}


def test_the_words_for_asking_again_must_hold_the_mark_once() -> None:
    with pytest.raises(ValueError, match="once"):
        SplitPromptVersion(name="x", instructions="i", examples=(), ask_again="no mark")

    assert SplitPromptVersion("x", "i", (), f"again: {PROBLEM_MARK}").name == "x"
