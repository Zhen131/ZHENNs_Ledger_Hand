"""Tests of exporting: the saved trades not exported yet, written as one new file, then marked.

The book here is the real SQLite plug in a temporary folder, except where a
failure of the book is staged with the in-memory stand-in. Every trade is
invented.
"""

from __future__ import annotations

import dataclasses
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from ledger_hand import __version__
from ledger_hand.core.book import ExportMark, Listing
from ledger_hand.core.coins import BUILT_IN_TABLE
from ledger_hand.core.stored import StoredTrade
from ledger_hand.core.trade import OccurredTime, TimePrecision
from ledger_hand.export.backup import ExportProblem, export_backup
from ledger_hand.export.file_name import backup_file_name
from ledger_hand.flows import export_file
from ledger_hand.flows.export_file import WriteProblem
from ledger_hand.flows.exporting import APP_NAME, ExportResult, export
from ledger_hand.ports import StorageError, StorageErrorKind
from ledger_hand.storage.sqlite_store import SqliteStore
from tests.fakes.memory_store import MemoryStore
from tests.storage.invented import BUDAPEST, COINS, SHANGHAI, passage, records, stored

NOW = datetime(2026, 10, 9, 6, 0, 0, tzinfo=timezone.utc)
LATER = datetime(2026, 10, 9, 6, 0, 1, tzinfo=timezone.utc)
TODAY = date(2026, 10, 9)


def book_with_two(where: Path) -> tuple[SqliteStore, list[StoredTrade]]:
    """A book holding two trades not exported yet, one of them in a coin the user confirmed."""
    book = SqliteStore(where / "data" / "book.sqlite3")
    trades = [
        stored("hand-minute", records()["minute"]),
        stored("hand-second", records()["second"]),
    ]
    book.save(passage("p1", *trades, coins=("PIKA",)))
    return book, trades


def exports_of(where: Path) -> Path:
    return where / "data" / "exports"


def files_in(folder: Path) -> list[str]:
    return sorted(path.name for path in folder.iterdir()) if folder.exists() else []


# --- the file and the marks ---------------------------------------------------


def test_two_new_trades_are_written_as_the_export_would_write_them_and_marked(
    tmp_path: Path,
) -> None:
    book, trades = book_with_two(tmp_path)

    outcome = export(book, exports_of(tmp_path), now=NOW, zone=BUDAPEST)

    assert outcome.result is ExportResult.EXPORTED
    assert outcome.path == exports_of(tmp_path) / backup_file_name(NOW)
    assert "incremental" in outcome.path.name
    assert files_in(exports_of(tmp_path)) == [backup_file_name(NOW)]
    expected = export_backup(
        trades,
        COINS,
        exported_at=NOW,
        today=TODAY,
        app_name=APP_NAME,
        app_version=__version__,
    )
    assert isinstance(expected, str)
    assert outcome.path.read_bytes() == expected.encode("utf-8")
    assert outcome.identifiers == ("hand-minute", "hand-second")
    assert [entry.exported_at for entry in book.trades(Listing.ALL)] == [NOW, NOW]
    assert book.trades(Listing.NOT_EXPORTED) == ()


def test_a_second_export_finds_nothing_new_and_writes_nothing(tmp_path: Path) -> None:
    book, _ = book_with_two(tmp_path)
    export(book, exports_of(tmp_path), now=NOW, zone=BUDAPEST)

    again = export(book, exports_of(tmp_path), now=LATER, zone=BUDAPEST)

    assert again.result is ExportResult.NOTHING_NEW
    assert again.path is None
    assert files_in(exports_of(tmp_path)) == [backup_file_name(NOW)]


def test_an_empty_book_writes_nothing_and_makes_no_folder(tmp_path: Path) -> None:
    outcome = export(
        SqliteStore(tmp_path / "book.sqlite3"), tmp_path / "exports", now=NOW, zone=BUDAPEST
    )

    assert outcome.result is ExportResult.NOTHING_NEW
    assert not (tmp_path / "exports").exists()


