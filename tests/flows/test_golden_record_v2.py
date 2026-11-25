"""Tests of the golden record of version 2: the program reads it, and makes entries like it.

Version 2 (68B2, 2026-11-25) keeps, for a call to record, one line in
"sent" for each trade sent: its number in what was said, and its own
proposal, or the code the ledger turned it down with. The golden record is
a committed file of three invented entries made by this program's own code
at version 2, and never changed afterwards: two trades sent at once of which
the ledger took one; a share bought with dollars, taken; a deletion.

- The file is still the bytes that were committed.
- The current code reads it and gets the three entries with what they hold.
- An entry made now has the same names, and the same names in each line of
  "sent", so a change to what an entry holds cannot go without a new
  version and a new sample.
- A file holding entries of both versions is read whole.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from ledger_hand.flows.assistant_record import (
    RECORD_VERSION,
    RecordRead,
    entry_for,
    read_record,
)
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ledger.invented_book import INVENTED_NOW
from tests.flows.test_conversation_screenshot import SHARES, SHARES_ROW, typed

GOLDEN = Path(__file__).parent / "golden" / "assistant-record-v2.jsonl"
VERSION_ONE = Path(__file__).parent / "golden" / "assistant-record-v1.jsonl"
# The digest of the file as committed. A golden sample is never changed.
GOLDEN_SHA256 = "923f100d865de4a06f24a886f57102e7a8877efa698185c9a8017bcc3eaef9a7"


def golden() -> RecordRead:
    read = read_record(GOLDEN)
    assert isinstance(read, RecordRead)
    return read


def test_the_file_is_still_the_bytes_that_were_committed() -> None:
    assert hashlib.sha256(GOLDEN.read_bytes()).hexdigest() == GOLDEN_SHA256


def test_the_current_code_reads_every_entry_of_version_two() -> None:
    read = golden()

    assert [entry["format_version"] for entry in read.entries] == [2, 2, 2]
    assert [entry["endings"]["recorded"] for entry in read.entries] == [
        "partly_sent",
        "sent",
        None,
    ]
    assert read.entries[2]["endings"]["edited"] == "sent"


def test_two_trades_sent_at_once_keep_a_line_each_the_one_turned_down_with_its_code() -> None:
    partly, shares, deleted = golden().entries

    assert partly["sent"] == [
        {"number": 1, "what": "record", "proposal": "proposal-1", "status": "pending"},
        {
            "number": 2,
            "what": "record",
            "proposal": None,
            "status": "refused",
            "code": "sells_more_than_held",
        },
    ]
    assert [trade["asset"] for trade in partly["trades"]] == ["BTC", "ETH"]
    assert shares["sent"] == [
        {"number": 1, "what": "record", "proposal": "proposal-1", "status": "pending"}
    ]
    assert deleted["sent"] == [
        {"number": None, "what": "delete", "proposal": "proposal-1", "status": "pending"}
    ]


def test_an_entry_made_now_has_the_names_of_the_golden_ones() -> None:
    said, _ = typed(SHARES, [SHARES_ROW], FakeLedger())
    made = entry_for(said, words=SHARES, at=INVENTED_NOW, model="invented-model")
    entries = golden().entries

    assert RECORD_VERSION == 2
    for entry in entries:
        assert list(entry) == list(made)
    assert list(entries[1]["trades"][0]) == list(made["trades"][0])
    assert list(entries[1]["sent"][0]) == list(made["sent"][0])


def test_a_file_of_both_versions_is_read_whole(tmp_path: Path) -> None:
    both = tmp_path / "assistant-record.jsonl"
    shutil.copyfile(VERSION_ONE, both)
    with both.open("ab") as file:
        file.write(GOLDEN.read_bytes())

    read = read_record(both)

    assert isinstance(read, RecordRead)
    assert [entry["format_version"] for entry in read.entries] == [1, 1, 1, 1, 2, 2, 2]
