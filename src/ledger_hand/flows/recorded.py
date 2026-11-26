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
- ``Sent``: the program's own word on what reached the ledger: one proposal
  for each trade the ledger took.
- ``MarkedTrade``: what the program noticed about one trade proposed: the
  marks on its cells (``core/marks.py``) and how its price compared with
  the ledger's market price (``core/price_check.py``). For now they stay
  on this side: the ledger is not handed them.
- ``Recorded``: all of it: the ending, the flow's progress as it stands
  (with every call the flow made to the model, counted apart from the
  assistant's steps), the trades proposed and each one's marks, the
  trades left out, the ledger's checks when it turned the proposal down,
  and the failure.

Names defined here: ``RecordEnding``, ``STAGE_ENDINGS``, ``SETTLED_STAGES``,
``LeftOut``, ``LeftOutTrade``, ``Sent``, ``MarkedTrade`` and ``Recorded``.
"""

from __future__ import annotations

import enum
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType

from ledger_hand.core.ledger_records import TradeFacts
from ledger_hand.core.marks import TradeMarks
from ledger_hand.core.price_check import PriceCheck
from ledger_hand.core.proposals import TradeCheck
from ledger_hand.flows.progress import Progress, Question, Stage
from ledger_hand.ports import LedgerError


class RecordEnding(enum.Enum):
    """How recording what the user said ended this time."""

    ASKING = "asking"
    """A question about a trade waits for the user's answer."""
    SENT = "sent"
    """Every trade sent waits in the ledger to be confirmed, each as a proposal of its own."""
    PARTLY_SENT = "partly_sent"
    """Some trades sent wait in the ledger to be confirmed; the ledger turned the others
    down, each with its reason."""
    LEDGER_REFUSED = "ledger_refused"
    """The ledger's check turned every trade down: nothing waits there."""
    MAYBE_SENT = "maybe_sent"
    """The ledger did not answer in time: the trades may be waiting there. They are not
    sent again; the user is asked to look at the ledger's pending list."""
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
    """Only its day was said, not the time of day. No path leads here now: such a trade is
    sent with its day alone. Kept so that the words for it, and older records, stay."""
    NOT_IN_LEDGER = "not_in_ledger"
    """An asset it names, or its fee's, is not in the ledger."""
    MONEY_TRADED = "money_traded"
    """What it trades is itself money of the ledger: an exchange, which the assistant leaves."""
    QUOTE_CANNOT_PRICE = "quote_cannot_price"
    """The money it is priced in is one the ledger prices no trade in."""
    MONEY_NOT_IN_LEDGER = "money_not_in_ledger"
    """The money it is priced in ("欧元") is not in the ledger at all."""
    FEE_MONEY_NOT_IN_LEDGER = "fee_money_not_in_ledger"
    """The money its fee was taken in is not in the ledger at all."""
    QUANTITY_IN_OTHER_UNIT = "quantity_in_other_unit"
    """Its quantity was said in a unit that is not the asset traded ("25U" of ETH)."""
    SAME_CODE = "same_code"
    """The ledger has more than one asset with the code it names; none is picked."""


@dataclass(frozen=True, kw_only=True)
class LeftOutTrade:
    """A trade not sent: its number (from 1, in the order said), why, and what it names.

    ``code`` is the asset the reason is about, when there is one;
    ``reason`` is the flow's own words for a trade that cannot be recorded.
    For a quantity said in another unit, ``quantity`` is the number as
    read and ``unit`` the unit as written beside it ("25" and "U").
    """

    number: int
    why: LeftOut
    code: str | None = None
    reason: str | None = None
    quantity: Decimal | None = None
    unit: str | None = None


@dataclass(frozen=True, kw_only=True)
class Sent:
    """What waits in the ledger: one proposal for each trade it took, in the order said."""

    proposals: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.proposals or not all(isinstance(one, str) for one in self.proposals):
            raise ValueError("what was sent holds at least one proposal's identifier")

    @property
    def trades(self) -> int:
        """How many trades wait in the ledger."""
        return len(self.proposals)

    @property
    def proposal(self) -> str:
        """The proposals' identifiers, one after another, for words that name them."""
        return ", ".join(self.proposals)


@dataclass(frozen=True, kw_only=True)
class MarkedTrade:
    """What the program noticed about one trade proposed: its marks, and its price check."""

    marks: TradeMarks
    price: PriceCheck


@dataclass(frozen=True, kw_only=True)
class Recorded:
    """How recording what was said ended this time, and everything it rests on.

    ``trades`` are the trades proposed, in the order said, and ``numbers``
    the number of each in what was said; ``checks`` are the ledger's checks
    of them, one each, in the same order: a proposal's identifier, or why
    the ledger turned it down. ``marked`` holds, in the same order, the
    marks of each and how its price compared. ``missing_money`` is the code
    of a money the ledger lacks, for a caller that names one; recording
    what the user said to the assistant leaves it empty.
    """

    ending: RecordEnding
    progress: Progress
    trades: tuple[TradeFacts, ...] = ()
    numbers: tuple[int, ...] = ()
    marked: tuple[MarkedTrade, ...] = ()
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
