"""What the ledger's tools hand back and take: assets, trades, sums and holdings.

These are the shapes the ledger port (``ports.LedgerPort``) uses. They carry
moments and exact amounts, so they live in the core, and the ports file only
names them. Nothing here reads a ledger, works a figure out or reads the
clock: whoever is behind the port fills them in.

- ``Asset``: one asset the ledger knows: its name, its code, its kind, its
  identifier inside the ledger, and whether it can be the money a trade is
  priced in (``Pricing``).
- ``TradeFacts``: the facts of one trade, as the user stated them. Every trade
  names the money it is priced in (``quote``) and what its fee was taken in
  (``fee_asset``); neither has a default, because a ledger holds stocks
  bought with dollars as well as coins bought with USDT. It also keeps the
  user's own words it came from (``raw_text``), byte for byte; this has no
  default either.
- ``LedgerTrade``: a trade in the ledger: its identifier, its facts, and for
  a sell the profit or loss it made (``realized``); a buy has none.
- ``TradeFilter``: which trades to list; every part of it may be left out.
- ``PeriodRequest``, ``PeriodSummary`` and ``CurrencyTotals``: the sums of a
  stretch of time, one set for each money the trades were priced in.
- ``Position``: what is held of one asset bought with one money.
- ``MoneyAmount`` and ``NotWorkedOut``: a figure in one named money, or the
  reason it could not be worked out (``Figure`` is either).

Money of two kinds is never added together: a sum or a holding is always
given for one money, named beside it. Amounts are exact decimals, never
floating-point numbers, and every moment carries an offset.

Names defined here: ``AssetKind``, ``Pricing``, ``Asset``, ``MoneyAmount``,
``NotWorkedOut``, ``Figure``, ``TradeFacts``, ``LedgerTrade``, ``TradeFilter``,
``PeriodRequest``, ``CurrencyTotals``, ``PeriodSummary`` and ``Position``.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from ledger_hand.core.trade import Side


class AssetKind(enum.Enum):
    """What sort of thing an asset is."""

    CRYPTO = "crypto"
    STOCK = "stock"
    CASH = "cash"
    """Money in the ordinary sense, or a coin that stands for it, such as USD or USDT."""


class Pricing(enum.Enum):
    """Whether an asset can be the money a trade is priced in."""

    CAN_PRICE = "can_price"
    CANNOT_PRICE = "cannot_price"


def _require_text(name: str, value: object) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is text that is not blank, not {value!r}")


def _require_moment(name: str, value: object) -> None:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} is a datetime, not {type(value).__name__}")
    if value.utcoffset() is None:
        raise ValueError(f"{name} must carry an offset")


def _require_amount(name: str, value: object) -> None:
    """Refuse anything but a finite exact decimal, 0 or more."""
    if not isinstance(value, Decimal):
        raise TypeError(f"{name} is an exact decimal, not {type(value).__name__}")
    if not value.is_finite() or value < 0:
        raise ValueError(f"{name} must be a finite amount, 0 or more, not {value}")


def _require_signed(name: str, value: object) -> None:
    """Refuse anything but a finite exact decimal; a profit or loss may be below zero."""
    if not isinstance(value, Decimal):
        raise TypeError(f"{name} is an exact decimal, not {type(value).__name__}")
    if not value.is_finite():
        raise ValueError(f"{name} must be finite, not {value}")


@dataclass(frozen=True, kw_only=True)
class Asset:
    """One asset the ledger knows."""

    id: str
    code: str
    name: str
    kind: AssetKind
    pricing: Pricing

    def __post_init__(self) -> None:
        _require_text("an asset's identifier", self.id)
        _require_text("an asset's code", self.code)
        _require_text("an asset's name", self.name)
        if not isinstance(self.kind, AssetKind):
            raise TypeError(f"an asset's kind is an AssetKind, not {type(self.kind).__name__}")
        if not isinstance(self.pricing, Pricing):
            raise TypeError(f"an asset's pricing is a Pricing, not {type(self.pricing).__name__}")


@dataclass(frozen=True, kw_only=True)
class MoneyAmount:
    """An amount of one named money; it may be below zero (a loss)."""

    currency: str
    amount: Decimal

    def __post_init__(self) -> None:
        _require_text("a money's code", self.currency)
        _require_signed("an amount of money", self.amount)


@dataclass(frozen=True, kw_only=True)
class NotWorkedOut:
    """A figure that could not be worked out, and why, in one plain English sentence."""

    reason: str

    def __post_init__(self) -> None:
        _require_text("the reason a figure was not worked out", self.reason)


type Figure = MoneyAmount | NotWorkedOut
"""A figure in one money, or the reason it could not be worked out."""


@dataclass(frozen=True, kw_only=True)
class TradeFacts:
    """The facts of one trade. ``quote`` and ``fee_asset`` are asset codes, never assumed.

    ``raw_text`` is what the user said, kept as it was said, never tidied.
    """

    occurred: datetime
    side: Side
    asset: str
    quantity: Decimal
    price: Decimal
    total: Decimal
    quote: str
    fee: Decimal
    fee_asset: str
    platform: str
    note: str
    raw_text: str

    def __post_init__(self) -> None:
        _require_moment("a trade's moment", self.occurred)
        if not isinstance(self.side, Side):
            raise TypeError(f"a trade's side is a Side, not {type(self.side).__name__}")
        for name in ("asset", "quote", "fee_asset", "raw_text"):
            _require_text(f"a trade's {name}", getattr(self, name))
        for name in ("quantity", "price", "total", "fee"):
            _require_amount(f"a trade's {name}", getattr(self, name))
        if self.quantity == 0:
            raise ValueError("a trade's quantity is more than 0")
        if not isinstance(self.platform, str) or not isinstance(self.note, str):
            raise TypeError("a trade's platform and note are text")


@dataclass(frozen=True, kw_only=True)
class LedgerTrade:
    """A trade in the ledger. ``realized`` is the sell's profit or loss; a buy has none."""

    id: str
    facts: TradeFacts
    realized: Figure | None

    def __post_init__(self) -> None:
        _require_text("a trade's identifier", self.id)
        if not isinstance(self.facts, TradeFacts):
            raise TypeError(f"a trade's facts are TradeFacts, not {type(self.facts).__name__}")
        if self.facts.side is Side.BUY and self.realized is not None:
            raise ValueError("a buy makes no profit or loss of its own")
        is_figure = isinstance(self.realized, MoneyAmount | NotWorkedOut)
        if self.facts.side is Side.SELL and not is_figure:
            raise ValueError("a sell carries its profit or loss, or why it was not worked out")


