"""The ledger's own exchange rates: reading its rows, picking one, and comparing a rate with it.

Since its dev 1b016ec (2026-11-27) the ledger has a tool that lists the
exchange rates it keeps (``list_exchange_rates``): those the user typed in
("manual") and those it fetched ("online", with the source named, such as
frankfurter). Each row reads "1 base = rate quote", in the direction it was
stored; the same two moneys may have rows both ways, and the rate the
ledger fetches for the euro is stored as "1 USD = x EUR", the other way
round from a rate of a trade paid in euros. So no direction is ever
assumed, and 1 is never taken for a rate that is not there.

A trade paid in one money P for an asset priced in another money Q has a
rate C: how many Q one P is worth (``cost_rate``). It is compared with one
row of the ledger, picked here (``pick``):

- only rows between P and Q count, in either direction;
- the row's rate must read as a finite decimal above 0 ("NaN", "Infinity",
  "0", "-1" and text are passed over and counted, never taken as 1);
- its day must read as a day: the first ten characters of ``rateDate``,
  as the ledger itself reads the day of any record (its
  ``getLedgerDateKey``, "only the first ten characters, the local day";
  a rate typed in on the ledger's price page with a time of day is stored
  as a moment, so a day alone is not the only shape);
- the day must not be after the trade's day D; of those left, the latest
  day wins; on one day, a rate typed in by hand wins over one fetched,
  and then the one listed first.

The gap is worked out exactly, with no rounding before it is compared
(``rate_gap``): for a row "1 P = rate Q", ``|C ÷ rate − 1|``; for a row
"1 Q = rate P", ``|C × rate − 1|``, which is the same as comparing C with
1 ÷ rate without working that out first. Example: C = 1.25 and "1 USD =
0.88 EUR" give exactly 0.1. A gap above the share the settings hold (ten
in a hundred by default) is far; exactly that share is not, as for the
rate of an earlier trade (``cost_rate.far_from_reference``). Only the
figures said are rounded: the ledger's rate as Q for 1 P to ``RATE_PLACES``
places, half up, its ending zeros left out (1 ÷ 0.925 is 1.0810810811),
and the gap in a hundred to one place, half up.

A rate dated ``LONG_AGO_DAYS`` or more days before the trade is still
compared; only the words say how far apart they are.

``LedgerRateNote`` says what came of asking the ledger for one trade, for
the words said, the mark and the assistant's record; ``LedgerRateOutcome``
names the six ways it can end.

Nothing here reads the ledger or the clock.

Names defined here: ``RATE_TOOL``, ``NO_RATE_TOOL``, ``LONG_AGO_DAYS``,
``RateRow``, ``RateRequest``, ``RateList``, ``read_rate``, ``row_day``,
``PickedRate``, ``pick``, ``rate_gap``, ``gap_in_a_hundred``,
``LedgerRateOutcome`` and ``LedgerRateNote``.
"""

from __future__ import annotations

import enum
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from ledger_hand.core.arithmetic import round_half_up, working_context

# The ledger's tool that lists the exchange rates it keeps (its dev 1b016ec).
RATE_TOOL = "list_exchange_rates"

# The code of the failure of a ledger that has no tool for exchange rates (an
# older one), told apart from a ledger that could not be asked this time.
NO_RATE_TOOL = "NO_RATE_TOOL"

# How many days before a trade a rate is said to be far off in time. Taken as
# 7 for now, as is usual; the reason is still to be settled. It changes only
# the words, never whether a rate is marked.
LONG_AGO_DAYS = 7

# How many places the ledger's rate is written to in the words, as a rate is.
_PLACES = 10
_MANUAL = "manual"


@dataclass(frozen=True, kw_only=True)
class RateRow:
    """One row of the ledger's exchange rates, as it listed it: "1 base = rate quote".

    Every field is kept as the ledger wrote it, the rate and the day as
    text. Example: base EUR, quote USD, rate "1.08", day "2026-11-20",
    source "manual", no online source.
    """

    base_id: str
    base_code: str
    quote_id: str
    quote_code: str
    rate: str
    rate_date: str
    source: str
    online_source: str | None

    def as_listed(self) -> dict[str, str | None]:
        """The eight fields under the ledger's own names, as it listed them."""
        return {
            "baseCurrencyAssetId": self.base_id,
            "baseCurrencyCode": self.base_code,
            "quoteCurrencyAssetId": self.quote_id,
            "quoteCurrencyCode": self.quote_code,
            "rate": self.rate,
            "rateDate": self.rate_date,
            "source": self.source,
            "onlineSourceId": self.online_source,
        }

    @property
    def by_hand(self) -> bool:
        """Whether the user typed this rate in."""
        return self.source == _MANUAL

    @property
    def where_from(self) -> str:
        """Where the rate came from, in words: "typed in by hand", or the source's name."""
        if self.by_hand:
            return "typed in by hand"
        return self.online_source or self.source


@dataclass(frozen=True, kw_only=True)
class RateRequest:
    """What the ledger is asked for: the rows between two moneys, by its identifiers.

    ``last_day`` is the latest day wanted (the latest trade's day);
    ``enough_day`` the earliest trade's day: once a row that is not after
    it has been read, the page it is on is the last one read.
    """

    currency_id: str
    other_id: str
    last_day: date
    enough_day: date


@dataclass(frozen=True, kw_only=True)
class RateList:
    """The ledger's rows, newest first as it listed them; ``today`` its own day, when read.

    ``odd`` counts the rows passed over for lacking a field of the eight;
    ``more`` says pages were left unread.
    """

    today: date | None
    rows: tuple[RateRow, ...]
    odd: int = 0
    more: bool = False


