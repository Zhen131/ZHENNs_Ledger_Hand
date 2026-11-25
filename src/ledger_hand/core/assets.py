"""The asset table: what may be traded, which money a trade may be priced in, and what else.

Recording a trade keeps asking four things, and every one of them is asked
of the asset table handed in, never of a fixed list:

- which asset a word names ("比特币", "BTC", "msft"), or none;
- which money a word names ("U", "美元", "$", "刀"), in one of four ways:
  exactly one money the table prices trades in; more than one such money,
  so it is not clear which; money, but not one the table prices trades in;
  or not money at all;
- what becomes of an asset the table does not know: the user may confirm
  it on the spot, or it cannot be recorded (``UnknownAssets``);
- which more words may stand after a number as its unit ("股", "shares"),
  beside the counters the number reader knows. These words go to the number
  reader only; they are never money, so "2 股" is never read as a currency.

``BUILT_IN_ASSETS`` is the table every caller hands in today. It is made
from the built-in coin table and the words for USDT in ``coins``, unchanged:
USDT is the one money it prices in, every word for USDT (USD, "$", "刀",
"美元" and the rest among them) names it, an unseen coin may be confirmed,
and no more unit words are read. With it every part of the program behaves
exactly as it did when USDT was written into each of them.

This module holds data and lookup only. Whether a draft's asset and money
are acceptable is decided in ``validation``.

Names defined here: ``AssetTable``, ``Money``, ``MoneyUse``,
``MoneyReading``, ``MoneyFound``, ``UnknownAssets`` and
``BUILT_IN_ASSETS``.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, replace

from ledger_hand.core.coins import BUILT_IN_TABLE, USDT_WORDS, Coin, CoinTable, spoken_key
from ledger_hand.core.ledger_limits import QUOTE_CURRENCY


class MoneyUse(enum.Enum):
    """Whether a trade may be priced in a money of the table."""

    CAN_PRICE = "trades may be priced in it"
    CANNOT_PRICE = "it is money, but no trade may be priced in it"


class MoneyReading(enum.Enum):
    """What a word is, as money, to one asset table."""

    ONE = "exactly one money the table prices trades in"
    SEVERAL = "more than one money the table prices trades in"
    CANNOT_PRICE = "money the table does not price trades in"
    NOT_MONEY = "not money"


class UnknownAssets(enum.Enum):
    """What becomes of an asset the table does not know."""

    CONFIRM_ON_THE_SPOT = "the user may confirm it as a new asset"
    REFUSE = "the trade cannot be recorded; the asset is added in the ledger first"


@dataclass(frozen=True)
class Money:
    """One money: its code, the words people use for it, and whether trades are priced in it.

    The code is itself one of the words for the money.
    """

    code: str
    words: tuple[str, ...]
    use: MoneyUse

    def __post_init__(self) -> None:
        if not self.code or spoken_key(self.code) != self.code:
            raise ValueError(f"a money code is written in capitals, trimmed: {self.code!r}")

    def spoken_keys(self) -> frozenset[str]:
        """Every lookup form of this money: its code and its words."""
        return frozenset(spoken_key(word) for word in (self.code, *self.words))


@dataclass(frozen=True)
class MoneyFound:
    """What a word is as money, and the code it names when that is one money.

    ``code`` is there for ``ONE``, and for ``CANNOT_PRICE`` when the word
    names exactly one such money; otherwise it is ``None``.
    """

    reading: MoneyReading
    code: str | None = None


@dataclass(frozen=True, kw_only=True)
class AssetTable:
    """The assets that may be traded, the money they may be priced in, and two rules.

    ``coins`` are the assets. ``moneys`` hold at least one money the table
    prices trades in. ``unknown`` says what becomes of an asset ``coins``
    does not know. ``extra_units`` are the words the number reader may also
    take as a number's unit. No word may name both an asset and a money, and
    no extra unit word may be a word for money. A table never changes;
    confirming an asset gives back a new one.

    ``from_ledger`` marks a table made from the ledger's own list
    (``ledger_table``); such a table never speaks the older words that name
    USDT. ``shields`` are the names, in lookup form, of coins the table
    lacks but the built-in coin table knows: such a name is never an asset,
    and recording says the asset is not in the ledger. ``kinds`` gives the
    kind of each asset of a table made from the ledger's list, by its code
    ("stock", "crypto"), so that a question calls a share a share; the
    built-in table holds none.

    A table whose unknown assets may be confirmed on the spot holds no
    money that trades cannot be priced in: confirming such money as a new
    asset could never be done, so the table is refused when it is made.
    """

    coins: CoinTable
    moneys: tuple[Money, ...]
    unknown: UnknownAssets
    extra_units: tuple[str, ...]
    from_ledger: bool = False
    shields: frozenset[str] = frozenset()
    kinds: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not self.pricing_codes:
            raise ValueError("an asset table prices trades in at least one money")
        if self.unknown is UnknownAssets.CONFIRM_ON_THE_SPOT and any(
            money.use is MoneyUse.CANNOT_PRICE for money in self.moneys
        ):
            raise ValueError(
                "a table whose unknown assets may be confirmed holds no money it cannot price in:"
                " such money, said as the asset traded, could never be confirmed"
            )
        codes = [money.code for money in self.moneys]
        if len(set(codes)) != len(codes):
            raise ValueError(f"a money code is used twice: {codes}")
        money_keys = {key for money in self.moneys for key in money.spoken_keys()}
        for key in sorted(money_keys):
            if self.coins.find(key) is not None:
                raise ValueError(f"{key!r} names both an asset and a money")
        for word in self.extra_units:
            if spoken_key(word) in money_keys:
                raise ValueError(f"the unit word {word!r} is a word for money")

    @property
    def pricing_codes(self) -> tuple[str, ...]:
        """The codes of the money trades may be priced in, in the table's order."""
        return tuple(money.code for money in self.moneys if money.use is MoneyUse.CAN_PRICE)

    @property
    def sole_pricing_code(self) -> str | None:
        """The one money trades are priced in, when there is exactly one; else ``None``."""
        codes = self.pricing_codes
        return codes[0] if len(codes) == 1 else None

    def prices_only_in_usdt(self) -> bool:
        """Whether USDT is the one money this table prices trades in.

        The older reasons a trade cannot be recorded name USDT in their own
        words, so they are said only for such a table, and only when it is
        not made from the ledger's list (``speaks_of_usdt_only``); another
        table is given the reasons that name no money.
        """
        return self.pricing_codes == (QUOTE_CURRENCY,)

    def speaks_of_usdt_only(self) -> bool:
        """Whether the older words that name USDT are said: USDT prices alone, as built in.

        A table made from the ledger's list says the words that name no
        money, even when USDT is the one money it prices in.
        """
        return self.prices_only_in_usdt() and not self.from_ledger

    def is_shielded(self, spoken: str) -> bool:
        """Whether ``spoken`` names a coin the built-in table knows and this table lacks."""
        return spoken_key(spoken) in self.shields

    def kind_of(self, code: str) -> str | None:
        """The kind of the asset ``code`` names in the ledger ("stock", "crypto"), if known."""
        return next((kind for known, kind in self.kinds if known == code), None)

    def find(self, spoken: str) -> Coin | None:
        """The asset ``spoken`` names, or ``None`` when the table does not know it."""
        return self.coins.find(spoken)

    def money(self, spoken: str) -> MoneyFound:
        """What ``spoken`` is as money to this table."""
        key = spoken_key(spoken)
        if not key:
            return MoneyFound(MoneyReading.NOT_MONEY)
        named = [money for money in self.moneys if key in money.spoken_keys()]
        pricing = [money.code for money in named if money.use is MoneyUse.CAN_PRICE]
        if len(pricing) == 1:
            return MoneyFound(MoneyReading.ONE, pricing[0])
        if pricing:
            return MoneyFound(MoneyReading.SEVERAL)
        if named:
            code = named[0].code if len(named) == 1 else None
            return MoneyFound(MoneyReading.CANNOT_PRICE, code)
        return MoneyFound(MoneyReading.NOT_MONEY)

    def with_confirmed(self, spoken: str) -> AssetTable:
        """A table that also knows the asset the user confirmed.

        Only a table whose unknown assets may be confirmed on the spot takes
        one; asking another, or confirming a word for money, is a mistake of
        the caller and raises ``ValueError``.
        """
        if self.unknown is not UnknownAssets.CONFIRM_ON_THE_SPOT:
            raise ValueError("this table does not take assets confirmed on the spot")
        if self.money(spoken).reading is not MoneyReading.NOT_MONEY:
            raise ValueError(f"{spoken!r} is a word for money, never an asset")
        coins = self.coins.with_confirmed(spoken)
        return self if coins is self.coins else replace(self, coins=coins)


BUILT_IN_ASSETS = AssetTable(
    coins=BUILT_IN_TABLE,
    moneys=(Money(QUOTE_CURRENCY, tuple(sorted(USDT_WORDS)), MoneyUse.CAN_PRICE),),
    unknown=UnknownAssets.CONFIRM_ON_THE_SPOT,
    extra_units=(),
)
