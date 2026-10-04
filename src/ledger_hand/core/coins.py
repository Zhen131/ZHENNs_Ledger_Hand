"""The coin table: the coins this program knows, what people call them, and the words for USDT.

A coin named in a trade has to be either in this table or confirmed by the
user, for two reasons. The ledger wants a symbol, a full name and a market
pair for every coin in a file, and none of the three may be made up. And a
language model that mishears a coin, or invents one, has to be caught.

Looking a coin up ignores letter case, full-width forms and surrounding
whitespace, and matches the whole text: "以太" finds ETH, "以太经典" finds ETC.
Chinese nicknames are listed only where they can mean one coin.

The ledger prices every trade in USDT, so USDT is not a coin here. The words
people use for it ("U", "刀", "美元" and so on) are kept in a list of their own.

This module holds data and lookup only. Whether a draft's coin is acceptable
is decided in ``validation``.

Names defined here: ``Coin``, ``CoinOrigin``, ``CoinTable``,
``BUILT_IN_COINS``, ``BUILT_IN_TABLE``, ``USDT_WORDS``, ``spoken_key`` and
``means_usdt``.
"""

from __future__ import annotations

import enum
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, field

from ledger_hand.core.ledger_limits import (
    COIN_NAME_MAX_LENGTH,
    MARKET_PAIR_MAX_LENGTH,
    QUOTE_CURRENCY,
    is_symbol,
    text_length,
    trim,
)


class CoinOrigin(enum.Enum):
    """Where a coin in the table came from."""

    BUILT_IN = "built-in"
    USER_CONFIRMED = "user-confirmed"


def spoken_key(spoken: str) -> str:
    """The form under which a spoken name is looked up.

    Full-width characters become ordinary ones, runs of whitespace become one
    space, surrounding whitespace goes, and letters become capitals.
    """
    return " ".join(unicodedata.normalize("NFKC", spoken).split()).upper()


@dataclass(frozen=True)
class Coin:
    """One coin: its ledger symbol, its full name, its Binance market and other names for it.

    ``binance_pair`` is ``None`` when the market is not known for certain. A
    coin the user confirmed has its symbol as its name and no market pair.
    """

    symbol: str
    name: str
    binance_pair: str | None = None
    aliases: tuple[str, ...] = ()
    origin: CoinOrigin = CoinOrigin.BUILT_IN

    def __post_init__(self) -> None:
        if not is_symbol(self.symbol):
            raise ValueError(f"not a ledger coin symbol: {self.symbol!r}")
        if not self.name or text_length(self.name) > COIN_NAME_MAX_LENGTH:
            raise ValueError(f"{self.symbol}: the ledger would refuse the name {self.name!r}")
        pair = self.binance_pair
        if pair is not None and not _is_market_pair(pair):
            raise ValueError(f"{self.symbol}: the ledger would refuse the market pair {pair!r}")

    def spoken_keys(self) -> frozenset[str]:
        """Every lookup form of this coin: its symbol, its name and its aliases."""
        return frozenset(spoken_key(form) for form in (self.symbol, self.name, *self.aliases))


def _is_market_pair(pair: str) -> bool:
    return bool(pair) and trim(pair) == pair and text_length(pair) <= MARKET_PAIR_MAX_LENGTH


# Words that all mean USDT, in lookup form. None of them may also name a coin.
USDT_WORDS = frozenset(
    {
        QUOTE_CURRENCY,
        "U",
        "USD",
        "$",
        "DOLLAR",
        "DOLLARS",
        "TETHER",
        "刀",
        "美刀",
        "美元",
        "美金",
        "泰达币",
    }
)


def means_usdt(spoken: str) -> bool:
    """Whether ``spoken`` is one of the words for USDT."""
    return spoken_key(spoken) in USDT_WORDS


