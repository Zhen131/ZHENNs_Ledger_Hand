"""Tests of the second prompt version's own examples: they obey its rules and show the owner's way.

The examples added after the first prompt's ten are held to the rules the
first prompt's examples are held to (``test_prompt``): every field of every
row is a piece of its passage, every side one of the three words, every
number and time one the core reads, every reply read back as its rows with
all eleven fields. Every coin is one the built-in table knows. They are
written in the owner's way: buys only, no space at all, and a trade in each.

Each way of writing they are there to show is checked by what can be seen:
an amount with U that is the total and no quantity; a long opinion with a
number in it that is not the price, before the trade and after it, without
the mark that sets it apart; a quantity, a price and a fee right against the
Chinese; the owner's words for a buy; and two trades sharing the time and
the exchange, each with an opinion in its own part. Their prices,
quantities and fees are none of the voice set's gold values for the same
field. Nothing here sends anything to a model.
"""

from __future__ import annotations

import json
import re
from decimal import Decimal

import pytest

from evals.gold import Split, load_set
from evals.voice import VOICE_SET
from ledger_hand.core.coins import BUILT_IN_TABLE
from ledger_hand.core.numbers import Recognised, read_number
from ledger_hand.core.timeparse import TimeRecognised, read_time
from ledger_hand.extraction.passage import Passage, Piece
from ledger_hand.extraction.prompting import Example, ExampleRow, example_reply
from ledger_hand.extraction.prompts.second_examples import OWNER_EXAMPLES
from ledger_hand.extraction.reply_parser import ReplyRows, read_reply
from ledger_hand.extraction.reply_table import COPIED_FIELDS, SIDE_WORDS, Field
from ledger_hand.ports import FinishReason, ModelReply, ReplyRecord
from tests.extraction.scripted_runs import NOW, ZONE

NUMBER_FIELDS = (Field.QUANTITY, Field.PRICE, Field.TOTAL, Field.FEE)
EXAMPLE_ROWS = [(example, row) for example in OWNER_EXAMPLES for row in example.rows]
# The marks that set an opinion apart from the facts of its trade.
APART = "，。；"
# The fields whose numbers must be none of the voice set's gold numbers for the same field.
OWN_NUMBERS = (Field.QUANTITY, Field.PRICE, Field.FEE)
CHINESE = re.compile(r"[一-鿿]")


def rows() -> list[ExampleRow]:
    return [row for _, row in EXAMPLE_ROWS]


def where(example: Example, row: ExampleRow, field: Field) -> int:
    """Where the phrase of ``field`` begins in the passage."""
    found = Passage(example.passage).find(row[field])
    assert isinstance(found, Piece)
    return found.start


# --- the examples obey the rules ----------------------------------------------------


@pytest.mark.parametrize(("example", "row"), EXAMPLE_ROWS)
def test_every_field_of_every_example_is_a_piece_of_its_passage(
    example: Example, row: ExampleRow
) -> None:
    passage = Passage(example.passage)

    for field in COPIED_FIELDS:
        if row.get(field):
            found = passage.find(row[field])
            assert isinstance(found, Piece), (field, row[field])
            assert found.text == row[field], (field, row[field])


@pytest.mark.parametrize(("example", "row"), EXAMPLE_ROWS)
def test_every_side_is_one_of_the_three_words_and_every_trade_a_buy(
    example: Example, row: ExampleRow
) -> None:
    assert row.get(Field.SIDE, "") in SIDE_WORDS
    assert row[Field.SIDE] == "buy"


@pytest.mark.parametrize(("example", "row"), EXAMPLE_ROWS)
def test_every_number_and_time_of_every_example_is_one_the_core_reads(
    example: Example, row: ExampleRow
) -> None:
    allowed = tuple(row[field] for field in (Field.COIN, Field.FEE_CURRENCY) if row.get(field))
    for field in NUMBER_FIELDS:
        if row.get(field):
            assert isinstance(read_number(row[field], allowed), Recognised), row[field]
    if row.get(Field.TIME):
        assert isinstance(read_time(row[Field.TIME], NOW, ZONE), TimeRecognised), row[Field.TIME]


@pytest.mark.parametrize("example", OWNER_EXAMPLES)
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
    for example in OWNER_EXAMPLES:
        for row in json.loads(example_reply(example))["trades"]:
            assert list(row) == [field.value for field in Field]


@pytest.mark.parametrize(("example", "row"), EXAMPLE_ROWS)
def test_every_coin_and_currency_is_one_the_built_in_table_knows(
    example: Example, row: ExampleRow
) -> None:
    assert BUILT_IN_TABLE.find(row[Field.COIN]) is not None, row[Field.COIN]
    for field in (Field.PRICE_CURRENCY, Field.FEE_CURRENCY):
        assert not row.get(field), "a currency written next to its number is not copied again"


# --- the owner's way of writing --------------------------------------------------------


def test_every_example_has_a_trade_and_none_is_an_empty_table() -> None:
    assert all(example.rows for example in OWNER_EXAMPLES)


