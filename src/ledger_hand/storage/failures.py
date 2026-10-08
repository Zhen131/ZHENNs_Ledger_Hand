"""How a failure of SQLite, or of the file system under it, becomes one of the port's kinds.

SQLite reports a failure with a result code; its lowest eight bits are the
primary code, and the rest only refine it. Each primary code that means
something to the person using the book is sorted into a kind here; any other
becomes ``UNEXPECTED``, with SQLite's own words. An error of the file system
met before SQLite is reached (making the book's folder, say) is
``INACCESSIBLE``.

The kinds that say a file is newer, not a database or not this program's are
decided where a book is opened, before SQLite is asked to read it as one; a
file that SQLite cannot read as a database at all lands here as
``NOT_A_DATABASE``.

Names defined here: ``from_sqlite`` and ``from_os``.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from ledger_hand.ports import StorageError, StorageErrorKind

# SQLite's primary result codes, from its documentation.
_PERM = 3
_BUSY = 5
_LOCKED = 6
_READONLY = 8
_IOERR = 10
_CORRUPT = 11
_FULL = 13
_CANTOPEN = 14
_CONSTRAINT = 19
_AUTH = 23
_NOTADB = 26

_KIND_OF_CODE = {
    _BUSY: StorageErrorKind.LOCKED,
    _LOCKED: StorageErrorKind.LOCKED,
    _CORRUPT: StorageErrorKind.DAMAGED,
    _NOTADB: StorageErrorKind.NOT_A_DATABASE,
    _CONSTRAINT: StorageErrorKind.CONFLICT,
    _PERM: StorageErrorKind.INACCESSIBLE,
    _READONLY: StorageErrorKind.INACCESSIBLE,
    _IOERR: StorageErrorKind.INACCESSIBLE,
    _FULL: StorageErrorKind.INACCESSIBLE,
    _CANTOPEN: StorageErrorKind.INACCESSIBLE,
    _AUTH: StorageErrorKind.INACCESSIBLE,
}

# A few words for each kind, said before SQLite's own.
_WHAT = {
    StorageErrorKind.LOCKED: "the book is in use elsewhere and stayed busy",
    StorageErrorKind.DAMAGED: "the book is damaged",
    StorageErrorKind.NOT_A_DATABASE: "the file is not a database",
    StorageErrorKind.CONFLICT: "the book refused a value that clashes with what it holds",
    StorageErrorKind.INACCESSIBLE: "the book or its folder cannot be made, read or written",
    StorageErrorKind.UNEXPECTED: "the book failed",
}


def from_sqlite(error: sqlite3.Error, book: Path) -> StorageError:
    """The port's error for ``error``, raised while working on the book at ``book``."""
    code = getattr(error, "sqlite_errorcode", None)
    kind = StorageErrorKind.UNEXPECTED
    if isinstance(code, int):
        kind = _KIND_OF_CODE.get(code & 0xFF, StorageErrorKind.UNEXPECTED)
    name = getattr(error, "sqlite_errorname", None) or type(error).__name__
    return StorageError(kind, f"{_WHAT[kind]} ({book}): {error} [{name}]")


def from_os(error: OSError, book: Path) -> StorageError:
    """The port's error for a failure of the file system around the book at ``book``."""
    what = _WHAT[StorageErrorKind.INACCESSIBLE]
    return StorageError(StorageErrorKind.INACCESSIBLE, f"{what} ({book}): {error}")