@dataclass(frozen=True, kw_only=True)
class TradeFilter:
    """Which trades to list: from ``start`` (inclusive) to ``end`` (exclusive), of ``asset``,
    on ``side``. Each part left out (``None``) does not narrow the list."""

    start: datetime | None = None
    end: datetime | None = None
    asset: str | None = None
    side: Side | None = None

    def __post_init__(self) -> None:
        for name in ("start", "end"):
            if getattr(self, name) is not None:
                _require_moment(f"a filter's {name}", getattr(self, name))
        if self.asset is not None:
            _require_text("a filter's asset", self.asset)
        if self.side is not None and not isinstance(self.side, Side):
            raise TypeError(f"a filter's side is a Side, not {type(self.side).__name__}")
        if self.start is not None and self.end is not None and self.end <= self.start:
            raise ValueError("a filter's end comes after its start")


@dataclass(frozen=True, kw_only=True)
class PeriodRequest:
    """Which stretch of time to sum up, from ``start`` (inclusive) to ``end`` (exclusive),
    for ``asset`` alone or for every asset; each part may be left out."""

    start: datetime | None = None
    end: datetime | None = None
    asset: str | None = None

    def __post_init__(self) -> None:
        TradeFilter(start=self.start, end=self.end, asset=self.asset)


@dataclass(frozen=True, kw_only=True)
class CurrencyTotals:
    """The sums of the trades priced in one money: spent on buys, received from sells,
    and the profit or loss the sells made, or why it was not worked out."""

    currency: str
    spent: Decimal
    received: Decimal
    realized: Figure

    def __post_init__(self) -> None:
        _require_text("a money's code", self.currency)
        _require_amount("the amount spent", self.spent)
        _require_amount("the amount received", self.received)
        if not isinstance(self.realized, MoneyAmount | NotWorkedOut):
            raise TypeError("the profit or loss is a MoneyAmount or a NotWorkedOut")


@dataclass(frozen=True, kw_only=True)
class PeriodSummary:
    """The sums of one stretch of time: how many trades, and one set of sums for each
    money they were priced in; the fees, one amount for each asset they were taken in."""

    request: PeriodRequest
    trade_count: int
    by_currency: tuple[CurrencyTotals, ...]
    fees: tuple[MoneyAmount, ...]

    def __post_init__(self) -> None:
        if isinstance(self.trade_count, bool) or not isinstance(self.trade_count, int):
            raise TypeError("a summary's count of trades is a whole number")
        if self.trade_count < 0:
            raise ValueError("a summary's count of trades is 0 or more")
        currencies = [totals.currency for totals in self.by_currency]
        if len(set(currencies)) != len(currencies):
            raise ValueError("one money is summed once, not twice")
        fee_assets = [fee.currency for fee in self.fees]
        if len(set(fee_assets)) != len(fee_assets):
            raise ValueError("the fees taken in one asset are summed once, not twice")


@dataclass(frozen=True, kw_only=True)
class Position:
    """What is held of ``asset`` bought with ``quote``: how much, what it cost, and
    the profit or loss it stands at, or why that was not worked out."""

    asset: str
    quote: str
    quantity: Decimal
    cost: MoneyAmount
    unrealized: Figure

    def __post_init__(self) -> None:
        _require_text("a holding's asset", self.asset)
        _require_text("a holding's money", self.quote)
        _require_amount("a holding's quantity", self.quantity)
        if not isinstance(self.cost, MoneyAmount) or self.cost.currency != self.quote:
            raise ValueError("a holding's cost is given in the money it was bought with")
        if isinstance(self.unrealized, MoneyAmount) and self.unrealized.currency != self.quote:
            raise ValueError("a holding's profit or loss is given in the money it was bought with")
