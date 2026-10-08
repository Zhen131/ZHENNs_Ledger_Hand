"""Tests of the upgrade scripts: numbered from 1 with no gap, and each step whole or not at all.

Every script file is listed from the folder itself, so a script that is
there but not registered, or registered but not there, is caught. Running
them one by one from an empty file must give exactly the tables a new book
of the current version has.
"""

from __future__ import annotations

import importlib
import re
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from ledger_hand.core.book import Listing
from ledger_hand.ports import StorageError, StorageErrorKind
from ledger_hand.storage import book_file
from ledger_hand.storage.book_file import APPLICATION_ID, BOOK_VERSION, expected_schema
from ledger_hand.storage.sqlite_store import SqliteStore
from ledger_hand.storage.upgrades import UPGRADES, Upgrade

UPGRADES_DIR = Path(__file__).resolve().parents[2] / "src" / "ledger_hand" / "storage" / "upgrades"
SCRIPT_NAME = re.compile(r"upgrade_(\d{4})\.py")


def script_numbers() -> list[int]:
    numbers = []
    for path in UPGRADES_DIR.iterdir():
        found = SCRIPT_NAME.fullmatch(path.name)
        if found is not None:
            numbers.append(int(found.group(1)))
        else:
            assert path.name in {"__init__.py", "__pycache__"}, path.name
    return sorted(numbers)


def schema_of(connection: sqlite3.Connection) -> tuple[tuple[object, ...], ...]:
    rows = connection.execute(
        "SELECT type, name, tbl_name, sql FROM sqlite_schema ORDER BY type, name"
    ).fetchall()
    return tuple(tuple(row) for row in rows)


def test_the_scripts_are_numbered_from_one_with_no_gap() -> None:
    numbers = script_numbers()

    assert numbers == list(range(1, len(numbers) + 1))
    assert numbers, "there is at least the first script"


def test_every_script_is_registered_in_order_with_its_own_statements() -> None:
    numbers = script_numbers()

    assert [upgrade.number for upgrade in UPGRADES] == numbers
    for upgrade in UPGRADES:
        module = importlib.import_module(
            f"ledger_hand.storage.upgrades.upgrade_{upgrade.number:04d}"
        )
        assert upgrade.number == module.NUMBER
        assert upgrade.statements == module.STATEMENTS


def test_the_book_version_is_the_number_of_the_last_script() -> None:
    assert BOOK_VERSION == UPGRADES[-1].number == len(UPGRADES)


def test_the_scripts_run_one_by_one_from_an_empty_file_give_a_new_books_tables(
    tmp_path: Path,
) -> None:
    by_hand = sqlite3.connect(tmp_path / "by-hand.sqlite3", isolation_level=None)
    try:
        for upgrade in UPGRADES:
            by_hand.execute("BEGIN")
            for statement in upgrade.statements:
                by_hand.execute(statement)
            by_hand.execute("COMMIT")
        stepped = schema_of(by_hand)
    finally:
        by_hand.close()
    new = tmp_path / "new.sqlite3"
    SqliteStore(new).trades(Listing.ALL)
    made = sqlite3.connect(new)
    try:
        assert schema_of(made) == stepped == expected_schema(BOOK_VERSION)
    finally:
        made.close()


def test_the_tables_hold_no_floating_point_column() -> None:
    sql = " ".join(str(row[3]) for row in expected_schema(BOOK_VERSION) if row[3] is not None)

    assert "REAL" not in sql.upper()
    assert "FLOAT" not in sql.upper()
    assert "DOUBLE" not in sql.upper()
    assert sql.count("STRICT") == 3


@pytest.fixture
def one_more_upgrade(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """A second upgrade whose last statement fails, as if the book were at version 2."""
    broken = Upgrade(
        BOOK_VERSION + 1,
        ("CREATE TABLE added (value TEXT) STRICT", "INSERT INTO nowhere VALUES (1)"),
    )
    monkeypatch.setattr(book_file, "UPGRADES", (*UPGRADES, broken))
    monkeypatch.setattr(book_file, "BOOK_VERSION", BOOK_VERSION + 1)
    yield
    book_file.expected_schema.cache_clear()


def test_an_upgrade_step_that_fails_leaves_the_book_as_it_was_before_it(
    tmp_path: Path, one_more_upgrade: None
) -> None:
    book = tmp_path / "book.sqlite3"
    connection = sqlite3.connect(book, isolation_level=None)
    for statement in UPGRADES[0].statements:
        connection.execute(statement)
    connection.execute(f"PRAGMA application_id = {APPLICATION_ID}")
    connection.execute(f"PRAGMA user_version = {BOOK_VERSION}")
    connection.close()
    before = book.read_bytes()

    with pytest.raises(StorageError) as raised:
        SqliteStore(book).trades(Listing.ALL)

    assert raised.value.kind is StorageErrorKind.UNEXPECTED
    assert book.read_bytes() == before
    check = sqlite3.connect(book)
    try:
        assert check.execute("PRAGMA user_version").fetchone()[0] == BOOK_VERSION
        assert "added" not in {row[1] for row in schema_of(check)}
    finally:
        check.close()


def test_an_older_book_is_brought_up_to_the_newer_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    book = tmp_path / "book.sqlite3"
    SqliteStore(book).trades(Listing.ALL)
    added = Upgrade(BOOK_VERSION + 1, ("CREATE TABLE added (value TEXT) STRICT",))
    monkeypatch.setattr(book_file, "UPGRADES", (*UPGRADES, added))
    monkeypatch.setattr(book_file, "BOOK_VERSION", BOOK_VERSION + 1)
    try:
        assert SqliteStore(book).trades(Listing.ALL) == ()
        check = sqlite3.connect(book)
        try:
            assert check.execute("PRAGMA user_version").fetchone()[0] == BOOK_VERSION + 1
            assert "added" in {row[1] for row in schema_of(check)}
        finally:
            check.close()
    finally:
        book_file.expected_schema.cache_clear()
