"""Tests of a book whose last write was cut off part way, leaving SQLite's journal beside it.

A child process opens the book, starts a write, writes enough for SQLite to
put changed pages into the book itself, and is killed before it commits: the
book is changed, and the journal beside it holds what it was before. The
first look at a book cannot roll that back, since it cannot write; so, for a
file whose header shows it is a book this program reads, SQLite is let roll
the write back once, and the book is then used as if the write had never
begun. Any other file with a journal beside it is refused, and neither file
changes by one byte. Every book is made in a temporary folder.
"""

from __future__ import annotations

import shutil
import signal
import sqlite3
import stat
import subprocess
import sys
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from ledger_hand.core.book import ExportMark, Listing
from ledger_hand.ports import StorageError, StorageErrorKind
from ledger_hand.storage import book_file
from ledger_hand.storage.book_file import APPLICATION_ID, BOOK_VERSION, expected_schema
from ledger_hand.storage.sqlite_store import SqliteStore
from tests.storage.invented import SAVED_AT, passage, records, stored
from tests.storage.test_sqlite_store import (
    another_programs_database,
    book_at,
    header,
    marked_but_tables_changed,
    newer_book,
    not_a_database,
    saved_book,
    schema,
)

# The child: starts a write, writes until SQLite spills changed pages into
# the file (it may keep only two pages in memory), and is killed before it
# commits. Statements given after the path run first, inside the same write.
CUT_OFF_WRITE = """
import os, signal, sqlite3, sys
connection = sqlite3.connect(sys.argv[1], isolation_level=None)
connection.execute("PRAGMA cache_size = 2")
connection.execute("BEGIN IMMEDIATE")
for statement in sys.argv[2:]:
    connection.execute(statement)
connection.execute("CREATE TABLE cut_off (text TEXT)")
for _ in range(100):
    connection.execute("INSERT INTO cut_off VALUES (?)", ("x" * 2000,))
os.kill(os.getpid(), signal.SIGKILL)
"""

# What the cut-off write changes in a book before it is killed.
BOOK_CHANGES = (
    "UPDATE trades SET raw_text = raw_text || ' (changed)', exported_at = NULL",
    "DELETE FROM confirmed_coins",
    "UPDATE passages SET fingerprint = 'changed'",
)

READONLY_ROLLBACK = 776  # SQLite's SQLITE_READONLY_ROLLBACK, written out by hand


def journal_of(book: Path) -> Path:
    return book.with_name(f"{book.name}-journal")


def read_only_failure(book: Path) -> int | None:
    """SQLite's extended code when a connection that cannot write reads ``book``."""
    reader = sqlite3.connect(f"{book.absolute().as_uri()}?mode=ro", uri=True)
    try:
        reader.execute("PRAGMA application_id").fetchone()
    except sqlite3.Error as error:
        return error.sqlite_errorcode
    finally:
        reader.close()
    return None


def header_on_disk(book: Path) -> tuple[int, int]:
    """The mark and the version, read from the file's bytes: SQLite would roll the write back."""
    head = book.read_bytes()[:100]
    return int.from_bytes(head[68:72], "big"), int.from_bytes(head[60:64], "big")


def cut_off_a_write(book: Path, *statements: str) -> None:
    """Kill a process in the middle of a write to ``book``; check the journal is left hot."""
    before = book.read_bytes()

    done = subprocess.run([sys.executable, "-c", CUT_OFF_WRITE, str(book), *statements])

    assert done.returncode == -signal.SIGKILL
    assert book.read_bytes() != before, "the write changed nothing in the book itself"
    assert journal_of(book).is_file()
    assert read_only_failure(book) == READONLY_ROLLBACK


def everything_in(store: SqliteStore) -> tuple[object, ...]:
    return store.trades(Listing.ALL), store.confirmed_coins(), store.earlier_saves("p1")


def quick_check(book: Path) -> list[tuple[object, ...]]:
    connection = sqlite3.connect(book)
    try:
        return [tuple(row) for row in connection.execute("PRAGMA quick_check").fetchall()]
    finally:
        connection.close()


OPERATIONS: dict[str, Callable[[SqliteStore], object]] = {
    "save": lambda store: store.save(passage("p9", stored("hand-new", records()["minute"]))),
    "earlier_saves": lambda store: store.earlier_saves("p1"),
    "trades": lambda store: store.trades(Listing.ALL),
    "mark_exported": lambda store: store.mark_exported(
        ExportMark(identifiers=("hand-minute",), exported_at=SAVED_AT)
    ),
    "confirmed_coins": lambda store: store.confirmed_coins(),
}