def read_rate(text: str) -> Decimal | None:
    """``text`` as a finite decimal above 0; ``None`` for anything else.

    Example: "1.08" -> 1.08; "NaN", "Infinity", "0", "-1", "abc" -> None.
    """
    try:
        value = Decimal(text.strip())
    except (InvalidOperation, AttributeError):
        return None
    if not value.is_finite() or value <= 0:
        return None
    return value


def row_day(text: str) -> date | None:
    """The day a row is for: the first ten characters of ``text`` as a day, else ``None``.

    Example: "2026-11-20" and "2026-11-20T10:00:00+01:00" -> 20 November 2026.
    """
    head = text[:10]
    if len(head) != 10 or head[4] != "-" or head[7] != "-":
        return None
    try:
        return date.fromisoformat(head)
    except ValueError:
        return None


@dataclass(frozen=True, kw_only=True)
class PickedRate:
    """The row picked, read: its rate, its day, and which way round it is.

    ``inverted`` is true for a row "1 Q = rate P"; ``converted`` is the
    ledger's rate as Q for 1 P, rounded for the words (1 ÷ rate when
    inverted). Example: "1 USD = 0.925 EUR" for a trade paid in EUR for
    an asset priced in USD: inverted, converted 1.0810810811.
    """

    row: RateRow
    rate: Decimal
    day: date
    inverted: bool
    converted: Decimal


def pick(
    rows: Sequence[RateRow], paid_id: str, own_id: str, day: date
) -> tuple[PickedRate | None, int]:
    """The row between ``paid_id`` and ``own_id`` to compare with on ``day``, and how many
    rows between them were passed over for a rate or a day that does not read.

    ``None`` when no row fits: none between the two, or only later ones.
    """
    found: list[tuple[int, RateRow, Decimal, date, bool]] = []
    passed_over = 0
    for place, row in enumerate(rows):
        if (row.base_id, row.quote_id) == (paid_id, own_id):
            inverted = False
        elif (row.base_id, row.quote_id) == (own_id, paid_id):
            inverted = True
        else:
            continue
        rate = read_rate(row.rate)
        when = row_day(row.rate_date)
        if rate is None or when is None:
            passed_over += 1
            continue
        if when > day:
            continue
        found.append((place, row, rate, when, inverted))
    if not found:
        return None, passed_over
    # The latest day first; on one day a rate typed in first; then the order listed.
    place, row, rate, when, inverted = min(
        found, key=lambda one: (-one[3].toordinal(), not one[1].by_hand, one[0])
    )
    return PickedRate(
        row=row,
        rate=rate,
        day=when,
        inverted=inverted,
        converted=_converted(rate, inverted=inverted),
    ), passed_over


def _converted(rate: Decimal, *, inverted: bool) -> Decimal:
    context = working_context()
    value = context.divide(Decimal(1), rate) if inverted else rate
    rounded = round_half_up(value, _PLACES)
    normal = rounded.normalize(context=context)
    return normal.quantize(Decimal(1)) if normal == normal.to_integral_value() else normal


def rate_gap(rate: Decimal, picked: PickedRate) -> Decimal:
    """How far ``rate`` is from the ledger's rate, as a share of it, exactly, never rounded.

    Example: 1.08 against "1 EUR = 1.30 USD": |1.08 ÷ 1.30 − 1|, about 0.169;
    1.08 against "1 USD = 0.925 EUR": |1.08 × 0.925 − 1| = 0.001.
    """
    context = working_context()
    if picked.inverted:
        ratio = context.multiply(rate, picked.rate)
    else:
        ratio = context.divide(rate, picked.rate)
    return abs(context.subtract(ratio, Decimal(1)))


def gap_in_a_hundred(gap: Decimal) -> Decimal:
    """``gap`` in a hundred, to one place, half up. Example: 0.16923 -> 16.9."""
    return round_half_up(working_context().multiply(gap, Decimal(100)), 1)


class LedgerRateOutcome(enum.Enum):
    """What came of asking the ledger for its exchange rate for one trade."""

    COMPARED = "compared with the ledger's exchange rate"
    OLDER_THAN_TRADE = (
        "the ledger's latest exchange rate is older than the last trade paid the same way, "
        "so that trade was compared with instead"
    )
    NONE_FITTING = "the ledger has no exchange rate between the two moneys up to that day"
    NOT_READ = "the ledger's exchange rates could not be read this time"
    REFUSED = "the ledger turned the question for its exchange rates down"
    NO_TOOL = "this ledger has no tool for exchange rates"


@dataclass(frozen=True, kw_only=True)
class LedgerRateNote:
    """What came of the ledger's exchange rate for one trade paid in another money.

    ``day`` is the day compared on, and ``day_said`` whether the trade said
    it (``False``: no day was said, so today was taken). ``picked`` is the
    row picked, and ``gap`` how far the rate is from it, exactly, and
    ``far`` whether that is more than ``limit`` in a hundred (the setting
    it was compared by), when it was compared; ``days_apart``
    is how many days before ``day`` the row is. ``passed_over`` counts the
    rows between the two moneys whose rate or day did not read. For a
    failure, ``code`` and ``message`` are the ledger's, or this program's,
    and ``why`` this program's own words for a failure said without the
    ledger's.
    """

    outcome: LedgerRateOutcome
    day: date
    day_said: bool = True
    picked: PickedRate | None = None
    gap: Decimal | None = None
    far: bool = False
    limit: Decimal | None = None
    days_apart: int | None = None
    passed_over: int = 0
    code: str | None = None
    message: str | None = None
    why: str | None = None

    @property
    def long_ago(self) -> bool:
        """Whether the row compared with is ``LONG_AGO_DAYS`` or more days before the trade."""
        return self.days_apart is not None and self.days_apart >= LONG_AGO_DAYS
