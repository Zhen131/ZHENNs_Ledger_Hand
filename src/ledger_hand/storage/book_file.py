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

A refused file is never written to, not one byte, with the one exception
below. A book of an older version is brought up to the current one by the
upgrade scripts it has not had yet, one at a time, each in a transaction of
its own, so that a step that fails leaves the book as it was before that step.

The book is kept in SQLite's ordinary journal mode: nothing is left beside it
between operations, unless a write is cut off part way (the process killed,
the power lost). Then SQLite's journal stays beside the book, under the
book's name with ``-journal`` added, holding what the book was before that
write, and SQLite reads the book again only after rolling the write back from
it, which a connection that cannot write cannot do. The exception: when the
first look fails for that reason alone (SQLite's extended code
``SQLITE_READONLY_ROLLBACK``), the first 100 bytes of the file are read
straight from the disk, without SQLite. Only when they are SQLite's header,
with this program's mark and a version from 1 to ``BOOK_VERSION``, is the
file opened once by a connection that can write, which SQLite rolls the write
back through and then removes the journal; the program itself never deletes,
renames or changes the journal. Then the file is looked at again from the
start, once: empty again (a new book cut off while it was being made), it
becomes a new book; otherwise it is checked as above, and a journal SQLite
still finds then is a failure, not rolled back again. A file refused on that
second look has been written to already, by the rollback, and its refusal
says so. A header that is not such a book is refused as such, and neither
the file nor the journal is written to.

