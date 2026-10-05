"""Tests of the 50 test sentences and their gold answers.

These tests only read the two set files; nothing here calls a model. The
final set is read like the debug set, to check its coverage, that it
repeats no prompt example, and that its gold answers keep the rules.
"""

from __future__ import annotations

import pytest

from evals.cells import tidy_text
from evals.coverage import Item, coverage_table, feature_holds, items_of
from evals.gold import (
    DEBUG_SET,
    FINAL_SET,
    GoldTrade,
    Group,
    Sentence,
    Split,
    gold_draft,
    load_set,
)
from ledger_hand.core.coins import BUILT_IN_TABLE
from ledger_hand.core.numbers import NotANumber, Recognised, Unsure, read_number
from ledger_hand.core.timeparse import TimeRecognised, read_time
from ledger_hand.core.trade import OccurredTime, TradeRecord
from ledger_hand.core.validation import DraftProblems, check_draft
from ledger_hand.extraction.prompts.first_examples import FIRST_EXAMPLES
from ledger_hand.extraction.reply_table import Field
from ledger_hand.extraction.unit_currency import currencies_in_unit, word_identity
from tests.live.test_live_extraction import PASSAGES as SMOKE_PASSAGES

DEBUG = load_set(DEBUG_SET, Split.DEBUG)
FINAL = load_set(FINAL_SET, Split.FINAL)
EVERY = DEBUG + FINAL
SCORED_TRADES = [
    pytest.param(sentence, trade, id=f"{sentence.id}-{at}")
    for sentence in EVERY
    for at, trade in enumerate(sentence.trades)
]
NUMBER_FIELDS = (Field.QUANTITY, Field.PRICE, Field.TOTAL, Field.FEE)
# Asked for in both sets by name: the ways of writing a number that the
# extraction is known to find hard.
WRITINGS = (
    Item.PER_PIECE,
    Item.GAP_BEFORE_MULTIPLIER,
    Item.SPACE_THOUSANDS,
    Item.THOUSANDS_COMMA,
    Item.ADJACENT_NUMBERS,
)


def test_thirty_sentences_to_tune_against_and_twenty_kept_for_the_final_run() -> None:
    assert len(DEBUG) == 30
    assert len(FINAL) == 20
    assert {s.split for s in DEBUG} == {Split.DEBUG}
    assert {s.split for s in FINAL} == {Split.FINAL}


def test_ids_and_texts_are_unique() -> None:
    assert len({s.id for s in EVERY}) == 50
    assert len({tidy_text(s.text) for s in EVERY}) == 50


@pytest.mark.parametrize("item", list(Item), ids=lambda item: item.name)
def test_every_item_is_covered_in_both_sets(item: Item) -> None:
    table = coverage_table(EVERY)

    assert table[item][Split.DEBUG] >= 1
    assert table[item][Split.FINAL] >= 1


@pytest.mark.parametrize("item", WRITINGS, ids=lambda item: item.name)
def test_the_hard_writings_of_numbers_are_in_both_sets(item: Item) -> None:
    for sentences in (DEBUG, FINAL):
        assert any(item in items_of(s) for s in sentences if s.group is Group.SCORED)


@pytest.mark.parametrize("sentence", EVERY, ids=lambda s: s.id)
def test_every_hand_given_label_is_borne_out(sentence: Sentence) -> None:
    for feature in sentence.features:
        assert feature_holds(sentence, feature), feature


def test_the_kinds_of_trade_count_are_spread_alike() -> None:
    def share(sentences: tuple[Sentence, ...], item: Item) -> float:
        return sum(item in items_of(s) for s in sentences) / len(sentences)

    for item in (Item.ONE_TRADE, Item.TWO_TRADES, Item.THREE_OR_MORE, Item.NO_TRADE):
        assert abs(share(DEBUG, item) - share(FINAL, item)) <= 0.1, item


def test_no_sentence_repeats_a_prompt_example_or_a_smoke_passage() -> None:
    examples = {tidy_text(example.passage) for example in FIRST_EXAMPLES}
    smoke = {tidy_text(str(param.values[0])) for param in SMOKE_PASSAGES}

    for sentence in EVERY:
        assert tidy_text(sentence.text) not in examples, sentence.id
        assert tidy_text(sentence.text) not in smoke, sentence.id
        assert sentence.text not in {example.passage for example in FIRST_EXAMPLES}


