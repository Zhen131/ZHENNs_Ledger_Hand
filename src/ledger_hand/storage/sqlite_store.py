"""The SQLite plug for the storage port: saved trades kept in one file, the book.

``SqliteStore`` does everything ``ports.StoragePort`` promises. Each
operation opens the book (``book_file.open_book``: checked, and brought up to
the current version), does its work and closes it again, so no connection is
ever shared between threads or kept between operations. A save, and a
marking, run in one transaction each: all of it is kept, or none of it.

Every failure is a ``StorageError`` with the port's kinds; no exception of
``sqlite3`` leaves this module. A row that cannot be read back as what the
book wrote makes the book ``DAMAGED``. A trade that cannot be written at all
(a number or a time the ledger's way of writing cannot hold) is a mistake of
the calling code, since the check of a draft never lets one through, and
raises ``ValueError`` before the book is opened.

Names defined here: ``SqliteStore`` and ``DEFAULT_BUSY_TIMEOUT_SECONDS``.
"""

from __future__ import annotations

import math
import sqlite3
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from decimal import InvalidOperation
from pathlib import Path

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
from ledger_hand.storage.book_file import open_book, roll_back
from ledger_hand.storage.failures import from_sqlite
from ledger_hand.storage.rows import (
    TRADE_COLUMNS,
    moment_from,
    moment_text,
    trade_from,
    trade_values,
)

# How long an operation waits for a book that someone else is using.
DEFAULT_BUSY_TIMEOUT_SECONDS = 5.0

_SELECT_TRADES = f"SELECT {', '.join(TRADE_COLUMNS)}, exported_at FROM trades"
_INSERT_TRADE = (
    f"INSERT INTO trades ({', '.join(TRADE_COLUMNS)}, passage) "
    f"VALUES ({', '.join(':' + column for column in TRADE_COLUMNS)}, :passage)"
)
_EARLIER_SAVES = """SELECT passages.saved_at AS saved_at, count(trades.place) AS trades
FROM passages JOIN trades ON trades.passage = passages.place
WHERE passages.fingerprint = ?
GROUP BY passages.place
ORDER BY passages.place"""
# A coin already in the book keeps the moment it was first confirmed.
_KEEP_COIN = """INSERT INTO confirmed_coins (symbol, confirmed_at) VALUES (?, ?)
ON CONFLICT (symbol) DO NOTHING"""
# The errors a row that cannot be read back raises.
_UNREADABLE = (ValueError, TypeError, KeyError, InvalidOperation)


class SqliteStore:
    """Saved trades in the SQLite file at ``path``, made with its folder when it is missing."""

    def __init__(
        self, path: Path, *, busy_timeout_seconds: float = DEFAULT_BUSY_TIMEOUT_SECONDS
    ) -> None:
        if not isinstance(busy_timeout_seconds, int | float) or isinstance(
            busy_timeout_seconds, bool
        ):
            raise TypeError("the wait for a busy book is a number of seconds")
        if not math.isfinite(busy_timeout_seconds) or busy_timeout_seconds < 0:
            raise ValueError("the wait for a busy book is 0 seconds or more")
        self.path = Path(path)
        self.busy_timeout_seconds = float(busy_timeout_seconds)

    def save(self, passage: PassageSave) -> tuple[StoredTrade, ...]:
        rows = [trade_values(trade) for trade in passage.trades]
        coins = [(coin.symbol, moment_text(coin.confirmed_at)) for coin in passage.coins]
        with self._book() as book, _transaction(book):
            place = book.execute(
                "INSERT INTO passages (fingerprint, saved_at) VALUES (?, ?)",
                (passage.fingerprint, moment_text(passage.saved_at)),
            ).lastrowid
            book.executemany(_INSERT_TRADE, [{**row, "passage": place} for row in rows])
            book.executemany(_KEEP_COIN, coins)
            kept = book.execute(f"{_SELECT_TRADES} WHERE passage = ? ORDER BY place", (place,))
            saved = tuple(self._read(_listed, row).trade for row in kept.fetchall())
        return saved

    def earlier_saves(self, fingerprint: str) -> tuple[EarlierSave, ...]:
        with self._book() as book:
            rows = book.execute(_EARLIER_SAVES, (fingerprint,)).fetchall()
        return tuple(self._read(_earlier_save, row) for row in rows)

    def trades(self, listing: Listing) -> tuple[ListedTrade, ...]:
        where = " WHERE exported_at IS NULL" if listing is Listing.NOT_EXPORTED else ""
        with self._book() as book:
            rows = book.execute(f"{_SELECT_TRADES}{where} ORDER BY place").fetchall()
        return tuple(self._read(_listed, row) for row in rows)

    def mark_exported(self, mark: ExportMark) -> None:
        at = moment_text(mark.exported_at)
        with self._book() as book, _transaction(book):
            for identifier in mark.identifiers:
                changed = book.execute(
                    "UPDATE trades SET exported_at = ? WHERE id = ? AND exported_at IS NULL",
                    (at, identifier),
                ).rowcount
                if changed != 1:
                    raise StorageError(
                        StorageErrorKind.CONFLICT,
                        f"{identifier!r} is not in the book, or was exported already; "
                        "nothing was marked",
                    )

    def confirmed_coins(self) -> tuple[ConfirmedCoin, ...]:
        with self._book() as book:
            rows = book.execute(
                "SELECT symbol, confirmed_at FROM confirmed_coins ORDER BY symbol"
            ).fetchall()
        return tuple(self._read(_confirmed_coin, row) for row in rows)

    @contextmanager
    def _book(self) -> Iterator[sqlite3.Connection]:
        """The book, open for one operation, closed afterwards; SQLite's failures as the port's."""
        connection = open_book(self.path, self.busy_timeout_seconds)
        try:
            yield connection
        except sqlite3.Error as error:
            raise from_sqlite(error, self.path) from None
        finally:
            connection.close()

    def _read[T](self, read: Callable[[Mapping[str, object]], T], row: sqlite3.Row) -> T:
        """What ``read`` makes of ``row``; a row it cannot read makes the book damaged."""
        try:
            return read(row)
        except _UNREADABLE as error:
            raise StorageError(
                StorageErrorKind.DAMAGED,
                f"the book is damaged ({self.path}): a row cannot be read back: {error}",
            ) from None


def _listed(row: Mapping[str, object]) -> ListedTrade:
    exported = row["exported_at"]
    return ListedTrade(
        trade=trade_from(row),
        exported_at=None if exported is None else moment_from(exported),
    )


def _earlier_save(row: Mapping[str, object]) -> EarlierSave:
    count = row["trades"]
    if not isinstance(count, int):
        raise TypeError(f"a count is not a whole number: {count!r}")
    return EarlierSave(saved_at=moment_from(row["saved_at"]), trades=count)


def _confirmed_coin(row: Mapping[str, object]) -> ConfirmedCoin:
    symbol = row["symbol"]
    if not isinstance(symbol, str):
        raise TypeError(f"a symbol is not text: {symbol!r}")
    return ConfirmedCoin(symbol=symbol, confirmed_at=moment_from(row["confirmed_at"]))


@contextmanager
def _transaction(connection: sqlite3.Connection) -> Iterator[None]:
    """All of the block is kept, or none of it; others wait while it runs."""
    connection.execute("BEGIN IMMEDIATE")
    try:
        yield
        connection.execute("COMMIT")
    except BaseException:
        roll_back(connection)
        raise
