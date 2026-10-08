"""Tests of the command line with the book: saving after asking, listing and exporting.

Each run uses an invented passage, fake models and a data folder in a
temporary directory; the working directory is another, empty one, which
must stay empty. Without ``--save``, ``--list`` or ``--export`` the script
is what it always was: the tests of that are in ``test_record_trades.py``,
unchanged.
"""

from __future__ import annotations

import io
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from ledger_hand.export.file_name import backup_file_name
from ledger_hand.flows.progress import Tuning
from ledger_hand.settings import DATA_DIRECTORY_VARIABLE, DataPlaces, SettingsError
from scripts import record_trades
from tests.fakes.routed_model import RoutedModel
from tests.flows.scripted_flow import NOW, ZONE, row, screened, table

TWO_TRADES = "今天下午 3 点买了 0.5 ETH，又卖了 2 个 SOL，价格 150"
TWO_ROWS = table(
    row(side="buy", coin="ETH", quantity="0.5 ETH", time="今天下午 3 点"),
    row(side="sell", coin="SOL", quantity="2 个", price="150"),
)
SPOT = screened(("spot_trade", "买了 0.5 ETH"))
ANSWERS = ["3420", "none", "0.2 USDT", "昨天下午 4 点"]
LATER = NOW + timedelta(hours=1)


def two_trades() -> RoutedModel:
    return RoutedModel(screen=[SPOT], extraction=[TWO_ROWS])


