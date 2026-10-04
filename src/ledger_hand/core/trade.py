"""What one trade looks like: a draft that may have blanks, and a finished record.

A ``TradeDraft`` is a trade that is still being put together. Every field may
be blank. Its numbers are already exact decimals and its time is already a
definite ``OccurredTime``; turning spoken phrases into those values happens
before a draft is filled. A draft also remembers which of its three amounts
the program worked out itself, so that such a value is never mistaken for
something the user said.

A ``TradeRecord`` is a trade with every required field filled that has passed
every rule. Only ``validation.check_draft`` builds one, and once built it
cannot be changed.

``OccurredTime`` is how every part of the program holds the time of a trade.
Day precision holds a calendar date. Minute and second precision hold a moment
with its offset. All three also carry the name of the time zone the trade was
recorded in, and the offset of a moment must be that zone's offset at that
moment, because the ledger checks exactly this. It can also say whether it
lies in the future as seen from a given moment, so that there is one
definition of "in the future" for everyone who needs it.

This module only states shapes and the conditions a value must meet to exist
at all. The rules of a trade are in ``validation``. Record identifiers,
creation times and the export format are not handled here.

Names defined here: ``Side``, ``TimePrecision``, ``Amount``, ``OccurredTime``,
``TradeDraft`` and ``TradeRecord``.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo


class Side(enum.Enum):
    """Whether the coin was bought or sold; the value is the ledger's word for it."""

    BUY = "buy"
    SELL = "sell"


class TimePrecision(enum.Enum):
    """How exactly the time of a trade is known; the value is the ledger's word for it."""

    DAY = "day"
    MINUTE = "minute"
    SECOND = "second"


class Amount(enum.Enum):
    """The three amounts of a trade, any two of which give the third.

    The total is quantity times price and never includes the fee.
    """

    QUANTITY = "quantity"
    PRICE = "price"
    TOTAL = "total"


@dataclass(frozen=True)
class OccurredTime:
    """When a trade happened, in the time zone it was recorded in.

    ``value`` is a ``date`` for day precision and a ``datetime`` carrying an
    offset for minute and second precision. ``time_zone`` is an IANA name such
    as ``Europe/Budapest``.

    A moment is kept with a plain fixed offset, whatever kind of zone object
    it arrived with. Python compares two moments that share one zone object by
    their wall-clock reading alone, which confuses the two readings of the
    hour that repeats when the clocks go back; with fixed offsets, comparing
    and subtracting always work on the actual instants.
    """

    value: date | datetime
    precision: TimePrecision
    time_zone: str

    def __post_init__(self) -> None:
        zone = _zone_named(self.time_zone)
        if not isinstance(self.value, date):
            raise TypeError(f"a time must be a date or a datetime, not {self.value!r}")
        if self.precision is TimePrecision.DAY:
            if isinstance(self.value, datetime):
                raise ValueError("day precision holds a date, not a moment")
        elif isinstance(self.value, datetime):
            _require_nothing_finer(self.value, self.precision)
            object.__setattr__(self, "value", _with_fixed_offset(self.value, zone))
        else:
            raise ValueError(f"{self.precision.value} precision holds a moment, not a bare date")

    @property
    def calendar_date(self) -> date:
        """The day on the wall clock of the trade's own zone."""
        return self.value.date() if isinstance(self.value, datetime) else self.value

    def is_in_the_future(self, now: datetime, grace: timedelta) -> bool:
        """Whether this time lies in the future as seen from ``now``.

        A moment is in the future when it is more than ``grace`` after ``now``.
        A day is in the future when it is after today's date in this time's
        own zone; ``grace`` plays no part there. ``now`` must carry an offset.
        """
        if now.utcoffset() is None:
            raise ValueError("the current moment must carry a time zone offset")
        if isinstance(self.value, datetime):
            # In UTC, so that adding the grace moves the instant and not a wall clock.
            return self.value > now.astimezone(timezone.utc) + grace
        return self.value > now.astimezone(_zone_named(self.time_zone)).date()


def _zone_named(name: str) -> ZoneInfo:
    # On some systems this name loads the machine's own zone, which the core
    # must never read.
    if name == "localtime":
        raise ValueError("not a time zone name: 'localtime'")
    try:
        return ZoneInfo(name)
    except (KeyError, ValueError, OSError) as error:
        raise ValueError(f"not a time zone name: {name!r}") from error


def _with_fixed_offset(moment: datetime, zone: ZoneInfo) -> datetime:
    """The same wall time and offset, held with a fixed offset; refused if the zone disagrees."""
    offset = moment.utcoffset()
    if offset is None:
        raise ValueError("a moment needs a time zone offset")
    # Through UTC and back: a wall time that the zone skips, or an offset from
    # some other zone, does not come back with the offset it went in with.
    if moment.astimezone(timezone.utc).astimezone(zone).utcoffset() != offset:
        raise ValueError(f"the offset of {moment.isoformat()} is not that of {zone.key} then")
    return moment.replace(tzinfo=timezone(offset), fold=0)


def _require_nothing_finer(moment: datetime, precision: TimePrecision) -> None:
    finer = moment.microsecond or (precision is TimePrecision.MINUTE and moment.second)
    if finer:
        raise ValueError(f"{moment.isoformat()} is finer than {precision.value} precision")


_NUMBER_FIELDS = ("quantity", "price", "total", "fee")


@dataclass(frozen=True, kw_only=True)
class TradeDraft:
    """A trade that may still have blanks.

    ``coin``, ``quote`` and ``fee_coin`` hold the words as they were said; the
    coin table turns them into symbols when the draft is checked. ``quote`` is
    the word used for the pricing currency, if one was said. ``derived`` names
    the amounts the program filled in by calculation.
    """

    side: Side | None = None
    coin: str | None = None
    quantity: Decimal | None = None
    price: Decimal | None = None
    total: Decimal | None = None
    quote: str | None = None
    fee: Decimal | None = None
    fee_coin: str | None = None
    occurred: OccurredTime | None = None
    platform: str | None = None
    note: str | None = None
    raw_text: str | None = None
    derived: frozenset[Amount] = frozenset()

    def __post_init__(self) -> None:
        for name in _NUMBER_FIELDS:
            number = getattr(self, name)
            if number is None:
                continue
            if not isinstance(number, Decimal):
                raise TypeError(f"{name} must be an exact decimal, not {type(number).__name__}")
            if not number.is_finite():
                raise ValueError(f"{name} must be a finite number, not {number}")

    def stated(self, amount: Amount) -> Decimal | None:
        """The amount as the user gave it; ``None`` when blank or worked out by the program."""
        if amount in self.derived:
            return None
        values = {
            Amount.QUANTITY: self.quantity,
            Amount.PRICE: self.price,
            Amount.TOTAL: self.total,
        }
        return values[amount]


@dataclass(frozen=True, kw_only=True)
class TradeRecord:
    """A complete trade that has passed every rule. It cannot be changed.

    ``coin`` is a ledger symbol. ``fee_coin`` is a ledger symbol or USDT.
    ``derived`` names the one amount the program calculated from the other
    two, or is ``None`` when the user gave all three. The pricing currency is
    always USDT and is therefore not a field.
    """

    side: Side
    coin: str
    quantity: Decimal
    price: Decimal
    total: Decimal
    derived: Amount | None
    fee: Decimal
    fee_coin: str
    occurred: OccurredTime
    raw_text: str
    platform: str | None = None
    note: str | None = None
