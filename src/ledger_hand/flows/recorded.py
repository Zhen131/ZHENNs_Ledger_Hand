"""How recording what the user said to the assistant ended, this time: shapes that never change.

The assistant records a trade by handing what the user said to the
recording flow (``recording``) and, once every trade is settled, sending
the records to the ledger as one proposal (``proposing``). This module
states what comes of that, for the assistant's chat, the try-out script and
later an interface to show; it works nothing out.

- ``RecordEnding``: how it ended this time: a question waits, a proposal
  was sent, or nothing was sent and why. ``STAGE_ENDINGS`` gives the ending
  for every stage of the flow that ends there; the stages in
  ``SETTLED_STAGES`` go on to the proposal instead. Between them they name
  every stage, and a test sees to it.
- ``LeftOut`` and ``LeftOutTrade``: a trade of what was said that was not
  sent, and why.
- ``Sent``: the program's own word on what reached the ledger.
- ``Recorded``: all of it: the ending, the flow's progress as it stands
  (with every call the flow made to the model, counted apart from the
  assistant's steps), the trades proposed, the trades left out, the
  ledger's checks when it turned the proposal down, and the failure.

Names defined here: ``RecordEnding``, ``STAGE_ENDINGS``, ``SETTLED_STAGES``,
``LeftOut``, ``LeftOutTrade``, ``Sent`` and ``Recorded``.
"""

from __future__ import annotations

import enum
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from ledger_hand.core.ledger_records import TradeFacts
from ledger_hand.core.proposals import TradeCheck
from ledger_hand.flows.progress import Progress, Question, Stage
from ledger_hand.ports import LedgerError


class RecordEnding(enum.Enum):
    """How recording what the user said ended this time."""

    ASKING = "asking"
    """A question about a trade waits for the user's answer."""
    SENT = "sent"
    """A proposal was sent to the ledger and waits there to be confirmed."""
    LEDGER_REFUSED = "ledger_refused"
    """The ledger's check turned the proposal down: nothing waits there."""
    NOTHING_TO_SEND = "nothing_to_send"
    """Every trade was left out; each has its reason."""
    NO_PRICING_MONEY = "no_pricing_money"
    """The ledger prices trades in no money at all, so nothing can be recorded."""
    CANCELLED = "cancelled"
    """The user dropped what was being recorded."""
    STOPPED = "stopped"
    """What was said reports only things the ledger does not record, such as an open order."""
    NO_TRADE = "no_trade"
    """No trade was found in what was said."""
    REFUSED = "refused"
    """What was said was not sent to the model: empty, too long or not valid text."""
    MODEL_FAILED = "model_failed"
    """The model failed, or its replies could not be read, while judging or extracting."""
    LEDGER_FAILED = "ledger_failed"
    """The ledger could not be asked."""


STAGE_ENDINGS: Mapping[Stage, RecordEnding] = MappingProxyType(
    {
        Stage.ASKING: RecordEnding.ASKING,
        Stage.CANCELLED: RecordEnding.CANCELLED,
        Stage.STOPPED: RecordEnding.STOPPED,
        Stage.NO_TRADE: RecordEnding.NO_TRADE,
        Stage.REFUSED: RecordEnding.REFUSED,
        Stage.FAILED: RecordEnding.MODEL_FAILED,
    }
)

SETTLED_STAGES = frozenset({Stage.REVIEWING, Stage.DONE})


class LeftOut(enum.Enum):
    """Why one trade of what was said was not sent to the ledger."""

    SKIPPED = "skipped"
    """The user said to leave it out."""
    CANNOT_RECORD = "cannot_record"
    """The flow found it cannot be recorded, and says why."""
    DAY_ONLY = "day_only"
    """Only its day was said, not the time of day; no time is made up for it."""
    NOT_IN_LEDGER = "not_in_ledger"
    """An asset it names, or its fee's, is not in the ledger."""
    MONEY_TRADED = "money_traded"
    """What it trades is itself money of the ledger: an exchange, which the assistant leaves."""
    QUOTE_CANNOT_PRICE = "quote_cannot_price"
    """The money it is priced in is one the ledger prices no trade in."""


@dataclass(frozen=True, kw_only=True)
class LeftOutTrade:
    """A trade not sent: its number (from 1, in the order said), why, and what it names.

    ``code`` is the asset the reason is about, when there is one;
    ``reason`` is the flow's own words for a trade that cannot be recorded.
    """

    number: int
    why: LeftOut
    code: str | None = None
    reason: str | None = None


@dataclass(frozen=True, kw_only=True)
class Sent:
    """What reached the ledger: the proposal's identifier, and how many trades it holds."""

    proposal: str
    trades: int


@dataclass(frozen=True, kw_only=True)
class Recorded:
    """How recording what was said ended this time, and everything it rests on.

    ``trades`` are the trades proposed, in the order said, and ``numbers``
    the number of each in what was said; ``checks`` are the ledger's checks
    of them when it turned the proposal down. ``missing_money`` is the code
    of a money the ledger lacks, for a caller that names one; recording
    what the user said to the assistant leaves it empty.
    """

    ending: RecordEnding
    progress: Progress
    trades: tuple[TradeFacts, ...] = ()
    numbers: tuple[int, ...] = ()
    left_out: tuple[LeftOutTrade, ...] = ()
    checks: tuple[TradeCheck, ...] = ()
    sent: Sent | None = None
    failure: LedgerError | None = None
    missing_money: str | None = None

    @property
    def question(self) -> Question | None:
        """The question waiting for the user's answer, if one is."""
        return self.progress.question if self.ending is RecordEnding.ASKING else None

    @property
    def well_ended(self) -> bool:
        """Whether it ended as asked or said why not, with no failure of the model or ledger."""
        if self.ending in (RecordEnding.MODEL_FAILED, RecordEnding.LEDGER_FAILED):
            return False
        question = self.question
        return question is None or question.model_failure is None
