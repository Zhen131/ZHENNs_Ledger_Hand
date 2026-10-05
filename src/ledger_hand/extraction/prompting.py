"""What a prompt version is, and the messages it makes for one passage.

A ``PromptVersion`` is the instructions, the examples and the words used to
ask again after a reply that could not be read. Each version lives in a file
of its own under ``prompts/``, and its examples in a file beside it, so that
the test sentences of an experiment can be checked against them.

``build_messages`` lays a version out as a conversation: the instructions
as the system message; then each example as the passage, said by the user,
and its table, written by the model; then the passage to read. Shown this
way, an example is exactly the exchange the model is asked to continue. When
the model is asked again, one more user message says what was wrong.

Names defined here: ``PromptVersion``, ``Example``, ``ExampleRow``,
``build_messages``, ``example_reply`` and ``PROBLEM_MARK``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass

from ledger_hand.extraction.reply_parser import ReplyProblem
from ledger_hand.extraction.reply_table import TRADES_KEY, Field
from ledger_hand.ports import Message, Role

type ExampleRow = Mapping[Field, str]
"""One row of an example's table; a field that is left out is empty."""

# Where the words for what was wrong go in a version's words for asking again.
PROBLEM_MARK = "<problem>"


@dataclass(frozen=True)
class Example:
    """An invented passage and the table the model should write for it."""

    passage: str
    rows: tuple[ExampleRow, ...]


@dataclass(frozen=True)
class PromptVersion:
    """One version of the prompt.

    ``ask_again`` holds ``PROBLEM_MARK`` once, where the words for what was
    wrong with the last reply go.
    """

    name: str
    instructions: str
    examples: tuple[Example, ...]
    ask_again: str

    def __post_init__(self) -> None:
        if self.ask_again.count(PROBLEM_MARK) != 1:
            raise ValueError(f"the words for asking again must hold {PROBLEM_MARK} once")


def example_reply(example: Example) -> str:
    """The table of ``example`` written as the model should write it."""
    rows = [{field.value: row.get(field, "") for field in Field} for row in example.rows]
    return json.dumps({TRADES_KEY: rows}, ensure_ascii=False)


def build_messages(
    prompt: PromptVersion, passage: str, problem: ReplyProblem | None = None
) -> tuple[Message, ...]:
    """The conversation that asks for the table of ``passage``.

    With ``problem``, it ends by saying what was wrong with the last reply.
    """
    messages = [Message(Role.SYSTEM, prompt.instructions)]
    for example in prompt.examples:
        messages.append(Message(Role.USER, example.passage))
        messages.append(Message(Role.ASSISTANT, example_reply(example)))
    messages.append(Message(Role.USER, passage))
    if problem is not None:
        messages.append(Message(Role.USER, prompt.ask_again.replace(PROBLEM_MARK, problem.value)))
    return tuple(messages)
