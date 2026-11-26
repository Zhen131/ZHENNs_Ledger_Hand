"""What the ledger's tools hand back and take: assets, trades, sums and holdings.

These are the shapes the ledger port (``ports.LedgerPort``) uses. They carry
moments and exact amounts, so they live in the core, and the ports file only
names them. Nothing here reads a ledger, works a figure out or reads the
clock: whoever is behind the port fills them in. They follow what the
ledger's assistant link really hands back (``assistant-link/README.md`` in
the ledger; samples in ``tests/ledger/samples/``, 2026-11-25).

- ``Asset``: one asset the ledger knows: its name, its code, its kind, its
  identifier inside the ledger, whether it can be the money a trade is
  priced in (``Pricing``), and the money it is itself priced in.
- ``TradeFacts``: the facts of one trade. Every trade names the money it is
  priced in (``quote``) and what its fee was taken in (``fee_asset``);
  neither has a default, because a ledger holds stocks bought with dollars
  as well as coins bought with USDT. It keeps the name of the time zone it
  was recorded in, whether only its day is known, the rate between the
  money it used and the asset's own money, and the user's own words it was
  recorded from (``raw_text``), byte for byte, or ``None`` when there are
  none.
- ``LedgerTrade``: a trade in the ledger: its identifier, its facts, for a
  sell the profit or loss it made (``realized``), why that figure is not
  reliable when it is not, and whether it is dated after today.
- ``TradeFilter``: which trades to list, by days (both ends counted), asset
  and side; every part of it may be left out. ``TradeList``: the trades
  listed, at most ``MOST_TRADES_LISTED``, and whether older ones were cut.
- ``PeriodRequest``, ``PeriodSummary``, ``CurrencyTotals`` and
  ``AssetRealized``: the sums of a stretch of days, one group for each money.
- ``Position``: what is held of one asset, in the asset's own money.
- ``MoneyAmount`` and ``NotWorkedOut``: a figure in one named money, or the
  reason it could not be worked out (``Figure`` is either).
- ``MarketPrice``: the ledger's market price of one asset, in one money,
  and the day it is for.
- ``CashBalance`` and ``CashBalances``: how much of each cash money the
  ledger holds, counted up to one day, one row a money, as the ledger
  hands them back; ``NO_CASH_TOOL`` is the code of the failure of a ledger
  that has no tool to read them (an older ledger), told apart from a
  ledger that could not be asked this time.

Money of two kinds is never added together: a sum or a holding is always
given for one money, named beside it. Amounts are exact decimals, never
floating-point numbers, and every moment carries an offset. A trade known
only to its day holds the start of that day, and says so (``date_only``):
it is never to be shown as midnight.

Names defined here: ``AssetKind``, ``Pricing``, ``Asset``, ``MoneyAmount``,
``NotWorkedOut``, ``Figure``, ``TradeFacts``, ``LedgerTrade``, ``TradeFilter``,
``PeriodRequest``, ``AssetRealized``, ``CurrencyTotals``, ``PeriodSummary``,
``Position``, ``MarketPrice``, ``MOST_TRADES_LISTED``, ``TradeList``,
``CashBalance``, ``CashBalances`` and ``NO_CASH_TOOL``.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import date, datetime
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


def _require_text_or_none(name: str, value: object) -> None:
    if value is not None:
        _require_text(name, value)


def _require_moment(name: str, value: object) -> None:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} is a datetime, not {type(value).__name__}")
    if value.utcoffset() is None:
        raise ValueError(f"{name} must carry an offset")


def _require_day(name: str, value: object) -> None:
    if not isinstance(value, date) or isinstance(value, datetime):
        raise TypeError(f"{name} is a date, not {type(value).__name__}")


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


def _require_count(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} is a whole number")
    if value < 0:
        raise ValueError(f"{name} is 0 or more")


def _require_flag(name: str, value: object) -> None:
    if not isinstance(value, bool):
        raise TypeError(f"{name} is True or False, not {value!r}")


@dataclass(frozen=True, kw_only=True)
class Asset:
    """One asset the ledger knows.

    ``price_currency`` is the code of the money the asset itself is priced
    in (USD for a US stock); ``None`` for money, and for a ledger that does
    not say.
    """

    id: str
    code: str
    name: str
    kind: AssetKind
    pricing: Pricing
    price_currency: str | None = None

    def __post_init__(self) -> None:
        _require_text("an asset's identifier", self.id)
        _require_text("an asset's code", self.code)
        _require_text("an asset's name", self.name)
        if not isinstance(self.kind, AssetKind):
            raise TypeError(f"an asset's kind is an AssetKind, not {type(self.kind).__name__}")
        if not isinstance(self.pricing, Pricing):
            raise TypeError(f"an asset's pricing is a Pricing, not {type(self.pricing).__name__}")
        _require_text_or_none("an asset's own money", self.price_currency)


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
    """A figure that could not be worked out, and why, in one plain sentence.

    The sentence is the ledger's own when the ledger gave one, in the
    language of the ledger's page.
    """

    reason: str

    def __post_init__(self) -> None:
        _require_text("the reason a figure was not worked out", self.reason)


type Figure = MoneyAmount | NotWorkedOut
"""A figure in one money, or the reason it could not be worked out."""


def _require_figure(name: str, value: object) -> None:
    if not isinstance(value, MoneyAmount | NotWorkedOut):
        raise TypeError(f"{name} is a MoneyAmount or a NotWorkedOut")


@dataclass(frozen=True, kw_only=True)
class TradeFacts:
    """The facts of one trade. ``quote`` and ``fee_asset`` are asset codes, never assumed.

    ``zone`` is the name of the time zone the trade was recorded in, such
    as ``Europe/Budapest``, or ``None`` when none was. ``date_only`` says
    only the day is known: ``occurred`` then holds the start of that day
    and is never shown as a time. ``cost_rate`` is how many units of the
    asset's own money one unit of ``quote`` is worth, given only when the
    two differ. ``raw_text`` is what the user said, kept as it was said,
    never tidied; ``None`` when the ledger holds no words of the user's.
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
    raw_text: str | None
    zone: str | None
    date_only: bool
    cost_rate: Decimal | None

    def __post_init__(self) -> None:
        _require_moment("a trade's moment", self.occurred)
        if not isinstance(self.side, Side):
            raise TypeError(f"a trade's side is a Side, not {type(self.side).__name__}")
        for name in ("asset", "quote", "fee_asset"):
            _require_text(f"a trade's {name}", getattr(self, name))
        _require_text_or_none("a trade's words", self.raw_text)
        _require_text_or_none("a trade's time zone", self.zone)
        _require_flag("whether only a trade's day is known", self.date_only)
        for name in ("quantity", "price", "total", "fee"):
            _require_amount(f"a trade's {name}", getattr(self, name))
        if self.quantity == 0:
            raise ValueError("a trade's quantity is more than 0")
        if self.cost_rate is not None:
            _require_amount("a trade's rate between moneys", self.cost_rate)
        if not isinstance(self.platform, str) or not isinstance(self.note, str):
            raise TypeError("a trade's platform and note are text")
        if self.date_only and (self.occurred.hour, self.occurred.minute) != (0, 0):
            raise ValueError("a trade known only to its day holds the start of that day")

    @property
    def day(self) -> date:
        """The day of the trade, on the clock of its own offset (the ledger's way)."""
        return self.occurred.date()


