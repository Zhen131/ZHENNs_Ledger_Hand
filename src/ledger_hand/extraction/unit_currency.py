"""Which currency a word names, and which currencies a unit word names.

The number reader hands back the unit that stood with a number exactly as
it was written ("刀", "BTC", "个 ETH", "个比特币"), and only when every part
of it is a word it knows: a word for USDT, a coin of the coin table, a
counter such as "个", or a word the caller allowed for that one call. This
module tells which of those parts name a currency, and which currency.

What a word names is its ``identity``:

- ``USDT`` for every word for USDT ("U", "刀", "美元");
- the coin's symbol for a name in the coin table ("比特币" and "BTC" are both
  ``BTC``);
- for a word allowed for this one call (the trade's own coin or fee coin,
  when the table does not know it), the word itself in lookup form.

Two words name the same currency when their identities are equal.

A unit is first looked up as a whole ("Bitcoin Cash"). Otherwise it is cut
at its gaps, and each word wherever Chinese characters meet anything else;
a run of other characters is one word, and a run of Chinese characters,
which is written without gaps, is searched from left to right for the
longest name at each place ("个比特币" holds 比特币). Counters and anything
else that names no currency are passed over. Each currency is listed once.

Names defined here: ``CurrencyWord``, ``identity_of``, ``word_identity``
and ``currencies_in_unit``.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterable
from dataclasses import dataclass

from ledger_hand.core.coins import CoinTable, means_usdt, spoken_key
from ledger_hand.core.ledger_limits import QUOTE_CURRENCY

# The block Unicode calls "CJK Unified Ideographs", the same one the number
# reader cuts at.
_FIRST_CHINESE_CHARACTER = "一"
_LAST_CHINESE_CHARACTER = "鿿"


@dataclass(frozen=True)
class CurrencyWord:
    """A word in a unit that names a currency: as written, and what it names."""

    text: str
    identity: str


def identity_of(word: str, coins: CoinTable, allowed: Iterable[str] = ()) -> str | None:
    """What ``word`` names, or ``None`` when it names no currency this program knows."""
    return _identity(word, coins, frozenset(spoken_key(other) for other in allowed))


def _identity(word: str, coins: CoinTable, allowed_keys: frozenset[str]) -> str | None:
    if means_usdt(word):
        return QUOTE_CURRENCY
    coin = coins.find(word)
    if coin is not None:
        return coin.symbol
    key = spoken_key(word)
    return key if key and key in allowed_keys else None


def word_identity(word: str, coins: CoinTable) -> str:
    """What a word the user wrote for a coin or currency names; itself when nothing else."""
    return identity_of(word, coins) or spoken_key(word)


def currencies_in_unit(
    unit: str, coins: CoinTable, allowed: Iterable[str] = ()
) -> tuple[CurrencyWord, ...]:
    """The currencies ``unit`` names, each once, in the order written."""
    allowed_keys = frozenset(spoken_key(other) for other in allowed)
    whole = _identity(unit.strip(), coins, allowed_keys)
    if whole is not None:
        return (CurrencyWord(unit.strip(), whole),)
    found: dict[str, CurrencyWord] = {}
    for word in unit.split():
        for is_chinese, run in itertools.groupby(word, key=_is_chinese):
            text = "".join(run)
            named = _names_in_chinese(text, coins, allowed_keys) if is_chinese else [text]
            for name in named:
                identity = _identity(name, coins, allowed_keys)
                if identity is not None and identity not in found:
                    found[identity] = CurrencyWord(name, identity)
    return tuple(found.values())


def _names_in_chinese(run: str, coins: CoinTable, allowed_keys: frozenset[str]) -> list[str]:
    """The names in a run of Chinese characters, the longest at each place, left to right.

    The run comes from a unit the number reader accepted, which is a few
    dozen characters at most, so trying every stretch costs little.
    """
    names: list[str] = []
    start = 0
    while start < len(run):
        for end in range(len(run), start, -1):
            if _identity(run[start:end], coins, allowed_keys) is not None:
                names.append(run[start:end])
                start = end
                break
        else:
            start += 1
    return names


def _is_chinese(character: str) -> bool:
    return _FIRST_CHINESE_CHARACTER <= character <= _LAST_CHINESE_CHARACTER
