"""Tests of the second version of the assistant's system prompt, and that it is the default."""

from __future__ import annotations

import inspect

import pytest

from evals import tool_run
from ledger_hand.assistant.prompts.assistant_first import ASSISTANT_FIRST
from ledger_hand.assistant.prompts.assistant_second import ASSISTANT_SECOND
from ledger_hand.flows.assisting import take_turn


def test_the_second_version_is_the_one_a_turn_uses_unless_told_otherwise() -> None:
    default = inspect.signature(take_turn).parameters["prompt"].default

    assert default is ASSISTANT_SECOND
    assert ASSISTANT_SECOND.name == "assistant-2"


def test_the_measure_knows_both_versions_and_takes_the_second_by_default() -> None:
    assert set(tool_run.PROMPTS) == {"assistant-1", "assistant-2"}
    assert sorted(tool_run.PROMPTS)[-1] == "assistant-2"


@pytest.mark.parametrize(
    "rule",
    [
        "list_trades",
        "get_period_summary",
        "get_positions",
        "list_assets",
        "you cannot answer: call nothing",
        "never turn it into a date, never translate it",
        "Give an asset only when the user named one",
        "never write a number that is not in what the tool returned",
        "propose_trade_add",
        "Reply in the user's language",
    ],
)
def test_the_second_version_says_each_rule(rule: str) -> None:
    assert rule in ASSISTANT_SECOND.words


def test_the_first_version_is_left_as_it_was() -> None:
    assert ASSISTANT_FIRST.name == "assistant-1"
    assert "program shows the user the table" not in ASSISTANT_FIRST.words
