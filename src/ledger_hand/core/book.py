"""What the local book keeps beside a saved trade, in the shapes the storage port uses.

The book is this program's own small store of saved trades; ``ports`` says
what may be asked of it. Beside each ``StoredTrade`` it keeps when the trade
was exported, if it has been; which passage the trade came from, by that
passage's fingerprint; and the coins the user confirmed. These shapes carry
moments, so they live in the core, where dates and times may be used, and
the ports file only names them.

- ``PassageSave``: the trades recorded from one passage, saved together, with
  the passage's fingerprint, the moment of saving and the coins the user
  confirmed for them.
- ``EarlierSave``: one earlier save of a passage with the same fingerprint:
  when, and how many trades.
- ``ListedTrade``: a saved trade and the moment it was exported, if it was.
- ``ExportMark``: the trades one export wrote, and the moment of that export.
- ``ConfirmedCoin``: a coin symbol the user confirmed, and when.
- ``Listing``: which saved trades to list.

Every moment must carry an offset and fall within the years UTC can hold. No
moment is read from the clock here, and no identifier or fingerprint is made
here: whoever saves or exports hands them in.

Names defined here: ``Listing``, ``ListedTrade``, ``ConfirmedCoin``,
``PassageSave``, ``EarlierSave`` and ``ExportMark``.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import datetime, timezone

from ledger_hand.core.coins import USDT_WORDS
from ledger_hand.core.ledger_limits import is_symbol
from ledger_hand.core.stored import StoredTrade


class Listing(enum.Enum):
    """Which saved trades to list."""

    ALL = "every saved trade"
    NOT_EXPORTED = "the saved trades that have not been exported yet"


@dataclass(frozen=True, kw_only=True)
class ListedTrade:
    """A saved trade, and the moment it was exported; ``None`` when it has not been."""

    trade: StoredTrade
    exported_at: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.trade, StoredTrade):
            raise TypeError(f"a listed trade holds a StoredTrade, not {type(self.trade).__name__}")
        if self.exported_at is not None:
            _require_moment("exported_at", self.exported_at)

    @property
    def exported(self) -> bool:
        """Whether the trade has been exported."""
        return self.exported_at is not None


@dataclass(frozen=True, kw_only=True)
class ConfirmedCoin:
    """A coin symbol the user confirmed as a coin, and when.

    ``symbol`` is a ledger symbol as the coin table writes a confirmed one:
    capital letters and digits, never a word for USDT.
    """

    symbol: str
    confirmed_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, str) or not is_symbol(self.symbol):
            raise ValueError(f"not a ledger coin symbol: {self.symbol!r}")
        if self.symbol in USDT_WORDS:
            raise ValueError(f"{self.symbol!r} means USDT and is never a coin")
        _require_moment("confirmed_at", self.confirmed_at)


@dataclass(frozen=True, kw_only=True)
class PassageSave:
    """The trades recorded from one passage, to be saved together.

    ``fingerprint`` stands for the passage when it is compared with passages
    saved before; ``saved_at`` is the moment of saving. ``coins`` are the
    coins the user confirmed that these trades use; they are kept only
    together with the trades. A save holds at least one trade, and no two
    trades or coins in it share an identifier or a symbol.
    """

    fingerprint: str
    saved_at: datetime
    trades: tuple[StoredTrade, ...]
    coins: tuple[ConfirmedCoin, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.fingerprint, str) or not self.fingerprint:
            raise ValueError("a passage's fingerprint is text that is not empty")
        _require_moment("saved_at", self.saved_at)
        if not isinstance(self.trades, tuple) or not self.trades:
            raise ValueError("a save holds a tuple of at least one trade")
        if not all(isinstance(trade, StoredTrade) for trade in self.trades):
            raise TypeError("a save holds StoredTrade values only")
        if len({trade.id for trade in self.trades}) != len(self.trades):
            raise ValueError("two trades in one save share an identifier")
        if not isinstance(self.coins, tuple):
            raise TypeError("the confirmed coins of a save are a tuple")
        if not all(isinstance(coin, ConfirmedCoin) for coin in self.coins):
            raise TypeError("the confirmed coins of a save are ConfirmedCoin values")
        if len({coin.symbol for coin in self.coins}) != len(self.coins):
            raise ValueError("a coin is listed twice among the confirmed coins of a save")


@dataclass(frozen=True, kw_only=True)
class EarlierSave:
    """One earlier save of a passage: when it was saved, and how many trades it saved."""

    saved_at: datetime
    trades: int

    def __post_init__(self) -> None:
        _require_moment("saved_at", self.saved_at)
        if isinstance(self.trades, bool) or not isinstance(self.trades, int) or self.trades < 1:
            raise ValueError("an earlier save saved a whole number of trades, at least one")


@dataclass(frozen=True, kw_only=True)
class ExportMark:
    """The trades one export wrote, by their identifiers, and the moment of that export."""

    identifiers: tuple[str, ...]
    exported_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.identifiers, tuple) or not self.identifiers:
            raise ValueError("an export mark names a tuple of at least one trade")
        if not all(isinstance(identifier, str) for identifier in self.identifiers):
            raise TypeError("an export mark names its trades by their identifiers, as text")
        if len(set(self.identifiers)) != len(self.identifiers):
            raise ValueError("an export mark names a trade twice")
        _require_moment("exported_at", self.exported_at)


def _require_moment(name: str, moment: object) -> None:
    """Refuse anything but a datetime with an offset that UTC can hold."""
    if not isinstance(moment, datetime):
        raise TypeError(f"{name} must be a datetime, not {type(moment).__name__}")
    if moment.utcoffset() is None:
        raise ValueError(f"{name} must carry a time zone offset")
    try:
        moment.astimezone(timezone.utc)
    except OverflowError as error:
        raise ValueError(f"{name} falls outside the years UTC can hold") from error