def test_only_the_trades_saved_since_the_last_export_go_into_the_next_file(tmp_path: Path) -> None:
    book, _ = book_with_two(tmp_path)
    export(book, exports_of(tmp_path), now=NOW, zone=BUDAPEST)
    book.save(passage("p2", stored("hand-day", records()["day"])))

    outcome = export(book, exports_of(tmp_path), now=LATER, zone=BUDAPEST)

    assert outcome.result is ExportResult.EXPORTED
    assert outcome.identifiers == ("hand-day",)
    assert outcome.path is not None
    written = json.loads(outcome.path.read_text(encoding="utf-8"))
    assert [trade["id"] for trade in written["ledgerData"]["trades"]] == ["hand-day"]
    assert len(files_in(exports_of(tmp_path))) == 2


def test_a_coin_the_user_confirmed_and_saved_gets_its_card(tmp_path: Path) -> None:
    book, _ = book_with_two(tmp_path)

    outcome = export(SqliteStore(book.path), exports_of(tmp_path), now=NOW, zone=BUDAPEST)

    assert outcome.path is not None
    cards = json.loads(outcome.path.read_text(encoding="utf-8"))["ledgerData"]["assets"]
    assert "PIKA" in {card["symbol"] for card in cards}


# --- today is the person's today ------------------------------------------------


def test_today_is_the_current_moments_date_in_the_persons_zone(tmp_path: Path) -> None:
    late_evening = datetime(2026, 10, 4, 23, 30, tzinfo=timezone.utc)
    record = records()["day"]
    shanghai_day = OccurredTime(date(2026, 10, 5), TimePrecision.DAY, SHANGHAI)
    trade = stored("hand-shanghai", dataclasses.replace(record, occurred=shanghai_day))

    for zone, result in (
        (SHANGHAI, ExportResult.EXPORTED),
        ("America/Los_Angeles", ExportResult.REFUSED),
    ):
        book = MemoryStore()
        book.save(passage("p1", trade))
        outcome = export(book, tmp_path / zone.replace("/", "-"), now=late_evening, zone=zone)
        assert outcome.result is result, zone


# --- nothing written, nothing marked -------------------------------------------


def test_a_refused_export_says_every_reason_and_writes_and_marks_nothing(tmp_path: Path) -> None:
    book, _ = book_with_two(tmp_path)
    before_the_trades = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)

    outcome = export(book, exports_of(tmp_path), now=before_the_trades, zone=SHANGHAI)

    assert outcome.result is ExportResult.REFUSED
    assert [(issue.problem, issue.subject) for issue in outcome.issues] == [
        (ExportProblem.DATED_AFTER_TODAY, "hand-minute"),
        (ExportProblem.DATED_AFTER_TODAY, "hand-second"),
    ]
    assert not exports_of(tmp_path).exists()
    assert len(book.trades(Listing.NOT_EXPORTED)) == 2


def test_an_exports_folder_that_is_a_file_writes_and_marks_nothing(tmp_path: Path) -> None:
    book, _ = book_with_two(tmp_path)
    exports_of(tmp_path).write_text("not a folder", encoding="utf-8")

    outcome = export(book, exports_of(tmp_path), now=NOW, zone=BUDAPEST)

    assert outcome.result is ExportResult.NOT_WRITTEN
    assert outcome.problem is WriteProblem.CANNOT_WRITE
    assert outcome.detail
    assert exports_of(tmp_path).read_text(encoding="utf-8") == "not a folder"
    assert files_in(tmp_path / "data") == ["book.sqlite3", "exports"]
    assert len(book.trades(Listing.NOT_EXPORTED)) == 2


