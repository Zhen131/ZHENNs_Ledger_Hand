"""Where the recording of one passage stands: one value that never changes, handed back each step.

A ``Progress`` holds everything a command line or an interface needs to show
and nothing it has to work out: the stage (``Stage``), every trade with its
draft and what became of it (``TradeState``), the question waiting for its
answer (``Question``), why the passage was stopped or what was set aside, the
reminders from extraction, the earlier saves of the same passage when a book
was handed in, why nothing could be done when the model failed, which prompt
versions were used and a record of every call to the model. Its
properties say what may be done next: whether a trade can be removed, and
which, whether the records can be saved, whether the whole passage can be
dropped, whether every trade is settled and whether the passage is over.

Only ``recording`` makes a ``Progress``, and ``screenshot`` for a passage
that starts from a screenshot; this module states the shapes.

Names defined here: ``Progress``, ``Stage``, ``TradeState``, ``TradeStatus``,
``Question``, ``Failure``, ``Setting``, ``Step``, ``Call``, ``Tuning``,
``DEFAULT_TUNING``, ``REMINDER_KINDS``, ``MoneyClash`` and ``Asked``.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from ledger_hand.asking.question_text import Writer
from ledger_hand.core.assets import AssetTable
from ledger_hand.core.book import EarlierSave
from ledger_hand.core.card_record import CardRecord
from ledger_hand.core.followup import (
    AskCell,
    AskSaidPrice,
    AskWhichCell,
    Cell,
    ConfirmCoin,
    Problem,
)
from ledger_hand.core.stock_names import NameOutcome
from ledger_hand.core.trade import MoneysSaid, OccurredTime, SaidPrice, TradeDraft, TradeRecord
from ledger_hand.extraction.asset_picking import AssetPick
from ledger_hand.extraction.extractor import DEFAULT_ASKS_AGAIN, PassageProblem
from ledger_hand.extraction.issues import Issue, IssueKind
from ledger_hand.extraction.screening import Report
from ledger_hand.flows.last_money import LastMoney
from ledger_hand.ports import ModelError, ModelErrorKind, ModelParameters, ReplyRecord

type Asked = AskCell | ConfirmCoin | AskWhichCell | AskSaidPrice


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
    UNFINISHED = "to be sent as a card, cells not said or wrong left empty and marked"


class Step(enum.Enum):
    """What a call to the model was for."""

    READING = "reading the screenshot"
    SCREENING = "judging the passage"
    EXTRACTION = "extracting the trades"
    QUESTION = "wording a question"
    ANSWER = "reading an answer"
    ASSET_PICK = "picking the asset from the ledger's list"


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

    ``now`` and ``zone`` are those the passage was given with. ``assets`` is
    the asset table, with every coin the user confirmed during this run.
    ``unfinished`` says the ledger takes a trade with cells left empty
    (the assistant's way, when the ledger offers it): then only which
    asset and buy or sell are asked, and every other gap becomes a card.
    """

    now: datetime
    zone: str
    assets: AssetTable
    tuning: Tuning = DEFAULT_TUNING
    unfinished: bool = False


@dataclass(frozen=True)
class TradeState:
    """One trade: its draft as it stands, and what became of it.

    ``record`` is there when the trade is recorded; ``reason`` says why a
    trade cannot be recorded; ``card`` is there when the trade is to be
    sent as a card, with cells left empty or marked (``UNFINISHED``).
    """

    draft: TradeDraft
    status: TradeStatus
    record: TradeRecord | None = None
    reason: Problem | None = None
    card: CardRecord | None = None


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
    ``model_failure`` is the kind of the model's failure when the last answer
    could not be read because the model could not be asked to read it, and
    ``None`` otherwise.
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
    model_failure: ModelErrorKind | None = None

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


@dataclass(frozen=True, kw_only=True)
class MoneyClash:
    """An answer whose money is not the one the trade already has; the user is asked which.

    ``trade`` is the trade's position, counting from 0; ``cell`` the
    amount answered (price, total or fee) and ``value`` its number, not
    filled in yet; ``said`` the word for money answered with it and
    ``said_code`` what it names; ``before`` what the trade's money (or
    its fee's) named until then, and ``guessed`` whether that was the
    program's guess. Example: "30 USDT" spent, then "2400美元" answered
    for the price: ``before`` is USDT and ``said_code`` USD.
    """

    trade: int
    cell: Cell
    value: Decimal
    said: str
    said_code: str
    before: str
    guessed: bool


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

    ``raw_text`` is the words as the user said them, when ``passage`` was
    tidied from them (the assistant's way); ``None`` when the passage is
    the words themselves (the record page, a screenshot). Each draft's own
    ``raw_text`` holds the passage, tidied on the assistant's way; the
    trades sent to the ledger carry this one when it is there. Every step
    after the start carries it on.

    ``picks`` holds what came of each name of an asset handed to the model
    to pick from the ledger's list at the start (the assistant's way), one
    for each name, in the order first met; empty when none was.
    ``names`` holds what came of each name of an asset the program looked
    up in the user's answers and its table of company names at the start
    (``stock_names.find_name``), one for each name, in the order first met.

    ``last_moneys`` keeps what the ledger said of each asset's last trade,
    by the asset's code, so that one asset is asked about once in a
    passage. ``clash`` is an answer whose money is not the trade's, while
    the user is asked which money it is; ``None`` otherwise.

    ``moneys_said`` holds, for each trade in order, the words for money
    its amounts were written with (``MoneysSaid``), or is empty when no
    trade has any. ``said_prices`` holds, by the trade's position, the
    price of one unit said in the asset's own money for a trade paid in
    another money (``SaidPrice``, ``paid_apart``).
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
    raw_text: str | None = None
    picks: tuple[AssetPick, ...] = ()
    names: tuple[NameOutcome, ...] = ()
    last_moneys: tuple[tuple[str, LastMoney], ...] = ()
    clash: MoneyClash | None = None
    totals_from_units: tuple[tuple[int, str], ...] = ()
    moneys_said: tuple[MoneysSaid | None, ...] = ()
    said_prices: tuple[tuple[int, SaidPrice], ...] = ()

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

    @property
    def removable(self) -> tuple[int, ...]:
        """The numbers (counting from 1, in passage order) of the trades that can be removed now."""
        if not self.can_remove:
            return ()
        return tuple(
            number
            for number, trade in enumerate(self.trades, start=1)
            if trade.status is TradeStatus.RECORDED and trade.record is not None
        )

    @property
    def can_save(self) -> bool:
        """Whether the records can be made final and saved now: all is settled, one is a record."""
        return self.stage is Stage.REVIEWING and bool(self.records)
