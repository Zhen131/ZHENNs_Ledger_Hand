"""A coin's entry in the file: the card the ledger needs for every coin a trade uses.

The ledger accepts a trade only when the file also holds an entry for its
coin, and for the coin its fee was paid in unless that was USDT. The entry
gives the coin's symbol, its full name, its market on Binance (the ledger
fetches prices there) and an identifier with two bookkeeping moments.

Everything on the card comes from the coin table, never from a language
model. A coin the user confirmed has no known name or market, so its name is
its symbol and its market is left empty, whatever else the coin carries.

The identifier and the two moments are the same in every export. The
identifier is made from the symbol. The two moments are one fixed moment:
this program keeps no record of when a coin was first used, and a moment that
changed from one export to the next would make the same coin look different.

Names defined here: ``coin_card``, ``coin_card_id`` and ``COIN_CARD_MOMENT``.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ledger_hand.core.coins import Coin, CoinOrigin
from ledger_hand.core.ledger_limits import QUOTE_CURRENCY
from ledger_hand.export.moments import write_moment

# The creation and change moment on every coin card.
COIN_CARD_MOMENT = datetime(2026, 10, 4, tzinfo=timezone.utc)

_ID_PREFIX = "asset-hand-"


def coin_card_id(symbol: str) -> str:
    """The identifier of the card of the coin with ``symbol``.

    Symbols are capital letters and digits, so two symbols never give the same
    identifier.
    """
    return f"{_ID_PREFIX}{symbol.lower()}"


def coin_card(coin: Coin) -> dict[str, object]:
    """The ledger's fields for ``coin``, in the ledger's order."""
    confirmed = coin.origin is CoinOrigin.USER_CONFIRMED
    pair = None if confirmed else coin.binance_pair
    moment = write_moment(COIN_CARD_MOMENT)
    return {
        "id": coin_card_id(coin.symbol),
        "symbol": coin.symbol,
        "name": coin.symbol if confirmed else coin.name,
        "quoteCurrency": QUOTE_CURRENCY,
        "binanceMapping": None if pair is None else _market(coin.symbol, pair),
        "createdAt": moment,
        "updatedAt": moment,
    }


def _market(symbol: str, pair: str) -> dict[str, object]:
    return {
        "provider": "binance",
        "symbol": pair,
        "baseAsset": symbol,
        "quoteAsset": QUOTE_CURRENCY,
    }