def test_a_file_of_the_same_name_is_never_replaced_and_nothing_is_marked(tmp_path: Path) -> None:
    book, _ = book_with_two(tmp_path)
    exports_of(tmp_path).mkdir(parents=True)
    earlier = exports_of(tmp_path) / backup_file_name(NOW)
    earlier.write_bytes(b"an earlier export of the same second\n")

    outcome = export(book, exports_of(tmp_path), now=NOW, zone=BUDAPEST)

    assert outcome.result is ExportResult.NOT_WRITTEN
    assert outcome.problem is WriteProblem.NAME_TAKEN
    assert earlier.read_bytes() == b"an earlier export of the same second\n"
    assert files_in(exports_of(tmp_path)) == [earlier.name]
    assert len(book.trades(Listing.NOT_EXPORTED)) == 2


def test_a_write_that_fails_half_way_leaves_no_file_behind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    book, _ = book_with_two(tmp_path)

    def disk_fails(_: int) -> None:
        raise OSError(5, "Input/output error (staged)")

    monkeypatch.setattr(export_file.os, "fsync", disk_fails)

    outcome = export(book, exports_of(tmp_path), now=NOW, zone=BUDAPEST)

    assert outcome.result is ExportResult.NOT_WRITTEN
    assert outcome.problem is WriteProblem.CANNOT_WRITE
    assert files_in(exports_of(tmp_path)) == []
    assert len(book.trades(Listing.NOT_EXPORTED)) == 2


def test_a_marking_that_fails_leaves_the_file_and_says_the_trades_will_come_again(
    tmp_path: Path,
) -> None:
    book = MemoryStore()
    book.save(passage("p1", stored("hand-minute", records()["minute"])))
    book.fail_next("mark_exported", StorageErrorKind.LOCKED)

    outcome = export(book, tmp_path, now=NOW, zone=BUDAPEST)

    assert outcome.result is ExportResult.NOT_MARKED
    assert outcome.error is not None
    assert outcome.error.kind is StorageErrorKind.LOCKED
    assert outcome.path is not None
    assert outcome.path.is_file()
    assert len(book.trades(Listing.NOT_EXPORTED)) == 1
    assert "write them again" in ExportResult.NOT_MARKED.value


def test_the_file_is_there_before_the_trades_are_marked(tmp_path: Path) -> None:
    seen: list[list[str]] = []
    book = MemoryStore()
    book.save(passage("p1", stored("hand-minute", records()["minute"])))
    marking = book.mark_exported

    def mark_and_look(mark: ExportMark) -> None:
        seen.append(files_in(tmp_path))
        marking(mark)

    book.mark_exported = mark_and_look  # type: ignore[method-assign]

    export(book, tmp_path, now=NOW, zone=BUDAPEST)

    assert seen == [[backup_file_name(NOW)]]


def test_a_failure_to_read_the_book_is_raised_before_anything_is_written(tmp_path: Path) -> None:
    book = MemoryStore()
    book.fail_next("trades", StorageErrorKind.DAMAGED)

    with pytest.raises(StorageError):
        export(book, tmp_path / "exports", now=NOW, zone=BUDAPEST)
    assert not (tmp_path / "exports").exists()


@pytest.mark.parametrize(
    ("now", "zone"), [(datetime(2026, 10, 9, 6, 0), BUDAPEST), (NOW, "Not/AZone")]
)
def test_the_moment_must_carry_an_offset_and_the_zone_be_a_zone(
    tmp_path: Path, now: datetime, zone: str
) -> None:
    with pytest.raises(ValueError):
        export(MemoryStore(), tmp_path, now=now, zone=zone)


def test_nothing_but_the_file_is_left_in_the_folder(tmp_path: Path) -> None:
    book, _ = book_with_two(tmp_path)

    export(book, exports_of(tmp_path), now=NOW, zone=BUDAPEST)

    assert files_in(exports_of(tmp_path)) == [backup_file_name(NOW)]
    assert not any(name.startswith(".") for name in os.listdir(exports_of(tmp_path)))
    assert BUILT_IN_TABLE.find("PIKA") is None
