"""Tests of the later versions of the assistant's system prompt; the latest is used."""

from __future__ import annotations

import inspect

import pytest

from evals import tool_run
from ledger_hand.assistant.prompts.assistant_first import ASSISTANT_FIRST
from ledger_hand.assistant.prompts.assistant_fourth import ASSISTANT_FOURTH
from ledger_hand.assistant.prompts.assistant_second import ASSISTANT_SECOND
from ledger_hand.assistant.prompts.assistant_third import ASSISTANT_THIRD
from ledger_hand.flows.assisting import take_turn


def test_the_latest_version_is_the_one_a_turn_uses_unless_told_otherwise() -> None:
    default = inspect.signature(take_turn).parameters["prompt"].default

    assert default is ASSISTANT_FOURTH
    assert ASSISTANT_FOURTH.name == "assistant-4"
    assert ASSISTANT_SECOND.name == "assistant-2"
    assert ASSISTANT_THIRD.name == "assistant-3"


def test_the_measure_knows_every_version_and_takes_the_latest_by_default() -> None:
    assert set(tool_run.PROMPTS) == {"assistant-1", "assistant-2", "assistant-3", "assistant-4"}
    assert sorted(tool_run.PROMPTS)[-1] == "assistant-4"


def test_the_fourth_version_is_the_first_with_two_rules_changed() -> None:
    first = ASSISTANT_FIRST.words.splitlines()
    fourth = ASSISTANT_FOURTH.words.splitlines()

    changed = [index for index, line in enumerate(first) if fourth[index] != line]
    assert len(first) == len(fourth)
    assert [first[index][:12] for index in changed] == ["- Fill a too", "- If the use"]
    assert fourth[changed[0]].endswith("a time the user wrote in English is copied in English.")
    assert "how much the holdings grew between two days" in fourth[changed[1]]


@pytest.mark.parametrize(
    "rule",
    [
        "propose_trade_add",
        "list_trades, get_period_summary, get_positions",
        'if the user wrote "this year", give "this year"',
        "Give an asset only when the user named one",
        "Call nothing for them",
        "Reply with one short sentence and no figures",
        "Reply in the user's language",
    ],
)
def test_the_third_version_says_each_rule(rule: str) -> None:
    assert rule in ASSISTANT_THIRD.words


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
