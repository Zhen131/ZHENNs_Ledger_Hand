"""Judging one tool call the model made: taken as it stands, or a wrong step and why.

A tool call is untrusted input. ``judge`` takes it, with everything the
user has said in this chat so far, and gives back an ``Accepted`` call (the
tool and its arguments as text), or a ``Misstep`` saying what is wrong, in
words the model is shown so that it can try again. A call is a wrong step
when:

- its tool is not one of the eight (``UNKNOWN_TOOL``);
- it gives an argument the tool does not take (``UNKNOWN_ARGUMENT``), leaves
  out a required one (``MISSING_ARGUMENT``), gives one that is not text
  (``NOT_TEXT``), or a choice that is not on its list (``NOT_A_CHOICE``);
- a copied argument is not a piece of anything the user said
  (``NOT_COPIED``).

Whether a copied argument is a piece of the user's words is judged the way
extraction judges a copied phrase (``extraction.passage``): full and half
width and runs of whitespace are tidied, letter case is not, and a phrase
that cuts a number in two is not a piece ("0.0016" is not a piece of "改成
0.00167"). A new value for a number field is judged as a number, as a
copied number is in extraction. A phrase is looked for in each thing the
user said, one at a time.

An optional argument given as blank text counts as not given: a model often
fills every argument it sees, and an empty one says nothing the program
could take for the user's words.

Names defined here: ``MisstepKind``, ``Misstep``, ``Accepted`` and ``judge``.
"""

from __future__ import annotations

import enum
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from ledger_hand.assistant.tools import (
    NUMBER_FIELDS,
    Argument,
    ArgumentKind,
    Need,
    Tool,
    ToolName,
    tool_named,
)
from ledger_hand.extraction.passage import Passage, Piece, PieceMiss
from ledger_hand.ports import ToolCall


class MisstepKind(enum.Enum):
    """What is wrong with a tool call."""

    UNKNOWN_TOOL = "unknown_tool"
    UNKNOWN_ARGUMENT = "unknown_argument"
    MISSING_ARGUMENT = "missing_argument"
    NOT_TEXT = "not_text"
    NOT_A_CHOICE = "not_a_choice"
    NOT_COPIED = "not_copied"


@dataclass(frozen=True, kw_only=True)
class Misstep:
    """A wrong step: its kind, and what is wrong in one sentence the model is shown."""

    kind: MisstepKind
    detail: str


@dataclass(frozen=True, kw_only=True)
class Accepted:
    """A call taken as it stands: its tool, and the arguments given, all text."""

    tool: ToolName
    arguments: Mapping[str, str]


def judge(call: ToolCall, user_said: Sequence[str]) -> Accepted | Misstep:
    """Judge ``call`` against the tools and everything the user said in this chat."""
    tool = tool_named(call.name)
    if tool is None:
        return Misstep(
            kind=MisstepKind.UNKNOWN_TOOL, detail=f"There is no tool called {call.name!r}."
        )
    given: dict[str, str] = {}
    for name, value in call.arguments.items():
        argument = tool.argument(name)
        if argument is None:
            return Misstep(
                kind=MisstepKind.UNKNOWN_ARGUMENT,
                detail=f"{tool.name.value} takes no argument {name!r}.",
            )
        if not isinstance(value, str):
            return Misstep(kind=MisstepKind.NOT_TEXT, detail=f"The argument {name!r} must be text.")
        if value.strip() or argument.need is Need.REQUIRED:
            given[name] = value
    return _checked(tool, given, user_said)


def _checked(tool: Tool, given: dict[str, str], user_said: Sequence[str]) -> Accepted | Misstep:
    for argument in tool.arguments:
        value = given.get(argument.name)
        if value is None:
            if argument.need is Need.REQUIRED:
                return Misstep(
                    kind=MisstepKind.MISSING_ARGUMENT,
                    detail=f"{tool.name.value} needs the argument {argument.name!r}.",
                )
            continue
        problem = _problem(argument, value, given, user_said)
        if problem is not None:
            return problem
    return Accepted(tool=tool.name, arguments=given)


def _problem(
    argument: Argument, value: str, given: Mapping[str, str], user_said: Sequence[str]
) -> Misstep | None:
    if argument.kind is ArgumentKind.CHOICE:
        if value in argument.choices:
            return None
        return Misstep(
            kind=MisstepKind.NOT_A_CHOICE,
            detail=(
                f"{argument.name!r} must be one of {', '.join(argument.choices)}, not {value!r}."
            ),
        )
    as_number = argument.name == "new_value" and given.get("field") in NUMBER_FIELDS
    find = _find_number if as_number else _find
    if any(isinstance(find(Passage(said), value), Piece) for said in user_said):
        return None
    return Misstep(
        kind=MisstepKind.NOT_COPIED,
        detail=(
            f"{argument.name!r} is {value!r}, which is not copied from what the user said. "
            "Copy the user's own words exactly; never convert or rewrite them."
        ),
    )


def _find(passage: Passage, value: str) -> Piece | PieceMiss:
    return passage.find(value)


def _find_number(passage: Passage, value: str) -> Piece | PieceMiss:
    return passage.find_number(value)
