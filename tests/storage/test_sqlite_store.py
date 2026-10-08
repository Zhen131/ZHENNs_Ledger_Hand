"""Tests of the SQLite book itself: its file, its version, and how it fails.

What every plug does is tested in ``test_storage_port.py``. Here: a book
keeps its trades between connections and between processes; a file that is
newer, not a database or not this program's is refused without one byte of it
changing; a missing, empty or folderless book is made new; and a book that is
locked, cut short, damaged or in a folder that cannot be written fails with
the port's error and the right kind, never with one of ``sqlite3``'s. Every
book is made in a temporary folder.
"""

from __future__ import annotations

import os
import sqlite3
import stat
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from ledger_hand.core.book import ExportMark, Listing
from ledger_hand.ports import StorageError, StorageErrorKind
from ledger_hand.storage.book_file import APPLICATION_ID, BOOK_VERSION, expected_schema
from ledger_hand.storage.sqlite_store import SqliteStore
from tests.storage.invented import SAVED_AT, passage, records, stored

REPO_ROOT = Path(__file__).resolve().parents[2]
QUICK = 0.05


def book_at(path: Path) -> SqliteStore:
    return SqliteStore(path, busy_timeout_seconds=QUICK)


def saved_book(path: Path) -> SqliteStore:
    """A book at ``path`` holding the four invented trades, one of them exported."""
    store = book_at(path)
    trades = [stored(f"hand-{name}", record) for name, record in records().items()]
    store.save(passage("p1", *trades, coins=("PIKA",)))
    store.mark_exported(ExportMark(identifiers=(trades[0].id,), exported_at=SAVED_AT))
    return store


def header(path: Path) -> tuple[int, int]:
    connection = sqlite3.connect(path)
    try:
        identity = connection.execute("PRAGMA application_id").fetchone()[0]
        version = connection.execute("PRAGMA user_version").fetchone()[0]
    finally:
        connection.close()
    return identity, version


def schema(path: Path) -> tuple[tuple[object, ...], ...]:
    connection = sqlite3.connect(path)
    try:
        rows = connection.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_schema ORDER BY type, name"
        ).fetchall()
    finally:
        connection.close()
    return tuple(tuple(row) for row in rows)


def every_operation(store: SqliteStore) -> Iterator[tuple[str, object]]:
    """Each operation of the port, tried once; what it gave back, or the error it raised."""
    trade = stored("hand-new", records()["minute"])
    attempts = {
        "save": lambda: store.save(passage("p9", trade)),
        "earlier_saves": lambda: store.earlier_saves("p1"),
        "trades": lambda: store.trades(Listing.ALL),
        "mark_exported": lambda: store.mark_exported(
            ExportMark(identifiers=("hand-minute",), exported_at=SAVED_AT)
        ),
        "confirmed_coins": store.confirmed_coins,
    }
    for name, attempt in attempts.items():
        try:
            yield name, attempt()
        except StorageError as error:
            yield name, error


# --- a book keeps what it was given ------------------------------------------


def test_a_new_book_carries_the_mark_and_the_current_version(tmp_path: Path) -> None:
    book = tmp_path / "book.sqlite3"
    book_at(book).trades(Listing.ALL)

    assert header(book) == (APPLICATION_ID, BOOK_VERSION)
    assert schema(book) == expected_schema(BOOK_VERSION)


def test_trades_outlive_the_connection_and_the_store_that_saved_them(tmp_path: Path) -> None:
    book = tmp_path / "book.sqlite3"
    before = saved_book(book).trades(Listing.ALL)

    after = book_at(book).trades(Listing.ALL)

    assert after == before
    assert [entry.trade.created_at for entry in after] == [SAVED_AT] * 4
    assert after[0].exported_at == SAVED_AT


def test_another_process_reads_the_same_trades(tmp_path: Path) -> None:
    book = tmp_path / "book.sqlite3"
    before = saved_book(book).trades(Listing.ALL)
    program = (
        "import sys; from pathlib import Path\n"
        "from ledger_hand.core.book import Listing\n"
        "from ledger_hand.storage.sqlite_store import SqliteStore\n"
        "for entry in SqliteStore(Path(sys.argv[1])).trades(Listing.ALL):\n"
        "    print(entry.trade.id, entry.trade.created_at.isoformat(), entry.exported_at)\n"
    )

    done = subprocess.run(
        [sys.executable, "-c", program, str(book)],
        capture_output=True,
        text=True,
        check=True,
        cwd=REPO_ROOT,
    )

    expected = [
        f"{entry.trade.id} {entry.trade.created_at.isoformat()} {entry.exported_at}"
        for entry in before
    ]
    assert done.stdout.splitlines() == expected


