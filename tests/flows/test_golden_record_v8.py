"""Tests of the golden record of version 8: the program reads it, and reads it beside 1 to 7.

The golden record of version 8 is a committed file of three invented
entries made by this program's own code at version 8, and never changed
afterwards: two shares of KO bought for 128 euros at 69.5 dollars a share,
its rate compared with an AAPL trade paid in euros; the same with "美金",
its money guessed from KO's last trade; and BTC bought for 95 euros at
98000 USDT, with no earlier trade to compare its rate with. Version 8
added "rates".

- The file is still the bytes that were committed.
- An entry made now has the same names as the golden ones, in order, and
  so does each of its "rates".
- A file holding entries of all eight versions is read whole.
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
from tests.flows.test_paid_apart_examples import E1, E1_ROW, E3, E3_ROW, one

GOLDEN = Path(__file__).parent / "golden" / "assistant-record-v8.jsonl"
EARLIER = [
    Path(__file__).parent / "golden" / f"assistant-record-v{number}.jsonl"
    for number in (1, 2, 3, 4, 5, 6, 7)
]
# The digest of the file as committed. A golden sample is never changed.
GOLDEN_SHA256 = "4af704574164d1356939abc88b75aec46aaafc6b1fa8cfd9c619774faeaeedca"

COIN = "今天上午10点花了95欧元买了0.001个BTC，价格98000 USDT，手续费0"
COIN_ROW = {
    "side": "buy",
    "coin": "BTC",
    "quantity": "0.001个BTC",
    "price": "98000 USDT",
    "total": "95欧元",
    "fee": "0",
    "time": "今天上午10点",
}


def made_now() -> list[tuple[str, Said]]:
    """The three things said, each against its own ledger, as the golden file was made."""
    return [
        (E1, one(E1, E1_ROW, books.jia())),
        (E3, one(E3, E3_ROW, books.jia())),
        (COIN, one(COIN, COIN_ROW, books.jia())),
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


def test_the_current_code_reads_every_entry_of_version_eight() -> None:
    entries = _read(GOLDEN).entries

    assert [entry["format_version"] for entry in entries] == [8, 8, 8]
    (named,) = entries[0]["rates"]
    assert (named["rate"], named["money"], named["paid"], named["said_price"]) == (
        "1.0859375",
        "USD",
        "EUR",
        "69.5",
    )
    assert named["guessed_from"] is None
    assert (named["reference"]["rate"], named["reference"]["asset"]) == ("1.0859", "AAPL")
    (guessed,) = entries[1]["rates"]
    assert guessed["guessed_from"]["trade"] == "t-ko"
    (coin,) = entries[2]["rates"]
    assert (coin["rate"], coin["money"], coin["reference"]) == ("1.0315789474", "USDT", None)


def test_an_entry_made_now_has_the_names_of_the_golden_ones() -> None:
    made = [entry_now(words, said) for words, said in made_now()]
    entries = _read(GOLDEN).entries

    assert RECORD_VERSION == 8
    for entry, now in zip(entries, made, strict=True):
        assert list(entry) == list(now)
        assert [list(rate) for rate in entry["rates"]] == [  # type: ignore[union-attr]
            list(rate)
            for rate in now["rates"]  # type: ignore[attr-defined]
        ]
    assert entries[0]["rates"] == made[0]["rates"]


def test_a_file_with_entries_of_all_eight_versions_is_read_whole(tmp_path: Path) -> None:
    place = tmp_path / "assistant-record.jsonl"
    shutil.copyfile(EARLIER[0], place)
    with place.open("ab") as out:
        for earlier in EARLIER[1:]:
            out.write(earlier.read_bytes())
        out.write(GOLDEN.read_bytes())

    read = _read(place)

    versions = [entry["format_version"] for entry in read.entries]
    assert versions == (
        [1] * 4 + [2] * 3 + [3] * 3 + [4] * 3 + [5] * 2 + [6] * 3 + [7] * 3 + [8] * 3
    )
    assert all("rates" not in entry for entry in read.entries[:21])
    assert not read.cut_line
