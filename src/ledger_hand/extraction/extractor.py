"""Extraction: one passage in, drafts of trades and a list of issues out.

``extract`` takes the passage the user typed, a model port, the current
moment, the time zone's name and the coin table, and gives back one of:

- ``Extracted``: the drafts, one per trade the model found, and the issues
  (see ``issues``). No trade at all is an ordinary result: no drafts.
- ``PassageRefused``: the passage was not sent to the model, because it is
  empty, longer than the ledger keeps as the original text (measured the
  ledger's way), or holds a character that is not valid Unicode text.
- ``ReplyUnreadable``: every reply the model gave missed the shape of the
  table, after asking again as often as the caller allowed.
- ``ModelFailed``: the model port raised one of its six kinds of error. The
  error is handed back exactly as raised, and the model is not asked again:
  the plug has already tried again where trying again can help.

It never raises for anything in the passage or in a reply. It raises only
for a mistake of the calling code: a current moment without an offset, a
name that is not a time zone, or a number of times to ask again out of range.

The steps:

1. The passage is checked before anything is sent.
2. The model is asked once, with the table it has to fill and the caller's
   parameters (``None`` leaves the plug's defaults, which the settings set
   to temperature 0 for exactly this).
3. The reply is read against the table. Only when it misses the table's
   shape is the model asked again, with a note saying what was wrong.
4. Each row becomes a draft (``row_draft``): every phrase is checked to be
   a piece of the passage, and turned into a value by the core's rules. A
   row with every field empty is left out. A row the model gave twice is
   kept twice, with an issue.
5. Every number written in the passage that no row's phrases hold is listed
   in one issue: a trade may be missing. Each number a row holds accounts
   for one number of the same writing in the passage, so a number written
   twice needs two rows that hold it.

Every draft's original text is the whole passage, unchanged.

Names defined here: ``extract``, ``Extraction``, ``Extracted``,
``PassageRefused``, ``PassageProblem``, ``ReplyUnreadable``,
``ModelFailed``, ``DEFAULT_ASKS_AGAIN`` and ``MAX_ASKS_AGAIN``.
"""

from __future__ import annotations

import collections
import enum
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime

from ledger_hand.core.coins import BUILT_IN_TABLE, CoinTable
from ledger_hand.core.ledger_limits import RAW_TEXT_MAX_LENGTH, text_length, trim
from ledger_hand.core.trade import TradeDraft
from ledger_hand.core.zones import is_zone_name
from ledger_hand.extraction.issues import Issue, IssueKind
from ledger_hand.extraction.passage import Passage
from ledger_hand.extraction.prompting import PromptVersion, build_messages
from ledger_hand.extraction.prompts.first import FIRST_PROMPT
from ledger_hand.extraction.reply_parser import ReplyProblem, ReplyRow, ReplyRows, read_reply
from ledger_hand.extraction.reply_table import REPLY_TABLE
from ledger_hand.extraction.row_draft import Surroundings, draft_from_row
from ledger_hand.ports import ModelError, ModelParameters, ModelPort, ReplyRecord

# Asked again once after a reply that misses the table: a second chance for
# a slip, without making a model that never fits cost many calls.
DEFAULT_ASKS_AGAIN = 1
# The most a caller may ask for, so that the calls for one passage stay few.
MAX_ASKS_AGAIN = 5


class PassageProblem(enum.Enum):
    """Why a passage was not sent to the model."""

    EMPTY = "the passage is empty"
    TOO_LONG = "the passage is longer than the ledger keeps as the original text"
    NOT_VALID_TEXT = "the passage holds a character that is not valid Unicode text"


@dataclass(frozen=True)
class Extracted:
    """The drafts the passage gave, the issues, and a record of each call to the model."""

    drafts: tuple[TradeDraft, ...]
    issues: tuple[Issue, ...]
    calls: tuple[ReplyRecord, ...]


@dataclass(frozen=True)
class PassageRefused:
    """The passage was not sent to the model."""

    problem: PassageProblem


@dataclass(frozen=True)
class ReplyUnreadable:
    """Every reply missed the table's shape; one problem per reply, in order."""

    problems: tuple[ReplyProblem, ...]
    calls: tuple[ReplyRecord, ...]


@dataclass(frozen=True)
class ModelFailed:
    """The model port raised; ``error`` is the error exactly as it was raised."""

    error: ModelError
    calls: tuple[ReplyRecord, ...]


