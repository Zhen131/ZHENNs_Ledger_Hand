"""The assistant's record on this machine: one line of JSON for each thing said, kept in a file.

Each time the assistant has dealt with one thing said (typed, an answer,
or a screenshot's text), one entry is added to the end of a plain text
file in the data folder (``settings.DataPlaces.assistant_record``): which
kind of ledger it was said to (the demo ledger or the ledger page; never
the link's port or token), what was said, what it was read as once
tidied (with each change), which way it went, who wrote the reply (and the question in
it, when one was asked), each tool the model asked for with its
arguments as given (those dropped among them), a short piece of what was
handed back, the failures and their codes, the trades proposed, each
trade not sent and why, the kinds of reminder said, each trade sent with
its proposal and how it stood when sent (or why the ledger turned it
down), each name of an asset handed to the model to pick from the
ledger's list when recording began (what it was, the words and the code
the model gave, whether it was taken and why not), each trade proposed
with its marks, what came of comparing its price with the market price
and its cells sent empty, how it ended, and the
model and prompt versions used. Amounts are
written as text, each beside the money the result names. A screenshot's
picture is never written: only that it came from a screenshot, and the
passage made from it.

The file is not the book and not in Git. It is plain text and holds what
the person said, word for word, with its numbers; the settings page says
so beside the button that clears it.

- ``entry_for`` makes one entry from what came of one thing said; the
  moment is handed in, as this module reads no clock.
- ``keep`` adds one entry. It reads the whole file first: a file holding
  a line it cannot read, or one of a newer version, is left exactly as it
  is and nothing is added (``NotKept`` says why). Only a last line cut
  off half-way, with no line end, is passed over, and cut off before the
  next entry is added; nothing else already there is ever changed.
  Beyond ``KEPT_AT_MOST`` entries the oldest go: the entries kept are
  written to a new file beside it, which then takes its name
  (``os.replace``), so the file is never rewritten in place.
- ``read_record`` gives the entries, or why the file cannot be read;
  ``clear_record`` deletes the file, whatever it holds.

Two browser tabs adding an entry at the same moment may lose one; this
is accepted (``docs/known-gaps.md``).

Names defined here: ``RECORD_VERSION``, ``KEPT_AT_MOST``,
``RESULT_KEPT``, ``RecordProblem``, ``NotKept``, ``Kept``, ``RecordRead``,
``Unreadable``, ``Cleared``, ``entry_for``, ``keep``, ``read_record`` and
``clear_record``.
"""

from __future__ import annotations

import enum
import json
import os
import uuid
from collections.abc import Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from ledger_hand.assistant.outcome import NotRunCall, RefusedCall, TakenCall
from ledger_hand.core.ledger_records import TradeFacts
from ledger_hand.core.marks import Field
from ledger_hand.core.price_check import PriceCheck
from ledger_hand.core.proposals import CheckOutcome, ProposalStatus
from ledger_hand.core.trade_card import TradeCard
from ledger_hand.flows.assisting import DEFAULT_PROMPT
from ledger_hand.flows.conversation import Route, Said
from ledger_hand.flows.record_words import spoken_reminders
from ledger_hand.flows.recorded import RecordEnding
from ledger_hand.flows.standing import LedgerKind
from ledger_hand.ports import LedgerError, ModelError

# The record's own version, written in every entry; it is none of the
# ledger's four version numbers and not the book's. Version 2 (2026-11-25,
# 68B2): a call to record keeps one line in "sent" for each trade sent, with
# its number, its own proposal or why the ledger turned it down. Entries of
# version 1 are still read as they are. Version 3 (2026-11-25) added
# "read_as": the words tidied and each change, or null when nothing was
# changed. Entries of versions 1 and 2 are still read as they are.
# Version 4 (2026-11-25) added "asset_picks": each name of an asset handed
# to the model to pick from the ledger's list when recording began, or an
# empty list. Entries of versions 1 to 3 are still read as they are.
# Version 5 (2026-11-25, 68B3) added "ledger": which kind of ledger it was
# said to, "demo" or "page". A new name, so a new version, as version 4's
# golden sample is committed and never changed (architecture, rule 11).
# Entries of versions 1 to 4 are still read as they are.
# Version 6 (2026-11-25) added "marks": for each trade proposed, its number,
# the marks on its cells (cell, kind, reason), what came of comparing its
# price with the ledger's market price, and the cells sent empty (filled in
# since cards with empty cells are sent, 2026-11-26, with no new version: a
# trade's cell sent empty is null in "trades", and its name is in "empty").
# Entries of versions 1 to 5 are still read as they are.
RECORD_VERSION = 6

