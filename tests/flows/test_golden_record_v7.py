"""Tests of the golden record of version 7: the program reads it, and reads it beside 1 to 6.

The golden record of version 7 is a committed file of three invented
entries made by this program's own code at version 7, and never changed
afterwards: a question about cash answered with the ledger's balances
(USDT 1200.5, US dollars 830, yuan 0, euros 250), a deposit said, which
the assistant does not record, and the same question asked of a ledger
with no tool for cash balances. Version 7 added "manual" and "cash".

- The file is still the bytes that were committed.
- An entry made now has the same names as the golden ones, in order, and
  so do its "manual" and "cash".
- A file holding entries of all seven versions is read whole.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from ledger_hand.flows.assistant_record import RECORD_VERSION, RecordRead, entry_for, read_record
from ledger_hand.flows.conversation import Said
from ledger_hand.flows.standing import LedgerKind
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ledger.invented_book import INVENTED_NOW
from tests.flows.test_cash_balances_examples import k1, said_once

GOLDEN = Path(__file__).parent / "golden" / "assistant-record-v7.jsonl"
EARLIER = [
    Path(__file__).parent / "golden" / f"assistant-record-v{number}.jsonl"
    for number in (1, 2, 3, 4, 5, 6)
]
# The digest of the file as committed. A golden sample is never changed.
GOLDEN_SHA256 = "9e5425d6fd853000cf807ba06f1a46f8a94f2ba19fc65da9ab8a61c73c472bb9"

BALANCES = "我还有多少USDT"
DEPOSIT = "我今天入金了500 USDT"


def made_now() -> list[tuple[str, Said]]:
    """The three things said, each against its own ledger, as the golden file was made."""
    return [
        (BALANCES, said_once(BALANCES, k1())),
        (DEPOSIT, said_once(DEPOSIT, k1())),
        (BALANCES, said_once(BALANCES, FakeLedger())),
    ]


def entry_now(words: str, said: Said) -> dict[str, object]:
    return entry_for(
        said, words=words, at=INVENTED_NOW, model="invented-model", ledger=LedgerKind.DEMO
    )


def _read(place: Path) -> RecordRead:
    read = read_record(place)
    assert isinstance(read, RecordRead)
    return read


def test_the_file_is_still_the_bytes_that_were_committed() -> None:
    assert hashlib.sha256(GOLDEN.read_bytes()).hexdigest() == GOLDEN_SHA256


def test_the_current_code_reads_every_entry_of_version_seven() -> None:
    entries = _read(GOLDEN).entries

    assert [entry["format_version"] for entry in entries] == [7, 7, 7]
    assert [entry["route"] for entry in entries] == ["cash", "manual", "cash"]
    shown = entries[0]["cash"]
    assert shown["tool"] is True and shown["day"] == "2026-11-24"
    assert [(row["code"], row["balance"]) for row in shown["balances"]] == [
        ("USDT", "1200.5"),
        ("USD", "830"),
        ("CNY", "0"),
        ("EUR", "250"),
    ]
    assert entries[1]["manual"] == {"kinds": ["deposit"], "with_trade": False}
    assert entries[1]["cash"] is None
    assert entries[2]["cash"]["tool"] is False and entries[2]["cash"]["balances"] == []


def test_an_entry_made_now_has_the_names_of_the_golden_ones() -> None:
    made = [entry_now(words, said) for words, said in made_now()]
    entries = _read(GOLDEN).entries

    assert RECORD_VERSION == 8
    for entry, now in zip(entries, made, strict=True):
        assert list(entry) == [name for name in now if name != "rates"]
    assert list(entries[0]["cash"]) == list(made[0]["cash"])  # type: ignore[arg-type]
    assert list(entries[1]["manual"]) == list(made[1]["manual"])  # type: ignore[arg-type]
    assert entries[0]["cash"] == made[0]["cash"]


def test_a_file_with_entries_of_all_seven_versions_is_read_whole(tmp_path: Path) -> None:
    place = tmp_path / "assistant-record.jsonl"
    shutil.copyfile(EARLIER[0], place)
    with place.open("ab") as out:
        for earlier in EARLIER[1:]:
            out.write(earlier.read_bytes())
        out.write(GOLDEN.read_bytes())

    read = _read(place)

    versions = [entry["format_version"] for entry in read.entries]
    assert versions == [1] * 4 + [2] * 3 + [3] * 3 + [4] * 3 + [5] * 2 + [6] * 3 + [7] * 3
    assert all("cash" not in entry and "manual" not in entry for entry in read.entries[:18])
    assert not read.cut_line
