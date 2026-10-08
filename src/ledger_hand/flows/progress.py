"""Where the recording of one passage stands: one value that never changes, handed back each step.

A ``Progress`` holds everything a command line or an interface needs to show
and nothing it has to work out: the stage (``Stage``), every trade with its
draft and what became of it (``TradeState``), the question waiting for its
answer (``Question``), why the passage was stopped or what was set aside, the
reminders from extraction, the earlier saves of the same passage when a book
was handed in, why nothing could be done when the model failed, which prompt
versions were used and a record of every call to the model. Its
properties say what may be done next: whether a trade can be removed, whether
the whole passage can be dropped, whether every trade is settled and whether
the passage is over.

Only ``recording`` makes a ``Progress``; this module states the shapes.

Names defined here: ``Progress``, ``Stage``, ``TradeState``, ``TradeStatus``,
``Question``, ``Failure``, ``Setting``, ``Step``, ``Call``, ``Tuning``,
``DEFAULT_TUNING``, ``REMINDER_KINDS`` and ``Asked``.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import datetime

from ledger_hand.asking.question_text import Writer
from ledger_hand.core.book import EarlierSave
from ledger_hand.core.coins import CoinTable
from ledger_hand.core.followup import AskCell, AskWhichCell, ConfirmCoin, Problem
from ledger_hand.core.trade import OccurredTime, TradeDraft, TradeRecord
from ledger_hand.extraction.extractor import DEFAULT_ASKS_AGAIN, PassageProblem
from ledger_hand.extraction.issues import Issue, IssueKind
from ledger_hand.extraction.screening import Report
from ledger_hand.ports import ModelError, ModelParameters, ReplyRecord

type Asked = AskCell | ConfirmCoin | AskWhichCell


class Stage(enum.Enum):
    """Where the passage stands; the value says it in words."""

    REFUSED = "the passage was not sent: it is empty, too long or not valid text"
    STOPPED = "the passage reports only things the ledger does not record"
    NO_TRADE = "no trade was found in the passage"
    FAILED = "the model failed, or its replies could not be read; nothing is kept"
    ASKING = "a question is waiting for its answer"
    REVIEWING = "every trade is settled; a trade may be removed, or the passage dropped"
    CANCELLED = "the whole passage was dropped; nothing is kept"
    DONE = "the records are final"


# The stages after which nothing more can happen.
_OVER = frozenset(
    {Stage.REFUSED, Stage.STOPPED, Stage.NO_TRADE, Stage.FAILED, Stage.CANCELLED, Stage.DONE}
)


class TradeStatus(enum.Enum):
    """What became of one trade."""

    OPEN = "still being asked about"
    RECORDED = "complete"
    SKIPPED = "left out"
    CANNOT_RECORD = "cannot be recorded"


class Step(enum.Enum):
    """What a call to the model was for."""

    SCREENING = "judging the passage"
    EXTRACTION = "extracting the trades"
    QUESTION = "wording a question"
    ANSWER = "reading an answer"


# The issues of extraction that are reminders to keep in mind, rather than a
# field left empty that a question will take up.
REMINDER_KINDS = frozenset(
    {
        IssueKind.NUMBER_CAUTION,
        IssueKind.TIME_CAUTION,
        IssueKind.UNIT_NOT_THE_COIN,
        IssueKind.UNIT_NOT_THE_PRICE_CURRENCY,
        IssueKind.UNIT_NOT_THE_FEE_CURRENCY,
        IssueKind.UNIT_NAMES_SEVERAL,
        IssueKind.EMPTY_ROW,
        IssueKind.SAME_AS_ANOTHER,
        IssueKind.NUMBERS_LEFT_OVER,
    }
)


@dataclass(frozen=True)
class Tuning:
    """How the model is called: the parameters for wording a question, and how often to ask again.

    ``None`` leaves the plug's defaults. Judging a passage, extraction and
    reading an answer always use the plug's defaults.
    """

    question_parameters: ModelParameters | None = None
    asks_again: int = DEFAULT_ASKS_AGAIN


DEFAULT_TUNING = Tuning()


@dataclass(frozen=True)
class Setting:
    """What every step of one passage shares.

    ``now`` and ``zone`` are those the passage was given with. ``coins`` is
    the coin table, with every coin the user confirmed during this run.
    """

    now: datetime
    zone: str
    coins: CoinTable
    tuning: Tuning = DEFAULT_TUNING


@dataclass(frozen=True)
class TradeState:
    """One trade: its draft as it stands, and what became of it.

    ``record`` is there when the trade is recorded; ``reason`` says why a
    trade cannot be recorded.
    """

    draft: TradeDraft
    status: TradeStatus
    record: TradeRecord | None = None
    reason: Problem | None = None


@dataclass(frozen=True)
class Question:
    """The question waiting for its answer.

    ``trade`` is the position of the trade it is about, counting from 0.
    ``label`` (which trade, which field) and ``notes`` (the passage's own
    words, the values in question, what may be answered) are the program's;
    ``sentence`` is the model's or, when it would not do, the program's, as
    ``writer`` says. ``choices`` are the answers to choose from, and
    ``candidates`` the two moments behind them, when the time is asked with
    them. ``again`` says why the same question is asked again.
    """

    trade: int
    asked: Asked
    label: str
    sentence: str
    writer: Writer
    notes: tuple[str, ...] = ()
    choices: tuple[str, ...] = ()
    candidates: tuple[OccurredTime, ...] = ()
    again: str | None = None

    @property
    def text(self) -> str:
        """The label and the sentence, as shown."""
        return f"{self.label} {self.sentence}"


@dataclass(frozen=True)
class Failure:
    """Why nothing could be done: the step, and the model's error or its replies' problems."""

    step: Step
    error: ModelError | None
    problems: tuple[str, ...] = ()


@dataclass(frozen=True)
class Call:
    """One call to the model, and what it was for."""

    step: Step
    record: ReplyRecord


@dataclass(frozen=True)
class Progress:
    """Where the recording of one passage stands. It never changes; each step gives a new one.

    ``stopped`` holds what the passage reports that the ledger does not
    record, when that is all it reports; ``set_aside`` the same, when it
    reports a trade as well. ``issues`` are every issue extraction raised;
    ``reminders`` the ones to keep in mind. ``note`` says why an answer given
    once every trade was settled could not be used. ``prompts`` names the
    prompt version used for each step, in the order first used.
    ``seen_before`` lists the earlier saves of this passage, or of one that
    differs from it only in spacing or the width of its characters, oldest
    first; it is only ever filled when a book was handed in, and it only
    reminds: nothing is held back for it.
    """

    stage: Stage
    passage: str
    setting: Setting
    trades: tuple[TradeState, ...] = ()
    question: Question | None = None
    stopped: tuple[Report, ...] = ()
    set_aside: tuple[Report, ...] = ()
    issues: tuple[Issue, ...] = ()
    refused: PassageProblem | None = None
    failure: Failure | None = None
    note: str | None = None
    prompts: tuple[tuple[Step, str], ...] = ()
    calls: tuple[Call, ...] = ()
    seen_before: tuple[EarlierSave, ...] = ()

    @property
    def records(self) -> tuple[TradeRecord, ...]:
        """The complete trades, in passage order; none once the passage is dropped."""
        if self.stage is Stage.CANCELLED:
            return ()
        return tuple(
            trade.record
            for trade in self.trades
            if trade.status is TradeStatus.RECORDED and trade.record is not None
        )

    @property
    def reminders(self) -> tuple[Issue, ...]:
        """The issues of extraction to keep in mind: cautions, units, rows, numbers left over."""
        return tuple(issue for issue in self.issues if issue.kind in REMINDER_KINDS)

    @property
    def settled(self) -> bool:
        """Whether every trade is settled: no question is waiting."""
        return self.stage is not Stage.ASKING

    @property
    def over(self) -> bool:
        """Whether nothing more can happen to this passage."""
        return self.stage in _OVER

    @property
    def can_remove(self) -> bool:
        """Whether a recorded trade can be removed now (it then counts as skipped)."""
        return self.stage is Stage.REVIEWING and bool(self.records)

    @property
    def can_cancel(self) -> bool:
        """Whether the whole passage can be dropped now."""
        return self.stage in (Stage.ASKING, Stage.REVIEWING)
