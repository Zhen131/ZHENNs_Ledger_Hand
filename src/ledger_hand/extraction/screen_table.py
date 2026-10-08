"""The list the model fills when it judges a passage: what kinds of thing it reports.

The model is given one fixed list of kinds (``Kind``) and answers with a flat
list of reports, each one kind and a piece of the passage it copied as its
evidence. ``SCREEN_TABLE`` is that answer written as a JSON schema, handed to
the model with the call so that the model server holds the reply to it.
``read_screen_reply`` reads a reply against it and gives back the reports, or
``ScreenUnreadable`` with the part of the shape the reply missed. It never
raises for anything the model wrote, and it mends nothing.

The shape, and nothing else, is: a reply the model ended itself, of at most
``MAX_SCREEN_REPLY_CHARACTERS`` characters; valid JSON with no key written
twice in one object and no ``NaN`` or ``Infinity``; an object with the key
``reports`` holding a list of at most ``MAX_REPORTS`` items; every item an
object whose ``kind`` is one of the kinds and whose ``evidence``, where it is
there, is valid text. Keys the table does not have are ignored. Whether the
evidence is a piece of the passage is not looked at here.

Names defined here: ``Kind``, ``NOT_TO_RECORD``, ``ScreenReport``,
``ScreenProblem``, ``ScreenReplyUnreadable``, ``read_screen_reply``,
``SCREEN_TABLE``, ``MAX_SCREEN_REPLY_CHARACTERS`` and ``MAX_REPORTS``.
"""

from __future__ import annotations

import enum
import json
from collections.abc import Mapping
from dataclasses import dataclass

from ledger_hand.ports import FinishReason, ModelReply

# Far longer than any honest list of reports about one passage, which is at
# most 16,384 characters long; more is not parsed at all.
MAX_SCREEN_REPLY_CHARACTERS = 100_000
# Far more reports than one passage holds.
MAX_REPORTS = 100

_REPORTS_KEY = "reports"
_KIND_KEY = "kind"
_EVIDENCE_KEY = "evidence"


class Kind(enum.Enum):
    """A kind of thing a passage may report; the value is the model's word for it."""

    SPOT_TRADE = "spot_trade"
    FUTURES_OR_LEVERAGE = "futures_or_leverage"
    COIN_FOR_COIN = "coin_for_coin"
    OPEN_ORDER = "open_order"
    PLAN = "plan"


# The kinds the ledger does not record.
NOT_TO_RECORD: frozenset[Kind] = frozenset(Kind) - {Kind.SPOT_TRADE}

SCREEN_TABLE: Mapping[str, object] = {
    "type": "object",
    "properties": {
        _REPORTS_KEY: {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    _KIND_KEY: {"type": "string", "enum": [kind.value for kind in Kind]},
                    _EVIDENCE_KEY: {"type": "string"},
                },
                "required": [_KIND_KEY, _EVIDENCE_KEY],
                "additionalProperties": False,
            },
        }
    },
    "required": [_REPORTS_KEY],
    "additionalProperties": False,
}


class ScreenProblem(enum.Enum):
    """Which part of the shape a reply missed."""

    CUT_OFF = "the model stopped at the length limit, so the reply is not whole"
    TOO_LONG = "the reply is longer than any list of reports about one passage"
    NOT_JSON = "the reply is not valid JSON"
    REPEATED_KEY = "the reply writes the same key twice in one object"
    NO_REPORTS_LIST = "the reply is not an object with a list under 'reports'"
    TOO_MANY_REPORTS = "the reply lists more reports than one passage can hold"
    REPORT_NOT_AN_OBJECT = "a report of the reply is not an object"
    KIND_NOT_ALLOWED = "the kind of a report is not one of the list"
    EVIDENCE_NOT_TEXT = "the evidence of a report is not valid text"


@dataclass(frozen=True)
class ScreenReport:
    """One report as the model wrote it: a kind, and its evidence as written (may be empty)."""

    kind: Kind
    evidence: str


@dataclass(frozen=True)
class ScreenReplyUnreadable:
    """A reply that does not have the shape of the list."""

    problem: ScreenProblem


class _NotTheListError(Exception):
    def __init__(self, problem: ScreenProblem) -> None:
        super().__init__(problem)
        self.problem = problem


_KINDS = {kind.value: kind for kind in Kind}


def read_screen_reply(reply: ModelReply) -> tuple[ScreenReport, ...] | ScreenReplyUnreadable:
    """The reports in ``reply``, in the order written, or why it is not the list."""
    if reply.record.finish is FinishReason.LENGTH_LIMIT:
        return ScreenReplyUnreadable(ScreenProblem.CUT_OFF)
    if len(reply.text) > MAX_SCREEN_REPLY_CHARACTERS:
        return ScreenReplyUnreadable(ScreenProblem.TOO_LONG)
    try:
        parsed = json.loads(
            reply.text, object_pairs_hook=_without_repeated_keys, parse_constant=_refuse
        )
    except _NotTheListError as error:
        return ScreenReplyUnreadable(error.problem)
    except (ValueError, RecursionError):
        return ScreenReplyUnreadable(ScreenProblem.NOT_JSON)
    try:
        return _reports(parsed)
    except _NotTheListError as error:
        return ScreenReplyUnreadable(error.problem)


def _without_repeated_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    found = dict(pairs)
    if len(found) != len(pairs):
        raise _NotTheListError(ScreenProblem.REPEATED_KEY)
    return found


def _refuse(name: str) -> object:
    raise ValueError(f"{name} is not JSON")


def _reports(parsed: object) -> tuple[ScreenReport, ...]:
    if not isinstance(parsed, dict) or not isinstance(parsed.get(_REPORTS_KEY), list):
        raise _NotTheListError(ScreenProblem.NO_REPORTS_LIST)
    listed: list[object] = parsed[_REPORTS_KEY]
    if len(listed) > MAX_REPORTS:
        raise _NotTheListError(ScreenProblem.TOO_MANY_REPORTS)
    return tuple(_report(item) for item in listed)


def _report(item: object) -> ScreenReport:
    if not isinstance(item, dict):
        raise _NotTheListError(ScreenProblem.REPORT_NOT_AN_OBJECT)
    kind = item.get(_KIND_KEY)
    if not isinstance(kind, str) or kind not in _KINDS:
        raise _NotTheListError(ScreenProblem.KIND_NOT_ALLOWED)
    evidence = item.get(_EVIDENCE_KEY, "")
    if not _is_text(evidence):
        raise _NotTheListError(ScreenProblem.EVIDENCE_NOT_TEXT)
    return ScreenReport(_KINDS[kind], evidence)


def _is_text(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True
