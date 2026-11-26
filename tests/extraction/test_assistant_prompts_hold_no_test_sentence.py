"""The prompt versions only the assistant uses hold no test sentence either.

The same check as for the judging prompt the record page uses
(``test_new_prompts_hold_no_test_sentence``), run on what each version
added for the assistant says that the version it was made from does not
(the old words were checked when they were written), its examples'
passages and replies among them: neither the whole of any of the 50 test
sentences, nor any clause of one, is in it; nor any sentence, or clause,
of the share set the new versions were measured on.
The share examples obey the rules every example obeys: each field a piece
of its passage, each number and time one the core reads.
"""

from __future__ import annotations

import pytest

from evals.cells import tidy_text
from evals.stock_set import load_stock_set
from ledger_hand.core.ledger_table import SHARE_UNITS
from ledger_hand.core.numbers import Recognised, read_number
from ledger_hand.core.timeparse import TimeRecognised, read_time
from ledger_hand.extraction.passage import Passage, Piece
from ledger_hand.extraction.prompting import PromptVersion, example_reply
from ledger_hand.extraction.prompts.first import FIRST_PROMPT
from ledger_hand.extraction.prompts.first2 import FIRST_PROMPT_2
from ledger_hand.extraction.prompts.first2_examples import SHARE_EXAMPLES
from ledger_hand.extraction.prompts.first3 import FIRST_PROMPT_3
from ledger_hand.extraction.prompts.first3_examples import SHARE_EXAMPLES_3
from ledger_hand.extraction.prompts.screen import SCREEN_PROMPT
from ledger_hand.extraction.prompts.screen2 import SCREEN_PROMPT_2
from ledger_hand.extraction.prompts.spoken1 import SPOKEN_PROMPT_1
from ledger_hand.extraction.reply_table import Field
from tests.extraction.test_new_prompts_hold_no_test_sentence import SENTENCES, clauses
from tests.flows.scripted_flow import NOW, ZONE


def whole(prompt: PromptVersion) -> str:
    """Every word a version says: instructions, asking again, the examples and their replies."""
    return "\n".join(
        [
            prompt.instructions,
            prompt.ask_again,
            *(example.passage for example in prompt.examples),
            *(example_reply(example) for example in prompt.examples),
        ]
    )


# Each new version, and the version it was made from; only what it adds is checked.
PROMPTS = {
    SCREEN_PROMPT_2.name: (whole(SCREEN_PROMPT_2), whole(SCREEN_PROMPT)),
    FIRST_PROMPT_2.name: (whole(FIRST_PROMPT_2), whole(FIRST_PROMPT)),
    FIRST_PROMPT_3.name: (whole(FIRST_PROMPT_3), whole(FIRST_PROMPT)),
    SPOKEN_PROMPT_1.name: (whole(SPOKEN_PROMPT_1), whole(FIRST_PROMPT_3)),
}
SHARE_SENTENCES = [sentence.text for sentence in load_stock_set().sentences]


@pytest.mark.parametrize("name", sorted(PROMPTS))
def test_no_sentence_nor_any_of_its_clauses_is_in_what_the_new_version_adds(name: str) -> None:
    new, old = (tidy_text(text) for text in PROMPTS[name])
    found = [
        (sentence.id, piece)
        for sentence in SENTENCES
        for piece in [tidy_text(sentence.text), *clauses(sentence.text)]
        if piece in new and piece not in old
    ]

    assert found == []


@pytest.mark.parametrize("name", sorted(PROMPTS))
def test_no_sentence_of_the_share_set_is_in_what_the_new_version_adds(name: str) -> None:
    new, old = (tidy_text(text) for text in PROMPTS[name])
    found = [
        piece
        for text in SHARE_SENTENCES
        for piece in [tidy_text(text), *clauses(text)]
        if piece in new and piece not in old
    ]

    assert found == []


def test_the_new_versions_are_named_apart_and_keep_the_first_one_s_examples() -> None:
    assert SCREEN_PROMPT_2.examples == ()
    assert (SCREEN_PROMPT_2.name, FIRST_PROMPT_2.name) == ("screen-2", "first-2")
    assert FIRST_PROMPT_2.examples[: len(FIRST_PROMPT.examples)] == FIRST_PROMPT.examples
    assert FIRST_PROMPT_2.examples[len(FIRST_PROMPT.examples) :] == SHARE_EXAMPLES
    assert FIRST_PROMPT_3.name == "first-3"
    assert FIRST_PROMPT_3.examples[: len(FIRST_PROMPT.examples)] == FIRST_PROMPT.examples
    assert FIRST_PROMPT_3.examples[len(FIRST_PROMPT.examples) :] == SHARE_EXAMPLES_3


@pytest.mark.parametrize("example", (*SHARE_EXAMPLES, *SHARE_EXAMPLES_3))
def test_every_share_example_is_copied_from_its_passage_and_read_by_the_core(example) -> None:  # type: ignore[no-untyped-def]
    passage = Passage(example.passage)
    for row in example.rows:
        for field, text in row.items():
            if field is Field.SIDE or not text:
                continue
            found = passage.find(text)
            assert isinstance(found, Piece) and found.text == text, (field, text)
        allowed = (*SHARE_UNITS, *(row[f] for f in (Field.COIN, Field.FEE_CURRENCY) if f in row))
        for field in (Field.QUANTITY, Field.PRICE, Field.TOTAL, Field.FEE):
            if row.get(field):
                assert isinstance(read_number(row[field], allowed), Recognised), row[field]
        if row.get(Field.TIME):
            assert isinstance(read_time(row[Field.TIME], NOW, ZONE), TimeRecognised)
