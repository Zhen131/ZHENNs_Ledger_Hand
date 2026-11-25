"""The prompt versions only the assistant uses hold no test sentence either.

The same check as for the judging prompt the record page uses
(``test_new_prompts_hold_no_test_sentence``), run on the versions added for
the assistant: neither the whole of any of the 50 test sentences, nor any
clause of one, is in them.
"""

from __future__ import annotations

import pytest

from evals.cells import tidy_text
from ledger_hand.extraction.prompts.screen2 import SCREEN_PROMPT_2
from tests.extraction.test_new_prompts_hold_no_test_sentence import SENTENCES, clauses

PROMPTS = {SCREEN_PROMPT_2.name: SCREEN_PROMPT_2.instructions + SCREEN_PROMPT_2.ask_again}


@pytest.mark.parametrize("name", sorted(PROMPTS))
def test_no_sentence_nor_any_of_its_clauses_is_in_the_assistant_s_prompt(name: str) -> None:
    prompt = tidy_text(PROMPTS[name])
    found = [
        (sentence.id, piece)
        for sentence in SENTENCES
        for piece in [tidy_text(sentence.text), *clauses(sentence.text)]
        if piece in prompt
    ]

    assert found == []


def test_the_second_judging_version_is_zero_shot_and_named_apart() -> None:
    assert SCREEN_PROMPT_2.examples == ()
    assert SCREEN_PROMPT_2.name == "screen-2"
