"""Tests of the assistant's record on this machine: what an entry holds, adding, reading, clearing.

Every entry is made from invented results through the real flows, and every
file lies in the test's temporary folder.

- An entry holds its version, the moment with its offset, the words said,
  each tool asked for with its arguments as given (numbers written as
  text), the trades proposed with every amount as text beside its own
  money, each trade not sent and why, the reminders said, the proposals
  sent, and the models and prompt versions; a screenshot's entry says it
  came from a screenshot and holds no picture.
- Three entries added make a file of exactly three lines, each read back.
- A file with an entry of a newer version, or a line in the middle that
  cannot be read, is not one byte changed, and nothing is added.
- A last line cut off half-way is passed over, cut off before the next
  entry, and the file is whole again.
- Beyond the most kept, only the most recent stay, and the file is a new
  one put in its place.
- No data folder adds nothing and says so; a folder that cannot be written
  says so.
- Clearing deletes the file, whatever it holds.
"""

from __future__ import annotations

import json
import os
import stat
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from ledger_hand.flows import assistant_record
from ledger_hand.flows.assistant_record import (
    RECORD_VERSION,
    Cleared,
    Kept,
    NotKept,
    RecordProblem,
    RecordRead,
    Unreadable,
    clear_record,
    entry_for,
    keep,
    read_record,
)
from ledger_hand.flows.conversation import AssistantChat, say
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ledger.invented_book import INVENTED_NOW, INVENTED_ZONE
from ledger_hand.ports import ToolCall, ToolReply
from tests.fakes.routed_model import RoutedModel
from tests.fakes.scripted_model import scripted_record
from tests.flows.scripted_flow import screened
from tests.flows.test_conversation_screenshot import (
    OTHER_UNIT,
    OTHER_UNIT_ROW,
    SHARES,
    SHARES_ROW,
    from_reading,
    typed,
)
from tests.folder_lock import allow_writing_on_windows, refuse_writing_on_windows

MODEL = "invented-model"


def an_entry(minutes: int = 0) -> dict[str, Any]:
    said, _ = typed(SHARES, [SHARES_ROW], FakeLedger())
    return entry_for(said, words=SHARES, at=INVENTED_NOW + timedelta(minutes=minutes), model=MODEL)


def a_line(version: int = RECORD_VERSION, said: str = "invented") -> bytes:
    return json.dumps({"format_version": version, "said": said}).encode() + b"\n"


@pytest.fixture
def place(tmp_path: Path) -> Path:
    return tmp_path / "data" / "assistant-record.jsonl"


# --- what an entry holds -----------------------------------------------------------


def test_an_entry_holds_the_trade_sent_its_amounts_as_text_beside_its_own_money() -> None:
    entry = an_entry()

    assert entry["format_version"] == RECORD_VERSION
    assert entry["at"] == "2026-11-24T23:55:00+01:00"
    assert entry["said"] == SHARES
    assert entry["route"] == "model"
    assert entry["words_by"] == "program"
    (trade,) = entry["trades"]
    for name in ("quantity", "price", "total", "fee"):
        assert isinstance(trade[name], str)
    assert (trade["price"], trade["quote"], trade["fee"], trade["fee_asset"]) == (
        "410",
        "USD",
        "1",
        "USD",
    )
    assert entry["sent"] == [
        {"number": 1, "what": "record", "proposal": "proposal-1", "status": "pending"}
    ]
    assert entry["reminders"] == ["numbers_left_over"]
    assert entry["models"] == {"tools": MODEL, "vision": None}
    assert set(entry["prompts"]) == {"assistant", "screening", "extraction"}


def test_an_entry_holds_why_a_trade_was_not_sent() -> None:
    said, _ = typed(OTHER_UNIT, [OTHER_UNIT_ROW], FakeLedger())

    entry = entry_for(said, words=OTHER_UNIT, at=INVENTED_NOW, model=MODEL)

    assert entry["left_out"] == [
        {
            "number": 1,
            "why": "quantity_in_other_unit",
            "asset": "ETH",
            "quantity": "25",
            "unit": "U",
        }
    ]
    assert entry["sent"] == []
    assert entry["endings"]["recorded"] == "nothing_to_send"


