"""Whether the price of a trade is far from the ledger's market price of its asset.

``check_price`` takes the price a trade was done at and the money it is
in, the ledger's market prices of the asset (none, one, or one for each
money it is priced in) and how many times apart counts as far. It hands
back one of these (``PriceVerdict``), with what the words about it need:

- far: the price is at least that many times the market price, or the
  market price at least that many times the price; exactly that many
  times counts ("差到 5 倍以上" counts 5);
- within: not far;
- no market price: the ledger has none, or one of 0 or below, which is
  taken as none; nothing is said about it;
- in other money: the market price is in another money than the trade's
  (USDT against USD); the two are never compared, never converted, and
  never taken as one money;
- no money: the money the trade used is not known; nothing stands in
  for it, not the asset's own money and not the last trade's.

A fifth outcome is the caller's, not this function's: the ledger could
not be asked for its market prices (``PriceVerdict.NOT_ASKED``, made by
``not_asked``).

How many times apart is shown as the larger over the smaller: a whole
number from 10 times up, one place after the point below 10, a tie
rounded up. Ten is where a place after the point stops telling anything;
the line was drawn by the contract's author and waits for a reason
(2026-11-25). Only the comparison above decides far or not.

All of it is exact decimal arithmetic; nothing reads the ledger or the
clock. Example: 950 USDT against BTC's 64880 USDT, five times apart:
far, about 68 times lower.

Names defined here: ``PriceVerdict``, ``PriceCheck``, ``check_price``
and ``not_asked``.
"""

from __future__ import annotations

import enum
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from ledger_hand.core.arithmetic import round_half_up, working_context
from ledger_hand.core.ledger_records import MarketPrice

# From ten times apart up, the times are shown as a whole number.
_WHOLE_FROM = Decimal(10)


class PriceVerdict(enum.Enum):
    """What came of comparing a trade's price with the ledger's market price."""

    FAR = "far from the market price"
    WITHIN = "within reach of the market price"
    NO_MARKET_PRICE = "the ledger has no market price of the asset"
    OTHER_MONEY = "the market price is in another money than the trade"
    NO_MONEY = "the money the trade used is not known yet"
    NOT_ASKED = "the ledger could not be asked for its market prices"

    @property
    def compared(self) -> bool:
        """Whether the price was compared with a market price at all."""
        return self in (PriceVerdict.FAR, PriceVerdict.WITHIN)


@dataclass(frozen=True, kw_only=True)
class PriceCheck:
    """One trade's price compared with the market price, and what the words need.

    ``market`` is the market price compared with, or, in other money, one
    of those not compared. ``times`` is how many times apart, as shown,
    and ``higher`` whether the trade's price is the higher; both only when
    compared. ``failure`` is the ledger's sentence when it could not be
    asked.
    """

    verdict: PriceVerdict
    price: Decimal | None = None
    money: str | None = None
    market: MarketPrice | None = None
    times: Decimal | None = None
    higher: bool | None = None
    failure: str | None = None


def check_price(
    price: Decimal, money: str | None, markets: Sequence[MarketPrice], gap: Decimal
) -> PriceCheck:
    """``price`` in ``money`` against ``markets``, the asset's market prices; far at ``gap`` times.

    ``price`` must be above 0 and ``gap`` above 1. Example: 950 in USDT,
    BTC's 64880 USDT, 5: far, about 68 times lower.
    """
    if price <= 0:
        raise ValueError(f"a price compared must be above 0, not {price}")
    if gap <= 1:
        raise ValueError(f"how many times apart counts as far must be above 1, not {gap}")
    if money is None:
        return PriceCheck(verdict=PriceVerdict.NO_MONEY, price=price)
    usable = [one for one in markets if one.price.amount > 0]
    if not usable:
        return PriceCheck(verdict=PriceVerdict.NO_MARKET_PRICE, price=price, money=money)
    same = next((one for one in usable if one.price.currency == money), None)
    if same is None:
        return PriceCheck(
            verdict=PriceVerdict.OTHER_MONEY, price=price, money=money, market=usable[0]
        )
    market = same.price.amount
    context = working_context()
    far = price >= context.multiply(market, gap) or context.multiply(price, gap) <= market
    return PriceCheck(
        verdict=PriceVerdict.FAR if far else PriceVerdict.WITHIN,
        price=price,
        money=money,
        market=same,
        times=_times_apart(price, market),
        higher=price > market,
    )


def not_asked(price: Decimal | None, money: str | None, failure: str) -> PriceCheck:
    """The outcome when the ledger could not be asked: ``failure`` is its sentence."""
    return PriceCheck(verdict=PriceVerdict.NOT_ASKED, price=price, money=money, failure=failure)


def _times_apart(price: Decimal, market: Decimal) -> Decimal:
    """The larger over the smaller, rounded as it is shown. Example: 64880 / 950 -> 68."""
    larger, smaller = (price, market) if price >= market else (market, price)
    ratio = working_context().divide(larger, smaller)
    return round_half_up(ratio, 0 if ratio >= _WHOLE_FROM else 1)