@dataclass(frozen=True)
class CoinTable:
    """A set of coins that can be looked up by anything they are called.

    A table never changes. Confirming a coin gives back a new table.
    """

    coins: tuple[Coin, ...]
    _by_key: Mapping[str, Coin] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        by_key: dict[str, Coin] = {}
        for coin in self.coins:
            for key in sorted(coin.spoken_keys()):
                if key in USDT_WORDS:
                    raise ValueError(f"{coin.symbol}: {key!r} means USDT and cannot name a coin")
                if key in by_key:
                    other = by_key[key].symbol
                    raise ValueError(f"{key!r} is claimed by both {other} and {coin.symbol}")
                by_key[key] = coin
        object.__setattr__(self, "_by_key", by_key)

    def find(self, spoken: str) -> Coin | None:
        """The coin that ``spoken`` names, or ``None`` when the table does not know it."""
        return self._by_key.get(spoken_key(spoken))

    def with_confirmed(self, spoken: str) -> CoinTable:
        """A table that also knows the coin the user confirmed.

        A coin the table already knows changes nothing. Text that could never
        be a ledger symbol is a mistake by the caller, because such a coin is
        refused outright instead of being offered for confirmation.
        """
        if self.find(spoken) is not None:
            return self
        symbol = spoken_key(spoken)
        if not is_symbol(symbol) or symbol in USDT_WORDS:
            raise ValueError(f"{spoken!r} cannot be a coin symbol")
        confirmed = Coin(symbol=symbol, name=symbol, origin=CoinOrigin.USER_CONFIRMED)
        return CoinTable((*self.coins, confirmed))


def _listed(symbol: str, name: str, *aliases: str) -> Coin:
    """A built-in coin whose Binance market is its symbol quoted in USDT."""
    return Coin(symbol, name, f"{symbol}{QUOTE_CURRENCY}", aliases)


def _unlisted(symbol: str, name: str, *aliases: str) -> Coin:
    """A built-in coin with no Binance market that is known for certain."""
    return Coin(symbol, name, None, aliases)


BUILT_IN_COINS: tuple[Coin, ...] = (
    _listed("BTC", "Bitcoin", "比特币", "大饼", "XBT"),
    _listed("ETH", "Ethereum", "Ether", "以太坊", "以太币", "以太", "二饼", "姨太"),
    _listed("BNB", "BNB", "币安币"),
    _listed("SOL", "Solana", "索拉纳"),
    _listed("XRP", "XRP", "Ripple", "瑞波币", "瑞波"),
    _listed("DOGE", "Dogecoin", "狗狗币"),
    _listed("ADA", "Cardano", "艾达币"),
    _listed("TRX", "TRON", "波场", "波场币"),
    _listed("AVAX", "Avalanche"),
    _listed("LINK", "Chainlink"),
    _listed("DOT", "Polkadot", "波卡"),
    _listed("LTC", "Litecoin", "莱特币"),
    _listed("BCH", "Bitcoin Cash", "比特币现金", "比特现金"),
    _listed("SHIB", "Shiba Inu", "Shiba", "柴犬币"),
    _listed("UNI", "Uniswap"),
    _listed("ATOM", "Cosmos"),
    _listed("XLM", "Stellar", "恒星币"),
    _listed("ETC", "Ethereum Classic", "以太经典"),
    _listed("NEAR", "NEAR Protocol"),
    _listed("APT", "Aptos"),
    _listed("ARB", "Arbitrum"),
    _listed("OP", "Optimism"),
    _listed("SUI", "Sui"),
    _listed("TON", "Toncoin"),
    _listed("FIL", "Filecoin"),
    _listed("AAVE", "Aave"),
    _listed("PEPE", "Pepe"),
    _listed("POL", "Polygon"),
    _listed("USDC", "USD Coin"),
    _unlisted("XMR", "Monero", "门罗币", "门罗"),
    _unlisted("OKB", "OKB"),
)

BUILT_IN_TABLE = CoinTable(BUILT_IN_COINS)
