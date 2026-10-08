"""What the model is asked when an answer cannot be read by the rules, and how its reply is read.

When the rules cannot read a whole answer, the model is asked to copy out of
it the one piece that gives what was asked (``Wanted``). Its reply is a JSON
object with one text, ``{"phrase": "..."}``; ``ANSWER_TABLE`` is that shape
as a JSON schema, handed to the model with the call. ``read_copy_reply``
gives back the phrase, or ``CopyReplyUnreadable`` with the part of the
shape the reply missed. It never raises for anything the model wrote, and
it mends nothing. Whether the phrase is a piece of the answer is not looked
at here.

The shape, and nothing else: a reply the model ended itself, of at most
``MAX_COPY_REPLY_CHARACTERS`` characters; valid JSON with no key written
twice and no ``NaN`` or ``Infinity``; an object whose ``phrase`` is valid
text. Keys the shape does not have are ignored.

``AnswerPromptVersion`` is what a version of the prompt for this holds: the
instructions, the words that describe each thing that may be wanted, and the
words for asking again after a reply that could not be read.

Names defined here: ``Wanted``, ``AnswerPromptVersion``, ``ANSWER_TABLE``,
``CopyProblem``, ``CopyReplyUnreadable``, ``read_copy_reply`` and
``MAX_COPY_REPLY_CHARACTERS``.
"""

from __future__ import annotations

import enum
import json
from collections.abc import Mapping
from dataclasses import dataclass

from ledger_hand.extraction.prompting import PROBLEM_MARK
from ledger_hand.ports import FinishReason, ModelReply

# An answer is at most as long as a passage; a copy of a piece of it is
# shorter still, and a reply far longer is not parsed at all.
MAX_COPY_REPLY_CHARACTERS = 100_000

_PHRASE_KEY = "phrase"


class Wanted(enum.Enum):
    """What the model is asked to copy out of an answer."""

    SIDE = "side"
    COIN = "coin"
    QUANTITY = "quantity"
    PRICE = "price"
    TOTAL = "total"
    FEE = "fee"
    FEE_COIN = "fee coin"
    TIME = "time"
    YES_OR_NO = "yes or no"


@dataclass(frozen=True)
class AnswerPromptVersion:
    """One version of the prompt that copies a piece out of an answer.

    ``fields`` describes each thing that may be wanted, in the words the
    model is given. ``ask_again`` holds ``PROBLEM_MARK`` once.
    """

    name: str
    instructions: str
    fields: Mapping[Wanted, str]
    ask_again: str

    def __post_init__(self) -> None:
        if set(self.fields) != set(Wanted):
            raise ValueError("a version must describe everything that may be wanted")
        if self.ask_again.count(PROBLEM_MARK) != 1:
            raise ValueError(f"the words for asking again must hold {PROBLEM_MARK} once")


ANSWER_TABLE: Mapping[str, object] = {
    "type": "object",
    "properties": {_PHRASE_KEY: {"type": "string"}},
    "required": [_PHRASE_KEY],
    "additionalProperties": False,
}


class CopyProblem(enum.Enum):
    """Which part of the shape a reply missed."""

    CUT_OFF = "the model stopped at the length limit, so the reply is not whole"
    TOO_LONG = "the reply is longer than any copy of a piece of an answer"
    NOT_JSON = "the reply is not valid JSON"
    REPEATED_KEY = "the reply writes the same key twice in one object"
    NO_PHRASE = "the reply is not an object with a text under 'phrase'"


@dataclass(frozen=True)
class CopyReplyUnreadable:
    """A reply that does not have the shape."""

    problem: CopyProblem


class _RepeatedKeyError(ValueError):
    pass


def read_copy_reply(reply: ModelReply) -> str | CopyReplyUnreadable:
    """The phrase in ``reply`` as the model wrote it (may be empty), or why it is not one."""
    if reply.record.finish is FinishReason.LENGTH_LIMIT:
        return CopyReplyUnreadable(CopyProblem.CUT_OFF)
    if len(reply.text) > MAX_COPY_REPLY_CHARACTERS:
        return CopyReplyUnreadable(CopyProblem.TOO_LONG)
    try:
        parsed = json.loads(
            reply.text, object_pairs_hook=_without_repeated_keys, parse_constant=_refuse
        )
    except _RepeatedKeyError:
        return CopyReplyUnreadable(CopyProblem.REPEATED_KEY)
    except (ValueError, RecursionError):
        return CopyReplyUnreadable(CopyProblem.NOT_JSON)
    phrase = parsed.get(_PHRASE_KEY) if isinstance(parsed, dict) else None
    if not isinstance(phrase, str) or not _is_valid_text(phrase):
        return CopyReplyUnreadable(CopyProblem.NO_PHRASE)
    return phrase


def _without_repeated_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    found = dict(pairs)
    if len(found) != len(pairs):
        raise _RepeatedKeyError
    return found


def _refuse(name: str) -> object:
    raise ValueError(f"{name} is not JSON")


def _is_valid_text(text: str) -> bool:
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True
