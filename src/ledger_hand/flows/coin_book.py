"""The coins the user confirmed, between the book and the coin table.

A coin the user confirmed while a passage was recorded is known for the rest
of that run only (``recording``). It is kept for good only together with a
saved trade that uses it, as the coin traded or the coin a fee was paid in;
a coin confirmed for a trade that was then left out is forgotten. From then
on, recording a passage and exporting use the built-in coin table with the
kept coins added.

Names defined here: ``with_confirmed_coins`` and ``coins_to_keep``.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from ledger_hand.core.book import ConfirmedCoin
from ledger_hand.core.coins import CoinOrigin, CoinTable
from ledger_hand.core.ledger_limits import QUOTE_CURRENCY
from ledger_hand.core.trade import TradeRecord


def with_confirmed_coins(coins: CoinTable, confirmed: Iterable[ConfirmedCoin]) -> CoinTable:
    """``coins`` that also knows each coin in ``confirmed``; a coin it knows changes nothing."""
    for coin in confirmed:
        coins = coins.with_confirmed(coin.symbol)
    return coins


def coins_to_keep(
    records: Iterable[TradeRecord], coins: CoinTable, at: datetime
) -> tuple[ConfirmedCoin, ...]:
    """The coins the user confirmed that ``records`` use, each confirmed ``at``, by symbol."""
    used = set()
    for record in records:
        used.add(record.coin)
        if record.fee_coin != QUOTE_CURRENCY:
            used.add(record.fee_coin)
    kept = []
    for symbol in sorted(used):
        coin = coins.find(symbol)
        if coin is not None and coin.symbol == symbol and coin.origin is CoinOrigin.USER_CONFIRMED:
            kept.append(ConfirmedCoin(symbol=symbol, confirmed_at=at))
    return tuple(kept)