def each_operation(book: Path) -> Iterator[tuple[str, object]]:
    """Each operation, tried once on ``book``; what it gave back, or the error it raised."""
    for name, operation in OPERATIONS.items():
        try:
            yield name, operation(book_at(book))
        except StorageError as error:
            yield name, error


# --- a book of this program's: rolled back, then used as before ---------------


@pytest.mark.parametrize("name", list(OPERATIONS))
def test_a_cut_off_write_is_rolled_back_by_the_first_operation(tmp_path: Path, name: str) -> None:
    book = tmp_path / "book" / "book.sqlite3"
    untouched = tmp_path / "untouched" / "book.sqlite3"
    book.parent.mkdir()
    untouched.parent.mkdir()
    saved_book(book)
    shutil.copyfile(book, untouched)
    cut_off_a_write(book, *BOOK_CHANGES)

    outcome = OPERATIONS[name](book_at(book))

    assert outcome == OPERATIONS[name](book_at(untouched))
    assert everything_in(book_at(book)) == everything_in(book_at(untouched))
    assert not journal_of(book).exists()
    assert quick_check(book) == [("ok",)]
    assert sorted(path.name for path in book.parent.iterdir()) == ["book.sqlite3"]


def test_the_book_rolled_back_holds_what_it_held_before_the_write(tmp_path: Path) -> None:
    book = tmp_path / "book.sqlite3"
    before = everything_in(saved_book(book))
    cut_off_a_write(book, *BOOK_CHANGES)

    after = everything_in(book_at(book))

    assert after == before
    assert len(after[0]) == 4  # type: ignore[arg-type]


def test_a_book_rolled_back_takes_another_save(tmp_path: Path) -> None:
    book = tmp_path / "book.sqlite3"
    saved_book(book)
    cut_off_a_write(book, *BOOK_CHANGES)
    book_at(book).trades(Listing.ALL)

    book_at(book).save(passage("p9", stored("hand-new", records()["minute"])))

    assert len(book_at(book).trades(Listing.ALL)) == 5
    assert quick_check(book) == [("ok",)]
    assert not journal_of(book).exists()


def new_book_cut_off_while_it_was_being_made(book: Path) -> None:
    """The book as a crash between writing a new book and removing its journal leaves it.

    A child writes into an empty database until SQLite has written the
    journal's header for good (the database was 0 pages long), and is killed;
    that journal is put beside a book this program has just made.
    """
    scratch = book.parent / "scratch"
    scratch.mkdir()
    empty = scratch / "empty.sqlite3"
    empty.write_bytes(b"")
    done = subprocess.run([sys.executable, "-c", CUT_OFF_WRITE, str(empty)])
    assert done.returncode == -signal.SIGKILL
    book_at(book).trades(Listing.ALL)
    shutil.copyfile(journal_of(empty), journal_of(book))
    shutil.rmtree(scratch)
    journal = journal_of(book).read_bytes()
    assert journal[:8] == bytes.fromhex("d9d505f920a163d7"), "the journal's header is not written"
    assert int.from_bytes(journal[16:20], "big") == 0, "the journal does not start from 0 pages"
    assert header_on_disk(book) == (APPLICATION_ID, BOOK_VERSION)
    assert read_only_failure(book) == READONLY_ROLLBACK


@pytest.mark.parametrize("name", ["save", "earlier_saves", "trades", "confirmed_coins"])
def test_a_new_book_cut_off_while_being_made_is_made_new_again(tmp_path: Path, name: str) -> None:
    book = tmp_path / "book.sqlite3"
    new_book_cut_off_while_it_was_being_made(book)

    OPERATIONS[name](book_at(book))

    assert header(book) == (APPLICATION_ID, BOOK_VERSION)
    assert schema(book) == expected_schema(BOOK_VERSION)
    assert not journal_of(book).exists()
    assert sorted(path.name for path in tmp_path.iterdir()) == ["book.sqlite3"]


def test_a_new_book_made_new_again_is_empty(tmp_path: Path) -> None:
    book = tmp_path / "book.sqlite3"
    new_book_cut_off_while_it_was_being_made(book)

    assert everything_in(book_at(book)) == ((), (), ())
    with pytest.raises(StorageError) as raised:
        OPERATIONS["mark_exported"](book_at(book))
    assert raised.value.kind is StorageErrorKind.CONFLICT