Names defined here: ``BOOK_VERSION``, ``APPLICATION_ID``, ``open_book``,
``expected_schema`` and ``roll_back``.
"""

from __future__ import annotations

import enum
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

# How every SQLite file begins, and where its header keeps the two numbers
# (each 4 bytes, big-endian, signed) that are read when SQLite cannot be asked.
_SQLITE_HEADER = b"SQLite format 3\x00"
_HEADER_SIZE = 100
_USER_VERSION_AT = 60
_APPLICATION_ID_AT = 68


class _Left(enum.Enum):
    """What was done to a file before it was refused; said at the end of the refusal."""

    AS_IT_IS = "It was left as it is."
    ROLLED_BACK = (
        "SQLite first rolled back a write to it that had been cut off part way; "
        "nothing else was written to it."
    )


class _FirstLook(enum.Enum):
    """What the read-only first look at a file found, when it did not refuse it."""

    SOUND = enum.auto()
    CUT_OFF_WRITE = enum.auto()


def open_book(path: Path, busy_timeout_seconds: float) -> sqlite3.Connection:
    """A connection to the book at ``path``, checked and at the current version.

    Waits up to ``busy_timeout_seconds`` for a book someone else is using.
    Raises ``StorageError`` when the book cannot be used; the caller closes
    the connection.
    """
    try:
        left = _check_file(path, busy_timeout_seconds)
    except OSError as error:
        raise from_os(error, path) from None
    try:
        connection = sqlite3.connect(path, timeout=busy_timeout_seconds, isolation_level=None)
    except sqlite3.Error as error:
        raise from_sqlite(error, path) from None
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        _bring_up_to_date(connection, path, left)
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


def _check_file(path: Path, busy_timeout_seconds: float) -> _Left:
    """Refuse the file at ``path`` unless it is a sound book, or make the folder for a new one.

    Says whether SQLite rolled back a write cut off part way on the way.
    """
    if not _holds_something(path):
        path.parent.mkdir(parents=True, exist_ok=True)
        return _Left.AS_IT_IS
    if _inspect(path, busy_timeout_seconds, _Left.AS_IT_IS) is _FirstLook.SOUND:
        return _Left.AS_IT_IS
    _judge_header(path)
    _roll_back_cut_off_write(path, busy_timeout_seconds)
    if not _holds_something(path):
        path.parent.mkdir(parents=True, exist_ok=True)
        return _Left.ROLLED_BACK
    _inspect(path, busy_timeout_seconds, _Left.ROLLED_BACK)
    return _Left.ROLLED_BACK


def _inspect(path: Path, busy_timeout_seconds: float, left: _Left) -> _FirstLook:
    """Refuse the file at ``path`` unless it is a sound book this program can read.

    On the first look (``left`` is ``AS_IT_IS``), a write cut off part way
    that SQLite would have to roll back first is reported instead of refused;
    on the look after the rollback it is refused like any other failure.
    """
    uri = f"{path.absolute().as_uri()}?mode=ro"
    try:
        with closing(sqlite3.connect(uri, uri=True, timeout=busy_timeout_seconds)) as reader:
            identity = reader.execute("PRAGMA application_id").fetchone()[0]
            version = reader.execute("PRAGMA user_version").fetchone()[0]
            _judge(path, identity, version, left)
            if _schema(reader) != expected_schema(version):
                why = f"its tables are not those of version {version}"
                raise _not_this_programs(path, why, left)
            found = reader.execute("PRAGMA quick_check").fetchall()
    except sqlite3.Error as error:
        code = getattr(error, "sqlite_errorcode", None)
        if left is _Left.AS_IT_IS and code == sqlite3.SQLITE_READONLY_ROLLBACK:
            return _FirstLook.CUT_OFF_WRITE
        raise _saying(from_sqlite(error, path), left) from None
    if [tuple(row) for row in found] != [("ok",)]:
        problems = "; ".join(str(row[0]) for row in found[:3])
        damaged = StorageError(
            StorageErrorKind.DAMAGED, f"the book is damaged ({path}): {problems}"
        )
        raise _saying(damaged, left)
    return _FirstLook.SOUND


def _judge_header(path: Path) -> None:
    """Refuse, before anything is written, a file whose header is not a book this program reads.

    The header is read straight from the file: SQLite reads nothing before the
    cut-off write is rolled back.
    """
    with path.open("rb") as file:
        header = file.read(_HEADER_SIZE)
    if len(header) < _HEADER_SIZE or not header.startswith(_SQLITE_HEADER):
        raise StorageError(
            StorageErrorKind.NOT_A_DATABASE,
            f"the file is not a database ({path}): it does not start with SQLite's header, "
            "so the journal beside it was not played back. Both were left as they are.",
        )
    version = _header_number(header, _USER_VERSION_AT)
    _judge(path, _header_number(header, _APPLICATION_ID_AT), version, _Left.AS_IT_IS)


def _header_number(header: bytes, at: int) -> int:
    return int.from_bytes(header[at : at + 4], "big", signed=True)


def _roll_back_cut_off_write(path: Path, busy_timeout_seconds: float) -> None:
    """Let SQLite roll back the write cut off part way, and remove its journal.

    A connection that may write does both by itself the first time it reads
    the file; it is asked for nothing else.
    """
    uri = f"{path.absolute().as_uri()}?mode=rw"
    try:
        with closing(sqlite3.connect(uri, uri=True, timeout=busy_timeout_seconds)) as writer:
            writer.execute("PRAGMA user_version").fetchone()
    except sqlite3.Error as error:
        raise from_sqlite(error, path) from None


def _judge(path: Path, identity: int, version: int, left: _Left) -> None:
    if identity != APPLICATION_ID:
        raise _not_this_programs(path, "it does not carry this program's mark", left)
    if version > BOOK_VERSION:
        raise StorageError(
            StorageErrorKind.NEWER_VERSION,
            f"the book ({path}) is version {version}, written by a newer version of this "
            f"program; this one reads up to version {BOOK_VERSION}. {left.value}",
        )
    if version < 1:
        raise _not_this_programs(path, f"it carries the mark but no version ({version})", left)


def _not_this_programs(path: Path, why: str, left: _Left) -> StorageError:
    return StorageError(
        StorageErrorKind.NOT_THIS_PROGRAMS,
        f"the file ({path}) is not this program's book: {why}. {left.value}",
    )


def _saying(error: StorageError, left: _Left) -> StorageError:
    """``error``, saying at the end that SQLite rolled a write back first, when it did."""
    if left is _Left.AS_IT_IS:
        return error
    return StorageError(error.kind, f"{error.message} {left.value}")


def _bring_up_to_date(connection: sqlite3.Connection, path: Path, left: _Left) -> None:
    version = _version(connection)
    for upgrade in UPGRADES[version:]:
        _run(connection, upgrade, path, left)
    if _schema(connection) != expected_schema(BOOK_VERSION):
        why = f"its tables are not those of version {BOOK_VERSION}"
        raise _not_this_programs(path, why, left)


def _run(connection: sqlite3.Connection, upgrade: Upgrade, path: Path, left: _Left) -> None:
    """One upgrade script, in a transaction of its own; skipped when someone else just ran it."""
    connection.execute("BEGIN IMMEDIATE")
    try:
        before = _version(connection)
        if before < upgrade.number:
            if before != upgrade.number - 1 or (before == 0 and _schema(connection)):
                why = "it changed while it was being made a book"
                raise _not_this_programs(path, why, left)
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
