"""A storage port kept in memory, for tests: the stand-in for the SQLite book.

``MemoryStore`` does what the port promises, the way the SQLite plug does
it: a save is whole or not at all, an identifier already saved is a
conflict, a marking is whole or not at all, a coin keeps the moment it was
first confirmed, and moments come back in UTC. It passes the same tests of
the port as the real plug (``tests/storage/test_storage_port.py``).

A test can make the next call of one operation fail with a ``StorageError``
of its choosing (``fail_next``), and can see every operation called, in
order (``calls``).
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ledger_hand.core.book import (
    ConfirmedCoin,
    EarlierSave,
    ExportMark,
    ListedTrade,
    Listing,
    PassageSave,
)
from ledger_hand.core.stored import StoredTrade
from ledger_hand.ports import StorageError, StorageErrorKind


def in_utc(moment: datetime) -> datetime:
    return moment.astimezone(timezone.utc)


def trade_in_utc(trade: StoredTrade) -> StoredTrade:
    return dataclasses.replace(
        trade, created_at=in_utc(trade.created_at), updated_at=in_utc(trade.updated_at)
    )


@dataclass
class MemoryStore:
    """Saved trades, passages and confirmed coins, held in lists for the length of a test."""

    listed: list[ListedTrade] = field(default_factory=list)
    passages: list[tuple[str, datetime, int]] = field(default_factory=list)
    coins: dict[str, ConfirmedCoin] = field(default_factory=dict)
    calls: list[str] = field(default_factory=list)
    failures: dict[str, StorageError] = field(default_factory=dict)

    def fail_next(self, operation: str, kind: StorageErrorKind = StorageErrorKind.LOCKED) -> None:
        """Make the next call of ``operation`` (a method's name) raise a ``StorageError``."""
        self.failures[operation] = StorageError(kind, f"{operation} was made to fail")

    def _called(self, operation: str) -> None:
        self.calls.append(operation)
        failure = self.failures.pop(operation, None)
        if failure is not None:
            raise failure

    def save(self, passage: PassageSave) -> tuple[StoredTrade, ...]:
        self._called("save")
        held = {listed.trade.id for listed in self.listed}
        taken = sorted(trade.id for trade in passage.trades if trade.id in held)
        if taken:
            raise StorageError(StorageErrorKind.CONFLICT, f"already saved: {', '.join(taken)}")
        saved = tuple(trade_in_utc(trade) for trade in passage.trades)
        self.listed.extend(ListedTrade(trade=trade) for trade in saved)
        self.passages.append((passage.fingerprint, in_utc(passage.saved_at), len(saved)))
        for coin in passage.coins:
            if coin.symbol not in self.coins:
                self.coins[coin.symbol] = dataclasses.replace(
                    coin, confirmed_at=in_utc(coin.confirmed_at)
                )
        return saved

    def earlier_saves(self, fingerprint: str) -> tuple[EarlierSave, ...]:
        self._called("earlier_saves")
        return tuple(
            EarlierSave(saved_at=saved_at, trades=count)
            for kept, saved_at, count in self.passages
            if kept == fingerprint
        )

    def trades(self, listing: Listing) -> tuple[ListedTrade, ...]:
        self._called("trades")
        if listing is Listing.NOT_EXPORTED:
            return tuple(listed for listed in self.listed if listed.exported_at is None)
        return tuple(self.listed)

    def mark_exported(self, mark: ExportMark) -> None:
        self._called("mark_exported")
        places = {listed.trade.id: place for place, listed in enumerate(self.listed)}
        for identifier in mark.identifiers:
            place = places.get(identifier)
            if place is None or self.listed[place].exported_at is not None:
                raise StorageError(
                    StorageErrorKind.CONFLICT,
                    f"{identifier} is not in the book, or was exported already",
                )
        for identifier in mark.identifiers:
            place = places[identifier]
            self.listed[place] = dataclasses.replace(
                self.listed[place], exported_at=in_utc(mark.exported_at)
            )

    def confirmed_coins(self) -> tuple[ConfirmedCoin, ...]:
        self._called("confirmed_coins")
        return tuple(self.coins[symbol] for symbol in sorted(self.coins))