def test_nothing_is_left_beside_the_book_between_operations(tmp_path: Path) -> None:
    saved_book(tmp_path / "book.sqlite3")

    assert sorted(path.name for path in tmp_path.iterdir()) == ["book.sqlite3"]


# --- opening: refused files are left as they are ------------------------------


def newer_book(path: Path) -> None:
    saved_book(path)
    connection = sqlite3.connect(path)
    connection.execute(f"PRAGMA user_version = {BOOK_VERSION + 1}")
    connection.close()


def not_a_database(path: Path) -> None:
    path.write_bytes(b"these are not the bytes of a database\n" * 200)


def another_programs_database(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE notes (text TEXT)")
    connection.execute("INSERT INTO notes VALUES ('invented')")
    connection.commit()
    connection.close()


def marked_but_tables_changed(path: Path) -> None:
    saved_book(path)
    connection = sqlite3.connect(path)
    connection.execute("ALTER TABLE trades ADD COLUMN extra TEXT")
    connection.close()


def marked_without_a_version(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.execute(f"PRAGMA application_id = {APPLICATION_ID}")
    connection.execute("CREATE TABLE notes (text TEXT)")
    connection.close()


@pytest.mark.parametrize(
    ("make", "kind"),
    [
        (newer_book, StorageErrorKind.NEWER_VERSION),
        (not_a_database, StorageErrorKind.NOT_A_DATABASE),
        (another_programs_database, StorageErrorKind.NOT_THIS_PROGRAMS),
        (marked_but_tables_changed, StorageErrorKind.NOT_THIS_PROGRAMS),
        (marked_without_a_version, StorageErrorKind.NOT_THIS_PROGRAMS),
    ],
)
def test_a_file_that_is_not_a_book_this_program_reads_is_refused_and_left_byte_for_byte(
    tmp_path: Path, make: object, kind: StorageErrorKind
) -> None:
    book = tmp_path / "book.sqlite3"
    make(book)  # type: ignore[operator]
    before = book.read_bytes()
    modified = book.stat().st_mtime_ns

    for name, outcome in every_operation(book_at(book)):
        assert isinstance(outcome, StorageError), name
        assert outcome.kind is kind, (name, outcome)

    assert book.read_bytes() == before
    assert book.stat().st_mtime_ns == modified
    assert sorted(path.name for path in tmp_path.iterdir()) == ["book.sqlite3"]


def test_a_refusal_names_the_versions(tmp_path: Path) -> None:
    book = tmp_path / "book.sqlite3"
    newer_book(book)

    with pytest.raises(StorageError) as raised:
        book_at(book).trades(Listing.ALL)

    assert f"version {BOOK_VERSION + 1}" in raised.value.message
    assert f"up to version {BOOK_VERSION}" in raised.value.message


@pytest.mark.parametrize(
    "where",
    [
        "book.sqlite3",
        "data/book.sqlite3",
        "data/deeper/still/book.sqlite3",
    ],
)
def test_a_missing_book_is_made_new_with_its_folders(tmp_path: Path, where: str) -> None:
    book = tmp_path / where

    assert book_at(book).trades(Listing.ALL) == ()
    assert header(book) == (APPLICATION_ID, BOOK_VERSION)


def test_an_empty_file_is_made_a_new_book(tmp_path: Path) -> None:
    book = tmp_path / "book.sqlite3"
    book.write_bytes(b"")

    assert book_at(book).confirmed_coins() == ()
    assert header(book) == (APPLICATION_ID, BOOK_VERSION)
    assert schema(book) == expected_schema(BOOK_VERSION)


# --- failing ------------------------------------------------------------------


def test_a_locked_book_fails_as_locked_for_every_operation(tmp_path: Path) -> None:
    book = tmp_path / "book.sqlite3"
    saved_book(book)
    holder = sqlite3.connect(book, isolation_level=None)
    holder.execute("BEGIN EXCLUSIVE")
    try:
        outcomes = dict(every_operation(book_at(book)))
    finally:
        holder.execute("ROLLBACK")
        holder.close()

    for name, outcome in outcomes.items():
        assert isinstance(outcome, StorageError), name
        assert outcome.kind is StorageErrorKind.LOCKED, (name, outcome)
    assert len(book_at(book).trades(Listing.ALL)) == 4


def test_a_book_being_written_elsewhere_can_be_read_but_not_written(tmp_path: Path) -> None:
    book = tmp_path / "book.sqlite3"
    saved_book(book)
    holder = sqlite3.connect(book, isolation_level=None)
    holder.execute("BEGIN IMMEDIATE")
    try:
        outcomes = dict(every_operation(book_at(book)))
    finally:
        holder.execute("ROLLBACK")
        holder.close()

    for name in ("save", "mark_exported"):
        assert isinstance(outcomes[name], StorageError), name
        assert outcomes[name].kind is StorageErrorKind.LOCKED  # type: ignore[union-attr]
    assert len(outcomes["trades"]) == 4  # type: ignore[arg-type]


@pytest.mark.parametrize("keep", [0.75, 0.5, 0.1])
def test_a_book_cut_short_is_damaged_for_every_operation(tmp_path: Path, keep: float) -> None:
    book = tmp_path / "book.sqlite3"
    saved_book(book)
    size = book.stat().st_size
    with book.open("r+b") as file:
        file.truncate(int(size * keep))
    before = book.read_bytes()

    for name, outcome in every_operation(book_at(book)):
        assert isinstance(outcome, StorageError), name
        assert outcome.kind is StorageErrorKind.DAMAGED, (name, outcome)
    assert book.read_bytes() == before


def test_a_row_that_cannot_be_read_back_makes_the_book_damaged(tmp_path: Path) -> None:
    book = tmp_path / "book.sqlite3"
    saved_book(book)
    connection = sqlite3.connect(book)
    connection.execute("UPDATE trades SET quantity = 'two' WHERE id = 'hand-minute'")
    connection.commit()
    connection.close()

    with pytest.raises(StorageError) as raised:
        book_at(book).trades(Listing.ALL)

    assert raised.value.kind is StorageErrorKind.DAMAGED
    assert "cannot be read back" in raised.value.message


@pytest.fixture
def read_only_folder(tmp_path: Path) -> Iterator[Path]:
    folder = tmp_path / "read-only"
    folder.mkdir()
    yield folder
    folder.chmod(stat.S_IRWXU)


def test_a_new_book_in_a_folder_that_cannot_be_written_is_inaccessible(
    read_only_folder: Path,
) -> None:
    read_only_folder.chmod(stat.S_IRUSR | stat.S_IXUSR)

    for name, outcome in every_operation(book_at(read_only_folder / "book.sqlite3")):
        assert isinstance(outcome, StorageError), name
        assert outcome.kind is StorageErrorKind.INACCESSIBLE, (name, outcome)
    assert list(read_only_folder.iterdir()) == []


def test_a_book_in_a_folder_that_cannot_be_written_is_read_but_never_written(
    read_only_folder: Path,
) -> None:
    book = read_only_folder / "book.sqlite3"
    saved_book(book)
    before = book.read_bytes()
    read_only_folder.chmod(stat.S_IRUSR | stat.S_IXUSR)

    outcomes = dict(every_operation(book_at(book)))

    for name in ("save", "mark_exported"):
        assert isinstance(outcomes[name], StorageError), name
        assert outcomes[name].kind is StorageErrorKind.INACCESSIBLE  # type: ignore[union-attr]
    assert len(outcomes["trades"]) == 4  # type: ignore[arg-type]
    assert book.read_bytes() == before
    assert sorted(path.name for path in read_only_folder.iterdir()) == ["book.sqlite3"]


def test_a_book_whose_folder_is_a_file_is_inaccessible(tmp_path: Path) -> None:
    (tmp_path / "data").write_text("a file where the folder should be", encoding="utf-8")

    for name, outcome in every_operation(book_at(tmp_path / "data" / "book.sqlite3")):
        assert isinstance(outcome, StorageError), name
        assert outcome.kind is StorageErrorKind.INACCESSIBLE, (name, outcome)


def test_a_read_only_book_is_read_but_never_written(tmp_path: Path) -> None:
    book = tmp_path / "book.sqlite3"
    saved_book(book)
    book.chmod(stat.S_IRUSR)
    try:
        outcomes = dict(every_operation(book_at(book)))
    finally:
        book.chmod(stat.S_IRUSR | stat.S_IWUSR)

    assert outcomes["save"].kind is StorageErrorKind.INACCESSIBLE  # type: ignore[union-attr]
    assert len(outcomes["trades"]) == 4  # type: ignore[arg-type]


def test_the_wait_for_a_busy_book_is_a_number_of_seconds(tmp_path: Path) -> None:
    for wait, error in ((-1, ValueError), (float("nan"), ValueError), (True, TypeError)):
        with pytest.raises(error):
            SqliteStore(tmp_path / "book.sqlite3", busy_timeout_seconds=wait)
    assert not (tmp_path / "book.sqlite3").exists()


def test_no_exception_of_sqlite3_leaves_the_plug(tmp_path: Path) -> None:
    folder = tmp_path / "folder.sqlite3"
    folder.mkdir()

    for name, outcome in every_operation(book_at(folder)):
        assert isinstance(outcome, StorageError), name
        assert not isinstance(outcome.__cause__, sqlite3.Error)
    assert os.listdir(folder) == []
