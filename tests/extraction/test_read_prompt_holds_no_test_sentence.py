"""The words of the reading prompt ``read-1`` hold no test sentence, nor any clause of one.

The test sentences measure how well the model reads passages it has not
seen; words in a prompt that held one of them, or a clause of one, would
teach the model the answer, and the text a screenshot is read into is
extracted as a passage is. Every word ``read-1`` sends (its instructions
and its ask) is checked against every sentence of the four sets (debug,
final, writings, voice) and the four smoke passages, as a whole and in every
clause of ``SHORTEST_CLAUSE`` characters or more, after the tidying the
scoring uses, with the pieces of the check of the second prompt. A clause of
the voice set is also looked for with its numbers and coin names put as one
mark each. For the final set a finding names the sentence only, never its
words. Nothing here sends anything to a model.
"""

from __future__ import annotations

import pytest

from evals.cells import tidy_text
from evals.gold import Split
from ledger_hand.extraction.prompts.read import READ_PROMPT
from tests.extraction.test_second_prompt_holds_no_test_sentence import (
    SETS,
    SHORTEST_CLAUSE,
    SMOKE,
    found_in,
    marked,
    marked_clauses,
    pieces,
)


def read_words() -> str:
    """Every word ``read-1`` sends to the model."""
    return "\n".join([READ_PROMPT.instructions, READ_PROMPT.ask])


def test_the_clauses_are_as_long_as_in_the_other_checks() -> None:
    assert SHORTEST_CLAUSE == 8


@pytest.mark.parametrize("split", [Split.DEBUG, Split.WRITINGS, Split.VOICE])
def test_no_sentence_nor_any_of_its_clauses_is_in_the_reading_prompt(split: Split) -> None:
    text = tidy_text(read_words())
    found = [
        (sentence.id, piece)
        for sentence in SETS[split]
        for piece in pieces(sentence.text)
        if piece in text
    ]

    assert found == []


def test_no_final_sentence_nor_any_of_its_clauses_is_in_the_reading_prompt() -> None:
    # Only the ids are said: the final set's words are kept out of sight.
    assert found_in(SETS[Split.FINAL], read_words()) == []


def test_no_smoke_passage_nor_any_of_its_clauses_is_in_the_reading_prompt() -> None:
    text = tidy_text(read_words())

    assert [piece for passage in SMOKE for piece in pieces(passage) if piece in text] == []


def test_no_voice_clause_is_in_the_reading_prompt_with_only_its_numbers_or_coins_changed() -> None:
    text = marked(read_words())
    found = [
        (sentence.id, piece)
        for sentence in SETS[Split.VOICE]
        for piece in marked_clauses(sentence.text)
        if piece in text
    ]

    assert found == []


def test_every_set_is_checked() -> None:
    assert set(SETS) == {Split.DEBUG, Split.FINAL, Split.WRITINGS, Split.VOICE}
    assert all(SETS[split] for split in SETS)
    assert len(SMOKE) == 4
