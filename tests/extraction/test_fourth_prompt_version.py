"""Tests of the fourth prompt version: the first prompt, the two rules of the second, new examples.

``fourth`` is built on ``first`` and ``second`` and changes two things from
``first``: the two rules of ``second``, the very same constants, said after
the first prompt's instructions, and examples added after the first
prompt's ten. Its instructions are those of ``second`` and ``third`` to the
letter. Everything else is the first prompt's, the very same text and
objects: its ten examples in their order, the words for asking again and the
reply table. Its examples file does not take the examples of ``second``.
Every passage and reply here is invented; nothing is sent to a model.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ledger_hand.extraction import prompts
from ledger_hand.extraction.extractor import Extracted
from ledger_hand.extraction.prompting import build_messages, example_reply
from ledger_hand.extraction.prompts import fourth, fourth_examples, second, third
from ledger_hand.extraction.prompts.first import FIRST_PROMPT
from ledger_hand.extraction.prompts.first_examples import FIRST_EXAMPLES
from ledger_hand.extraction.reply_table import REPLY_TABLE
from ledger_hand.ports import Role
from tests.extraction.scripted_runs import row, run, table

FOURTH = fourth.FOURTH_PROMPT
# The paragraphs said after the first prompt's instructions, in their order.
ADDED_AFTER = (second.BUY_WORDS_RULE, second.U_TOTAL_RULE)
# At most two paragraphs and ten examples more than the first prompt.
MOST_PARAGRAPHS = 2
MOST_EXAMPLES = 10


def imported_modules(path: Path) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            found.add(node.module or "")
            found.update(f"{node.module}.{alias.name}" for alias in node.names)
    return found


def test_the_name_is_the_file_name_and_each_file_says_what_it_holds() -> None:
    assert FOURTH.name == "fourth"
    assert fourth.__name__ == f"{prompts.__name__}.{FOURTH.name}"
    assert fourth_examples.__name__ == f"{prompts.__name__}.fourth_examples"
    assert fourth.__doc__ and fourth_examples.__doc__


def test_the_instructions_are_the_first_ones_then_the_two_rules_of_second_and_nothing_else() -> (
    None
):
    assert FOURTH.instructions == FIRST_PROMPT.instructions + "".join(ADDED_AFTER)
    assert FOURTH.instructions.startswith(FIRST_PROMPT.instructions)
    assert FOURTH.instructions == second.SECOND_PROMPT.instructions
    assert FOURTH.instructions == third.THIRD_PROMPT.instructions
    assert len(ADDED_AFTER) <= MOST_PARAGRAPHS


def test_the_two_rules_are_the_constants_of_second_taken_not_copied() -> None:
    assert fourth.BUY_WORDS_RULE is second.BUY_WORDS_RULE
    assert fourth.U_TOTAL_RULE is second.U_TOTAL_RULE


def test_the_examples_are_the_first_ten_themselves_then_the_new_ones() -> None:
    first_count = len(FIRST_EXAMPLES)

    assert FOURTH.examples is fourth_examples.FOURTH_EXAMPLES
    assert FOURTH.examples[:first_count] == FIRST_EXAMPLES
    for given, own in zip(FOURTH.examples[:first_count], FIRST_EXAMPLES, strict=True):
        assert given is own
    assert FOURTH.examples[first_count:] == fourth_examples.ADDED_EXAMPLES
    assert 1 <= len(fourth_examples.ADDED_EXAMPLES) <= MOST_EXAMPLES


def test_the_examples_file_takes_nothing_from_the_examples_of_second() -> None:
    names = imported_modules(Path(fourth_examples.__file__))

    assert not any("second" in name for name in names), names
    assert not hasattr(fourth_examples, "second_examples")
    assert not hasattr(fourth_examples, "OWNER_EXAMPLES")


def test_the_words_for_asking_again_are_the_first_prompts() -> None:
    assert FOURTH.ask_again == FIRST_PROMPT.ask_again


def test_the_reply_table_is_the_shared_table_itself() -> None:
    # The scripted model of the flow tests routes a call by the identity of its table.
    assert FOURTH.reply_table is REPLY_TABLE
    assert FOURTH.reply_table is FIRST_PROMPT.reply_table


def test_the_messages_are_the_instructions_every_example_in_order_and_the_passage() -> None:
    messages = build_messages(FOURTH, "买了 BTC")

    assert (messages[0].role, messages[0].content) == (Role.SYSTEM, FOURTH.instructions)
    pairs = messages[1:-1]
    assert len(pairs) == 2 * len(FOURTH.examples)
    for index, example in enumerate(FOURTH.examples):
        said, written = pairs[2 * index], pairs[2 * index + 1]
        assert (said.role, said.content) == (Role.USER, example.passage)
        assert (written.role, written.content) == (Role.ASSISTANT, example_reply(example))
    assert (messages[-1].role, messages[-1].content) == (Role.USER, "买了 BTC")


@pytest.mark.parametrize("passage", ["今天在OKX补了20U的DOT，均价4.1", "Bought 2 SOL at 150 today"])
def test_a_reply_to_the_fourth_version_is_read_as_with_the_first(passage: str) -> None:
    rows = [row(side="buy", coin="DOT", total="20U", price="4.1", platform="OKX")]
    if passage.startswith("Bought"):
        rows = [row(side="buy", coin="SOL", quantity="2 SOL", price="150", time="today")]

    with_fourth, model = run(passage, table(*rows), prompt=FOURTH)
    with_first, _ = run(passage, table(*rows))

    assert isinstance(with_fourth, Extracted) and isinstance(with_first, Extracted)
    assert with_fourth.drafts == with_first.drafts
    assert with_fourth.issues == with_first.issues
    assert model.calls[0].reply_schema is REPLY_TABLE
    assert model.calls[0].messages[0].content == FOURTH.instructions
