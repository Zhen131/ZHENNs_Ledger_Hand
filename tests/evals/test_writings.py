"""Tests of the writings set: its coverage, that it repeats nothing, that its gold keeps the rules.

The set is read like the other two; nothing here calls a model. Every way
of writing a number it is made for has at least two sentences, and among
them Chinese and English passages. No sentence is one of the 50 test
sentences, a prompt example or a smoke passage, and no clause of one stands
in any prompt. Its gold answers are held to the same checks as those of the
50 sentences: the check of a draft finds missing exactly what they say, and
every number, time, coin and currency is the core's reading of its phrase.
"""

from __future__ import annotations

import io
import re
from pathlib import Path

import pytest

from evals import run as runner
from evals.cells import tidy_text
from evals.coverage import feature_holds
from evals.gold import DEBUG_SET, FINAL_SET, GoldTrade, Group, Sentence, Split, gold_draft, load_set
from evals.writings import (
    WRITINGS_SET,
    Context,
    Writing,
    coverage_markdown,
    writings_of,
    writings_table,
)
from ledger_hand.asking.prompts.bookkeeper import BOOKKEEPER_PROMPT
from ledger_hand.core.coins import BUILT_IN_TABLE
from ledger_hand.core.numbers import NotANumber, Recognised, Unsure, read_number
from ledger_hand.core.timeparse import TimeRecognised, read_time
from ledger_hand.core.trade import OccurredTime, TradeRecord
from ledger_hand.core.validation import DraftProblems, check_draft
from ledger_hand.extraction.prompting import example_reply
from ledger_hand.extraction.prompts.answer import ANSWER_PROMPT
from ledger_hand.extraction.prompts.first_examples import FIRST_EXAMPLES
from ledger_hand.extraction.prompts.screen import SCREEN_PROMPT
from ledger_hand.extraction.reply_table import Field
from ledger_hand.extraction.unit_currency import currencies_in_unit, word_identity
from tests.evals.test_sets import allowed_units
from tests.extraction.scripted_runs import table
from tests.fakes.scripted_model import ScriptedModel
from tests.live.test_live_extraction import PASSAGES as SMOKE_PASSAGES

WRITINGS = load_set(WRITINGS_SET, Split.WRITINGS)
FIFTY = load_set(DEBUG_SET, Split.DEBUG) + load_set(FINAL_SET, Split.FINAL)
TRADES = [
    pytest.param(sentence, trade, id=f"{sentence.id}-{at}")
    for sentence in WRITINGS
    for at, trade in enumerate(sentence.trades)
]
NUMBER_FIELDS = (Field.QUANTITY, Field.PRICE, Field.TOTAL, Field.FEE)
SHORTEST_CLAUSE = 8
_CLAUSE_ENDS = re.compile(r"[，,；;。.!！?？:：]")


def every_prompt_text() -> str:
    """Every word any prompt version holds: instructions, examples, their tables, asking again."""
    texts: list[str] = []
    for version, _ in runner.PROMPTS.values():
        texts += [version.instructions, version.ask_again]
        texts += [example.passage for example in version.examples]
        texts += [example_reply(example) for example in version.examples]
    texts += [SCREEN_PROMPT.instructions, SCREEN_PROMPT.ask_again]
    texts += [ANSWER_PROMPT.instructions, ANSWER_PROMPT.ask_again, *ANSWER_PROMPT.fields.values()]
    texts.append(BOOKKEEPER_PROMPT.instructions)
    return tidy_text("\n".join(texts))


def clauses(text: str) -> list[str]:
    return [
        piece
        for piece in (tidy_text(part) for part in _CLAUSE_ENDS.split(text))
        if len(piece) >= SHORTEST_CLAUSE
    ]


def test_the_set_is_read_as_the_writings_set_and_every_sentence_is_scored() -> None:
    assert len(WRITINGS) >= 2 * len(Writing)
    assert {s.split for s in WRITINGS} == {Split.WRITINGS}
    assert {s.group for s in WRITINGS} == {Group.SCORED}
    assert all(s.trades for s in WRITINGS)


@pytest.mark.parametrize("writing", list(Writing), ids=lambda w: w.name)
def test_every_writing_has_two_sentences_or_more_in_chinese_and_in_english(
    writing: Writing,
) -> None:
    counts = writings_table(WRITINGS)[writing]

    assert sum(counts.values()) >= 2
    assert counts[Context.CHINESE] >= 1
    assert counts[Context.ENGLISH] >= 1


@pytest.mark.parametrize("sentence", WRITINGS, ids=lambda s: s.id)
def test_every_sentence_shows_a_writing(sentence: Sentence) -> None:
    assert writings_of(sentence)


def test_the_writings_are_told_apart_by_the_gold_answer() -> None:
    by_id = {sentence.id: writings_of(sentence) for sentence in WRITINGS}

    assert by_id["w09"] == {Writing.SPACE_THOUSANDS}
    assert by_id["w13"] == {Writing.ADJACENT_NUMBERS}
    assert by_id["w01"] == {Writing.GAP_LETTER_MULTIPLIER}
    assert by_id["w05"] == {Writing.GAP_CHINESE_MULTIPLIER}
    assert by_id["w17"] == {Writing.FULL_WIDTH_COMMA}


