"""The money of an asset's last trade in the ledger, to guess what a vague word for money meant.

When the user says only a vague word for money ("美金", "刀", "$") for a
trade, and the trade itself names neither USDT nor the US dollar, the
program looks at the asset's trades in the ledger (the product owner's
rule of 2026-11-25). ``last_money_of`` makes the one function the
recording flow is handed for that; the flow itself never touches the
ledger, and without the function nothing is guessed.

How the last trade is found:

- only trades whose time is not after the current moment count, a buy or
  a sell alike;
- the latest such day is taken, on the clock of each trade's own time:
  the ledger may know a trade only to the day, and this program's trades
  carry no mark of that, so days are compared, not moments;
- when every trade of that day used one money, that money is the answer,
  with the latest of them as the trade it came from;
- when that day used more than one money, whichever came first, nothing
  is guessed (``LastMoneyMiss.TWO_MONEYS``).

Example: ETH bought for USDT on 2026-08-03 and nothing later gives USDT,
from that trade. BTC bought for US dollars on 2026-08-01 and for USDT on
2026-08-02 gives USDT. SOL bought for USDT and for US dollars on the same
day gives nothing.

What the ledger listed of the asset is kept with the answer (``listed``),
so that the rate of a trade paid in another money can be compared with
the asset's own last such trade without asking the ledger again
(``proposing``, 2026-11-26); it plays no part in which money is found.

An asset with no trade gives nothing (``NO_TRADE``); so does a ledger
that cannot be asked, or says it does not know the asset
(``LEDGER_FAILED``). Whether the money found may be used (USDT or the US
dollar, and one the ledger prices trades in now) is the flow's to judge.

Names defined here: ``LastMoney``, ``LastMoneyMiss``, ``LastMoneyLookup``
and ``last_money_of``.
"""

from __future__ import annotations

import enum
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from ledger_hand.core.ledger_records import LedgerTrade, TradeFilter
from ledger_hand.core.trade import InferredFrom
from ledger_hand.ports import LedgerError, LedgerPort


class LastMoneyMiss(enum.Enum):
    """Why no money was found for an asset."""

    NO_TRADE = "the ledger has no trade of this asset up to now"
    TWO_MONEYS = "the latest day of its trades used more than one money"
    LEDGER_FAILED = "the ledger could not be asked about its trades"


@dataclass(frozen=True)
class LastMoney:
    """What the ledger's trades of one asset say: the trade a money is taken from, or why none.

    Exactly one of ``found`` and ``miss`` is there. ``listed`` holds the
    asset's trades as the ledger listed them, none when it could not be
    asked; it is not part of what the answer is, and two answers that
    differ only in it are the same.
    """

    found: InferredFrom | None = None
    miss: LastMoneyMiss | None = None
    listed: tuple[LedgerTrade, ...] = field(default=(), compare=False)

    def __post_init__(self) -> None:
        if (self.found is None) == (self.miss is None):
            raise ValueError("a last money is either found or missed, not both or neither")


type LastMoneyLookup = Callable[[str], LastMoney]
"""Given an asset's code, the money of its last trade in the ledger."""


def last_money_of(ledger: LedgerPort, now: datetime) -> LastMoneyLookup:
    """The function that asks ``ledger`` for an asset's trades up to ``now``, and finds its money.

    Each call asks the ledger once (``list_trades``); the recording flow
    keeps each answer for the rest of the passage, so one asset is asked
    about at most once.
    """
    if now.utcoffset() is None:
        raise ValueError("the current moment must carry a time zone offset")

    def lookup(code: str) -> LastMoney:
        try:
            listed = ledger.list_trades(TradeFilter(asset=code))
        except LedgerError:
            return LastMoney(miss=LastMoneyMiss.LEDGER_FAILED)
        return _last_money(code, listed.trades, now)

    return lookup


def _last_money(code: str, trades: tuple[LedgerTrade, ...], now: datetime) -> LastMoney:
    """The money of the latest day's trades of ``code`` up to ``now``, when that day used one."""
    own = tuple(trade for trade in trades if trade.facts.asset == code)
    past = [trade for trade in own if trade.facts.occurred <= now]
    if not past:
        return LastMoney(miss=LastMoneyMiss.NO_TRADE, listed=own)
    latest_day = max(trade.facts.day for trade in past)
    that_day = [trade for trade in past if trade.facts.day == latest_day]
    if len({trade.facts.quote for trade in that_day}) > 1:
        return LastMoney(miss=LastMoneyMiss.TWO_MONEYS, listed=own)
    last = max(that_day, key=lambda trade: trade.facts.occurred)
    return LastMoney(
        found=InferredFrom(
            trade_id=last.id,
            occurred=last.facts.occurred,
            money=last.facts.quote,
            asset=code,
        ),
        listed=own,
    )
