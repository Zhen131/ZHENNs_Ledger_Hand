"""Tests of the reading prompt ``read-1`` and the shape of a reading prompt.

``read-1`` is zero-shot: instructions only, not one example, and no table to
fill. Its instructions say what the model is to do with a screenshot, each
point checked here by the words that say it: copy the order's values, each
with its label, as they stand; never translate; never change a number; keep
the unit or coin beside it; add nothing the screen does not show; leave out
what is not the order; add no comment of its own.
"""

from __future__ import annotations

import pytest

from ledger_hand.extraction.picture_prompt import PicturePromptVersion
from ledger_hand.extraction.prompts import read
from ledger_hand.extraction.prompts.read import READ_PROMPT

SAID = " ".join(READ_PROMPT.instructions.split())


def test_the_version_is_read_1_and_a_reading_prompt() -> None:
    assert READ_PROMPT.name == "read-1"
    assert isinstance(READ_PROMPT, PicturePromptVersion)
    assert READ_PROMPT.ask == "Read out the order on this screenshot."


def test_the_module_says_its_technique_and_that_a_version_is_never_changed() -> None:
    doc = " ".join((read.__doc__ or "").split())

    assert "Zero-shot." in doc
    assert "instructions only, not one example" in doc
    assert "A version is never changed once it has been used with a real model" in doc
    assert "``read-1``" in doc


def test_the_instructions_hold_no_example_and_ask_for_no_table() -> None:
    lowered = SAID.lower()

    assert "example" not in lowered
    assert "json" not in lowered
    assert "{" not in SAID


@pytest.mark.parametrize(
    "words",
    [
        # Each value of the order, with its label, as it stands.
        "Write one line for each value the order shows: the label the screen gives it",
        "character for character, in the language they are written in, Chinese or English",
        "never translate them",
        # Every number as written.
        "Copy every number as it is written: never calculate, convert or round it",
        "never add or drop a digit, a zero, a sign, a decimal point or a thousands separator",
        "Copy the unit, coin or currency written next to a number together with it",
        # The labels that tell a price from a total.
        "the side (buy or sell), the pair or the coin, the amount, the price it was filled at, "
        "the total, the fee, the time and the status",
        "so that each number keeps the label that says what it is",
        # Nothing made up.
        "Write only what the screenshot shows",
        "such as the name of the exchange when the screen does not write it",
        # Not the order.
        "the phone's clock, battery and signal at the top of the screen, balances, "
        "advertisements, menus and buttons",
        # Nothing of its own.
        "Add no comment, judgement or explanation of your own",
    ],
)
def test_the_instructions_say(words: str) -> None:
    assert words in SAID


@pytest.mark.parametrize(
    "changes",
    [{"name": ""}, {"instructions": "  "}, {"ask": "\n"}, {"ask": None}, {"name": 1}],
)
def test_a_reading_prompt_with_a_blank_part_is_refused(changes: dict[str, object]) -> None:
    given: dict[str, object] = {"name": "read-x", "instructions": "Read it.", "ask": "Read."}
    given.update(changes)

    with pytest.raises(ValueError, match="must be text that is not blank"):
        PicturePromptVersion(**given)  # type: ignore[arg-type]