def test_ids_and_texts_repeat_no_other_sentence_example_or_smoke_passage() -> None:
    texts = [tidy_text(s.text) for s in WRITINGS]
    others = {tidy_text(s.text) for s in FIFTY}
    examples = {tidy_text(example.passage) for example in FIRST_EXAMPLES}
    smoke = {tidy_text(str(param.values[0])) for param in SMOKE_PASSAGES}

    assert len(set(texts)) == len(texts)
    assert len({s.id for s in WRITINGS}) == len(WRITINGS)
    assert not {s.id for s in WRITINGS} & {s.id for s in FIFTY}
    for text in texts:
        assert text not in others
        assert text not in examples
        assert text not in smoke


@pytest.mark.parametrize("sentence", WRITINGS, ids=lambda s: s.id)
def test_no_sentence_nor_any_of_its_clauses_stands_in_a_prompt(sentence: Sentence) -> None:
    prompts = every_prompt_text()

    for piece in [tidy_text(sentence.text), *clauses(sentence.text)]:
        assert piece not in prompts, piece


@pytest.mark.parametrize("sentence", WRITINGS, ids=lambda s: s.id)
def test_every_hand_given_label_is_borne_out(sentence: Sentence) -> None:
    for feature in sentence.features:
        assert feature_holds(sentence, feature), feature


@pytest.mark.parametrize(("sentence", "trade"), TRADES)
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


@pytest.mark.parametrize(("sentence", "trade"), TRADES)
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


@pytest.mark.parametrize(("sentence", "trade"), TRADES)
def test_every_gold_time_is_the_core_reading_of_its_phrase(
    sentence: Sentence, trade: GoldTrade
) -> None:
    cell = trade.cell(Field.TIME)
    assert cell.phrase is not None
    reading = read_time(cell.phrase, sentence.now, sentence.zone)
    assert isinstance(reading, TimeRecognised), reading
    assert isinstance(cell.value, OccurredTime)
    assert reading.time == cell.value


@pytest.mark.parametrize(("sentence", "trade"), TRADES)
def test_every_gold_coin_and_currency_is_what_its_phrase_names(
    sentence: Sentence, trade: GoldTrade
) -> None:
    for field in (Field.COIN, Field.PRICE_CURRENCY, Field.FEE_CURRENCY):
        cell = trade.cell(field)
        if cell.phrase is not None:
            assert word_identity(cell.phrase, BUILT_IN_TABLE) == cell.value, field
    platform = trade.cell(Field.PLATFORM)
    if platform.phrase is not None:
        assert platform.value == platform.phrase


@pytest.mark.parametrize(("sentence", "trade"), TRADES)
def test_a_currency_written_with_a_number_is_in_the_gold_answer(
    sentence: Sentence, trade: GoldTrade
) -> None:
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


@pytest.mark.parametrize("sentence", WRITINGS, ids=lambda s: s.id)
def test_every_gold_phrase_stands_in_the_passage(sentence: Sentence) -> None:
    for trade in sentence.trades:
        for field, cell in trade.cells.items():
            if cell.phrase is not None:
                assert cell.phrase in sentence.text, field


def test_the_set_needs_its_own_switch_and_cannot_go_with_the_final_exam() -> None:
    assert runner.set_for(runner._arguments(["--set", "writings"])) == (
        Split.WRITINGS,
        WRITINGS_SET,
    )
    assert runner.set_for(runner._arguments(["--set", "debug"]))[0] is Split.DEBUG
    with pytest.raises(SystemExit):
        runner._arguments(["--set", "writings", "--final-exam"])
    with pytest.raises(SystemExit):
        runner._arguments(["--set", "final"])


def test_a_run_of_the_writings_set_is_named_and_recorded_as_such(tmp_path: Path) -> None:
    chosen = runner.Backend(
        model=ScriptedModel([table()]),
        name="scripted",
        fingerprint="a" * 64,
        server_version="0.0.0",
        base_url="http://127.0.0.1:59999",
        parameters={"temperature": 0.0},
    )
    out = io.StringIO()

    status = runner.main(
        ["--set", "writings", "--only", "w01"],
        out=out,
        backend=lambda _: chosen,
        results_dir=tmp_path,
    )

    assert status == 0, out.getvalue()
    (path,) = tmp_path.glob("*.jsonl")
    assert path.name.endswith("-writings-first.jsonl")
    head = path.read_text(encoding="utf-8").splitlines()[0]
    assert '"set": "writings"' in head
    assert '"final_exam_switch": false' in head
    assert '"set_file": "evals/sets/writings.json"' in head


def test_the_coverage_table_has_a_line_for_each_writing() -> None:
    text = coverage_markdown(WRITINGS)

    assert (
        text.splitlines()[0] == "| Way of writing | Chinese or mixed passages | English passages |"
    )
    assert len(text.splitlines()) == 2 + len(Writing)
    assert "| a space between thousands (94 900) | 2 | 2 |" in text
