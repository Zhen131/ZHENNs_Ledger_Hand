"""The asset table made from the ledger's own list of assets, and the names of its assets.

The assistant records into the ledger, so what may be traded and which money
a trade may be priced in come from the ledger's list (``list_assets``), not
from the coin table built into this program. ``table_of`` makes an
``AssetTable`` of that list; ``names_of`` gives every name an asset of the
list goes by, for finding the assets a question names. Both are worked out
here, once, so that recording, asking and changing a trade recognise an
asset the same way.

The names (``AssetNames``):

- an asset goes by its code and its name, letter case aside;
- a coin of the built-in coin table lends its other names ("比特币",
  "大饼" for BTC) only to an asset of the ledger with the same code: with no
  BTC in the ledger, "比特币" names nothing;
- the built-in names of the coins the ledger lacks are kept apart, to cover
  only (``shields``): a longer name such as "比特币现金" still hides the
  shorter "比特币" inside it, and recording says such a coin is not in the
  ledger instead of asking which coin was meant.

The table (``table_of``):

- the money: every asset of the kind "cash", and every asset the ledger
  prices trades in; those the ledger prices trades in are the money a
  trade may be priced in. Each goes by its code, its name and the
  nicknames of ``MONEY_NICKNAMES`` that point to its code;
- the assets traded: every other asset, by its names as above;
- an asset the ledger lacks cannot be recorded: the user adds it there
  first (``UnknownAssets.REFUSE``);
- with a stock in the ledger, "股", "share" and "shares" may stand after a
  number as its unit.

An asset that cannot go into the table is left out of it, and the rest are
kept: a code that cannot be written as a ledger symbol (such as "BRK.B"),
and an asset one of whose names is also a word for money (a stock whose code
is "U"). Such an asset cannot be recorded by the assistant.

``table_of`` gives ``None`` when the ledger prices trades in no money at
all: nothing could be recorded then.

This module reads no clock and asks nothing of the ledger: the list is
handed in.

Names defined here: ``MONEY_NICKNAMES``, ``SHARE_UNITS``, ``AssetNames``,
``names_of`` and ``table_of``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from ledger_hand.core.assets import AssetTable, Money, MoneyUse, UnknownAssets
from ledger_hand.core.coins import BUILT_IN_COINS, USDT_WORDS, Coin, CoinTable, spoken_key
from ledger_hand.core.ledger_limits import is_symbol
from ledger_hand.core.ledger_records import Asset, AssetKind, Pricing

_USDT = "USDT"
_USD = "USD"

# What people call a money, and the code of each money it may mean. A word
# names a money only when that money is in the ledger; one that may mean
# both USDT and USD names both, and is asked about when both price trades.
# (Settled for now on 2026-11-24, until the product owner agrees.)
MONEY_NICKNAMES: tuple[tuple[str, frozenset[str]], ...] = (
    # Traders write "U" for USDT ("100U").
    ("U", frozenset({_USDT})),
    ("USDT", frozenset({_USDT})),
    # The name of the company behind USDT, in English and in Chinese.
    ("Tether", frozenset({_USDT})),
    ("泰达币", frozenset({_USDT})),
    ("USD", frozenset({_USD})),
    ("$", frozenset({_USD})),
    ("dollar", frozenset({_USD})),
    ("dollars", frozenset({_USD})),
    # "美元" and "美金" are the US dollar itself; never taken for USDT.
    ("美元", frozenset({_USD})),
    ("美金", frozenset({_USD})),
    # Spoken Chinese uses "刀" and "美刀" for the dollar and for USDT alike.
    ("刀", frozenset({_USDT, _USD})),
    ("美刀", frozenset({_USDT, _USD})),
)

# The words that may stand after a number of shares, read with a stock in the ledger.
SHARE_UNITS = ("股", "share", "shares")


@dataclass(frozen=True)
class AssetNames:
    """Every name of the built-in coins and of the ledger's assets, each to its code.

    ``built_in`` holds each built-in coin's symbol, name and other names,
    in the coin table's order; ``ledger`` each asset's code and name, in the
    ledger's order; ``codes`` the ledger's codes.
    """

    built_in: tuple[tuple[str, str], ...]
    ledger: tuple[tuple[str, str], ...]
    codes: frozenset[str]

    def sayings(self) -> tuple[tuple[str, str], ...]:
        """The names the ledger's assets go by: the built-in ones for its codes, then its own."""
        lent = tuple(pair for pair in self.built_in if pair[1] in self.codes)
        return (*lent, *self.ledger)

    def shields(self) -> tuple[tuple[str, str], ...]:
        """The built-in names of the coins the ledger lacks: to cover with, never an asset."""
        return tuple(pair for pair in self.built_in if pair[1] not in self.codes)

    def in_lookup_order(self) -> tuple[tuple[str, str], ...]:
        """Every name: the built-in ones in the coin table's order, then the ledger's own.

        A later pair wins where two claim one name, so the ledger's own
        names win over the coin table's.
        """
        return (*self.built_in, *self.ledger)


