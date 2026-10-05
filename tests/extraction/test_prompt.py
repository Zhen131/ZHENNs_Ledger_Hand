"""Tests of the first prompt version: what it tells the model, and that its examples obey it.

The examples are held to the same rules as the model: every field of every
row is a piece of its passage, every number and time in them is one the core
reads, and between them they cover the kinds of passage the prompt has to
show.
"""

from __future__ import annotations

import json
import re

import pytest

from ledger_hand.core.coins import BUILT_IN_TABLE
from ledger_hand.core.numbers import Recognised, read_number
from ledger_hand.core.timeparse import TimeRecognised, read_time
from ledger_hand.extraction import prompts
from ledger_hand.extraction.passage import Passage, Piece
from ledger_hand.extraction.prompting import (
    PROBLEM_MARK,
    Example,
    PromptVersion,
    build_messages,
    example_reply,
)
from ledger_hand.extraction.prompts import first, first_examples
from ledger_hand.extraction.prompts.first import FIRST_PROMPT
from ledger_hand.extraction.prompts.first_examples import FIRST_EXAMPLES
from ledger_hand.extraction.reply_parser import ReplyProblem, ReplyRows, read_reply
from ledger_hand.extraction.reply_table import COPIED_FIELDS, SIDE_WORDS, Field
from ledger_hand.extraction.unit_currency import word_identity
from ledger_hand.ports import FinishReason, ModelReply, ReplyRecord, Role
from tests.extraction.scripted_runs import NOW, ZONE

CHINESE = re.compile(r"[一-鿿]")
LATIN = re.compile(r"[A-Za-z]")
NUMBER_FIELDS = (Field.QUANTITY, Field.PRICE, Field.TOTAL, Field.FEE)
EXAMPLE_ROWS = [(example, row) for example in FIRST_EXAMPLES for row in example.rows]


def flat(text: str) -> str:
    return " ".join(text.split())


# --- what the instructions say -------------------------------------------------------


@pytest.mark.parametrize(
    "said",
    [
        "You never calculate, convert, translate, correct or guess anything.",
        "Copy, never rewrite.",
        'Leave a field "" when the passage does not say it.',
        "Never fill in a market price, a date, a fee or a currency the passage does not write.",
        'If it mentions no trade, reply {"trades": []}.',
        "with one row for each trade the passage mentions",
        "copied character for character",
        "Each field is one unbroken piece of the passage.",
        "Two coins, or two separate buys or sells, are two rows.",
    ],
)
def test_the_instructions_say_copy_only_and_leave_empty(said: str) -> None:
    assert said in flat(FIRST_PROMPT.instructions)


def test_the_instructions_name_every_field_of_the_table() -> None:
    for field in Field:
        assert f"{field.value}" in FIRST_PROMPT.instructions


def test_the_words_for_asking_again_hold_the_place_for_the_problem_once() -> None:
    assert FIRST_PROMPT.ask_again.count(PROBLEM_MARK) == 1
    with pytest.raises(ValueError, match="once"):
        PromptVersion("broken", "x", (), "no mark here")


def test_each_version_and_its_examples_live_in_files_of_their_own() -> None:
    assert FIRST_PROMPT.examples is FIRST_EXAMPLES
    assert first.__name__ != first_examples.__name__
    assert first_examples.__name__.startswith(prompts.__name__)
    assert first.__doc__ and first_examples.__doc__ and prompts.__doc__


# --- the examples obey the rules ----------------------------------------------------


@pytest.mark.parametrize(("example", "row"), EXAMPLE_ROWS)
def test_every_field_of_every_example_is_a_piece_of_its_passage(
    example: Example, row: dict[Field, str]
) -> None:
    passage = Passage(example.passage)

    for field in COPIED_FIELDS:
        if row.get(field):
            found = passage.find(row[field])
            assert isinstance(found, Piece), (field, row[field])
            assert found.text == row[field], (field, row[field])


@pytest.mark.parametrize(("example", "row"), EXAMPLE_ROWS)
def test_every_side_of_every_example_is_one_of_the_three_words(
    example: Example, row: dict[Field, str]
) -> None:
    assert row.get(Field.SIDE, "") in SIDE_WORDS


@pytest.mark.parametrize(("example", "row"), EXAMPLE_ROWS)
def test_every_number_and_time_of_every_example_is_one_the_core_reads(
    example: Example, row: dict[Field, str]
) -> None:
    allowed = tuple(row[field] for field in (Field.COIN, Field.FEE_CURRENCY) if row.get(field))
    for field in NUMBER_FIELDS:
        if row.get(field):
            assert isinstance(read_number(row[field], allowed), Recognised), row[field]
    if row.get(Field.TIME):
        assert isinstance(read_time(row[Field.TIME], NOW, ZONE), TimeRecognised), row[Field.TIME]