@dataclass(frozen=True, kw_only=True)
class LedgerTrade:
    """A trade in the ledger. ``realized`` is the sell's profit or loss; a buy has none.

    The profit or loss of a sell is in the asset's own money, which may
    not be the money the trade used. ``realized_unreliable`` says why that
    figure is given but not exact, when it is not. ``dated_after_today``
    marks a trade the ledger counts in no sum yet.
    """

    id: str
    facts: TradeFacts
    realized: Figure | None
    realized_unreliable: str | None
    dated_after_today: bool

    def __post_init__(self) -> None:
        _require_text("a trade's identifier", self.id)
        if not isinstance(self.facts, TradeFacts):
            raise TypeError(f"a trade's facts are TradeFacts, not {type(self.facts).__name__}")
        if self.facts.side is Side.BUY and self.realized is not None:
            raise ValueError("a buy makes no profit or loss of its own")
        is_figure = isinstance(self.realized, MoneyAmount | NotWorkedOut)
        if self.facts.side is Side.SELL and not is_figure:
            raise ValueError("a sell carries its profit or loss, or why it was not worked out")
        _require_text_or_none("why a profit is not reliable", self.realized_unreliable)
        if self.realized_unreliable is not None and not isinstance(self.realized, MoneyAmount):
            raise ValueError("only a figure that is given can be said to be not reliable")
        _require_flag("whether a trade is dated after today", self.dated_after_today)


