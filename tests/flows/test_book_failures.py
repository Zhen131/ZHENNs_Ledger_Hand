"""Tests of the flows when the real book fails: saving, the look-up at the start, and exporting.

The book is the SQLite plug in a temporary folder, made locked, cut short,
or put where its folder cannot be written. Each flow then raises the port's
``StorageError`` with the right kind, never an exception of ``sqlite3``, and
writes no export file. Every passage is invented.
"""

from __future__ import annotations

import sqlite3
import stat
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from datetime import datetime, timezone
from pathlib import Path

import pytest

from ledger_hand.flows.exporting import export
from ledger_hand.flows.recording import finish, start
from ledger_hand.flows.saving import save
from ledger_hand.ports import StorageError, StorageErrorKind
from ledger_hand.storage.sqlite_store import SqliteStore
from tests.fakes.routed_model import RoutedModel
from tests.flows.scripted_flow import NOW, ZONE, begin, row, screened, table

SPOT = screened(("spot_trade", "买了 0.5 ETH"))
PASSAGE = "昨天买了 0.5 ETH，价格 3,420，手续费 0"
ROWS = table(row(side="buy", coin="ETH", quantity="0.5 ETH", price="3,420", fee="0", time="昨天"))
LATER = datetime(2026, 10, 8, 6, 0, tzinfo=timezone.utc)


def model() -> RoutedModel:
    return RoutedModel(screen=[SPOT], extraction=[ROWS])


def a_book_with_one_trade(path: Path) -> SqliteStore:
    book = SqliteStore(path, busy_timeout_seconds=0.05)
    save(finish(begin(PASSAGE, model())), book, now=NOW)
    return book


@contextmanager
def locked(path: Path) -> Iterator[SqliteStore]:
    book = a_book_with_one_trade(path)
    holder = sqlite3.connect(path, isolation_level=None)
    holder.execute("BEGIN EXCLUSIVE")
    try:
        yield book
    finally:
        holder.execute("ROLLBACK")
        holder.close()


@contextmanager
def cut_short(path: Path) -> Iterator[SqliteStore]:
    book = a_book_with_one_trade(path)
    with path.open("r+b") as file:
        file.truncate(path.stat().st_size // 2)
    yield book


@contextmanager
def in_a_folder_that_cannot_be_written(path: Path) -> Iterator[SqliteStore]:
    path.parent.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        yield SqliteStore(path, busy_timeout_seconds=0.05)
    finally:
        path.parent.chmod(stat.S_IRWXU)


Condition = Callable[[Path], AbstractContextManager[SqliteStore]]
CONDITIONS: list[tuple[Condition, StorageErrorKind]] = [
    (locked, StorageErrorKind.LOCKED),
    (cut_short, StorageErrorKind.DAMAGED),
    (in_a_folder_that_cannot_be_written, StorageErrorKind.INACCESSIBLE),
]


@pytest.mark.parametrize(("condition", "kind"), CONDITIONS)
def test_saving_looking_up_and_exporting_raise_the_books_error_with_its_kind(
    tmp_path: Path, condition: Condition, kind: StorageErrorKind
) -> None:
    folder = tmp_path / "data"
    folder.mkdir()
    done = finish(begin(PASSAGE, model()))
    fake = model()

    with condition(folder / "book.sqlite3") as book:
        attempts = {
            "save": lambda: save(done, book, now=LATER),
            "look up": lambda: start(PASSAGE, fake, now=NOW, zone=ZONE, book=book),
            "export": lambda: export(book, tmp_path / "exports", now=LATER, zone=ZONE),
        }
        for name, attempt in attempts.items():
            with pytest.raises(StorageError) as raised:
                attempt()
            assert raised.value.kind is kind, (name, raised.value)
            assert not isinstance(raised.value.__cause__, sqlite3.Error), name

    assert fake.screen.calls == []
    assert not (tmp_path / "exports").exists()
