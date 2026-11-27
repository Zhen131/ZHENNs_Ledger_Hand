"""Tests of the golden record of version 4: the program reads it, and reads it beside 1, 2 and 3.

The golden record of version 4 is a committed file of three invented
entries made by this program's own code at version 4, against the demo
book, and never changed afterwards: a share said by its Chinese name that
the model picked from the ledger's list and that was sent; a name the
model said the list lacks, asked about; and a share said by its code,
with nothing handed over. Version 4 added "asset_picks".

- The file is still the bytes that were committed.
- An entry made now has the same names as the golden ones, in order, and
  the same names in each line of "asset_picks".
- A file holding entries of all four versions is read whole.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest

from ledger_hand.flows import conversation
from ledger_hand.flows.assistant_record import (
    RECORD_VERSION,
    RecordRead,
    entry_for,
    read_record,
)
from ledger_hand.ledger.invented_book import INVENTED_NOW
from tests.flows.scripted_flow import copied
from tests.flows.test_conversation_asset_pick import model_for, pick, row_of, said_as, talk

GOLDEN = Path(__file__).parent / "golden" / "assistant-record-v4.jsonl"
EARLIER = [
    Path(__file__).parent / "golden" / f"assistant-record-v{number}.jsonl" for number in (1, 2, 3)
]
# The digest of the file as committed. A golden sample is never changed.
GOLDEN_SHA256 = "06065e7727572dd7adc8a129b73d30df522783748dd8f429777170661ab8f438"


@pytest.fixture(autouse=True)
def _picking_on(monkeypatch: pytest.MonkeyPatch) -> None:
    """The step is off on the assistant; these tests turn it on to try it."""
    monkeypatch.setattr(conversation, "ASSISTANT_PICKS_ASSETS", True)
    # The program's table of company names would match these names before the model
    # is asked; it is turned off, so that the step these tests lock is reached.
    monkeypatch.setattr(conversation, "ASSISTANT_NAME_TABLE", False)


def _read(place: Path) -> RecordRead:
    read = read_record(place)
    assert isinstance(read, RecordRead)
    return read


def test_the_file_is_still_the_bytes_that_were_committed() -> None:
    assert hashlib.sha256(GOLDEN.read_bytes()).hexdigest() == GOLDEN_SHA256


def test_the_current_code_reads_every_entry_of_version_four() -> None:
    entries = _read(GOLDEN).entries

    assert [entry["format_version"] for entry in entries] == [4, 4, 4]
    taken, missed, plain = entries
    assert taken["asset_picks"] == [
        {"word": "微软的股票", "said": "微软", "code": "MSFT", "picked": True, "miss": None}
    ]
    assert taken["trades"][0]["asset"] == "MSFT"
    assert taken["prompts"]["asset_pick"] == "asset-pick-1"
    assert missed["asset_picks"] == [
        {"word": "特斯拉", "said": "特斯拉", "code": "", "picked": False, "miss": "none_on_list"}
    ]
    assert missed["endings"]["recorded"] == "asking"
    assert plain["asset_picks"] == []
    assert "asset_pick" not in plain["prompts"]


def test_an_entry_made_now_has_the_names_of_the_golden_ones() -> None:
    words = said_as("微软的股票")
    (said,) = talk(model_for(words, [row_of("微软的股票")], picks=[pick("微软", "MSFT")]), words)
    made = entry_for(said, words=words, at=INVENTED_NOW, model="invented-model")
    entries = _read(GOLDEN).entries

    # Version 5 added "ledger" and nothing else; the names of an entry made now
    # are checked against version 5's golden record, in test_golden_record_v5.py.
    assert RECORD_VERSION == 9
    for entry in entries:
        assert list(entry) == [
            name for name in made if name not in ("ledger", "marks", "manual", "cash", "rates")
        ]
    assert list(entries[0]["asset_picks"][0]) == list(made["asset_picks"][0])
    assert list(entries[0]["trades"][0]) == list(made["trades"][0])


def test_a_file_with_entries_of_all_four_versions_is_read_whole(tmp_path: Path) -> None:
    place = tmp_path / "assistant-record.jsonl"
    shutil.copyfile(EARLIER[0], place)
    with place.open("ab") as out:
        for earlier in EARLIER[1:]:
            out.write(earlier.read_bytes())
        out.write(GOLDEN.read_bytes())

    read = _read(place)

    assert [entry["format_version"] for entry in read.entries] == [
        1,
        1,
        1,
        1,
        2,
        2,
        2,
        3,
        3,
        3,
        4,
        4,
        4,
    ]
    assert all("asset_picks" not in entry for entry in read.entries[:10])
    assert not read.cut_line


def test_an_answer_keeps_no_pick_the_start_kept() -> None:
    words = "2026年11月20号14:30在IBKR买了2股微软，100美元一股"
    no_fee = row_of("微软") | {"fee": ""}
    model = model_for(words, [no_fee], picks=[pick("微软", "MSFT")], answers=[copied("1美元")])
    first, last = talk(model, words, "1美元")

    begun = entry_for(first, words=words, at=INVENTED_NOW, model="invented-model")
    answered = entry_for(last, words="1美元", at=INVENTED_NOW, model="invented-model")

    assert [found["code"] for found in begun["asset_picks"]] == ["MSFT"]
    assert answered["asset_picks"] == []
