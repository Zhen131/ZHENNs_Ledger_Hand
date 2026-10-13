"""Tests of the voice set: it is read as its own set, repeats nothing, and its gold keeps the rules.

The set is read like the others; nothing here calls a model. No sentence is
one of the debug, final or writings sentences, a prompt example or a smoke
passage, and neither a sentence nor any clause of one stands in any prompt,
the split prompt included. Its gold answers are held to the same checks as
those of the 50 sentences (``test_sets``): the check of a draft finds
missing exactly what they say; every number, time, coin and currency is the
core's reading of its phrase (a trade whose passage gives no time is left
alone, as there); a platform or an opinion is its phrase. The run switch
takes the set on its own, and its file is pinned by its fingerprint.
"""

from __future__ import annotations

import hashlib
import io
from pathlib import Path

import pytest

from evals import run as runner
from evals.cells import tidy_text
from evals.coverage import feature_holds
from evals.gold import DEBUG_SET, FINAL_SET, GoldTrade, Group, Sentence, Split, gold_draft, load_set
from evals.voice import VOICE_SET
from evals.writings import WRITINGS_SET
from ledger_hand.core.coins import BUILT_IN_TABLE
from ledger_hand.core.numbers import NotANumber, Recognised, Unsure, read_number
from ledger_hand.core.timeparse import TimeRecognised, read_time
from ledger_hand.core.trade import OccurredTime, TradeRecord
from ledger_hand.core.validation import DraftProblems, check_draft
from ledger_hand.extraction.prompts.first_examples import FIRST_EXAMPLES
from ledger_hand.extraction.prompts.split import SPLIT_PROMPT
from ledger_hand.extraction.reply_table import Field
from ledger_hand.extraction.split_table import example_split_reply
from ledger_hand.extraction.unit_currency import currencies_in_unit, word_identity
from tests.evals.test_sets import allowed_units
from tests.evals.test_writings import clauses, every_prompt_text
from tests.extraction.scripted_runs import table
from tests.fakes.scripted_model import ScriptedModel
from tests.live.test_live_extraction import PASSAGES as SMOKE_PASSAGES

# The fingerprint of the set file; the set is never changed.
VOICE_SHA256 = "884e678672d4fcedc2d36da18e96e7e70261785936b4fc48cd2a3259d2b35196"
VOICE = load_set(VOICE_SET, Split.VOICE)
OTHERS = (
    load_set(DEBUG_SET, Split.DEBUG)
    + load_set(FINAL_SET, Split.FINAL)
    + load_set(WRITINGS_SET, Split.WRITINGS)
)
TRADES = [
    pytest.param(sentence, trade, id=f"{sentence.id}-{at}")
    for sentence in VOICE
    for at, trade in enumerate(sentence.trades)
]
NUMBER_FIELDS = (Field.QUANTITY, Field.PRICE, Field.TOTAL, Field.FEE)


def split_prompt_text() -> str:
    """Every word of the split prompt: instructions, asking again, examples and their replies."""
    texts = [SPLIT_PROMPT.instructions, SPLIT_PROMPT.ask_again]
    texts += [example.passage for example in SPLIT_PROMPT.examples]
    texts += [example_split_reply(example) for example in SPLIT_PROMPT.examples]
    return tidy_text("\n".join(texts))


def test_the_set_file_is_the_one_pinned() -> None:
    assert hashlib.sha256(VOICE_SET.read_bytes()).hexdigest() == VOICE_SHA256


def test_the_set_is_read_as_the_voice_set_in_its_order() -> None:
    assert {s.split for s in VOICE} == {Split.VOICE}
    assert [s.id for s in VOICE] == [f"u{number:02d}" for number in range(1, 11)]


def test_scored_sentences_have_gold_trades_and_the_others_none_and_a_kind() -> None:
    scored = [s for s in VOICE if s.group is Group.SCORED]
    apart = [s for s in VOICE if s.group is Group.NOT_TO_RECORD]

    assert scored and apart
    assert all(s.trades for s in scored)
    assert all(not s.trades and s.kind is not None for s in apart)


def test_ids_and_texts_repeat_no_other_sentence_example_or_smoke_passage() -> None:
    texts = [tidy_text(s.text) for s in VOICE]
    others = {tidy_text(s.text) for s in OTHERS}
    examples = {tidy_text(example.passage) for example in FIRST_EXAMPLES}
    smoke = {tidy_text(str(param.values[0])) for param in SMOKE_PASSAGES}

    assert len(set(texts)) == len(texts)
    assert len({s.id for s in VOICE}) == len(VOICE)
    assert not {s.id for s in VOICE} & {s.id for s in OTHERS}
    for text in texts:
        assert text not in others
        assert text not in examples
        assert text not in smoke


@pytest.mark.parametrize("sentence", VOICE, ids=lambda s: s.id)
def test_no_sentence_nor_any_of_its_clauses_stands_in_a_prompt(sentence: Sentence) -> None:
    prompts = every_prompt_text()
    split = split_prompt_text()

    for piece in [tidy_text(sentence.text), *clauses(sentence.text)]:
        assert piece not in prompts, piece
        assert piece not in split, piece


@pytest.mark.parametrize("sentence", VOICE, ids=lambda s: s.id)
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
    if cell.phrase is None:
        return
    reading = read_time(cell.phrase, sentence.now, sentence.zone)
    if cell.value is None:
        assert not isinstance(reading, TimeRecognised)
    else:
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
    for field in (Field.PLATFORM, Field.OPINION):
        cell = trade.cell(field)
        if cell.phrase is not None:
            assert cell.value == cell.phrase, field


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


@pytest.mark.parametrize("sentence", VOICE, ids=lambda s: s.id)
def test_every_gold_phrase_stands_in_the_passage(sentence: Sentence) -> None:
    for trade in sentence.trades:
        for field, cell in trade.cells.items():
            if cell.phrase is not None:
                assert cell.phrase in sentence.text, field


def test_the_set_needs_its_own_switch_and_cannot_go_with_the_final_exam() -> None:
    assert runner.set_for(runner._arguments(["--set", "voice"])) == (Split.VOICE, VOICE_SET)
    with pytest.raises(SystemExit):
        runner._arguments(["--set", "voice", "--final-exam"])


def test_a_run_of_the_voice_set_is_named_and_recorded_as_such(tmp_path: Path) -> None:
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
        ["--set", "voice", "--only", "u01"],
        out=out,
        backend=lambda _: chosen,
        results_dir=tmp_path,
    )

    assert status == 0, out.getvalue()
    (path,) = tmp_path.glob("*.jsonl")
    assert path.name.endswith("-voice-first.jsonl")
    head = path.read_text(encoding="utf-8").splitlines()[0]
    assert '"set": "voice"' in head
    assert '"final_exam_switch": false' in head
    assert '"set_file": "evals/sets/voice.json"' in head
