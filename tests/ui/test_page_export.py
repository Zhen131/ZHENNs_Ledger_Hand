"""Tests of Export on the page: the file, what is said, what is marked, and the warning beside it.

Export writes the saved trades not exported yet into a new file in the
exports folder, says where and how many, and marks them; a second press
finds nothing new. When the export is refused, or its file cannot be
written, every reason is said and nothing is marked. The warning not to
import the file into the ledger yet stands beside the button whatever
happens. Nothing breaks. Every passage and reply below is invented.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from streamlit.testing.v1 import AppTest

from ledger_hand.core.book import Listing
from ledger_hand.export.backup import ExportProblem
from ledger_hand.ports import StorageErrorKind, StoragePort
from ledger_hand.settings import DataPlaces
from ledger_hand.storage.sqlite_store import SqliteStore
from ledger_hand.ui.export_panel import EXPORT_KEY, WARNING
from ledger_hand.ui.session import PARTS_KEY
from tests.fakes.memory_store import MemoryStore
from tests.fakes.routed_model import RoutedModel
from tests.flows.scripted_flow import row, screened, table
from tests.ui.app_harness import SAVE_KEY, button, open_page, press, send
from tests.ui.page_harness import note, open_with, warning

SPOT = screened(("spot_trade", "Bought 0.02 BTC"))
COMPLETE = (
    "Bought 0.02 BTC at 94,900 yesterday, fee 1 USDT; sold 1.5 ETH at 3,180 yesterday, fee 2 USDT"
)
COMPLETE_ROWS = table(
    row(
        side="buy", coin="BTC", quantity="0.02 BTC", price="94,900", fee="1 USDT", time="yesterday"
    ),
    row(side="sell", coin="ETH", quantity="1.5 ETH", price="3,180", fee="2 USDT", time="yesterday"),
)
# Two days before the trades' day: in the person's zone they lie after today.
EARLIER = datetime(2026, 10, 5, 21, 0, tzinfo=ZoneInfo("Europe/Budapest"))


def two_complete() -> RoutedModel:
    return RoutedModel(screen=[SPOT], extraction=[COMPLETE_ROWS])


def saved_two(book: StoragePort, data: Path) -> AppTest:
    """The page once two trades are saved and none exported."""
    page = press(send(open_with(two_complete(), book, data), COMPLETE), SAVE_KEY)
    assert len(book.trades(Listing.NOT_EXPORTED)) == 2
    return page


def pending(book: StoragePort) -> int:
    return len(book.trades(Listing.NOT_EXPORTED))


def exports(data: Path) -> list[Path]:
    folder = DataPlaces(data).exports
    return sorted(folder.iterdir()) if folder.is_dir() else []


def with_clock(page: AppTest, moment: datetime) -> AppTest:
    parts = page.session_state[PARTS_KEY]
    page.session_state[PARTS_KEY] = dataclasses.replace(parts, clock=lambda: moment)
    return page


# --- V-1: two trades exported, then nothing new --------------------------------


def test_export_writes_the_two_saved_trades_says_where_and_marks_them(tmp_path: Path) -> None:
    data = tmp_path / "data"
    book = SqliteStore(DataPlaces(data).book)
    page = saved_two(book, data)
    identifiers = [listed.trade.id for listed in book.trades(Listing.ALL)]

    page = press(page, EXPORT_KEY)

    assert not page.exception
    (written,) = exports(data)
    assert written.parent == DataPlaces(data).exports
    assert "incremental" in written.name
    assert note(page) == (
        "success",
        f"Exported 2 trade(s) to {written}. They are marked as exported, so the next export "
        "leaves them out.",
    )
    assert pending(book) == 0
    assert all(listed.exported for listed in book.trades(Listing.ALL))
    held = json.loads(written.read_text(encoding="utf-8"))
    assert sorted(trade["id"] for trade in held["ledgerData"]["trades"]) == sorted(identifiers)
    assert warning(page) == f":red[{WARNING}]"

    page = press(page, EXPORT_KEY)

    assert not page.exception
    tone, words = note(page) or ("", "")
    assert tone == "info"
    assert words.startswith("Nothing new to export")
    assert exports(data) == [written]
    assert warning(page) == f":red[{WARNING}]"


def test_with_nothing_saved_export_says_there_is_nothing_new(tmp_path: Path) -> None:
    data = tmp_path / "data"
    page = press(open_with(RoutedModel(), SqliteStore(DataPlaces(data).book), data), EXPORT_KEY)

    assert not page.exception
    assert note(page) == (
        "info",
        "Nothing new to export: every saved trade has been exported already, so no file was "
        "written.",
    )
    assert exports(data) == []


# --- the warning stands beside the button whatever happens ----------------------


def test_the_warning_says_not_to_import_the_file_and_why() -> None:
    assert WARNING.startswith("Do not import this file into the ledger yet")
    assert "replaces the whole ledger" in WARNING


def test_the_warning_stands_beside_export_before_during_and_after(tmp_path: Path) -> None:
    data = tmp_path / "data"
    book = SqliteStore(DataPlaces(data).book)
    asking = "Sold 1.5 ETH at 3,180 yesterday"
    reply = table(row(side="sell", coin="ETH", quantity="1.5 ETH", price="3,180", time="yesterday"))
    page = open_with(RoutedModel(screen=[SPOT], extraction=[reply]), book, data)
    seen = [warning(page)]

    page = send(page, asking)
    seen.append(warning(page))
    page = press(page, EXPORT_KEY)
    seen.append(warning(page))
    (data / "exports").mkdir(parents=True, exist_ok=True)
    seen.append(warning(press(page, EXPORT_KEY)))

    assert seen == [f":red[{WARNING}]"] * 4


def test_without_a_data_folder_export_cannot_be_pressed(tmp_path: Path) -> None:
    page = open_page(RoutedModel(), SqliteStore(tmp_path / "book.sqlite3"))

    assert button(page, EXPORT_KEY).disabled
    assert warning(page) == f":red[{WARNING}]"


# --- V-2: refused, or not written: every reason, nothing marked --------------------


def test_an_export_refused_gives_every_reason_and_marks_nothing(tmp_path: Path) -> None:
    data = tmp_path / "data"
    book = SqliteStore(DataPlaces(data).book)
    page = with_clock(saved_two(book, data), EARLIER)
    identifiers = sorted(listed.trade.id for listed in book.trades(Listing.ALL))

    page = press(page, EXPORT_KEY)

    assert not page.exception
    tone, words = note(page) or ("", "")
    assert tone == "error"
    first, *reasons = words.split("\n")
    assert first.startswith("Nothing was exported and nothing was marked as exported")
    assert sorted(reasons) == sorted(
        f"• {ExportProblem.DATED_AFTER_TODAY.value}: {identifier}" for identifier in identifiers
    )
    assert pending(book) == 2
    assert exports(data) == []


def test_an_export_file_that_cannot_be_written_marks_nothing(tmp_path: Path) -> None:
    data = tmp_path / "data"
    book = SqliteStore(DataPlaces(data).book)
    page = saved_two(book, data)
    in_the_way = DataPlaces(data).exports
    in_the_way.write_text("a file where the exports folder belongs", encoding="utf-8")

    page = press(page, EXPORT_KEY)

    assert not page.exception
    tone, words = note(page) or ("", "")
    assert tone == "error"
    assert words.startswith(
        "Nothing was exported and nothing was marked as exported. The file could not be written."
    )
    assert pending(book) == 2
    assert in_the_way.read_text(encoding="utf-8") == "a file where the exports folder belongs"


def test_a_file_written_but_not_marked_says_where_it_is_and_that_it_comes_again(
    tmp_path: Path,
) -> None:
    data = tmp_path / "data"
    book = MemoryStore()
    page = saved_two(book, data)
    book.fail_next("mark_exported", StorageErrorKind.LOCKED)

    page = press(page, EXPORT_KEY)

    assert not page.exception
    (written,) = exports(data)
    tone, words = note(page) or ("", "")
    assert tone == "error"
    assert words.startswith(f"The file was written to {written}, but its trades could not be")
    assert "next export writes them again" in words
    assert "in use by another program" in words
    assert pending(book) == 2


def test_a_book_that_cannot_be_read_exports_nothing(tmp_path: Path) -> None:
    data = tmp_path / "data"
    book = MemoryStore()
    page = saved_two(book, data)
    book.fail_next("trades", StorageErrorKind.LOCKED)

    page = press(page, EXPORT_KEY)

    assert not page.exception
    tone, words = note(page) or ("", "")
    assert tone == "error"
    assert words.startswith(
        "Nothing was exported: the book could not be used. The book is in use by another program"
    )
    assert exports(data) == []
    assert pending(book) == 2
