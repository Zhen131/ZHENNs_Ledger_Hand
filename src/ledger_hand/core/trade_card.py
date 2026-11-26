"""A card: one trade as it is proposed to the ledger, some of its cells perhaps left empty.

Since 2026-11-25 the ledger takes a trade with cells left empty
(``allowUnfinished``, the ledger's ``assistant-link/README.md``,
"Unfinished trades and field marks"). Such a trade waits on the ledger's
pending list and cannot be saved until the person fills the empty cells
in on the ledger's own page. A ``TradeCard`` is that trade on this side:
the cells of ``TradeFacts``, of which the seven the ledger lets be empty
(the day, quantity, price, total, the money used, the fee and the fee's
money) may be ``None``, and the marks that go with it (``SentMark``).
The asset and buy or sell are always there: the ledger never takes them
empty.

``TradeFacts`` stays as it is, since reading trades uses it too; a card
whose every cell is there gives one (``facts``), and one is made from
``TradeFacts`` (``card_of``).

An empty cell is ``None``, never 0 and never empty text: a fee nobody
said is empty, not 0 (the product owner's rule, 81A, 2026-11-24).

Names defined here: ``EMPTY_ALLOWED``, ``TradeCard`` and ``card_of``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from ledger_hand.core.ledger_records import TradeFacts
from ledger_hand.core.marks import SentMark
from ledger_hand.core.trade import Side

# The ledger's names of the seven cells it lets be empty, in the ledger's own
# order (UNFINISHED_ALLOWED_FIELDS in its proposalTypes.ts, dev, 2026-11-26).
EMPTY_ALLOWED = (
    "occurredDate",
    "quantity",
    "price",
    "totalValue",
    "quoteAssetId",
    "fee",
    "feeAssetId",
)


def _require_positive_or_none(name: str, value: object) -> None:
    if value is None:
        return
    if not isinstance(value, Decimal) or not value.is_finite():
        raise TypeError(f"a card's {name} is an exact, finite decimal or none")
    if value <= 0:
        raise ValueError(f"a card's {name} is above 0, or left empty")


@dataclass(frozen=True, kw_only=True)
class TradeCard:
    """One trade proposed to the ledger: its cells, ``None`` where left empty, and its marks.

    ``occurred`` is the moment, or the start of the day for a trade known
    only to its day (``date_only``), or ``None`` when the day is left
    empty. ``quote`` and ``fee_asset`` are asset codes, never assumed.
    ``platform`` and ``note`` are empty text when not sent. ``marks`` are
    the marks as they leave for the ledger, after the guard
    (``marks.sent_marks``). Example: 0.1 ETH bought at 2600 USDT, no fee
    said: ``fee`` and ``fee_asset`` are ``None``.
    """

    occurred: datetime | None
    side: Side
    asset: str
    quantity: Decimal | None
    price: Decimal | None
    total: Decimal | None
    quote: str | None
    fee: Decimal | None
    fee_asset: str | None
    platform: str
    note: str
    raw_text: str | None
    zone: str | None
    date_only: bool
    cost_rate: Decimal | None = None
    marks: tuple[SentMark, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.side, Side):
            raise TypeError("a card's side is a Side")
        if not isinstance(self.asset, str) or not self.asset.strip():
            raise ValueError("a card always names its asset")
        for name in ("quantity", "price", "total"):
            _require_positive_or_none(name, getattr(self, name))
        if self.fee is not None and (not self.fee.is_finite() or self.fee < 0):
            raise ValueError("a card's fee is 0 or more, or left empty")
        for name in ("quote", "fee_asset"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"a card's {name} is a code, or left empty; never empty text")
        self._require_time_fits()
        if not isinstance(self.platform, str) or not isinstance(self.note, str):
            raise TypeError("a card's platform and note are text")

    def _require_time_fits(self) -> None:
        """No day: no time, no zone. A moment has an offset; a day alone starts at 00:00."""
        moment = self.occurred
        if moment is None:
            if self.date_only or self.zone is not None:
                raise ValueError("a card with no day says no time and no time zone")
            return
        if moment.utcoffset() is None:
            raise ValueError("a card's moment carries an offset")
        if self.date_only and (moment.hour, moment.minute) != (0, 0):
            raise ValueError("a card known only to its day holds the start of that day")

    @property
    def missing(self) -> tuple[str, ...]:
        """The ledger's names of the cells left empty, in the ledger's order."""
        empty = {
            "occurredDate": self.occurred is None,
            "quantity": self.quantity is None,
            "price": self.price is None,
            "totalValue": self.total is None,
            "quoteAssetId": self.quote is None,
            "fee": self.fee is None,
            "feeAssetId": self.fee_asset is None,
        }
        return tuple(name for name in EMPTY_ALLOWED if empty[name])

    @property
    def complete(self) -> bool:
        """Whether no cell is left empty: the card can be saved as it is, if the ledger agrees."""
        return not self.missing

    @property
    def day(self) -> date | None:
        """The day of the trade, on the clock of its own offset; ``None`` when left empty."""
        return self.occurred.date() if self.occurred is not None else None

    @property
    def facts(self) -> TradeFacts | None:
        """The card as ``TradeFacts`` when no cell is left empty; ``None`` otherwise."""
        if (
            self.occurred is None
            or self.quantity is None
            or self.price is None
            or self.total is None
            or self.quote is None
            or self.fee is None
            or self.fee_asset is None
        ):
            return None
        return TradeFacts(
            occurred=self.occurred,
            side=self.side,
            asset=self.asset,
            quantity=self.quantity,
            price=self.price,
            total=self.total,
            quote=self.quote,
            fee=self.fee,
            fee_asset=self.fee_asset,
            platform=self.platform,
            note=self.note,
            raw_text=self.raw_text,
            zone=self.zone,
            date_only=self.date_only,
            cost_rate=self.cost_rate,
        )


def card_of(facts: TradeFacts, marks: tuple[SentMark, ...] = ()) -> TradeCard:
    """The card of a trade whose every cell is there, with ``marks``."""
    return TradeCard(
        occurred=facts.occurred,
        side=facts.side,
        asset=facts.asset,
        quantity=facts.quantity,
        price=facts.price,
        total=facts.total,
        quote=facts.quote,
        fee=facts.fee,
        fee_asset=facts.fee_asset,
        platform=facts.platform,
        note=facts.note,
        raw_text=facts.raw_text,
        zone=facts.zone,
        date_only=facts.date_only,
        cost_rate=facts.cost_rate,
        marks=marks,
    )
