"""Tests of the golden record of version 3: the program reads it, and reads it beside 1 and 2.

The golden record of version 3 is a committed file of three invented
entries made by this program's own code at version 3, and never changed
afterwards: a trade said with its time and price in number words, tidied
and sent; the same kind of trade said in digits, nothing tidied; and a
screenshot's text, which is not tidied. Version 3 added "read_as".

- The file is still the bytes that were committed.
- An entry made now has the same names as the golden ones, in order, and
  the same names in each line of "sent".
- A file holding entries of all three versions is read whole.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from ledger_hand.flows.assistant_record import (
    RecordRead,
    entry_for,
    read_record,
)
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ledger.invented_book import INVENTED_NOW
from tests.flows.test_conversation_screenshot import SHARES, SHARES_ROW, typed

GOLDEN = Path(__file__).parent / "golden" / "assistant-record-v3.jsonl"
VERSION_ONE = Path(__file__).parent / "golden" / "assistant-record-v1.jsonl"
VERSION_TWO = Path(__file__).parent / "golden" / "assistant-record-v2.jsonl"
# The digest of the file as committed. A golden sample is never changed.
GOLDEN_SHA256 = "c91612d334b4df85617dcad379ac5c5c0c25ee5494e98981e9f4e80dc596a5e4"


def _read(place: Path) -> RecordRead:
    read = read_record(place)
    assert isinstance(read, RecordRead)
    return read


def test_the_file_is_still_the_bytes_that_were_committed() -> None:
    assert hashlib.sha256(GOLDEN.read_bytes()).hexdigest() == GOLDEN_SHA256


def test_the_current_code_reads_every_entry_of_version_three() -> None:
    entries = _read(GOLDEN).entries

    assert [entry["format_version"] for entry in entries] == [3, 3, 3]
    assert [entry["route"] for entry in entries] == ["model", "model", "screenshot"]
    tidied, plain, screenshot = entries
    assert tidied["said"].startswith("二六年十一月二十号下午十五点三十分")
    assert tidied["read_as"]["text"].startswith("2026年11月20号下午15点30分")
    assert [change["kind"] for change in tidied["read_as"]["changes"]] == [
        "year",
        "date",
        "date",
        "clock",
        "clock",
        "number",
    ]
    assert tidied["read_as"]["changes"][0] == {"kind": "year", "said": "二六", "written": "2026"}
    assert tidied["trades"][0]["occurred"] == "2026-11-20T15:30:00+01:00"
    assert plain["read_as"] is None
    assert screenshot["read_as"] is None


def test_an_entry_of_version_three_keeps_every_name_an_entry_of_version_four_has() -> None:
    # Version 4 added "asset_picks" and nothing else; the names of an entry made now
    # are checked against version 4's golden record, in test_golden_record_v4.py.
    said, _ = typed(SHARES, [SHARES_ROW], FakeLedger())
    made = entry_for(said, words=SHARES, at=INVENTED_NOW, model="invented-model")
    entries = _read(GOLDEN).entries

    for entry in entries:
        assert list(entry) == [
            name
            for name in made
            if name not in ("asset_picks", "ledger", "marks", "manual", "cash")
        ]
    assert list(entries[0]["trades"][0]) == list(made["trades"][0])
    assert list(entries[0]["sent"][0]) == list(made["sent"][0])


def test_a_file_with_entries_of_all_three_versions_is_read_whole(tmp_path: Path) -> None:
    place = tmp_path / "assistant-record.jsonl"
    shutil.copyfile(VERSION_ONE, place)
    with place.open("ab") as out:
        out.write(VERSION_TWO.read_bytes())
        out.write(GOLDEN.read_bytes())

    read = _read(place)

    assert [entry["format_version"] for entry in read.entries] == [1, 1, 1, 1, 2, 2, 2, 3, 3, 3]
    assert "read_as" not in read.entries[0]
    assert "read_as" not in read.entries[4]
    assert not read.cut_line