def test_talk_and_passages_not_to_record_have_no_gold_trade() -> None:
    not_to_record = [s for s in EVERY if s.group is Group.NOT_TO_RECORD]

    assert all(not s.trades and s.kind is not None for s in not_to_record)
    assert len([s for s in DEBUG if s.group is Group.NOT_TO_RECORD]) == 4
    assert len([s for s in FINAL if s.group is Group.NOT_TO_RECORD]) == 4


@pytest.mark.parametrize(("sentence", "trade"), SCORED_TRADES)
def test_the_check_of_a_draft_finds_missing_exactly_what_the_gold_answer_says(
    sentence: Sentence, trade: GoldTrade
) -> None:
    result = check_draft(gold_draft(trade, sentence.text), BUILT_IN_TABLE, sentence.now)

    if trade.missing:
        assert isinstance(result, DraftProblems)
        assert result.missing == trade.missing
        assert result.violations == ()
    else:
        assert isinstance(result, TradeRecord), result


def allowed_units(trade: GoldTrade) -> tuple[str, ...]:
    """The unit words extraction gives the number reader: the trade's coin and fee coin."""
    phrases = (trade.cell(Field.COIN).phrase, trade.cell(Field.FEE_CURRENCY).phrase)
    return tuple(phrase for phrase in phrases if phrase is not None)


@pytest.mark.parametrize(("sentence", "trade"), SCORED_TRADES)
def test_every_gold_number_is_the_core_reading_of_its_phrase(
    sentence: Sentence, trade: GoldTrade
) -> None:
    for field in NUMBER_FIELDS:
        cell = trade.cell(field)
        if cell.phrase is None:
            continue
        reading = read_number(cell.phrase, extra_units=allowed_units(trade))
        if cell.value is None:
            assert isinstance(reading, Unsure | NotANumber), (field, reading)
        else:
            assert isinstance(reading, Recognised), (field, reading)
            assert reading.value == cell.value, field


@pytest.mark.parametrize(("sentence", "trade"), SCORED_TRADES)
def test_every_gold_time_is_the_core_reading_of_its_phrase(
    sentence: Sentence, trade: GoldTrade
) -> None:
    cell = trade.cell(Field.TIME)
    if cell.phrase is None:
        return
    reading = read_time(cell.phrase, sentence.now, sentence.zone)
    if cell.value is None:
        assert not isinstance(reading, TimeRecognised)
    else:
        assert isinstance(reading, TimeRecognised), reading
        assert isinstance(cell.value, OccurredTime)
        assert reading.time == cell.value


@pytest.mark.parametrize(("sentence", "trade"), SCORED_TRADES)
def test_every_gold_coin_and_currency_is_what_its_phrase_names(
    sentence: Sentence, trade: GoldTrade
) -> None:
    for field in (Field.COIN, Field.PRICE_CURRENCY, Field.FEE_CURRENCY):
        cell = trade.cell(field)
        if cell.phrase is not None:
            assert word_identity(cell.phrase, BUILT_IN_TABLE) == cell.value, field
    for field in (Field.PLATFORM, Field.OPINION):
        cell = trade.cell(field)
        if cell.phrase is not None:
            assert cell.value == cell.phrase, field


@pytest.mark.parametrize(("sentence", "trade"), SCORED_TRADES)
def test_a_currency_written_with_a_number_is_in_the_gold_answer(
    sentence: Sentence, trade: GoldTrade
) -> None:
    # Extraction takes the unit of a price, total or fee as its currency
    # when no currency is written apart, so the gold answer must hold it.
    for number_field, currency_field in (
        (Field.PRICE, Field.PRICE_CURRENCY),
        (Field.TOTAL, Field.PRICE_CURRENCY),
        (Field.FEE, Field.FEE_CURRENCY),
    ):
        phrase = trade.cell(number_field).phrase
        if phrase is None:
            continue
        reading = read_number(phrase, extra_units=allowed_units(trade))
        if not isinstance(reading, Recognised) or reading.unit is None:
            continue
        named = currencies_in_unit(reading.unit, BUILT_IN_TABLE, allowed_units(trade))
        if named:
            assert trade.value(currency_field) == named[0].identity, number_field


@pytest.mark.parametrize("sentence", EVERY, ids=lambda s: s.id)
def test_every_gold_phrase_stands_in_the_passage(sentence: Sentence) -> None:
    for trade in sentence.trades:
        for field, cell in trade.cells.items():
            if cell.phrase is not None:
                assert cell.phrase in sentence.text, field