@pytest.mark.parametrize("example", FIRST_EXAMPLES)
def test_every_example_reply_is_read_back_as_its_rows(example: Example) -> None:
    record = ReplyRecord(
        model="x",
        elapsed_seconds=0,
        prompt_tokens=None,
        reply_tokens=None,
        finish=FinishReason.STOPPED,
    )
    read = read_reply(ModelReply(text=example_reply(example), record=record))

    assert isinstance(read, ReplyRows)
    assert len(read.rows) == len(example.rows)
    for written, given in zip(read.rows, example.rows, strict=True):
        assert written.side is SIDE_WORDS[given.get(Field.SIDE, "")]
        assert dict(written.cells) == {f: t for f, t in given.items() if f is not Field.SIDE}


def test_the_example_replies_name_every_field_in_every_row() -> None:
    for example in FIRST_EXAMPLES:
        for row in json.loads(example_reply(example))["trades"]:
            assert list(row) == [field.value for field in Field]


# --- the examples cover what they have to show -------------------------------------------


def test_the_examples_are_in_chinese_in_english_and_mixed() -> None:
    passages = [example.passage for example in FIRST_EXAMPLES]

    assert any(CHINESE.search(p) and not LATIN.search(p) for p in passages)
    assert any(LATIN.search(p) and not CHINESE.search(p) for p in passages)
    assert any(CHINESE.search(p) and LATIN.search(p) for p in passages)


def test_the_examples_have_one_trade_several_and_none() -> None:
    counts = [len(example.rows) for example in FIRST_EXAMPLES]

    assert 1 in counts
    assert any(count >= 2 for count in counts)
    assert 0 in counts


def test_the_examples_without_a_trade_include_one_with_numbers_and_one_without() -> None:
    chatter = [example.passage for example in FIRST_EXAMPLES if not example.rows]

    assert any(re.search(r"\d", passage) for passage in chatter)
    assert any(not re.search(r"\d", passage) for passage in chatter)


def test_the_examples_leave_out_fields_the_passage_does_not_say() -> None:
    rows = [row for _, row in EXAMPLE_ROWS]

    assert any(Field.FEE not in row for row in rows)
    assert any(Field.TIME not in row for row in rows)
    assert any(set(row) == {Field.SIDE, Field.COIN} for row in rows)


def test_the_examples_include_a_fee_paid_in_a_coin_other_than_usdt() -> None:
    fee_coins = set()
    for _, row in EXAMPLE_ROWS:
        if row.get(Field.FEE_CURRENCY):
            fee_coins.add(word_identity(row[Field.FEE_CURRENCY], BUILT_IN_TABLE))
        elif row.get(Field.FEE):
            unit = read_number(row[Field.FEE], (row.get(Field.COIN, ""),))
            if isinstance(unit, Recognised) and unit.unit:
                fee_coins.add(word_identity(unit.unit, BUILT_IN_TABLE))

    assert fee_coins - {"USDT"}


def test_the_examples_include_opinions_said_within_the_sentence() -> None:
    with_opinion = [(example, row) for example, row in EXAMPLE_ROWS if row.get(Field.OPINION)]

    assert len(with_opinion) >= 2
    assert any(
        not example.passage.rstrip().endswith(row[Field.OPINION]) for example, row in with_opinion
    )


def test_the_examples_share_a_detail_said_once_for_two_trades() -> None:
    several = [example for example in FIRST_EXAMPLES if len(example.rows) >= 2]

    assert any(
        len({row.get(Field.TIME) for row in example.rows}) == 1 and example.rows[0].get(Field.TIME)
        for example in several
    )


# --- the messages ---------------------------------------------------------------------


def test_the_messages_are_the_instructions_the_examples_and_the_passage() -> None:
    messages = build_messages(FIRST_PROMPT, "买了 BTC")

    assert messages[0].role is Role.SYSTEM
    assert messages[0].content == FIRST_PROMPT.instructions
    pairs = messages[1:-1]
    assert len(pairs) == 2 * len(FIRST_EXAMPLES)
    for index, example in enumerate(FIRST_EXAMPLES):
        said, written = pairs[2 * index], pairs[2 * index + 1]
        assert (said.role, said.content) == (Role.USER, example.passage)
        assert (written.role, written.content) == (Role.ASSISTANT, example_reply(example))
    assert (messages[-1].role, messages[-1].content) == (Role.USER, "买了 BTC")


def test_asking_again_adds_one_message_with_the_problem() -> None:
    plain = build_messages(FIRST_PROMPT, "买了 BTC")
    again = build_messages(FIRST_PROMPT, "买了 BTC", ReplyProblem.NOT_JSON)

    assert again[:-1] == plain
    assert again[-1].role is Role.USER
    assert ReplyProblem.NOT_JSON.value in again[-1].content
    assert PROBLEM_MARK not in again[-1].content