def test_each_tool_is_kept_with_its_arguments_as_given_numbers_as_text_and_those_dropped() -> None:
    call = ToolCall(
        name="propose_trade_add", arguments={"asset": "BTC", "quantity": 0.02, "side": "buy"}
    )
    model = RoutedModel(
        tools=[ToolReply(text="", calls=(call,), record=scripted_record())],
        screen=[screened()],
    )
    said = say(
        AssistantChat(),
        "invented words",
        model=model,
        ledger=FakeLedger(),
        now=INVENTED_NOW,
        zone=INVENTED_ZONE,
        max_steps=6,
    )

    entry = entry_for(said, words="invented words", at=INVENTED_NOW, model=MODEL)

    (step,) = entry["steps"]
    (kept,) = step["calls"]
    assert kept["tool"] == "propose_trade_add"
    assert kept["arguments"] == {"asset": "BTC", "quantity": "0.02", "side": "buy"}
    assert kept["handled"] == "taken"
    assert set(kept["dropped"]) == {"asset", "quantity", "side"}


def test_a_screenshots_entry_says_so_and_names_the_vision_model() -> None:
    said, _ = from_reading(SHARES, [SHARES_ROW], FakeLedger())
    assert said.recorded is not None
    passage = said.recorded.progress.passage

    entry = entry_for(said, words=passage, at=INVENTED_NOW, model=MODEL, vision_model="seeing")

    assert entry["from_screenshot"] is True
    assert entry["route"] == "screenshot"
    assert entry["said"] == passage
    assert entry["steps"] == []
    assert entry["models"] == {"tools": MODEL, "vision": "seeing"}
    assert "reading" in entry["prompts"]


def test_a_moment_without_an_offset_is_refused() -> None:
    said, _ = typed(SHARES, [SHARES_ROW], FakeLedger())

    with pytest.raises(ValueError, match="offset"):
        entry_for(said, words=SHARES, at=INVENTED_NOW.replace(tzinfo=None), model=MODEL)


# --- adding and reading ------------------------------------------------------------


def test_three_entries_make_three_lines_each_read_back_with_its_version(place: Path) -> None:
    for minutes in range(3):
        assert keep(place, an_entry(minutes)) == Kept(minutes + 1)

    assert place.read_bytes().count(b"\n") == 3
    read = read_record(place)
    assert isinstance(read, RecordRead)
    assert [entry["format_version"] for entry in read.entries] == [RECORD_VERSION] * 3
    assert [entry["at"] for entry in read.entries] == [an_entry(m)["at"] for m in range(3)]


def test_no_file_reads_as_no_entries_and_makes_nothing(place: Path) -> None:
    assert read_record(place) == RecordRead(())
    assert not place.parent.exists()


@pytest.mark.parametrize(
    ("lines", "problem"),
    [
        ([a_line(), a_line(RECORD_VERSION + 1), a_line()], RecordProblem.NEWER_VERSION),
        ([a_line(), b"not an entry\n", a_line()], RecordProblem.LINE_NOT_READ),
        ([a_line(), b'{"said": "no version"}\n'], RecordProblem.LINE_NOT_READ),
        ([b'{"format_version": true}\n'], RecordProblem.LINE_NOT_READ),
        ([b"\xff\xfe\n"], RecordProblem.LINE_NOT_READ),
        ([a_line(), b"\n", a_line()], RecordProblem.LINE_NOT_READ),
    ],
    ids=["newer", "not json", "no version", "a true version", "not utf-8", "an empty line"],
)
def test_a_file_that_cannot_be_read_is_left_byte_for_byte_and_nothing_is_added(
    place: Path, lines: list[bytes], problem: RecordProblem
) -> None:
    place.parent.mkdir(parents=True)
    place.write_bytes(b"".join(lines))
    before = place.read_bytes()

    kept = keep(place, an_entry())
    read = read_record(place)

    assert isinstance(kept, NotKept)
    assert kept.problem is problem
    assert isinstance(read, Unreadable)
    assert read.problem is problem
    assert place.read_bytes() == before


