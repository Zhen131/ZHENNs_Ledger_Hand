"""Tests of the golden book of version 1: the program still reads it, and its dump is what it holds.

The golden book is a committed SQLite file made by this program's own store
at version 1, and never changed afterwards (``golden_book`` says what it
holds). Every test copies it into a temporary folder first and opens only
the copy: opening a database can rewrite parts of its header, and nothing
may change the committed file.

- The current code reads the copy and gets exactly the trades, the export
  moments, the earlier saves and the confirmed coin written out in
  ``golden_book``; reading it changes not one byte.
- The committed dump, run in memory, makes a database with the same tables
  and the same rows as the file. The dump's text is not compared with a new
  dump: how ``sqlite3`` writes one may change between Python versions.
- Both files are still the bytes that were committed.
"""

from __future__ import annotations

import hashlib
import shutil
import sqlite3
from pathlib import Path

from ledger_hand.core.book import EarlierSave, Listing
from ledger_hand.flows.fingerprint import passage_fingerprint
from ledger_hand.storage.book_file import APPLICATION_ID
from ledger_hand.storage.sqlite_store import SqliteStore
from tests.storage import golden_book as golden

BOOK = golden.GOLDEN_DIR / "book-v1.sqlite3"
DUMP = golden.GOLDEN_DIR / "book-v1.sql"
# The digests of the two files as committed. A golden sample is never changed.
BOOK_SHA256 = "ceb255aceea48631e0a30f499c400281676029e102d7103427268ef92b6ad7b2"
DUMP_SHA256 = "3eda7b20eebe87a9bb3ea2553023b5ec756f56e70934f627dfee94917d791507"
TABLES = ("passages", "trades", "confirmed_coins")


def copy_of(source: Path, folder: Path) -> Path:
    target = folder / source.name
    shutil.copyfile(source, target)
    return target


def contents(connection: sqlite3.Connection) -> dict[str, object]:
    schema = connection.execute(
        "SELECT type, name, tbl_name, sql FROM sqlite_schema ORDER BY type, name"
    ).fetchall()
    rows = {
        table: connection.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall()
        for table in TABLES
    }
    return {"schema": schema, **rows}


def test_both_files_are_still_the_bytes_that_were_committed() -> None:
    assert hashlib.sha256(BOOK.read_bytes()).hexdigest() == BOOK_SHA256
    assert hashlib.sha256(DUMP.read_bytes()).hexdigest() == DUMP_SHA256


def test_the_current_code_reads_the_golden_book_as_it_was_written(tmp_path: Path) -> None:
    book = copy_of(BOOK, tmp_path)
    store = SqliteStore(book)

    assert store.trades(Listing.ALL) == golden.LISTED
    assert store.trades(Listing.NOT_EXPORTED) == golden.LISTED[1:]
    assert store.confirmed_coins() == golden.COINS
    assert store.earlier_saves(golden.FINGERPRINT_A) == (
        EarlierSave(saved_at=golden.SAVED_A, trades=1),
    )
    assert store.earlier_saves(golden.FINGERPRINT_B) == (
        EarlierSave(saved_at=golden.SAVED_B, trades=2),
    )
    assert book.read_bytes() == BOOK.read_bytes()
    assert sorted(path.name for path in tmp_path.iterdir()) == [BOOK.name]


def test_the_golden_book_is_version_1_with_the_mark(tmp_path: Path) -> None:
    connection = sqlite3.connect(copy_of(BOOK, tmp_path))
    try:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
        assert connection.execute("PRAGMA application_id").fetchone()[0] == APPLICATION_ID
        assert connection.execute("PRAGMA freelist_count").fetchone()[0] == 0
    finally:
        connection.close()


def test_the_fingerprints_in_the_golden_book_are_the_ones_the_program_works_out() -> None:
    assert passage_fingerprint(golden.PASSAGE_A) == golden.FINGERPRINT_A
    assert passage_fingerprint(golden.PASSAGE_B) == golden.FINGERPRINT_B


def test_the_dump_makes_the_same_tables_and_rows_as_the_book(tmp_path: Path) -> None:
    from_dump = sqlite3.connect(":memory:")
    from_file = sqlite3.connect(copy_of(BOOK, tmp_path))
    try:
        from_dump.executescript(DUMP.read_text(encoding="utf-8"))
        assert contents(from_dump) == contents(from_file)
        assert len(contents(from_file)["trades"]) == 3  # type: ignore[arg-type]
    finally:
        from_dump.close()
        from_file.close()


def test_the_golden_book_covers_what_it_says_it_covers() -> None:
    records = [entry.trade.record for entry in golden.LISTED]
    precisions = {record.occurred.precision.value for record in records}
    derived = {None if record.derived is None else record.derived.value for record in records}

    assert precisions == {"day", "minute", "second"}
    assert derived == {"quantity", "total", None}
    assert {record.fee_coin for record in records} == {"USDT", "BNB"}
    assert any(record.fee == 0 for record in records)
    assert [entry.exported for entry in golden.LISTED] == [True, False, False]
    assert {record.platform is None for record in records} == {True, False}
    assert {record.note is None for record in records} == {True, False}
    assert [coin.symbol for coin in golden.COINS] == ["PIKA"]
    assert "PIKA" in {record.coin for record in records}