# One thousand: an entry is a few thousand bytes, so the file stays at a few
# megabytes and is read whole in a blink each time an entry is added; at
# twenty things said a day it holds about the last seven weeks.
KEPT_AT_MOST = 1000

# What a tool handed back can run to a whole list; the first part is enough
# to see what it was, and the ledger keeps the rest.
RESULT_KEPT = 300

_LINE_END = b"\n"


class RecordProblem(enum.Enum):
    """Why the record was not added to, or cannot be read."""

    NEWER_VERSION = "the record file was written by a newer version of this program"
    LINE_NOT_READ = "a line of the record file cannot be read"
    CANNOT_READ = "the record file cannot be read"
    CANNOT_WRITE = "the record file cannot be written"
    NO_DATA_FOLDER = "these parts have no data folder"


@dataclass(frozen=True)
class NotKept:
    """Why nothing was added: the problem, and what the system or the file said."""

    problem: RecordProblem
    detail: str = ""


@dataclass(frozen=True)
class Kept:
    """The entry was added; ``entries`` is how many the file holds now."""

    entries: int


@dataclass(frozen=True)
class RecordRead:
    """The entries of the file, oldest first; none when there is no file yet.

    ``cut_line`` says that a last line cut off half-way was passed over.
    """

    entries: tuple[Mapping[str, Any], ...]
    cut_line: bool = False


@dataclass(frozen=True)
class Unreadable:
    """Why the file cannot be read: the problem, and which line or what the system said."""

    problem: RecordProblem
    detail: str


class Cleared(enum.Enum):
    """What came of clearing the record."""

    DELETED = "the record file was deleted"
    NOTHING_THERE = "there was no record file"


# --- one entry ----------------------------------------------------------------


def entry_for(
    said: Said,
    *,
    words: str,
    at: datetime,
    model: str,
    vision_model: str | None = None,
    ledger: LedgerKind = LedgerKind.DEMO,
) -> dict[str, Any]:
    """The entry for ``words``, said at ``at``, and ``said``, what came of them.

    ``words`` are what the person said; for a screenshot, the passage made
    from its text and note. ``model`` and ``vision_model`` name the models;
    ``vision_model`` is written only for a screenshot's text. ``ledger`` is
    which kind of ledger it was said to.
    """
    if at.utcoffset() is None:
        raise ValueError("the moment of an entry must carry an offset")
    screenshot = said.route is Route.SCREENSHOT
    return {
        "format_version": RECORD_VERSION,
        "at": at.isoformat(),
        "ledger": ledger.name.lower(),
        "said": words,
        "read_as": _read_as(said),
        "from_screenshot": screenshot,
        "route": said.route.name.lower(),
        "words_by": said.words_by.name.lower(),
        "question_by": _question_by(said),
        "reply": said.reply,
        "endings": _endings(said),
        "steps": _steps(said),
        "failures": _failures(said),
        "trades": _trades(said),
        "left_out": _left_out(said),
        "asset_picks": _asset_picks(said),
        "reminders": _reminders(said),
        "sent": _sent(said),
        "marks": _marks(said),
        "models": {"tools": model, "vision": vision_model if screenshot else None},
        "prompts": _prompts(said),
    }


def _read_as(said: Said) -> dict[str, Any] | None:
    """The words tidied and each change, when tidying changed anything; ``None`` otherwise."""
    tidied = said.read_as
    if tidied is None or not tidied.changed:
        return None
    changes = [
        {"kind": change.kind.name.lower(), "said": change.said, "written": change.written}
        for change in tidied.changes
    ]
    return {"text": tidied.text, "changes": changes}