def test_a_last_line_cut_half_way_is_passed_over_then_cut_off_before_the_next(
    place: Path,
) -> None:
    place.parent.mkdir(parents=True)
    whole = a_line(said="one")
    place.write_bytes(whole + b'{"format_version": 1, "sa')

    read = read_record(place)
    assert isinstance(read, RecordRead)
    assert [entry["said"] for entry in read.entries] == ["one"]
    assert read.cut_line

    assert keep(place, an_entry()) == Kept(2)

    data = place.read_bytes()
    assert data.startswith(whole)
    assert data.endswith(b"\n")
    again = read_record(place)
    assert isinstance(again, RecordRead)
    assert [entry["said"] for entry in again.entries] == ["one", SHARES]
    assert not again.cut_line


def test_beyond_the_most_kept_only_the_most_recent_stay_in_a_new_file(
    place: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(assistant_record, "KEPT_AT_MOST", 3)
    place.parent.mkdir(parents=True)
    place.write_bytes(b"".join(a_line(said=str(n)) for n in range(3)))
    first_file = place.stat().st_ino

    assert keep(place, an_entry()) == Kept(3)

    read = read_record(place)
    assert isinstance(read, RecordRead)
    assert [entry["said"] for entry in read.entries] == ["1", "2", SHARES]
    assert place.stat().st_ino != first_file
    assert sorted(p.name for p in place.parent.iterdir()) == [place.name]


def test_the_most_kept_is_named_with_its_reason() -> None:
    assert assistant_record.KEPT_AT_MOST == 1000


def test_without_a_data_folder_nothing_is_added_and_it_says_so() -> None:
    assert keep(None, an_entry()) == NotKept(RecordProblem.NO_DATA_FOLDER)


@pytest.fixture
def locked(tmp_path: Path) -> Iterator[Path]:
    folder = tmp_path / "locked"
    folder.mkdir()
    folder.chmod(stat.S_IRUSR | stat.S_IXUSR)
    refuse_writing_on_windows(folder)  # Windows ignores the write bit on a folder
    yield folder
    allow_writing_on_windows(folder)
    folder.chmod(stat.S_IRWXU)


@pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0, reason="the superuser writes anywhere"
)
def test_a_folder_that_cannot_be_written_says_so_and_makes_nothing(locked: Path) -> None:
    kept = keep(locked / "assistant-record.jsonl", an_entry())

    assert isinstance(kept, NotKept)
    assert kept.problem is RecordProblem.CANNOT_WRITE
    assert kept.detail
    assert list(locked.iterdir()) == []


@pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0, reason="the superuser writes anywhere"
)
def test_a_full_file_in_a_folder_that_cannot_be_written_is_left_as_it_is(
    locked: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(assistant_record, "KEPT_AT_MOST", 1)
    allow_writing_on_windows(locked)
    locked.chmod(stat.S_IRWXU)
    place = locked / "assistant-record.jsonl"
    place.write_bytes(a_line())
    locked.chmod(stat.S_IRUSR | stat.S_IXUSR)
    refuse_writing_on_windows(locked)  # Windows ignores the write bit on a folder

    kept = keep(place, an_entry())

    assert isinstance(kept, NotKept)
    assert kept.problem is RecordProblem.CANNOT_WRITE
    assert place.read_bytes() == a_line()
    assert [p.name for p in locked.iterdir()] == [place.name]


# --- clearing ------------------------------------------------------------------------


def test_clearing_deletes_the_file_even_one_that_cannot_be_read(place: Path) -> None:
    place.parent.mkdir(parents=True)
    place.write_bytes(a_line(RECORD_VERSION + 1))

    assert clear_record(place) is Cleared.DELETED
    assert not place.exists()
    assert clear_record(place) is Cleared.NOTHING_THERE
