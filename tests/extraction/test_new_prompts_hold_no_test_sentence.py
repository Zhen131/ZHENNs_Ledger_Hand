"""The prompts for judging, reading an answer and wording a question hold no test sentence.

The 50 test sentences measure how well the model reads passages it has not
seen; a prompt that held one of them, or a clause of one, would teach the
model the answer. Like the first prompt's examples, the three newer prompts
are checked against both sets: the whole of every sentence, and every clause
of it of ``SHORTEST_CLAUSE`` characters or more, compared after the same
tidying the scoring uses. Nothing here sends anything to a model.
"""

from __future__ import annotations

import re

import pytest

from evals.cells import tidy_text
from evals.gold import DEBUG_SET, FINAL_SET, Split, load_set
from ledger_hand.asking.prompts.bookkeeper import BOOKKEEPER_PROMPT
from ledger_hand.extraction.prompts.answer import ANSWER_PROMPT
from ledger_hand.extraction.prompts.screen import SCREEN_PROMPT

SENTENCES = load_set(DEBUG_SET, Split.DEBUG) + load_set(FINAL_SET, Split.FINAL)
# Shorter pieces ("0.5 ETH", "昨天") are everyday words, not a sentence's own.
SHORTEST_CLAUSE = 8
_CLAUSE_ENDS = re.compile(r"[，,；;。.!！?？:：]")

PROMPTS = {
    SCREEN_PROMPT.name: SCREEN_PROMPT.instructions + SCREEN_PROMPT.ask_again,
    ANSWER_PROMPT.name: "\n".join(
        [ANSWER_PROMPT.instructions, ANSWER_PROMPT.ask_again, *ANSWER_PROMPT.fields.values()]
    ),
    BOOKKEEPER_PROMPT.name: BOOKKEEPER_PROMPT.instructions,
}


def clauses(text: str) -> list[str]:
    return [
        piece
        for piece in (tidy_text(part) for part in _CLAUSE_ENDS.split(text))
        if len(piece) >= SHORTEST_CLAUSE
    ]


def test_there_are_fifty_sentences_to_check_against() -> None:
    assert len(SENTENCES) == 50


@pytest.mark.parametrize("name", sorted(PROMPTS))
def test_no_sentence_nor_any_of_its_clauses_is_in_the_prompt(name: str) -> None:
    prompt = tidy_text(PROMPTS[name])
    found = [
        (sentence.id, piece)
        for sentence in SENTENCES
        for piece in [tidy_text(sentence.text), *clauses(sentence.text)]
        if piece in prompt
    ]

    assert found == []


def test_the_three_prompts_are_zero_shot_or_a_persona_without_examples() -> None:
    assert SCREEN_PROMPT.examples == ()
    assert BOOKKEEPER_PROMPT.instructions.startswith("You are a meticulous bookkeeper")
    assert {SCREEN_PROMPT.name, ANSWER_PROMPT.name, BOOKKEEPER_PROMPT.name} == {
        "screen-1",
        "answer-1",
        "bookkeeper-1",
    }


def test_the_check_finds_a_clause_planted_in_a_prompt() -> None:
    sentence = SENTENCES[0]
    planted = tidy_text("Some instructions. " + clauses(sentence.text)[0] + " More words.")

    assert any(piece in planted for piece in clauses(sentence.text))
