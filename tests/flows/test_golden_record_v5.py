"""Tests of the golden record of version 5: the program reads it, and reads it beside 1 to 4.

The golden record of version 5 is a committed file of two invented entries
made by this program's own code at version 5, and never changed
afterwards: the same share bought, said once to the demo ledger and once
to the ledger page. Both were made against the demo book; only "ledger"
tells them apart. Version 5 added "ledger".

- The file is still the bytes that were committed.
- An entry made now has the same names as the golden ones, in order.
- A file holding entries of all five versions is read whole.
- Neither a port nor a token is among the names.
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
from ledger_hand.flows.standing import LedgerKind
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ledger.invented_book import INVENTED_NOW
from tests.flows.test_conversation_screenshot import SHARES, SHARES_ROW, typed

GOLDEN = Path(__file__).parent / "golden" / "assistant-record-v5.jsonl"
EARLIER = [
    Path(__file__).parent / "golden" / f"assistant-record-v{number}.jsonl"
    for number in (1, 2, 3, 4)
]
# The digest of the file as committed. A golden sample is never changed.
GOLDEN_SHA256 = "fdaf7877717e71c11d472b838173709095fea3575298e8dc93c77cab4085229f"


def _read(place: Path) -> RecordRead:
    read = read_record(place)
    assert isinstance(read, RecordRead)
    return read


def test_the_file_is_still_the_bytes_that_were_committed() -> None:
    assert hashlib.sha256(GOLDEN.read_bytes()).hexdigest() == GOLDEN_SHA256


def test_the_current_code_reads_every_entry_of_version_five() -> None:
    entries = _read(GOLDEN).entries

    assert [entry["format_version"] for entry in entries] == [5, 5]
    assert [entry["ledger"] for entry in entries] == ["demo", "page"]
    assert [entry["said"] for entry in entries] == [SHARES, SHARES]


def test_an_entry_made_now_has_the_names_of_the_golden_ones() -> None:
    said, _ = typed(SHARES, [SHARES_ROW], FakeLedger())
    made = entry_for(
        said, words=SHARES, at=INVENTED_NOW, model="invented-model", ledger=LedgerKind.PAGE
    )

    # Version 6 added "marks" and nothing else; the names of an entry made now
    # are checked against version 6's golden record, in test_golden_record_v6.py.
    assert RECORD_VERSION == 10
    assert made["ledger"] == "page"
    for entry in _read(GOLDEN).entries:
        assert list(entry) == [
            name for name in made if name not in ("marks", "manual", "cash", "rates")
        ]


def test_an_entry_names_no_port_and_no_token() -> None:
    names = set(_read(GOLDEN).entries[1])

    assert not {name for name in names if "port" in name or "token" in name}


def test_a_file_with_entries_of_all_five_versions_is_read_whole(tmp_path: Path) -> None:
    place = tmp_path / "assistant-record.jsonl"
    shutil.copyfile(EARLIER[0], place)
    with place.open("ab") as out:
        for earlier in EARLIER[1:]:
            out.write(earlier.read_bytes())
        out.write(GOLDEN.read_bytes())

    read = _read(place)

    versions = [entry["format_version"] for entry in read.entries]
    assert versions == [1] * 4 + [2] * 3 + [3] * 3 + [4] * 3 + [5] * 2
    assert all("ledger" not in entry for entry in read.entries[:13])
    assert not read.cut_line
