"""Reading the model's reply: the rows of the table, or why the reply is not the table.

``read_reply`` takes one reply of the model and gives back either
``ReplyRows``, the rows it holds, or ``Unreadable`` with a ``ReplyProblem``.
It never raises for anything the model wrote.

A reply is read only when it has exactly the shape of the table. That shape,
and nothing else, is:

- a reply the model ended itself, not one cut off at the length limit, of at
  most ``MAX_REPLY_CHARACTERS`` characters;
- valid JSON: no ``NaN`` or ``Infinity``, and no key written twice in one
  object, since which of the two was meant cannot be told;
- an object with the key ``trades``, holding a list of at most ``MAX_ROWS``
  rows;
- every row an object; in every row, each field of the table, where it is
  present, holds text that is valid Unicode, and ``side`` holds ``buy``,
  ``sell`` or nothing at all.

Within that shape the reply may leave things out and add things: a field
that is missing counts as empty, and so does text of nothing but whitespace;
keys the table does not have are ignored, in a row and around the list.
Everything that is not that shape is unreadable, whatever it looks like,
and the reason says which part of the shape it missed. No reply is mended to
fit.

Whether a phrase really is a piece of the passage, and what it means, is not
looked at here.

Names defined here: ``read_reply``, ``ReplyRow``, ``ReplyRows``,
``Unreadable``, ``ReplyProblem``, ``MAX_REPLY_CHARACTERS`` and ``MAX_ROWS``.
"""

from __future__ import annotations

import enum
import json
from collections.abc import Mapping
from dataclasses import dataclass

from ledger_hand.core.trade import Side
from ledger_hand.extraction.reply_table import COPIED_FIELDS, SIDE_WORDS, TRADES_KEY, Field
from ledger_hand.ports import FinishReason, ModelReply

# Far longer than any answer to one passage, which is at most 16,384
# characters long and is copied from in pieces. Text beyond it is not parsed
# at all, so that no reply costs more than a fixed amount of work.
MAX_REPLY_CHARACTERS = 1_000_000

# Far more trades than one passage reports: the default reply length holds
# about ten rows. A longer list is not an answer to one passage.
MAX_ROWS = 200


class ReplyProblem(enum.Enum):
    """Which part of the table's shape a reply missed."""

    CUT_OFF = "the model stopped at the length limit, so the reply is not whole"
    TOO_LONG = "the reply is longer than any answer to one passage"
    NOT_JSON = "the reply is not valid JSON"
    REPEATED_KEY = "the reply writes the same key twice in one object"
    NO_TRADES_LIST = "the reply is not an object with a list under 'trades'"
    TOO_MANY_ROWS = "the reply lists more rows than one passage can hold"
    ROW_NOT_AN_OBJECT = "a row of the reply is not an object"
    CELL_NOT_TEXT = "a field of a row holds something other than valid text"
    SIDE_NOT_ALLOWED = "the side of a row is not 'buy', 'sell' or empty"


@dataclass(frozen=True)
class ReplyRow:
    """One row as the model wrote it.

    ``cells`` holds the copied fields that are not empty, with their text
    exactly as the model wrote it; a field that is empty is left out.
    """

    side: Side | None
    cells: Mapping[Field, str]

    @property
    def is_empty(self) -> bool:
        return self.side is None and not self.cells


@dataclass(frozen=True)
class ReplyRows:
    """A reply that has the table's shape, and its rows in the order written."""

    rows: tuple[ReplyRow, ...]


@dataclass(frozen=True)
class Unreadable:
    """A reply that does not have the table's shape."""

    problem: ReplyProblem


class _RepeatedKeyError(ValueError):
    """An object in the reply writes one key twice."""


class _NotTheTableError(Exception):
    """The parsed reply misses the table's shape; carries the problem."""

    def __init__(self, problem: ReplyProblem) -> None:
        super().__init__(problem)
        self.problem = problem


class _Number:
    """Stands for a JSON number. No number is ever part of the table, so its
    value is not needed, and a number of thousands of digits is never built."""


def read_reply(reply: ModelReply) -> ReplyRows | Unreadable:
    """The rows of ``reply``, or the reason it does not have the table's shape."""
    if reply.record.finish is FinishReason.LENGTH_LIMIT:
        return Unreadable(ReplyProblem.CUT_OFF)
    if len(reply.text) > MAX_REPLY_CHARACTERS:
        return Unreadable(ReplyProblem.TOO_LONG)
    try:
        parsed = json.loads(
            reply.text,
            object_pairs_hook=_object_without_repeated_keys,
            parse_constant=_refuse_constant,
            parse_int=_number,
            parse_float=_number,
        )
    except _RepeatedKeyError:
        return Unreadable(ReplyProblem.REPEATED_KEY)
    except (ValueError, RecursionError):
        # RecursionError: lists or objects nested deeper than the parser goes.
        return Unreadable(ReplyProblem.NOT_JSON)
    try:
        return ReplyRows(_rows(parsed))
    except _NotTheTableError as error:
        return Unreadable(error.problem)


def _object_without_repeated_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    found = dict(pairs)
    if len(found) != len(pairs):
        raise _RepeatedKeyError
    return found


def _refuse_constant(name: str) -> object:
    raise ValueError(f"{name} is not JSON")


def _number(_text: str) -> _Number:
    return _Number()


def _rows(parsed: object) -> tuple[ReplyRow, ...]:
    if not isinstance(parsed, dict) or not isinstance(parsed.get(TRADES_KEY), list):
        raise _NotTheTableError(ReplyProblem.NO_TRADES_LIST)
    listed: list[object] = parsed[TRADES_KEY]
    if len(listed) > MAX_ROWS:
        raise _NotTheTableError(ReplyProblem.TOO_MANY_ROWS)
    return tuple(_row(item) for item in listed)


def _row(item: object) -> ReplyRow:
    if not isinstance(item, dict):
        raise _NotTheTableError(ReplyProblem.ROW_NOT_AN_OBJECT)
    side_word = item.get(Field.SIDE.value, "")
    if not _is_text(side_word):
        raise _NotTheTableError(ReplyProblem.CELL_NOT_TEXT)
    if side_word not in SIDE_WORDS:
        raise _NotTheTableError(ReplyProblem.SIDE_NOT_ALLOWED)
    cells: dict[Field, str] = {}
    for field in COPIED_FIELDS:
        text = item.get(field.value, "")
        if not _is_text(text):
            raise _NotTheTableError(ReplyProblem.CELL_NOT_TEXT)
        if text.strip():
            cells[field] = text
    return ReplyRow(SIDE_WORDS[side_word], cells)


def _is_text(value: object) -> bool:
    """Whether ``value`` is a string that is valid Unicode, with no lone surrogate."""
    if not isinstance(value, str):
        return False
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True