Extraction = Extracted | PassageRefused | ReplyUnreadable | ModelFailed


def extract(
    passage: str,
    model: ModelPort,
    *,
    now: datetime,
    zone: str,
    coins: CoinTable = BUILT_IN_TABLE,
    prompt: PromptVersion = FIRST_PROMPT,
    parameters: ModelParameters | None = None,
    asks_again: int = DEFAULT_ASKS_AGAIN,
) -> Extraction:
    """The drafts in ``passage``, as the model copies them out and the program checks them.

    ``now`` is the current moment, with its offset; ``zone`` the name of the
    time zone the trades are recorded in. ``asks_again`` is how many times the
    model is asked again after a reply that misses the table.
    """
    _check_arguments(passage, now, zone, asks_again)
    problem = _passage_problem(passage)
    if problem is not None:
        return PassageRefused(problem)
    calls: list[ReplyRecord] = []
    problems: list[ReplyProblem] = []
    for _ in range(asks_again + 1):
        last = problems[-1] if problems else None
        try:
            reply = model.chat(
                build_messages(prompt, passage, last),
                reply_schema=REPLY_TABLE,
                parameters=parameters,
            )
        except ModelError as error:
            return ModelFailed(error, tuple(calls))
        calls.append(reply.record)
        read = read_reply(reply)
        if isinstance(read, ReplyRows):
            surroundings = Surroundings(Passage(passage), coins, now, zone)
            return _extracted(read.rows, surroundings, tuple(calls))
        problems.append(read.problem)
    return ReplyUnreadable(tuple(problems), tuple(calls))


def _check_arguments(passage: object, now: object, zone: object, asks_again: object) -> None:
    if not isinstance(passage, str):
        raise TypeError(f"the passage is text, not {type(passage).__name__}")
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ValueError("the current moment must be a datetime that carries an offset")
    if not is_zone_name(zone):
        raise ValueError(f"not a time zone name: {zone!r}")
    if isinstance(asks_again, bool) or not isinstance(asks_again, int):
        raise TypeError(f"asks_again is a whole number, not {type(asks_again).__name__}")
    if not 0 <= asks_again <= MAX_ASKS_AGAIN:
        raise ValueError(f"asks_again must be from 0 to {MAX_ASKS_AGAIN}")


def _passage_problem(passage: str) -> PassageProblem | None:
    # Counted in characters first: a text with more characters than the limit
    # has more UTF-16 units too, and is turned away without being measured.
    if len(passage) > RAW_TEXT_MAX_LENGTH or text_length(passage) > RAW_TEXT_MAX_LENGTH:
        return PassageProblem.TOO_LONG
    if not trim(passage).strip():
        return PassageProblem.EMPTY
    try:
        passage.encode("utf-8")
    except UnicodeEncodeError:
        return PassageProblem.NOT_VALID_TEXT
    return None


def _extracted(
    rows: Sequence[ReplyRow], around: Surroundings, calls: tuple[ReplyRecord, ...]
) -> Extracted:
    drafts: list[TradeDraft] = []
    issues: list[Issue] = []
    used: collections.Counter[str] = collections.Counter()
    first_of: dict[object, int] = {}
    for row in rows:
        if row.is_empty:
            issues.append(Issue(kind=IssueKind.EMPTY_ROW))
            continue
        position = len(drafts)
        key = (row.side, tuple(row.cells.items()))
        if key in first_of:
            issues.append(
                Issue(kind=IssueKind.SAME_AS_ANOTHER, draft=position, same_as=first_of[key])
            )
        first_of.setdefault(key, position)
        made = draft_from_row(row, position, around)
        drafts.append(made.draft)
        issues.extend(made.issues)
        used.update(made.numbers)
    left_over = _left_over(around.passage.numbers, used)
    if left_over:
        issues.append(Issue(kind=IssueKind.NUMBERS_LEFT_OVER, numbers=left_over))
    return Extracted(tuple(drafts), tuple(issues), calls)


def _left_over(
    numbers: Iterable[tuple[str, str]], used: collections.Counter[str]
) -> tuple[str, ...]:
    """The passage's numbers, as written, that the rows' phrases do not account for."""
    unaccounted = collections.Counter(used)
    left: list[str] = []
    for written, tidied in numbers:
        if unaccounted[tidied] > 0:
            unaccounted[tidied] -= 1
        else:
            left.append(written)
    return tuple(left)
