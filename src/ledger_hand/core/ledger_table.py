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
  words of ``MONEY_WORDS`` that point to its code;
- the vague words for money (``VAGUE_MONEY_WORDS``) name no one money:
  the table reads each as vague, whatever money the ledger has;
- a word of ``MONEY_WORDS`` whose money the ledger lacks is kept apart,
  with that money's code, so that the trade is told as one in a money
  the ledger does not have yet;
- every word of the two lists is handed to the number reader as a unit
  it may read ("60000欧元", "30 bucks");
- the assets traded: every other asset, by its names as above;
- an asset the ledger lacks cannot be recorded: the user adds it there
  first (``UnknownAssets.REFUSE``);
- with a stock in the ledger, "股", "share" and "shares" may stand after a
  number as its unit;
- each asset traded keeps its kind ("stock", "crypto"), so that the words
  said to the user call a share a share and a coin a coin.

An asset that cannot go into the table is left out of it, and the rest are
kept: a code that cannot be written as a ledger symbol (such as "BRK.B"),
and an asset one of whose names is also a word for money (a stock whose code
is "U"). Such an asset cannot be recorded by the assistant.

The ledger lets a coin and a stock share one code. Neither of two such
assets goes into the table, so that none is picked for the user; which
two they are is kept (``same_codes``, ``SameCode``), and whatever said
names that code is neither recorded nor looked up: the program names both
and asks nothing of the ledger. (68B2, part 10, 2026-11-25.)

``table_of`` gives ``None`` when the ledger prices trades in no money at
all: nothing could be recorded then.

This module reads no clock and asks nothing of the ledger: the list is
handed in.

Names defined here: ``MONEY_WORDS``, ``VAGUE_MONEY_WORDS``,
``VAGUE_MONEY_CODES``, ``SHARE_UNITS``, ``AssetNames``,
``SameCode``, ``same_codes``, ``same_code_words``, ``names_of`` and
``table_of``.
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

# The words that name exactly one money, each with that money's code. A
# word names its money only when the ledger's list has it; otherwise it is
# a word for a money the ledger lacks, and a trade priced in it is not sent.
# To take another word, add a line. (Settled on 2026-11-25.)
MONEY_WORDS: tuple[tuple[str, str], ...] = (
    # Traders write "U" for USDT ("100U").
    ("U", _USDT),
    ("USDT", _USDT),
    # The name of the company behind USDT, in English and in Chinese.
    ("Tether", _USDT),
    ("泰达币", _USDT),
    # "dollar(s)" and "美元" name the US dollar itself, never USDT.
    ("USD", _USD),
    ("dollar", _USD),
    ("dollars", _USD),
    ("美元", _USD),
    # The euro. "欧" is how the product owner says it ("0.46 欧"); it is a
    # word of its own, so a platform such as "欧易" never reads as a euro.
    ("EUR", "EUR"),
    ("euro", "EUR"),
    ("euros", "EUR"),
    ("€", "EUR"),
    ("欧元", "EUR"),
    ("欧", "EUR"),
    # The Chinese yuan. "块", "元" and "¥" are left out: each is also said
    # of other moneys (the US dollar, the Hong Kong dollar, the yen).
    ("CNY", "CNY"),
    ("RMB", "CNY"),
    ("人民币", "CNY"),
    # The Hungarian forint, since the product owner lives in Hungary.
    ("HUF", "HUF"),
    ("forint", "HUF"),
    ("forints", "HUF"),
    ("福林", "HUF"),
)

# The vague words for money: each may mean USDT or the US dollar, and is
# never read as either by itself. Which is meant follows the money the same
# trade names outright, then the money of the asset's last trade in the
# ledger (marked as a guess); otherwise the user is asked.
# (The product owner's rule of 2026-11-25.)
VAGUE_MONEY_WORDS: tuple[str, ...] = (
    # Named as vague in the product owner's rule.
    "美金",
    # Spoken Chinese uses "刀" and "美刀" for the dollar and for USDT alike.
    "刀",
    "美刀",
    # Traders write "$" for USDT as often as for the dollar.
    "$",
    # Spoken English, as vague as "刀".
    "buck",
    "bucks",
)

# The two moneys a vague word may mean.
VAGUE_MONEY_CODES = frozenset({_USDT, _USD})

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


@dataclass(frozen=True)
class SameCode:
    """Two or more assets of the ledger that share one code, in the ledger's order."""

    code: str
    assets: tuple[Asset, ...]


def same_codes(assets: Sequence[Asset]) -> tuple[SameCode, ...]:
    """Every code more than one of ``assets`` goes by, with those assets; in code order."""
    by_code: dict[str, list[Asset]] = {}
    for asset in assets:
        by_code.setdefault(asset.code, []).append(asset)
    return tuple(
        SameCode(code=code, assets=tuple(found))
        for code, found in sorted(by_code.items())
        if len(found) > 1
    )


def same_code_words(same: SameCode) -> str:
    """The program's words for a code two assets share: both named, and nothing picked."""
    named = " and ".join(f"{asset.name} ({asset.kind.value})" for asset in same.assets)
    return (
        f"The ledger has more than one asset with the code {same.code}: {named}. "
        "I cannot tell which one you mean, so I did nothing with it. Please tell them "
        "apart in the ledger itself."
    )


def table_of(assets: Sequence[Asset]) -> AssetTable | None:
    """The asset table the ledger's ``assets`` make; ``None`` when none of them prices trades."""
    names = names_of(assets)
    moneys = _moneys(assets)
    if not any(money.use is MoneyUse.CAN_PRICE for money in moneys):
        return None
    vague = frozenset(spoken_key(word) for word in VAGUE_MONEY_WORDS)
    absent = _absent(moneys)
    taken = {key for money in moneys for key in money.spoken_keys()} | set(USDT_WORDS)
    taken |= vague | {key for key, _ in absent}
    shared = {same.code for same in same_codes(assets)}
    coins: list[Coin] = []
    for asset in assets:
        if _is_money(asset) or asset.code in shared:
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
        kinds=tuple((coin.symbol, _kind(coin.symbol, assets)) for coin in coins),
        vague_words=vague,
        absent_moneys=absent,
        money_units=(*(word for word, _ in MONEY_WORDS), *VAGUE_MONEY_WORDS),
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
        nicknames = tuple(word for word, named in MONEY_WORDS if named == code)
        use = MoneyUse.CAN_PRICE if asset.pricing is Pricing.CAN_PRICE else MoneyUse.CANNOT_PRICE
        moneys.append(Money(code, (asset.name, *nicknames), use))
    return tuple(moneys)


def _absent(moneys: Sequence[Money]) -> tuple[tuple[str, str], ...]:
    """Each word of ``MONEY_WORDS`` whose money is not among ``moneys``, in lookup form."""
    had = {money.code for money in moneys}
    return tuple((spoken_key(word), code) for word, code in MONEY_WORDS if code not in had)


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


def _kind(code: str, assets: Sequence[Asset]) -> str:
    """The kind of the asset ``code`` names: its own kind's word; one code names one asset here."""
    return next(asset.kind.value for asset in assets if asset.code == code)


def _codes(coins: Sequence[Coin]) -> frozenset[str]:
    return frozenset(coin.symbol for coin in coins)