def _question_by(said: Said) -> str | None:
    """Who wrote the sentence of the question asked, when one was: the model or the program."""
    question = said.recorded.question if said.recorded is not None else None
    return question.writer.name.lower() if question is not None else None


def _endings(said: Said) -> dict[str, str | None]:
    turn, recorded, edited = said.turn, said.recorded, said.edited
    return {
        "turn": turn.ending.name.lower() if turn is not None else None,
        "recorded": recorded.ending.value if recorded is not None else None,
        "edited": edited.ending.value if edited is not None else None,
    }


def _steps(said: Said) -> list[dict[str, Any]]:
    if said.turn is None:
        return []
    return [
        {"number": number, "calls": [_call(handled) for handled in step.calls]}
        for number, step in enumerate(said.turn.steps, start=1)
    ]


def _call(handled: TakenCall | RefusedCall | NotRunCall) -> dict[str, Any]:
    kept: dict[str, Any] = {
        "tool": handled.call.name,
        "arguments": _as_text(dict(handled.call.arguments)),
    }
    if isinstance(handled, TakenCall):
        kept["handled"] = "taken"
        kept["dropped"] = list(handled.dropped)
    elif isinstance(handled, RefusedCall):
        kept["handled"] = "wrong_step"
        kept["wrong_step"] = handled.misstep.kind.name.lower()
    else:
        kept["handled"] = "not_run"
    kept["result"] = _short(handled.result)
    return kept


def _as_text(value: Any) -> Any:
    """``value`` with every number in it written as text, as the model gave it."""
    if isinstance(value, Mapping):
        return {str(key): _as_text(inner) for key, inner in value.items()}
    if isinstance(value, list | tuple):
        return [_as_text(inner) for inner in value]
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    return str(value)


def _short(text: str) -> str:
    one_line = " ".join(text.split())
    if len(one_line) <= RESULT_KEPT:
        return one_line
    return f"{one_line[:RESULT_KEPT]}... ({len(one_line)} characters in all)"


def _failures(said: Said) -> list[dict[str, str]]:
    found: list[ModelError | LedgerError] = []
    if said.turn is not None and said.turn.failure is not None:
        found.append(said.turn.failure)
    recorded = said.recorded
    if recorded is not None:
        if recorded.failure is not None:
            found.append(recorded.failure)
        failure = recorded.progress.failure
        if failure is not None and failure.error is not None:
            found.append(failure.error)
    if said.edited is not None and said.edited.failure is not None:
        found.append(said.edited.failure)
    return [_failure(error) for error in found]


def _failure(error: ModelError | LedgerError) -> dict[str, str]:
    if isinstance(error, LedgerError):
        return {"from": "ledger", "kind": error.kind.name.lower(), "code": error.code}
    return {"from": "model", "kind": error.kind.name.lower()}