# --- any other file: refused, and neither file written ------------------------


def two_files(book: Path) -> tuple[bytes, int, bytes, int]:
    journal = journal_of(book)
    return (
        book.read_bytes(),
        book.stat().st_mtime_ns,
        journal.read_bytes(),
        journal.stat().st_mtime_ns,
    )


def with_a_journal_from_elsewhere(book: Path) -> None:
    """A file that is not a database, and a real hot journal copied beside it."""
    elsewhere = book.parent / "elsewhere"
    elsewhere.mkdir()
    other = elsewhere / "book.sqlite3"
    saved_book(other)
    cut_off_a_write(other, *BOOK_CHANGES)
    not_a_database(book)
    shutil.copyfile(journal_of(other), journal_of(book))
    shutil.rmtree(elsewhere)
    assert read_only_failure(book) == READONLY_ROLLBACK


def cut_off(make: Callable[[Path], None]) -> Callable[[Path], None]:
    def made_and_cut_off(book: Path) -> None:
        make(book)
        cut_off_a_write(book)

    return made_and_cut_off


@pytest.mark.parametrize(
    ("make", "kind"),
    [
        (cut_off(newer_book), StorageErrorKind.NEWER_VERSION),
        (cut_off(another_programs_database), StorageErrorKind.NOT_THIS_PROGRAMS),
        (with_a_journal_from_elsewhere, StorageErrorKind.NOT_A_DATABASE),
    ],
    ids=["newer-version", "another-programs-database", "not-a-database"],
)
def test_a_file_this_program_does_not_read_is_not_rolled_back(
    tmp_path: Path, make: Callable[[Path], None], kind: StorageErrorKind
) -> None:
    book = tmp_path / "book.sqlite3"
    make(book)
    before = two_files(book)

    for name, outcome in each_operation(book):
        assert isinstance(outcome, StorageError), name
        assert outcome.kind is kind, (name, outcome)
        assert "It was left as it is" in outcome.message or "left as they are" in outcome.message

    assert two_files(book) == before
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "book.sqlite3",
        "book.sqlite3-journal",
    ]
    assert read_only_failure(book) == READONLY_ROLLBACK


def test_a_book_refused_after_the_rollback_says_it_was_rolled_back(tmp_path: Path) -> None:
    book = tmp_path / "book.sqlite3"
    marked_but_tables_changed(book)
    cut_off_a_write(book, *BOOK_CHANGES)

    with pytest.raises(StorageError) as raised:
        book_at(book).trades(Listing.ALL)

    assert raised.value.kind is StorageErrorKind.NOT_THIS_PROGRAMS
    assert "It was left as it is" not in raised.value.message
    assert "rolled back a write to it that had been cut off" in raised.value.message
    assert not journal_of(book).exists()


def test_a_rollback_that_leaves_the_journal_is_not_tried_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    book = tmp_path / "book.sqlite3"
    saved_book(book)
    cut_off_a_write(book, *BOOK_CHANGES)
    before = two_files(book)
    tries: list[Path] = []
    monkeypatch.setattr(book_file, "_roll_back_cut_off_write", lambda path, _: tries.append(path))

    with pytest.raises(StorageError) as raised:
        book_at(book).trades(Listing.ALL)

    assert tries == [book]
    assert raised.value.kind is StorageErrorKind.INACCESSIBLE
    assert "SQLITE_READONLY_ROLLBACK" in raised.value.message
    assert two_files(book) == before


@pytest.fixture
def read_only_folder(tmp_path: Path) -> Iterator[Path]:
    folder = tmp_path / "read-only"
    folder.mkdir()
    yield folder
    folder.chmod(stat.S_IRWXU)


def test_a_rollback_in_a_folder_that_cannot_be_written_fails_as_the_ports_error(
    read_only_folder: Path,
) -> None:
    book = read_only_folder / "book.sqlite3"
    saved_book(book)
    cut_off_a_write(book, *BOOK_CHANGES)
    read_only_folder.chmod(stat.S_IRUSR | stat.S_IXUSR)

    for name, outcome in each_operation(book):
        assert isinstance(outcome, StorageError), name
        assert not isinstance(outcome.__cause__, sqlite3.Error), name
