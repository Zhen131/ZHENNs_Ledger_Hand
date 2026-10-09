"""The prompt that splits a passage holds no test sentence, and its examples are what it teaches.

The test sentences measure how well the model reads passages it has not
seen; a prompt that held one of them, or a clause of one, would teach the
model the answer. The prompt is checked against the 50 sentences of the
debug and final sets and the sentences of the writings set: the whole of
every sentence, and every clause of it of ``SHORTEST_CLAUSE`` characters or
more, compared after the same tidying the scoring uses, in the instructions,
the words for asking again and every example. Nothing here sends anything
to a model.
"""

from __future__ import annotations

import pytest

from evals.cells import tidy_text
from evals.gold import DEBUG_SET, FINAL_SET, Split, load_set
from evals.writings import WRITINGS_SET
from ledger_hand.extraction.passage import Passage, Piece
from ledger_hand.extraction.prompts.split import SPLIT_PROMPT
from ledger_hand.extraction.segments import segments_of
from ledger_hand.extraction.split_table import SplitExample, example_split_reply, read_split_reply
from ledger_hand.ports import FinishReason, ModelReply, ReplyRecord
from tests.extraction.test_new_prompts_hold_no_test_sentence import SHORTEST_CLAUSE, clauses

SENTENCES = (
    load_set(DEBUG_SET, Split.DEBUG)
    + load_set(FINAL_SET, Split.FINAL)
    + load_set(WRITINGS_SET, Split.WRITINGS)
)
PROMPT_TEXT = "\n".join(
    [
        SPLIT_PROMPT.instructions,
        SPLIT_PROMPT.ask_again,
        *(example.passage for example in SPLIT_PROMPT.examples),
        *(example_split_reply(example) for example in SPLIT_PROMPT.examples),
    ]
)


def test_there_are_seventy_sentences_to_check_against() -> None:
    assert len(SENTENCES) == 70
    assert SHORTEST_CLAUSE == 8


def test_no_sentence_nor_any_of_its_clauses_is_in_the_split_prompt() -> None:
    prompt = tidy_text(PROMPT_TEXT)
    found = [
        (sentence.id, piece)
        for sentence in SENTENCES
        for piece in [tidy_text(sentence.text), *clauses(sentence.text)]
        if piece in prompt
    ]

    assert found == []


def test_the_version_is_named_and_shows_a_few_examples() -> None:
    assert SPLIT_PROMPT.name == "split-1"
    assert len(SPLIT_PROMPT.examples) == 5


@pytest.mark.parametrize("example", SPLIT_PROMPT.examples, ids=lambda e: e.passage[:12])
def test_every_piece_of_an_example_is_a_piece_of_its_passage(example: SplitExample) -> None:
    passage = Passage(example.passage)

    for pieces in example.trades:
        for piece in pieces:
            assert isinstance(passage.find(piece), Piece), piece


@pytest.mark.parametrize("example", SPLIT_PROMPT.examples, ids=lambda e: e.passage[:12])
def test_an_example_gives_one_segment_per_trade_when_it_reports_several(
    example: SplitExample,
) -> None:
    trades = example.trades
    segments = segments_of(Passage(example.passage), trades)

    if len(trades) >= 2:
        assert isinstance(segments, tuple) and len(segments) == len(trades)
    else:
        assert segments == ()


@pytest.mark.parametrize("example", SPLIT_PROMPT.examples, ids=lambda e: e.passage[:12])
def test_an_example_reply_reads_back_as_its_trades(example: SplitExample) -> None:
    record = ReplyRecord(
        model="x",
        elapsed_seconds=0.0,
        prompt_tokens=None,
        reply_tokens=None,
        finish=FinishReason.STOPPED,
    )
    written = ModelReply(text=example_split_reply(example), record=record)

    assert read_split_reply(written) == example.trades


def test_the_check_finds_a_clause_planted_in_the_prompt() -> None:
    sentence = SENTENCES[0]
    planted = tidy_text(PROMPT_TEXT + " " + clauses(sentence.text)[0])

    assert any(piece in planted for piece in clauses(sentence.text))