def test_no_example_has_a_space_and_every_one_is_in_chinese_on_okx() -> None:
    for example in OWNER_EXAMPLES:
        assert not re.search(r"\s", example.passage), example.passage
        assert CHINESE.search(example.passage)
        assert all(row[Field.PLATFORM] == "OKX" for row in example.rows)


def test_no_price_quantity_or_fee_is_a_number_of_the_voice_sets_gold_for_that_field() -> None:
    gold: dict[Field, set[Decimal]] = {field: set() for field in OWN_NUMBERS}
    for sentence in load_set(VOICE_SET, Split.VOICE):
        for trade in sentence.trades:
            for field in OWN_NUMBERS:
                value = trade.value(field)
                if isinstance(value, Decimal):
                    gold[field].add(value)
    assert all(gold.values())

    for example, row in EXAMPLE_ROWS:
        allowed = (row[Field.COIN],)
        for field in OWN_NUMBERS:
            if row.get(field):
                reading = read_number(row[field], allowed)
                assert isinstance(reading, Recognised)
                assert reading.value not in gold[field], (example.passage, field)


# --- what the examples are there to show -------------------------------------------------


def test_an_amount_with_u_is_the_total_with_no_quantity_after_bu_and_before_mai_le_dian() -> None:
    shown = [
        example.passage
        for example, row in EXAMPLE_ROWS
        if row.get(Field.TOTAL, "").endswith("U")
        and not row[Field.TOTAL].endswith("USDT")
        and not row.get(Field.QUANTITY)
    ]

    assert any(re.search(r"补了?\d", passage) for passage in shown)
    assert any(re.search(r"\dU买了点", passage) for passage in shown)
    assert any("再补" in example.passage for example in OWNER_EXAMPLES)


def long_opinions() -> list[tuple[Example, ExampleRow]]:
    """Rows whose opinion has several clauses and a number that is not the row's price."""
    found = []
    for example, row in EXAMPLE_ROWS:
        opinion = row.get(Field.OPINION, "")
        numbers = re.findall(r"\d+(?:\.\d+)?%?", opinion)
        if "，" in opinion and numbers and row.get(Field.PRICE) not in numbers:
            found.append((example, row))
    return found


def test_a_long_opinion_with_another_number_is_said_before_one_trade_and_after_another() -> None:
    before = after = 0
    for example, row in long_opinions():
        start = where(example, row, Field.OPINION)
        end = start + len(row[Field.OPINION])
        facts = [where(example, row, f) for f in (Field.PRICE, Field.TIME) if row.get(f)]
        if end < min(facts):
            before += 1
            assert example.passage[end] in APART
        if start > max(facts):
            after += 1
            assert example.passage[start - 1] in APART
            assert end == len(example.passage)

    assert before >= 1
    assert after >= 1


def test_no_opinion_holds_the_mark_that_sets_it_apart() -> None:
    for _, row in EXAMPLE_ROWS:
        opinion = row.get(Field.OPINION, "")
        assert opinion and opinion[0] not in APART and opinion[-1] not in APART


def test_quantity_price_and_fee_are_written_right_against_the_chinese() -> None:
    passages_rows = EXAMPLE_ROWS

    assert any(
        re.fullmatch(r"\d[\d.]*个", row.get(Field.QUANTITY, ""))
        and ("成交" + row[Field.QUANTITY]) in example.passage
        for example, row in passages_rows
    )
    assert any(
        re.fullmatch(r"\d[\d.]*[A-Z]+", row.get(Field.FEE, ""))
        and ("手续费" + row[Field.FEE]) in example.passage
        for example, row in passages_rows
    )
    assert any(
        row.get(Field.PRICE) and (row[Field.PRICE] + "一个") in example.passage
        for example, row in passages_rows
    )


@pytest.mark.parametrize("words", ["买到", "买了点", "补仓", "限价单"])
def test_the_owners_words_for_a_buy_are_each_in_an_example_of_buys(words: str) -> None:
    showing = [example for example in OWNER_EXAMPLES if words in example.passage]

    assert showing
    assert all(row[Field.SIDE] == "buy" for example in showing for row in example.rows)


def test_a_limit_order_filled_is_a_buy() -> None:
    assert any(
        "限价单" in example.passage and "触发后成交" in example.passage
        for example in OWNER_EXAMPLES
    )


def test_two_trades_share_the_time_and_exchange_and_each_has_an_opinion_in_its_own_part() -> None:
    shown = 0
    for example in OWNER_EXAMPLES:
        if len(example.rows) != 2:
            continue
        one, other = example.rows
        shared = (Field.TIME, Field.PLATFORM)
        assert all(one[f] == other[f] and example.passage.count(one[f]) == 1 for f in shared)
        assert one[Field.OPINION] != other[Field.OPINION]
        own_facts = max(where(example, one, f) for f in (Field.PRICE, Field.FEE))
        assert where(example, one, Field.OPINION) < own_facts
        assert where(example, other, Field.OPINION) > own_facts
        shown += 1

    assert shown >= 1
