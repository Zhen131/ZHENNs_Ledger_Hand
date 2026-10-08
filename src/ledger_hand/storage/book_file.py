"""Opening the book: which file it is, which version, and bringing it up to the current one.

A book is a SQLite file. Two numbers in its header say what it is, and they
are read before anything else, through a connection that cannot write: the
application identifier, which marks the file as this program's book, and the
version (SQLite's ``user_version``), which says which upgrade scripts made
it. Then:

- a file that is not there, or is empty (0 bytes: SQLite itself takes such a
  file for an empty database, and nothing in it can be lost), becomes a new
  book of the current version, and its folder is made when it is missing;
- a file SQLite cannot read as a database at all is refused as
  ``NOT_A_DATABASE``;
- a database without this program's mark, or whose tables are not exactly
  the ones its version has, is refused as ``NOT_THIS_PROGRAMS``;
- a book of a newer version than this program knows is refused as
  ``NEWER_VERSION``;
- a book that SQLite finds damaged when it checks it is refused as
  ``DAMAGED``.

A refused file is never written to, not one byte. A book of an older version
is brought up to the current one by the upgrade scripts it has not had yet,
one at a time, each in a transaction of its own, so that a step that fails
leaves the book as it was before that step.

The book is kept in SQLite's ordinary journal mode: nothing is left beside it
between operations.

Names defined here: ``BOOK_VERSION``, ``APPLICATION_ID``, ``open_book``,
``expected_schema`` and ``roll_back``.
"""

from __future__ import annotations

import functools
import sqlite3
from contextlib import closing, suppress
from pathlib import Path

from ledger_hand.ports import StorageError, StorageErrorKind
from ledger_hand.storage.failures import from_os, from_sqlite
from ledger_hand.storage.upgrades import UPGRADES, Upgrade

# The version of the book this program writes. Raising it comes with a new
# upgrade script and a golden sample of the new version.
BOOK_VERSION = 1
# The mark in the file's header that says the file is this program's book:
# the letters "LHND" read as one number.
APPLICATION_ID = 0x4C48_4E44

type Schema = tuple[tuple[object, ...], ...]


def open_book(path: Path, busy_timeout_seconds: float) -> sqlite3.Connection:
    """A connection to the book at ``path``, checked and at the current version.

    Waits up to ``busy_timeout_seconds`` for a book someone else is using.
    Raises ``StorageError`` when the book cannot be used; the caller closes
    the connection.
    """
    try:
        if _holds_something(path):
            _inspect(path, busy_timeout_seconds)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise from_os(error, path) from None
    try:
        connection = sqlite3.connect(path, timeout=busy_timeout_seconds, isolation_level=None)
    except sqlite3.Error as error:
        raise from_sqlite(error, path) from None
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        _bring_up_to_date(connection, path)
    except sqlite3.Error as error:
        connection.close()
        raise from_sqlite(error, path) from None
    except BaseException:
        connection.close()
        raise
    connection.row_factory = sqlite3.Row
    return connection


@functools.cache
def expected_schema(version: int) -> Schema:
    """The tables and indexes a book of ``version`` has: the upgrade scripts run in memory."""
    connection = sqlite3.connect(":memory:", isolation_level=None)
    try:
        for upgrade in UPGRADES[:version]:
            for statement in upgrade.statements:
                connection.execute(statement)
        return _schema(connection)
    finally:
        connection.close()


def _holds_something(path: Path) -> bool:
    try:
        return path.stat().st_size > 0
    except FileNotFoundError:
        return False


def _inspect(path: Path, busy_timeout_seconds: float) -> None:
    """Refuse the file at ``path`` unless it is a sound book this program can read."""
    uri = f"{path.absolute().as_uri()}?mode=ro"
    try:
        with closing(sqlite3.connect(uri, uri=True, timeout=busy_timeout_seconds)) as reader:
            identity = reader.execute("PRAGMA application_id").fetchone()[0]
            version = reader.execute("PRAGMA user_version").fetchone()[0]
            _judge(path, identity, version)
            if _schema(reader) != expected_schema(version):
                raise _not_this_programs(path, f"its tables are not those of version {version}")
            found = reader.execute("PRAGMA quick_check").fetchall()
    except sqlite3.Error as error:
        raise from_sqlite(error, path) from None
    if [tuple(row) for row in found] != [("ok",)]:
        problems = "; ".join(str(row[0]) for row in found[:3])
        raise StorageError(StorageErrorKind.DAMAGED, f"the book is damaged ({path}): {problems}")


def _judge(path: Path, identity: int, version: int) -> None:
    if identity != APPLICATION_ID:
        raise _not_this_programs(path, "it does not carry this program's mark")
    if version > BOOK_VERSION:
        raise StorageError(
            StorageErrorKind.NEWER_VERSION,
            f"the book ({path}) is version {version}, written by a newer version of this "
            f"program; this one reads up to version {BOOK_VERSION}. It was left as it is.",
        )
    if version < 1:
        raise _not_this_programs(path, f"it carries the mark but no version ({version})")


def _not_this_programs(path: Path, why: str) -> StorageError:
    return StorageError(
        StorageErrorKind.NOT_THIS_PROGRAMS,
        f"the file ({path}) is not this program's book: {why}. It was left as it is.",
    )


def _bring_up_to_date(connection: sqlite3.Connection, path: Path) -> None:
    version = _version(connection)
    for upgrade in UPGRADES[version:]:
        _run(connection, upgrade, path)
    if _schema(connection) != expected_schema(BOOK_VERSION):
        raise _not_this_programs(path, f"its tables are not those of version {BOOK_VERSION}")


def _run(connection: sqlite3.Connection, upgrade: Upgrade, path: Path) -> None:
    """One upgrade script, in a transaction of its own; skipped when someone else just ran it."""
    connection.execute("BEGIN IMMEDIATE")
    try:
        before = _version(connection)
        if before < upgrade.number:
            if before != upgrade.number - 1 or (before == 0 and _schema(connection)):
                raise _not_this_programs(path, "it changed while it was being made a book")
            if before == 0:
                connection.execute(f"PRAGMA application_id = {APPLICATION_ID}")
            for statement in upgrade.statements:
                connection.execute(statement)
            connection.execute(f"PRAGMA user_version = {upgrade.number}")
        connection.execute("COMMIT")
    except BaseException:
        roll_back(connection)
        raise


def roll_back(connection: sqlite3.Connection) -> None:
    """End the open transaction, if there is one, changing nothing."""
    if connection.in_transaction:
        # When the rollback fails too, the transaction is gone with the failure that ended it.
        with suppress(sqlite3.Error):
            connection.execute("ROLLBACK")


def _version(connection: sqlite3.Connection) -> int:
    version: int = connection.execute("PRAGMA user_version").fetchone()[0]
    return version


def _schema(connection: sqlite3.Connection) -> Schema:
    rows = connection.execute(
        "SELECT type, name, tbl_name, sql FROM sqlite_schema ORDER BY type, name"
    ).fetchall()
    return tuple(tuple(row) for row in rows)