@dataclass(frozen=True, kw_only=True)
class TradeFilter:
    """Which trades to list: from ``first_day`` to ``last_day``, both counted, of ``asset``,
    on ``side``. Each part left out (``None``) does not narrow the list.

    A trade falls on the day of its own offset (``TradeFacts.day``).
    """

    first_day: date | None = None
    last_day: date | None = None
    asset: str | None = None
    side: Side | None = None

    def __post_init__(self) -> None:
        for name in ("first_day", "last_day"):
            if getattr(self, name) is not None:
                _require_day(f"a filter's {name}", getattr(self, name))
        if self.asset is not None:
            _require_text("a filter's asset", self.asset)
        if self.side is not None and not isinstance(self.side, Side):
            raise TypeError(f"a filter's side is a Side, not {type(self.side).__name__}")
        first, last = self.first_day, self.last_day
        if first is not None and last is not None and last < first:
            raise ValueError("a filter's last day is not before its first")

    def holds(self, facts: TradeFacts) -> bool:
        """Whether the trade of ``facts`` is one this filter lets through."""
        if self.first_day is not None and facts.day < self.first_day:
            return False
        if self.last_day is not None and facts.day > self.last_day:
            return False
        if self.asset is not None and facts.asset != self.asset:
            return False
        return self.side is None or facts.side is self.side


@dataclass(frozen=True, kw_only=True)
class PeriodRequest:
    """Which stretch of days to sum up, both ends counted, for ``asset`` alone or for
    every asset; each part may be left out (no days: all time)."""

    first_day: date | None = None
    last_day: date | None = None
    asset: str | None = None

    def __post_init__(self) -> None:
        TradeFilter(first_day=self.first_day, last_day=self.last_day, asset=self.asset)


@dataclass(frozen=True, kw_only=True)
class AssetRealized:
    """The profit or loss one asset's sells made in a stretch of time, in the group's money,
    and why it is not exact when it is not."""

    asset: str
    realized: MoneyAmount
    unreliable: str | None

    def __post_init__(self) -> None:
        _require_text("an asset's code", self.asset)
        if not isinstance(self.realized, MoneyAmount):
            raise TypeError("an asset's profit or loss is a MoneyAmount")
        _require_text_or_none("why a profit is not reliable", self.unreliable)


@dataclass(frozen=True, kw_only=True)
class CurrencyTotals:
    """The sums of one money's group in a stretch of time.

    ``buy_count`` buys were paid in it and ``sell_count`` sells received in
    it. ``spent`` and ``received`` are what they paid out and brought in,
    fees taken in this money already inside, or why they could not be
    added up. ``fees`` are the fees of the group's trades, one amount for
    each asset they were taken in. ``realized`` is the group's profit or
    loss, made of what sells made (``realized_from_sells``) and of the cost
    assets took along when moved out (``realized_from_transfers``, 0 or
    below, and never a losing sale); ``by_asset`` is one row an asset.
    """

    currency: str
    buy_count: int
    sell_count: int
    spent: Figure
    received: Figure
    fees: tuple[MoneyAmount, ...]
    realized: Figure
    realized_from_sells: Figure
    realized_from_transfers: Figure
    by_asset: tuple[AssetRealized, ...]

    def __post_init__(self) -> None:
        _require_text("a money's code", self.currency)
        _require_count("a group's count of buys", self.buy_count)
        _require_count("a group's count of sells", self.sell_count)
        for name in (
            "spent",
            "received",
            "realized",
            "realized_from_sells",
            "realized_from_transfers",
        ):
            _require_figure(f"a group's {name}", getattr(self, name))
        for name in ("spent", "received"):
            figure = getattr(self, name)
            if isinstance(figure, MoneyAmount):
                _require_amount(f"a group's {name}", figure.amount)
        if not all(isinstance(fee, MoneyAmount) for fee in self.fees):
            raise TypeError("a group's fees are MoneyAmount values")
        fee_assets = [fee.currency for fee in self.fees]
        if len(set(fee_assets)) != len(fee_assets):
            raise ValueError("the fees taken in one asset are summed once, not twice")
        if not all(isinstance(row, AssetRealized) for row in self.by_asset):
            raise TypeError("a group's rows by asset are AssetRealized values")

    @property
    def trade_count(self) -> int:
        """How many trades the group holds: its buys and its sells."""
        return self.buy_count + self.sell_count


@dataclass(frozen=True, kw_only=True)
class PeriodSummary:
    """The sums of one stretch of days: one group for each money."""

    request: PeriodRequest
    by_currency: tuple[CurrencyTotals, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.request, PeriodRequest):
            raise TypeError("a summary's request is a PeriodRequest")
        if not all(isinstance(totals, CurrencyTotals) for totals in self.by_currency):
            raise TypeError("a summary's groups are CurrencyTotals values")
        currencies = [totals.currency for totals in self.by_currency]
        if len(set(currencies)) != len(currencies):
            raise ValueError("one money is summed once, not twice")

    @property
    def trade_count(self) -> int:
        """How many trades were summed: the buys and the sells of every group."""
        return sum(totals.trade_count for totals in self.by_currency)

    @property
    def fees(self) -> tuple[MoneyAmount, ...]:
        """Every group's fees, added up for each asset they were taken in, by its code.

        A fee is an amount of the asset it was taken in, so fees taken in
        one asset add up whatever group they came from.
        """
        added: dict[str, Decimal] = {}
        for totals in self.by_currency:
            for fee in totals.fees:
                added[fee.currency] = added.get(fee.currency, Decimal(0)) + fee.amount
        return tuple(MoneyAmount(currency=code, amount=added[code]) for code in sorted(added))


