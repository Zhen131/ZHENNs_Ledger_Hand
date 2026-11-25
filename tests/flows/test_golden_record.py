"""Tests of the golden record of version 1: the program still reads it, and adds to a copy of it.

The golden record is a committed file of four invented entries made by this
program's own code at version 1, and never changed afterwards. Every test
copies it into a temporary folder first and works on the copy only.

- The file is still the bytes that were committed.
- The current code reads the copy and gets the four entries with what they
  hold: a trade not sent and why, a reminder said and a share priced in
  dollars in the first; a question in the second; a screenshot in the third;
  the model's own answer in the fourth.
- An entry made now has the same names as the golden ones; what one line
  of "sent" holds changed at version 2, checked against the golden record of
  version 2 (``test_golden_record_v2.py``).
- Adding to the copy keeps the four entries as they were.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from ledger_hand.flows.assistant_record import (
    Kept,
    RecordRead,
    entry_for,
    keep,
    read_record,
)
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ledger.invented_book import INVENTED_NOW
from tests.flows.test_conversation_screenshot import SHARES, SHARES_ROW, typed

GOLDEN = Path(__file__).parent / "golden" / "assistant-record-v1.jsonl"
# The digest of the file as committed. A golden sample is never changed.
GOLDEN_SHA256 = "f75426f37e96b704e3ec81df835594e5962c46a4b5f43c8fc8359ab2659aab29"


def copy_of(folder: Path) -> Path:
    target = folder / "assistant-record.jsonl"
    shutil.copyfile(GOLDEN, target)
    return target


def read_copy(folder: Path) -> RecordRead:
    read = read_record(copy_of(folder))
    assert isinstance(read, RecordRead)
    return read


def test_the_file_is_still_the_bytes_that_were_committed() -> None:
    assert hashlib.sha256(GOLDEN.read_bytes()).hexdigest() == GOLDEN_SHA256


def test_the_current_code_reads_every_entry_of_version_one(tmp_path: Path) -> None:
    read = read_copy(tmp_path)

    assert len(read.entries) == 4
    assert not read.cut_line
    assert [entry["format_version"] for entry in read.entries] == [1, 1, 1, 1]
    assert [entry["route"] for entry in read.entries] == ["model", "model", "screenshot", "model"]
    assert [entry["words_by"] for entry in read.entries] == [
        "program",
        "question",
        "program",
        "model",
    ]


def test_the_first_entry_holds_a_trade_left_out_a_reminder_and_a_share_in_dollars(
    tmp_path: Path,
) -> None:
    first = read_copy(tmp_path).entries[0]

    assert first["left_out"] == [
        {
            "number": 1,
            "why": "quantity_in_other_unit",
            "asset": "ETH",
            "quantity": "25",
            "unit": "U",
        }
    ]
    assert first["reminders"] == ["numbers_left_over"]
    (trade,) = first["trades"]
    assert (trade["asset"], trade["price"], trade["quote"], trade["fee"], trade["fee_asset"]) == (
        "MSFT",
        "410",
        "USD",
        "1",
        "USD",
    )
    assert first["sent"] == [{"proposal": "proposal-1", "what": "record", "status": "pending"}]
    assert first["steps"][0]["calls"][0]["tool"] == "propose_trade_add"
    assert first["models"] == {"tools": "qwen2.5:7b", "vision": None}


def test_the_other_entries_hold_a_question_a_screenshot_and_the_models_answer(
    tmp_path: Path,
) -> None:
    _, question, screenshot, answer = read_copy(tmp_path).entries

    assert question["question_by"] == "program"
    assert question["endings"]["recorded"] == "asking"
    assert question["sent"] == []
    assert screenshot["from_screenshot"] is True
    assert screenshot["models"] == {"tools": "qwen2.5:7b", "vision": "qwen3-vl:8b"}
    assert "reading" in screenshot["prompts"]
    assert answer["endings"]["turn"] == "answered"
    assert answer["reply"] == "I can look that up in the ledger for you."


def test_an_entry_of_version_one_keeps_every_name_an_entry_of_version_two_has() -> None:
    # Version 2 changed what one line of "sent" holds, not the names of an entry
    # (68B2); the names of an entry made now are checked against version 2's
    # golden record, in test_golden_record_v2.py.
    golden = read_record(GOLDEN)
    assert isinstance(golden, RecordRead)
    said, _ = typed(SHARES, [SHARES_ROW], FakeLedger())
    made = entry_for(said, words=SHARES, at=INVENTED_NOW, model="invented-model")

    for entry in golden.entries:
        assert list(entry) == [
            name for name in made if name not in ("read_as", "asset_picks", "ledger")
        ]


def test_adding_to_a_copy_keeps_the_golden_entries_as_they_were(tmp_path: Path) -> None:
    place = copy_of(tmp_path)
    said, _ = typed(SHARES, [SHARES_ROW], FakeLedger())

    kept = keep(place, entry_for(said, words=SHARES, at=INVENTED_NOW, model="invented-model"))

    assert kept == Kept(5)
    assert place.read_bytes().startswith(GOLDEN.read_bytes())
    assert hashlib.sha256(GOLDEN.read_bytes()).hexdigest() == GOLDEN_SHA256