@pytest.fixture
def places(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> DataPlaces:
    """A data folder in a temporary directory, and another, empty one to work in."""
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    return DataPlaces(tmp_path / "data")


def run(
    arguments: list[str],
    places: DataPlaces | None,
    *,
    stdin: str = "",
    model: RoutedModel | None = None,
    now: datetime = NOW,
) -> tuple[int, str]:
    out = io.StringIO()
    status = record_trades.main(
        arguments,
        stdin=io.StringIO(stdin),
        out=out,
        model=model or RoutedModel(),
        tuning=Tuning(),
        now=now,
        zone=ZONE,
        places=places,
    )
    return status, out.getvalue()


def everything_in(folder: Path) -> list[str]:
    return sorted(str(path.relative_to(folder)) for path in folder.rglob("*"))


def record_and_save(places: DataPlaces, *answers: str) -> tuple[int, str]:
    return run(
        ["--save", "--answers", "-", TWO_TRADES],
        places,
        stdin="\n".join(answers) + "\n",
        model=two_trades(),
    )


def test_records_are_listed_then_one_removed_then_saved_listed_and_exported(
    places: DataPlaces, tmp_path: Path
) -> None:
    status, shown = record_and_save(places, *ANSWERS, "remove 2", "done", "save")

    assert status == record_trades.DONE
    asked = shown.index("Save 1 record(s) to the book?")
    assert shown.index("Records:") < shown.index("> remove 2") < asked
    assert shown.index("1 record(s); nothing is saved yet.") < asked
    assert "> save" in shown[asked:]
    assert "saved 1 record(s):" in shown

    status, listed = run(["--list"], places)

    assert status == 0
    assert "1. hand-" in listed
    assert ": buy 0.5 ETH at 3420, total 1710 (total worked out), fee 0 USDT," in listed
    assert "saved 2026-10-07T21:00:00+02:00; not exported" in listed
    assert "1 trade(s) saved; 1 not exported yet." in listed
    assert "SOL" not in listed

    status, exported = run(["--export"], places, now=LATER)

    assert status == 0
    assert "exported: the file was written and its trades are marked as exported" in exported
    assert "1 trade(s) in it" in exported
    file = places.exports / backup_file_name(LATER)
    trades = json.loads(file.read_text(encoding="utf-8"))["ledgerData"]["trades"]
    assert [trade["assetSymbol"] for trade in trades] == ["ETH"]

    status, listed = run(["--list"], places)

    assert "exported 2026-10-07T22:00:00+02:00" in listed
    assert "1 trade(s) saved; 0 not exported yet." in listed

    status, again = run(["--export"], places, now=LATER + timedelta(seconds=5))

    assert status == 0
    assert "nothing_new: there is nothing new to export" in again
    assert everything_in(places.directory) == [
        "exports",
        f"exports/{backup_file_name(LATER)}",
        "ledger-hand-book.sqlite3",
    ]
    assert list((tmp_path / "work").iterdir()) == []


@pytest.mark.parametrize("last", [[], ["no"], ["later"], ["  "]])
def test_without_the_answer_save_nothing_is_saved(places: DataPlaces, last: list[str]) -> None:
    status, shown = record_and_save(places, *ANSWERS, "done", *last)

    assert status == record_trades.NOTHING_KEPT
    assert "Save 2 record(s) to the book?" in shown
    assert "not saved: nothing was kept" in shown
    _, listed = run(["--list"], places)
    assert "0 trade(s) saved; 0 not exported yet." in listed


@pytest.mark.parametrize("said", ["save", "SAVE", " yes ", "y", "存", "保存"])
def test_these_answers_save(places: DataPlaces, said: str) -> None:
    status, _ = record_and_save(places, *ANSWERS, "done", said)

    assert status == 0
    _, listed = run(["--list"], places)
    assert "2 trade(s) saved" in listed


def test_the_same_passage_again_is_reminded_and_not_held_back(places: DataPlaces) -> None:
    record_and_save(places, *ANSWERS, "done", "save")

    status, shown = record_and_save(places, *ANSWERS, "done", "no")

    assert status == record_trades.NOTHING_KEPT
    reminder = shown.index("Reminder: this passage, or one that differs from it only in spacing")
    assert "was saved on 2026-10-07, 2 trade(s)" in shown
    assert reminder < shown.index("[Trade 1 of 2: price]")


def test_records_dropped_are_not_asked_about(places: DataPlaces) -> None:
    status, shown = record_and_save(places, "3420", "cancel")

    assert status == record_trades.NOTHING_KEPT
    assert "Save" not in shown


def test_a_book_that_cannot_be_used_stops_with_its_own_status(places: DataPlaces) -> None:
    places.directory.parent.mkdir(parents=True, exist_ok=True)
    places.directory.write_text("a file where the data folder should be", encoding="utf-8")

    for arguments in (["--list"], ["--export"], ["--save", "--answers", "-", TWO_TRADES]):
        status, shown = run(arguments, places, model=two_trades())
        assert status == record_trades.BOOK_FAILED == 4, arguments
        assert "the book failed: inaccessible:" in shown, arguments


def test_an_export_that_is_refused_says_why_and_keeps_nothing(places: DataPlaces) -> None:
    record_and_save(places, *ANSWERS, "done", "save")

    status, shown = run(["--export"], places, now=NOW - timedelta(days=3))

    assert status == record_trades.NOTHING_KEPT
    assert "refused: the trades cannot be exported as they are" in shown
    assert "a trade's date, in its own time zone, is after today: hand-" in shown
    assert not places.exports.exists()


def test_a_data_folder_setting_that_is_refused_stops_the_script(
    places: DataPlaces, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refused() -> DataPlaces:
        raise SettingsError(f"{DATA_DIRECTORY_VARIABLE}: refused (staged)")

    monkeypatch.setattr(record_trades, "load_data_places", refused)

    for arguments in (["--list"], ["--save", TWO_TRADES]):
        status, shown = run(arguments, None, model=two_trades())
        assert status == record_trades.CANNOT_START, arguments
        assert "setting refused" in shown


def test_the_data_folder_is_read_from_the_setting(
    places: DataPlaces, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(DATA_DIRECTORY_VARIABLE, str(tmp_path / "named"))

    status, shown = run(["--list"], None)

    assert status == 0
    assert (tmp_path / "named" / "ledger-hand-book.sqlite3").is_file()
    assert list((tmp_path / "work").iterdir()) == []


def test_without_an_option_no_book_is_opened_and_no_folder_made(
    places: DataPlaces, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(DATA_DIRECTORY_VARIABLE, str(tmp_path / "named"))

    status, shown = run(
        ["--answers", "-", TWO_TRADES], None, stdin="\n".join(ANSWERS), model=two_trades()
    )

    assert status == 0
    assert "2 record(s); nothing is saved yet." in shown
    assert "Save" not in shown
    assert not (tmp_path / "named").exists()
    assert not places.directory.exists()
    assert list((tmp_path / "work").iterdir()) == []


def test_saving_listing_and_exporting_are_one_at_a_time(places: DataPlaces) -> None:
    with pytest.raises(SystemExit) as raised:
        run(["--save", "--list"], places)

    assert raised.value.code == 2
