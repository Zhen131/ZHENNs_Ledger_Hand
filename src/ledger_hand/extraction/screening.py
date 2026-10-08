"""Judging a passage before extraction: does it report a trade the ledger records?

``screen`` takes the passage the user typed and a model port, and gives back
one of:

- ``Screened``: what the model said the passage reports, and what the
  program decided from it (``Decision``):

  - ``STOP``: it reports only kinds the ledger does not record (futures or
    leverage, one coin swapped for another, an order not filled yet, a plan)
    and no filled spot trade. Nothing is extracted; each kind comes with the
    reason it is not recorded (``REASONS``) and, where the model's evidence
    is a piece of the passage, those words.
  - ``NO_TRADE``: it reports none of the kinds. Nothing is extracted.
  - ``EXTRACT``: it reports a filled spot trade. Extraction goes on; any kind
    not recorded that it reports as well is handed on, to be shown as a
    caution (``Screened.set_aside``).

- ``PassageRefused``: the passage was not sent (``passage_check``).
- ``ScreenUnreadable``: every reply missed the shape of the list, after
  asking again as often as the caller allowed.
- ``ScreenFailed``: the model port raised; the error is handed back exactly
  as raised, and nothing is decided.

It never raises for anything in the passage or in a reply; it raises only
for a mistake of the calling code. The model decides what the passage
reports; the program decides what follows from that, and never lets through
a kind the model called one the ledger does not record. A piece of evidence
the model wrote that is not a piece of the passage is dropped, and only the
kind is kept.

The prompt (``prompts/screen.py``) has no example at all (zero-shot). The
parameters are the caller's, ``None`` leaving the plug's defaults, which
the settings set to temperature 0.

Names defined here: ``screen``, ``Screening``, ``Screened``, ``Report``,
``Decision``, ``ScreenUnreadable``, ``ScreenFailed`` and ``REASONS``.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

from ledger_hand.extraction.extractor import DEFAULT_ASKS_AGAIN, MAX_ASKS_AGAIN, PassageRefused
from ledger_hand.extraction.passage import Passage, Piece
from ledger_hand.extraction.passage_check import passage_problem
from ledger_hand.extraction.prompting import PROBLEM_MARK, PromptVersion
from ledger_hand.extraction.prompts.screen import SCREEN_PROMPT
from ledger_hand.extraction.screen_table import (
    NOT_TO_RECORD,
    SCREEN_TABLE,
    Kind,
    ScreenProblem,
    ScreenReplyUnreadable,
    ScreenReport,
    read_screen_reply,
)
from ledger_hand.ports import (
    Message,
    ModelError,
    ModelParameters,
    ModelPort,
    ReplyRecord,
    Role,
)


class Decision(enum.Enum):
    """What follows from what the passage reports."""

    STOP = "only kinds the ledger does not record: nothing is extracted"
    NO_TRADE = "no trade of any kind: nothing is extracted"
    EXTRACT = "a filled spot trade: extraction goes on"


# Why each kind is not recorded, in the words shown to the user.
REASONS: dict[Kind, str] = {
    Kind.FUTURES_OR_LEVERAGE: (
        "this looks like futures or leveraged trading; only spot buys and sells are recorded"
    ),
    Kind.COIN_FOR_COIN: (
        "this looks like one coin swapped for another; only trades priced in USDT are recorded"
    ),
    Kind.OPEN_ORDER: (
        "this looks like an order that is not filled yet; only filled trades are recorded"
    ),
    Kind.PLAN: "this looks like a plan; only trades that have happened are recorded",
}


@dataclass(frozen=True)
class Report:
    """One kind the passage reports, and its evidence: the passage's own words, or ``None``."""

    kind: Kind
    evidence: str | None


@dataclass(frozen=True)
class Screened:
    """What the passage reports, each report once in the order given, and the decision."""

    decision: Decision
    reports: tuple[Report, ...]
    calls: tuple[ReplyRecord, ...]

    @property
    def set_aside(self) -> tuple[Report, ...]:
        """The reports of kinds the ledger does not record."""
        return tuple(report for report in self.reports if report.kind in NOT_TO_RECORD)


@dataclass(frozen=True)
class ScreenUnreadable:
    """Every reply missed the shape of the list; one problem per reply, in order."""

    problems: tuple[ScreenProblem, ...]
    calls: tuple[ReplyRecord, ...]


@dataclass(frozen=True)
class ScreenFailed:
    """The model port raised; ``error`` is the error exactly as it was raised."""

    error: ModelError
    calls: tuple[ReplyRecord, ...]


Screening = Screened | PassageRefused | ScreenUnreadable | ScreenFailed


def screen(
    passage: str,
    model: ModelPort,
    *,
    prompt: PromptVersion = SCREEN_PROMPT,
    parameters: ModelParameters | None = None,
    asks_again: int = DEFAULT_ASKS_AGAIN,
) -> Screening:
    """What ``passage`` reports, as the model judges it, and what follows from that."""
    _check_arguments(passage, asks_again)
    problem = passage_problem(passage)
    if problem is not None:
        return PassageRefused(problem)
    calls: list[ReplyRecord] = []
    problems: list[ScreenProblem] = []
    for _ in range(asks_again + 1):
        last = problems[-1] if problems else None
        try:
            reply = model.chat(
                _messages(prompt, passage, last), reply_schema=SCREEN_TABLE, parameters=parameters
            )
        except ModelError as error:
            return ScreenFailed(error, tuple(calls))
        calls.append(reply.record)
        read = read_screen_reply(reply)
        if not isinstance(read, ScreenReplyUnreadable):
            return _screened(read, Passage(passage), tuple(calls))
        problems.append(read.problem)
    return ScreenUnreadable(tuple(problems), tuple(calls))


def _check_arguments(passage: object, asks_again: object) -> None:
    if not isinstance(passage, str):
        raise TypeError(f"the passage is text, not {type(passage).__name__}")
    if isinstance(asks_again, bool) or not isinstance(asks_again, int):
        raise TypeError(f"asks_again is a whole number, not {type(asks_again).__name__}")
    if not 0 <= asks_again <= MAX_ASKS_AGAIN:
        raise ValueError(f"asks_again must be from 0 to {MAX_ASKS_AGAIN}")


def _messages(
    prompt: PromptVersion, passage: str, problem: ScreenProblem | None
) -> tuple[Message, ...]:
    messages = [Message(Role.SYSTEM, prompt.instructions), Message(Role.USER, passage)]
    if problem is not None:
        messages.append(Message(Role.USER, prompt.ask_again.replace(PROBLEM_MARK, problem.value)))
    return tuple(messages)


def _screened(
    written: tuple[ScreenReport, ...], passage: Passage, calls: tuple[ReplyRecord, ...]
) -> Screened:
    reports: list[Report] = []
    for item in written:
        report = Report(item.kind, _evidence(item.evidence, passage))
        if report not in reports:
            reports.append(report)
    return Screened(_decision(reports), tuple(reports), calls)


def _evidence(written: str, passage: Passage) -> str | None:
    """The passage's own words for ``written``, or ``None`` when it is not a piece of it."""
    found = passage.find(written)
    return found.text if isinstance(found, Piece) else None


def _decision(reports: list[Report]) -> Decision:
    kinds = {report.kind for report in reports}
    if Kind.SPOT_TRADE in kinds:
        return Decision.EXTRACT
    if kinds & NOT_TO_RECORD:
        return Decision.STOP
    return Decision.NO_TRADE