def names_of(assets: Sequence[Asset]) -> AssetNames:
    """The names of the built-in coins and of the ``assets`` the ledger listed."""
    built_in = tuple(
        (form, coin.symbol)
        for coin in BUILT_IN_COINS
        for form in (coin.symbol, coin.name, *coin.aliases)
    )
    ledger = tuple(
        pair for asset in assets for pair in ((asset.code, asset.code), (asset.name, asset.code))
    )
    return AssetNames(built_in, ledger, frozenset(asset.code for asset in assets))


def table_of(assets: Sequence[Asset]) -> AssetTable | None:
    """The asset table the ledger's ``assets`` make; ``None`` when none of them prices trades."""
    names = names_of(assets)
    moneys = _moneys(assets)
    if not any(money.use is MoneyUse.CAN_PRICE for money in moneys):
        return None
    taken = {key for money in moneys for key in money.spoken_keys()} | set(USDT_WORDS)
    coins: list[Coin] = []
    for asset in assets:
        if _is_money(asset):
            continue
        coin = _coin(asset, names)
        if coin is None or coin.spoken_keys() & taken:
            continue
        coins.append(coin)
        taken |= coin.spoken_keys()
    shields = frozenset(spoken_key(form) for form, _ in names.shields()) - taken
    stocks = any(asset.kind is AssetKind.STOCK and asset.code in _codes(coins) for asset in assets)
    return AssetTable(
        coins=CoinTable(tuple(coins)),
        moneys=moneys,
        unknown=UnknownAssets.REFUSE,
        extra_units=SHARE_UNITS if stocks else (),
        from_ledger=True,
        shields=shields,
    )


def _is_money(asset: Asset) -> bool:
    return asset.kind is AssetKind.CASH or asset.pricing is Pricing.CAN_PRICE


def _moneys(assets: Sequence[Asset]) -> tuple[Money, ...]:
    moneys: list[Money] = []
    for asset in assets:
        code = asset.code
        if not _is_money(asset) or not code or spoken_key(code) != code:
            continue
        if any(money.code == code for money in moneys):
            continue
        nicknames = tuple(word for word, codes in MONEY_NICKNAMES if code in codes)
        use = MoneyUse.CAN_PRICE if asset.pricing is Pricing.CAN_PRICE else MoneyUse.CANNOT_PRICE
        moneys.append(Money(code, (asset.name, *nicknames), use))
    return tuple(moneys)


def _coin(asset: Asset, names: AssetNames) -> Coin | None:
    """The asset as a coin of the table, or ``None`` when its code or name cannot be one."""
    lent = tuple(form for form, code in names.built_in if code == asset.code)
    aliases = tuple(dict.fromkeys(form for form in lent if form not in (asset.code, asset.name)))
    if not is_symbol(asset.code):
        return None
    try:
        return Coin(symbol=asset.code, name=asset.name, aliases=aliases)
    except ValueError:
        return None


def _codes(coins: Sequence[Coin]) -> frozenset[str]:
    return frozenset(coin.symbol for coin in coins)