@dataclass(frozen=True, kw_only=True)
class Position:
    """What is held of ``asset``, every figure in ``currency``, the asset's own money.

    ``cost`` is what the units still held cost, fees included;
    ``cost_unreliable`` says why it is not exact when it is not.
    ``unrealized`` is the profit or loss on paper, or why it was not worked
    out.
    """

    asset: str
    currency: str
    quantity: Decimal
    cost: MoneyAmount
    cost_unreliable: str | None
    unrealized: Figure

    def __post_init__(self) -> None:
        _require_text("a holding's asset", self.asset)
        _require_text("a holding's money", self.currency)
        _require_amount("a holding's quantity", self.quantity)
        if not isinstance(self.cost, MoneyAmount) or self.cost.currency != self.currency:
            raise ValueError("a holding's cost is given in the holding's money")
        _require_text_or_none("why a cost is not reliable", self.cost_unreliable)
        _require_figure("a holding's profit or loss", self.unrealized)
        if isinstance(self.unrealized, MoneyAmount) and self.unrealized.currency != self.currency:
            raise ValueError("a holding's profit or loss is given in the holding's money")


@dataclass(frozen=True, kw_only=True)
class MarketPrice:
    """The ledger's market price of one unit of ``asset``, in ``price.currency``.

    ``day`` is the day the price is for, or ``None`` when the ledger does
    not say. The amount is kept as the ledger gave it, even 0 or below;
    whoever compares a price with it takes such a one as no market price.
    Example: BTC at 64880 USDT on 2026-11-24.
    """

    asset: str
    price: MoneyAmount
    day: date | None = None

    def __post_init__(self) -> None:
        _require_text("a market price's asset", self.asset)
        if not isinstance(self.price, MoneyAmount):
            raise TypeError("a market price is a MoneyAmount")
        if self.day is not None:
            _require_day("the day of a market price", self.day)


# The most trades one listing hands back: the latest ones. Two thousand is
# about ten years of a few trades a week, and keeps a listing of the real
# ledger (fifty a page) to forty pages. (68B2, 2026-11-25; can be changed.)
MOST_TRADES_LISTED = 2000


@dataclass(frozen=True, kw_only=True)
class TradeList:
    """Trades listed, oldest first, and whether older ones were left out.

    ``cut`` is true when more trades matched than ``MOST_TRADES_LISTED``:
    only the latest that many are here, and whoever shows them says so.
    """

    trades: tuple[LedgerTrade, ...]
    cut: bool

    def __post_init__(self) -> None:
        if not isinstance(self.trades, tuple) or not all(
            isinstance(trade, LedgerTrade) for trade in self.trades
        ):
            raise TypeError("a list of trades holds a tuple of LedgerTrade values")
        _require_flag("whether older trades were left out", self.cut)


# The code of the failure a ledger with no tool to read its cash balances
# gives (its link answers "UNKNOWN_TOOL"): this ledger cannot, which is not
# the same as a ledger that could not be asked this time.
NO_CASH_TOOL = "NO_CASH_TOOL"


@dataclass(frozen=True)
class CashBalance:
    """How much of one cash money the ledger holds, in that money: 0 or below too.

    ``code`` and ``name`` are the money's own, as the ledger lists them.
    Example: USDT, "Tether", 1200.5; or USD, "US dollar", -30.
    """

    code: str
    name: str
    balance: Decimal

    def __post_init__(self) -> None:
        _require_text("a cash money's code", self.code)
        _require_text("a cash money's name", self.name)
        _require_signed("a cash balance", self.balance)


@dataclass(frozen=True)
class CashBalances:
    """Every cash money's balance, counted up to ``day`` (that day included).

    One row a money, those at 0 included, in the ledger's own order. Rows of
    two moneys are never added together nor converted: each is in its own
    money. The ledger hands no deposit, withdrawal or exchange back.
    """

    day: date
    balances: tuple[CashBalance, ...]

    def __post_init__(self) -> None:
        _require_day("the day cash balances are counted to", self.day)
        if not isinstance(self.balances, tuple) or not all(
            isinstance(row, CashBalance) for row in self.balances
        ):
            raise TypeError("cash balances are a tuple of CashBalance values")
        codes = [row.code for row in self.balances]
        if len(set(codes)) != len(codes):
            raise ValueError("one money has one balance, not two")