def _trades(said: Said) -> list[dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    recorded = said.recorded
    if recorded is not None:
        for number, facts in zip(recorded.numbers, recorded.trades, strict=True):
            kept.append({"number": number, **_facts(facts)})
    edited = said.edited
    if edited is not None and edited.sent is not None:
        change = {"kind": edited.sent.kind.value, "trade": edited.sent.trade}
        if edited.after is not None:
            change.update(_facts(edited.after))
        kept.append(change)
    return kept


def _facts(facts: TradeFacts | TradeCard) -> dict[str, str | None]:
    """A trade proposed, each cell as text; a cell a card left empty is ``None`` (null)."""
    occurred = facts.occurred
    when: str | None = None
    if occurred is not None:
        # A trade known only to its day keeps its day alone, never a made-up 00:00.
        when = occurred.date().isoformat() if facts.date_only else occurred.isoformat()
    return {
        "occurred": when,
        "side": facts.side.value,
        "asset": facts.asset,
        "quantity": _maybe(facts.quantity),
        "price": _maybe(facts.price),
        "total": _maybe(facts.total),
        "quote": facts.quote,
        "fee": _maybe(facts.fee),
        "fee_asset": facts.fee_asset,
        "platform": facts.platform,
    }


def _maybe(value: Decimal | None) -> str | None:
    return _amount(value) if value is not None else None


def _amount(value: Decimal) -> str:
    return format(value, "f")


def _left_out(said: Said) -> list[dict[str, Any]]:
    if said.recorded is None:
        return []
    return [
        {
            "number": trade.number,
            "why": trade.why.value,
            "asset": trade.code,
            "quantity": _amount(trade.quantity) if trade.quantity is not None else None,
            "unit": trade.unit,
        }
        for trade in said.recorded.left_out
    ]


def _asset_picks(said: Said) -> list[dict[str, Any]]:
    """Each name handed over to pick an asset, when recording began this time; else none.

    The picks are made when recording begins; an answer to a question that
    followed keeps none, so that each pick is kept once.
    """
    if said.recorded is None or said.route is Route.ANSWER:
        return []
    return [
        {
            "word": found.word,
            "said": found.said,
            "code": found.answered,
            "picked": found.picked,
            "miss": found.miss.name.lower() if found.miss is not None else None,
        }
        for found in said.recorded.progress.picks
    ]


def _reminders(said: Said) -> list[str]:
    if said.recorded is None:
        return []
    return [issue.kind.name.lower() for issue in spoken_reminders(said.recorded)]


def _sent(said: Said) -> list[dict[str, Any]]:
    # A proposal sent this time waits in the ledger to be confirmed: that is
    # how it stood when it was sent, which is what is kept. A trade the
    # ledger turned down keeps its code; one the ledger may have taken
    # without answering in time is kept as "maybe_sent", with no proposal.
    waiting = ProposalStatus.PENDING.value
    sent: list[dict[str, Any]] = []
    recorded = said.recorded
    if recorded is not None and recorded.ending is RecordEnding.MAYBE_SENT:
        sent.extend(
            {"number": number, "what": "record", "proposal": None, "status": "maybe_sent"}
            for number in recorded.numbers
        )
    elif recorded is not None and recorded.checks:
        for number, check in zip(recorded.numbers, recorded.checks, strict=True):
            line: dict[str, Any] = {"number": number, "what": "record"}
            if check.outcome is CheckOutcome.PASSED:
                line.update(proposal=check.proposal_id, status=waiting)
            else:
                line.update(proposal=None, status="refused", code=check.code)
            sent.append(line)
    edit_sent = said.edit_sent
    if edit_sent is not None:
        what = edit_sent.kind.value
        sent.append(
            {"number": None, "what": what, "proposal": edit_sent.proposal, "status": waiting}
        )
    return sent


def _marks(said: Said) -> list[dict[str, Any]]:
    """For each trade proposed: its marks, its price check and its cells sent empty."""
    recorded = said.recorded
    if recorded is None or len(recorded.marked) != len(recorded.numbers):
        return []
    return [
        {
            "number": number,
            "marks": [
                {"field": mark.field.value, "kind": mark.kind.value, "reason": mark.reason}
                for mark in marked.marks.marks
            ],
            "price_check": _price_check(marked.price),
            "empty": [field.value for field in Field if field in marked.marks.empty],
        }
        for number, marked in zip(recorded.numbers, recorded.marked, strict=True)
    ]


def _price_check(check: PriceCheck) -> dict[str, Any]:
    market = check.market
    return {
        "verdict": check.verdict.name.lower(),
        "market": {
            "price": _amount(market.price.amount),
            "money": market.price.currency,
            "day": market.day.isoformat() if market.day is not None else None,
        }
        if market is not None
        else None,
    }


def _prompts(said: Said) -> dict[str, str]:
    prompts: dict[str, str] = {}
    if said.turn is not None:
        prompts["assistant"] = DEFAULT_PROMPT.name
    if said.recorded is not None:
        for step, name in said.recorded.progress.prompts:
            prompts[step.name.lower()] = name
    return prompts


# --- the file -----------------------------------------------------------------


@dataclass(frozen=True)
class _Lines:
    """The whole lines of the file as they are, and whether a half line followed them."""

    whole: tuple[bytes, ...]
    cut: bool
    size_whole: int


def keep(place: Path | None, entry: Mapping[str, Any]) -> Kept | NotKept:
    """Add ``entry`` to the record at ``place``; how many it holds now, or why not."""
    if place is None:
        return NotKept(RecordProblem.NO_DATA_FOLDER)
    try:
        data = _read_bytes(place)
    except OSError as error:
        return NotKept(RecordProblem.CANNOT_READ, str(error))
    lines = _split(data)
    problem = _first_problem(lines.whole)
    if problem is not None:
        return NotKept(problem.problem, problem.detail)
    line = json.dumps(entry, ensure_ascii=False).encode("utf-8") + _LINE_END
    try:
        if len(lines.whole) + 1 > KEPT_AT_MOST:
            _replace_with(place, (*lines.whole[len(lines.whole) + 1 - KEPT_AT_MOST :], line))
            return Kept(KEPT_AT_MOST)
        _append(place, line, cut_at=lines.size_whole if lines.cut else None)
    except OSError as error:
        return NotKept(RecordProblem.CANNOT_WRITE, str(error))
    return Kept(len(lines.whole) + 1)


def read_record(place: Path) -> RecordRead | Unreadable:
    """The entries of the record at ``place``, or why they cannot be read; it changes nothing."""
    try:
        data = _read_bytes(place)
    except OSError as error:
        return Unreadable(RecordProblem.CANNOT_READ, str(error))
    lines = _split(data)
    problem = _first_problem(lines.whole)
    if problem is not None:
        return problem
    return RecordRead(tuple(json.loads(line) for line in lines.whole), cut_line=lines.cut)


def clear_record(place: Path) -> Cleared:
    """Delete the record at ``place``, whatever it holds. Raises ``OSError`` when it cannot."""
    try:
        place.unlink()
    except FileNotFoundError:
        return Cleared.NOTHING_THERE
    return Cleared.DELETED


def _read_bytes(place: Path) -> bytes:
    try:
        return place.read_bytes()
    except FileNotFoundError:
        return b""


def _split(data: bytes) -> _Lines:
    """The whole lines of ``data``; what follows the last line end is a half line."""
    end = data.rfind(_LINE_END) + 1
    whole = tuple(line + _LINE_END for line in data[:end].split(_LINE_END)[:-1])
    return _Lines(whole=whole, cut=end < len(data), size_whole=end)


def _first_problem(lines: Sequence[bytes]) -> Unreadable | None:
    """Why the file cannot be read: its first line that cannot, or is of a newer version."""
    for number, line in enumerate(lines, start=1):
        version = _version_of(line)
        if version is None:
            return Unreadable(RecordProblem.LINE_NOT_READ, f"line {number}")
        if version > RECORD_VERSION:
            return Unreadable(
                RecordProblem.NEWER_VERSION,
                f"line {number} is of version {version}; this program reads up to {RECORD_VERSION}",
            )
    return None


def _version_of(line: bytes) -> int | None:
    """The version of the entry on ``line``, or ``None`` when it is not an entry."""
    try:
        entry = json.loads(line.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    version = entry.get("format_version") if isinstance(entry, dict) else None
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        return None
    return version


def _append(place: Path, line: bytes, *, cut_at: int | None) -> None:
    """Add ``line`` at the end; first cut the half line off at ``cut_at``, when there is one."""
    place.parent.mkdir(parents=True, exist_ok=True)
    if cut_at is not None:
        os.truncate(place, cut_at)
    with place.open("ab") as file:
        file.write(line)
        file.flush()
        os.fsync(file.fileno())


def _replace_with(place: Path, lines: Sequence[bytes]) -> None:
    """Write ``lines`` to a new file beside ``place``, which then takes its name."""
    temporary = place.with_name(f".{place.name}.{uuid.uuid4().hex}.partial")
    try:
        with temporary.open("xb") as file:
            file.write(b"".join(lines))
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, place)
    finally:
        with suppress(OSError):
            temporary.unlink(missing_ok=True)
