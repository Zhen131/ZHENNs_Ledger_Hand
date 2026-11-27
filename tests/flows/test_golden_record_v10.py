"""Tests of the golden record of version 10: the program reads it, and reads it beside 1 to 9.

The golden record of version 10 is a committed file of three invented
entries made by this program's own code at version 10, and never changed
afterwards: the three things said of the golden record of version 9, the
first asked of DeepSeek (deepseek-v4-pro at https://api.deepseek.com), the
second of a cloud service at an address set by hand, the third of the
local model. Version 10 added "plug", "service" and "address" to "models".

- The file is still the bytes that were committed.
- An entry made now has the same names as the golden ones, in order, and
  so does its "models".
- A file holding entries of all ten versions is read whole.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from ledger_hand.flows.assistant_record import RECORD_VERSION, RecordRead, entry_for, read_record
from ledger_hand.flows.standing import LedgerKind
from ledger_hand.ledger.invented_book import INVENTED_NOW
from tests.flows.test_golden_record_v9 import made_now

GOLDEN = Path(__file__).parent / "golden" / "assistant-record-v10.jsonl"
EARLIER = [
    Path(__file__).parent / "golden" / f"assistant-record-v{number}.jsonl"
    for number in range(1, 10)
]
# The digest of the file as committed. A golden sample is never changed.
GOLDEN_SHA256 = "37b6cc029b365c298126db1b294ece8905a8437b13db60098bd12d5cca398f1e"


def _read(place: Path) -> RecordRead:
    read = read_record(place)
    assert isinstance(read, RecordRead)
    return read


def test_the_file_is_still_the_bytes_that_were_committed() -> None:
    assert hashlib.sha256(GOLDEN.read_bytes()).hexdigest() == GOLDEN_SHA256


def test_the_current_code_reads_every_entry_of_version_ten() -> None:
    entries = _read(GOLDEN).entries

    assert [entry["format_version"] for entry in entries] == [10, 10, 10]
    assert [entry["models"] for entry in entries] == [
        {
            "tools": "deepseek-v4-pro",
            "vision": None,
            "plug": "deepseek",
            "service": "DeepSeek",
            "address": "https://api.deepseek.com",
        },
        {
            "tools": "invented-cloud-model",
            "vision": None,
            "plug": "cloud",
            "service": None,
            "address": "https://api.example.com/v1",
        },
        {
            "tools": "qwen2.5:7b",
            "vision": None,
            "plug": "local",
            "service": None,
            "address": "http://127.0.0.1:11434",
        },
    ]


def test_an_entry_made_now_has_the_names_of_the_golden_ones() -> None:
    made = [
        entry_for(
            said,
            words=words,
            at=INVENTED_NOW,
            model="invented-model",
            ledger=LedgerKind.DEMO,
            plug="deepseek",
            service="DeepSeek",
            address="https://api.deepseek.com",
        )
        for words, said in made_now()
    ]
    entries = _read(GOLDEN).entries

    assert RECORD_VERSION == 10
    for entry, now in zip(entries, made, strict=True):
        assert list(entry) == list(now)
        assert list(entry["models"]) == list(now["models"])  # type: ignore[call-overload]


def test_a_file_with_entries_of_all_ten_versions_is_read_whole(tmp_path: Path) -> None:
    place = tmp_path / "assistant-record.jsonl"
    shutil.copyfile(EARLIER[0], place)
    with place.open("ab") as out:
        for earlier in EARLIER[1:]:
            out.write(earlier.read_bytes())
        out.write(GOLDEN.read_bytes())

    read = _read(place)

    versions = [entry["format_version"] for entry in read.entries]
    assert versions == (
        [1] * 4
        + [2] * 3
        + [3] * 3
        + [4] * 3
        + [5] * 2
        + [6] * 3
        + [7] * 3
        + [8] * 3
        + [9] * 3
        + [10] * 3
    )
    assert all("plug" not in entry["models"] for entry in read.entries[:27])
    assert not read.cut_line
