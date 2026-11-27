"""Tests of the golden record of version 9: the program reads it, and reads it beside 1 to 8.

The golden record of version 9 is a committed file of three invented
entries made by this program's own code at version 9, and never changed
afterwards: two shares of KO bought on 2026-11-20 for 100 euros at 54
dollars a share, its rate compared with the ledger's own exchange rate,
fetched the other way round ("1 USD = 0.925 EUR"); the same against a rate
typed in by hand 15 days before ("1 EUR = 1.30 USD"), far; and the same
against a ledger with no tool for exchange rates, compared with an AAPL
trade paid in euros instead. Version 9 added "ledger_rate" to each of
"rates".

- The file is still the bytes that were committed.
- An entry made now has the same names as the golden ones, in order, and
  so does each of its "rates" and each "ledger_rate".
- A file holding entries of all nine versions is read whole.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from ledger_hand.flows.assistant_record import RECORD_VERSION, RecordRead, entry_for, read_record
from ledger_hand.flows.conversation import Said
from ledger_hand.flows.standing import LedgerKind
from ledger_hand.ledger.invented_book import INVENTED_NOW
from tests.flows import paid_apart_books as books
from tests.flows.test_ledger_rate_examples import EUR, SAID, USD, rate, said_to, with_rates

GOLDEN = Path(__file__).parent / "golden" / "assistant-record-v9.jsonl"
EARLIER = [
    Path(__file__).parent / "golden" / f"assistant-record-v{number}.jsonl"
    for number in (1, 2, 3, 4, 5, 6, 7, 8)
]
# The digest of the file as committed. A golden sample is never changed.
GOLDEN_SHA256 = "179567b34db8cc886c27796ba9858e7c0ab0dc44dd0a6961791867afddb71a6e"


def made_now() -> list[tuple[str, Said]]:
    """The three things said, each against its own ledger, as the golden file was made."""
    online = rate(USD, EUR, "0.925", "2026-11-19", "online", "frankfurter")
    return [
        (SAID, said_to(with_rates(online))),
        (SAID, said_to(with_rates(rate(EUR, USD, "1.30", "2026-11-05")))),
        (SAID, said_to(books.jia())),
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


def test_the_current_code_reads_every_entry_of_version_nine() -> None:
    entries = _read(GOLDEN).entries

    assert [entry["format_version"] for entry in entries] == [9, 9, 9]
    (compared,) = entries[0]["rates"]
    ledger = compared["ledger_rate"]
    assert (ledger["outcome"], ledger["converted"], ledger["inverted"]) == (
        "compared",
        "1.0810810811",
        True,
    )
    assert ledger["row"]["onlineSourceId"] == "frankfurter"
    assert (ledger["gap_percent"], ledger["far"], ledger["days_apart"]) == ("0.1", False, 1)
    assert compared["reference"] is None
    (far,) = entries[1]["rates"]
    assert (far["ledger_rate"]["far"], far["ledger_rate"]["days_apart"]) == (True, 15)
    (old,) = entries[2]["rates"]
    assert old["ledger_rate"]["outcome"] == "no_tool"
    assert old["reference"]["asset"] == "AAPL"


def test_an_entry_made_now_has_the_names_of_the_golden_ones() -> None:
    made = [entry_now(words, said) for words, said in made_now()]
    entries = _read(GOLDEN).entries

    assert RECORD_VERSION == 9
    for entry, now in zip(entries, made, strict=True):
        assert list(entry) == list(now)
        for kept, fresh in zip(entry["rates"], now["rates"], strict=True):  # type: ignore[call-overload]
            assert list(kept) == list(fresh)
            assert list(kept["ledger_rate"]) == list(fresh["ledger_rate"])
    assert entries[0]["rates"] == made[0]["rates"]


def test_a_file_with_entries_of_all_nine_versions_is_read_whole(tmp_path: Path) -> None:
    place = tmp_path / "assistant-record.jsonl"
    shutil.copyfile(EARLIER[0], place)
    with place.open("ab") as out:
        for earlier in EARLIER[1:]:
            out.write(earlier.read_bytes())
        out.write(GOLDEN.read_bytes())

    read = _read(place)

    versions = [entry["format_version"] for entry in read.entries]
    assert versions == (
        [1] * 4 + [2] * 3 + [3] * 3 + [4] * 3 + [5] * 2 + [6] * 3 + [7] * 3 + [8] * 3 + [9] * 3
    )
    assert all(
        "ledger_rate" not in rate for entry in read.entries[:24] for rate in entry.get("rates", [])
    )
    assert not read.cut_line
