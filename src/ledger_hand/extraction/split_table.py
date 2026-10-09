"""The table the model fills when it splits a passage: the pieces each trade needs.

When a passage is split before extraction (``splitting``), the model is
asked to copy out, for each trade the passage reports, the pieces of the
passage that trade needs, a detail said once for several trades going into
each of them. ``SPLIT_TABLE`` is that answer written as a JSON schema,
handed to the model with the call so that the model server holds the reply
to it. ``read_split_reply`` reads a reply against it and gives back the
pieces of each trade, or ``SplitUnreadable`` with the part of the shape the
reply missed. It never raises for anything the model wrote, and it mends
nothing.

The shape, and nothing else, is: a reply the model ended itself, of at most
``MAX_SPLIT_REPLY_CHARACTERS`` characters; valid JSON with no key written
twice in one object and no ``NaN`` or ``Infinity``; an object with the key
``trades`` holding a list of at most ``MAX_SPLIT_TRADES`` items; every item
an object whose ``pieces`` is a list of at most ``MAX_PIECES`` items, each
valid text. Keys the table does not have are ignored. Whether a piece is a
piece of the passage is not looked at here.

A version of the prompt for this (``SplitPromptVersion``) holds the
instructions, the words for asking again and its examples; an example
(``SplitExample``) is an invented passage and the pieces of each of its
trades, and ``example_split_reply`` writes it as the model should.

Names defined here: ``SPLIT_TABLE``, ``SplitProblem``, ``SplitUnreadable``,
``read_split_reply``, ``SplitExample``, ``SplitPromptVersion``,
``example_split_reply``, ``MAX_SPLIT_REPLY_CHARACTERS``,
``MAX_SPLIT_TRADES`` and ``MAX_PIECES``.
"""

from __future__ import annotations

import enum
import json
from collections.abc import Mapping
from dataclasses import dataclass

from ledger_hand.extraction.prompting import PROBLEM_MARK
from ledger_hand.ports import FinishReason, ModelReply

# Far longer than any honest split of one passage, which is at most 16,384
# characters long and is copied out in pieces; more is not parsed at all.
MAX_SPLIT_REPLY_CHARACTERS = 1_000_000
# Far more trades than one passage reports, and far more pieces than a trade needs.
MAX_SPLIT_TRADES = 100
MAX_PIECES = 100

_TRADES_KEY = "trades"
_PIECES_KEY = "pieces"

SPLIT_TABLE: Mapping[str, object] = {
    "type": "object",
    "properties": {
        _TRADES_KEY: {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {_PIECES_KEY: {"type": "array", "items": {"type": "string"}}},
                "required": [_PIECES_KEY],
                "additionalProperties": False,
            },
        }
    },
    "required": [_TRADES_KEY],
    "additionalProperties": False,
}


class SplitProblem(enum.Enum):
    """Which part of the shape a reply missed."""

    CUT_OFF = "the model stopped at the length limit, so the reply is not whole"
    TOO_LONG = "the reply is longer than any split of one passage"
    NOT_JSON = "the reply is not valid JSON"
    REPEATED_KEY = "the reply writes the same key twice in one object"
    NO_TRADES_LIST = "the reply is not an object with a list under 'trades'"
    TOO_MANY_TRADES = "the reply lists more trades than one passage can hold"
    TRADE_NOT_AN_OBJECT = "a trade of the reply is not an object"
    NO_PIECES_LIST = "a trade of the reply has no list under 'pieces'"
    TOO_MANY_PIECES = "a trade of the reply lists more pieces than a trade needs"
    PIECE_NOT_TEXT = "a piece of the reply is not valid text"


@dataclass(frozen=True)
class SplitUnreadable:
    """A reply that does not have the shape of the table."""

    problem: SplitProblem


class _NotTheTableError(Exception):
    def __init__(self, problem: SplitProblem) -> None:
        super().__init__(problem)
        self.problem = problem


def read_split_reply(reply: ModelReply) -> tuple[tuple[str, ...], ...] | SplitUnreadable:
    """The pieces of each trade in ``reply``, as written, or why it is not the table."""
    if reply.record.finish is FinishReason.LENGTH_LIMIT:
        return SplitUnreadable(SplitProblem.CUT_OFF)
    if len(reply.text) > MAX_SPLIT_REPLY_CHARACTERS:
        return SplitUnreadable(SplitProblem.TOO_LONG)
    try:
        parsed = json.loads(
            reply.text, object_pairs_hook=_without_repeated_keys, parse_constant=_refuse
        )
    except _NotTheTableError as error:
        return SplitUnreadable(error.problem)
    except (ValueError, RecursionError):
        return SplitUnreadable(SplitProblem.NOT_JSON)
    try:
        return _trades(parsed)
    except _NotTheTableError as error:
        return SplitUnreadable(error.problem)


def _without_repeated_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    found = dict(pairs)
    if len(found) != len(pairs):
        raise _NotTheTableError(SplitProblem.REPEATED_KEY)
    return found


def _refuse(name: str) -> object:
    raise ValueError(f"{name} is not JSON")


def _trades(parsed: object) -> tuple[tuple[str, ...], ...]:
    if not isinstance(parsed, dict) or not isinstance(parsed.get(_TRADES_KEY), list):
        raise _NotTheTableError(SplitProblem.NO_TRADES_LIST)
    listed: list[object] = parsed[_TRADES_KEY]
    if len(listed) > MAX_SPLIT_TRADES:
        raise _NotTheTableError(SplitProblem.TOO_MANY_TRADES)
    return tuple(_pieces(item) for item in listed)


def _pieces(item: object) -> tuple[str, ...]:
    if not isinstance(item, dict):
        raise _NotTheTableError(SplitProblem.TRADE_NOT_AN_OBJECT)
    pieces = item.get(_PIECES_KEY)
    if not isinstance(pieces, list):
        raise _NotTheTableError(SplitProblem.NO_PIECES_LIST)
    if len(pieces) > MAX_PIECES:
        raise _NotTheTableError(SplitProblem.TOO_MANY_PIECES)
    if not all(_is_text(piece) for piece in pieces):
        raise _NotTheTableError(SplitProblem.PIECE_NOT_TEXT)
    return tuple(pieces)


def _is_text(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


@dataclass(frozen=True)
class SplitExample:
    """An invented passage, and the pieces of each of its trades as the model should copy them."""

    passage: str
    trades: tuple[tuple[str, ...], ...]


@dataclass(frozen=True)
class SplitPromptVersion:
    """One version of the prompt that splits a passage.

    ``ask_again`` holds ``PROBLEM_MARK`` once, where the words for what was
    wrong with the last reply go.
    """

    name: str
    instructions: str
    examples: tuple[SplitExample, ...]
    ask_again: str

    def __post_init__(self) -> None:
        if self.ask_again.count(PROBLEM_MARK) != 1:
            raise ValueError(f"the words for asking again must hold {PROBLEM_MARK} once")


def example_split_reply(example: SplitExample) -> str:
    """The table of ``example`` written as the model should write it."""
    trades = [{_PIECES_KEY: list(pieces)} for pieces in example.trades]
    return json.dumps({_TRADES_KEY: trades}, ensure_ascii=False)
