"""Tests of the four prompt versions built on the first: each differs from it in one thing only.

``zero_shot`` drops the examples; ``persona`` says a role before the
instructions; ``price_total`` adds a rule after them; ``stepwise`` adds a
paragraph after them and a field for the written analysis in its reply
table. Everything else is the first prompt's, the very same text: the
instructions, the examples, and the words for asking again. Every passage
and reply here is invented; nothing is sent to a model.
"""

from __future__ import annotations

import json

import pytest

from ledger_hand.extraction import prompts
from ledger_hand.extraction.extractor import Extracted
from ledger_hand.extraction.prompting import PromptVersion
from ledger_hand.extraction.prompts import persona, price_total, stepwise, zero_shot
from ledger_hand.extraction.prompts.first import FIRST_PROMPT
from ledger_hand.extraction.prompts.first_examples import FIRST_EXAMPLES
from ledger_hand.extraction.reply_table import REPLY_TABLE, TRADES_KEY
from tests.extraction.scripted_runs import row, run, table

ZERO_SHOT = zero_shot.ZERO_SHOT_PROMPT
PERSONA = persona.PERSONA_PROMPT
PRICE_TOTAL = price_total.PRICE_TOTAL_PROMPT
STEPWISE = stepwise.STEPWISE_PROMPT
VERSIONS = (ZERO_SHOT, PERSONA, PRICE_TOTAL, STEPWISE)
# Each version and the words it adds: before the first instructions, after them, or none.
ADDED_BEFORE = {PERSONA.name: persona.ROLE}
ADDED_AFTER = {PRICE_TOTAL.name: price_total.PRICE_TOTAL_RULE, STEPWISE.name: stepwise.THINK_FIRST}


def flat(text: str) -> str:
    return " ".join(text.split())


@pytest.mark.parametrize("version", VERSIONS, ids=lambda v: v.name)
def test_the_words_for_asking_again_are_the_first_prompts(version: PromptVersion) -> None:
    assert version.ask_again == FIRST_PROMPT.ask_again


def test_the_names_are_the_file_names_and_differ_from_the_first() -> None:
    names = [version.name for version in VERSIONS]

    assert names == ["zero_shot", "persona", "price_total", "stepwise"]
    for module, version in zip((zero_shot, persona, price_total, stepwise), VERSIONS, strict=True):
        assert module.__name__ == f"{prompts.__name__}.{version.name}"
        assert module.__doc__


def test_zero_shot_has_the_first_instructions_and_no_example() -> None:
    assert ZERO_SHOT.instructions == FIRST_PROMPT.instructions
    assert ZERO_SHOT.examples == ()
    assert ZERO_SHOT.reply_table is REPLY_TABLE


def test_persona_is_a_role_said_before_the_first_instructions() -> None:
    assert PERSONA.instructions == persona.ROLE + FIRST_PROMPT.instructions
    assert persona.ROLE.startswith("You are a meticulous bookkeeper")
    assert persona.ROLE.endswith("\n\n")
    assert PERSONA.examples is FIRST_EXAMPLES
    assert PERSONA.reply_table is REPLY_TABLE


def test_price_total_is_one_rule_after_the_first_instructions() -> None:
    assert PRICE_TOTAL.instructions == FIRST_PROMPT.instructions + price_total.PRICE_TOTAL_RULE
    rule = flat(price_total.PRICE_TOTAL_RULE)
    assert rule.startswith("6. Price and total are two different fields.")
    for said in ('"一共"', '"总共"', '"花了"', '"total"', "never into price"):
        assert said in rule
    assert PRICE_TOTAL.examples is FIRST_EXAMPLES
    assert PRICE_TOTAL.reply_table is REPLY_TABLE


def test_stepwise_is_one_paragraph_after_the_first_instructions() -> None:
    assert STEPWISE.instructions == FIRST_PROMPT.instructions + stepwise.THINK_FIRST
    paragraph = flat(stepwise.THINK_FIRST)
    assert "think step by step" in paragraph
    assert '"steps"' in paragraph
    assert STEPWISE.examples is FIRST_EXAMPLES


def test_the_stepwise_table_is_the_reply_table_with_steps_before_the_rows() -> None:
    table_ = STEPWISE.reply_table
    properties = table_["properties"]
    assert isinstance(properties, dict)

    assert list(properties) == [stepwise.STEPS_KEY, TRADES_KEY]
    assert properties[stepwise.STEPS_KEY] == {"type": "string"}
    assert properties[TRADES_KEY] is REPLY_TABLE["properties"][TRADES_KEY]  # type: ignore[index]
    assert table_["required"] == [stepwise.STEPS_KEY, TRADES_KEY]
    assert table_["additionalProperties"] is False
    assert table_ is stepwise.STEPWISE_TABLE


@pytest.mark.parametrize("version", VERSIONS, ids=lambda v: v.name)
def test_nothing_but_the_declared_words_is_added(version: PromptVersion) -> None:
    before = ADDED_BEFORE.get(version.name, "")
    after = ADDED_AFTER.get(version.name, "")

    assert version.instructions == before + FIRST_PROMPT.instructions + after
    assert (version.examples == ()) is (version is ZERO_SHOT)


def test_a_stepwise_reply_is_read_as_its_rows() -> None:
    passage = "Bought 30 DOT at 6.2 today"
    rows = [row(side="buy", coin="DOT", quantity="30 DOT", price="6.2", time="today")]
    reply = json.dumps({"steps": "One trade. 30 is the quantity, 6.2 the price.", "trades": rows})

    with_steps, model = run(passage, reply, prompt=STEPWISE)
    plain, _ = run(passage, table(*rows))

    assert isinstance(with_steps, Extracted) and isinstance(plain, Extracted)
    assert with_steps.drafts == plain.drafts
    assert with_steps.issues == plain.issues
    assert model.calls[0].reply_schema is stepwise.STEPWISE_TABLE
    assert model.calls[0].messages[0].content == STEPWISE.instructions
