"""Tests of the golden record of version 6: the program reads it, and reads it beside 1 to 5.

The golden record of version 6 is a committed file of three invented
entries made by this program's own code at version 6, against the demo
book, and never changed afterwards: a trade with all three kinds of mark
(ETH for 30 dollars at 240, the money guessed, the quantity worked out, the
price far from the market price), a trade with no mark at all (ADA, every
amount said, no market price), and a trade whose price was not compared,
its market price being in another money. Version 6 added "marks".

- The file is still the bytes that were committed.
- An entry made now has the same names as the golden ones, in order, and
  so do its marks and its price check.
- Version 5's golden entries have the names of one made now, "marks" left
  out, in order.
- A file holding entries of all six versions is read whole.
"""

from __future__ import annotations

import hashlib
import shutil
from decimal import Decimal
from pathlib import Path

from ledger_hand.flows.assistant_record import RECORD_VERSION, RecordRead, entry_for, read_record
from ledger_hand.flows.conversation import Said
from ledger_hand.flows.standing import LedgerKind
from ledger_hand.ledger.demo_book import DEMO_ASSETS, DEMO_TRADES, demo_ledger
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ledger.invented_book import INVENTED_NOW
from tests.flows.test_marks_examples import send

GOLDEN = Path(__file__).parent / "golden" / "assistant-record-v6.jsonl"
EARLIER = [
    Path(__file__).parent / "golden" / f"assistant-record-v{number}.jsonl"
    for number in (1, 2, 3, 4, 5)
]
# The digest of the file as committed. A golden sample is never changed.
GOLDEN_SHA256 = "e65a4479a49896763c4320fb82c11b11171d4379a1ccaeb7e2c29178cab0f7ab"

THREE_KINDS = (
    "今天上午10点花了30美金买了ETH，均价240，手续费0",
    {
        "side": "buy",
        "coin": "ETH",
        "total": "30美金",
        "price": "240",
        "fee": "0",
        "time": "今天上午10点",
    },
)
NO_MARK = (
    "今天上午10点买了100个ADA，价格5 USDT，共500 USDT，手续费0",
    {
        "side": "buy",
        "coin": "ADA",
        "quantity": "100个ADA",
        "price": "5 USDT",
        "total": "500 USDT",
        "fee": "0",
        "time": "今天上午10点",
    },
)
OTHER_MONEY = (
    "今天上午10点买了0.1个ETH，成交价2600 USDT，手续费0",
    {
        "side": "buy",
        "coin": "ETH",
        "quantity": "0.1个ETH",
        "price": "2600 USDT",
        "fee": "0",
        "time": "今天上午10点",
    },
)


def priced_in_dollars() -> FakeLedger:
    """The demo book, ETH's only market price in dollars."""
    return FakeLedger(
        assets=DEMO_ASSETS, trades=DEMO_TRADES, prices={("ETH", "USD"): Decimal("2700")}
    )


def made_now() -> list[tuple[str, Said]]:
    """The three things said, each against its own ledger, as the golden file was made."""
    made = []
    for (words, cells), ledger in (
        (THREE_KINDS, demo_ledger()),
        (NO_MARK, demo_ledger()),
        (OTHER_MONEY, priced_in_dollars()),
    ):
        said, _ = send(words, cells, ledger=ledger)
        made.append((words, said))
    return made


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


def test_the_current_code_reads_every_entry_of_version_six() -> None:
    entries = _read(GOLDEN).entries

    assert [entry["format_version"] for entry in entries] == [6, 6, 6]
    kinds = [[mark["kind"] for mark in entry["marks"][0]["marks"]] for entry in entries]
    assert kinds == [["computed", "suspicious", "inferred"], [], ["computed"]]
    checks = [entry["marks"][0]["price_check"]["verdict"] for entry in entries]
    assert checks == ["far", "no_market_price", "other_money"]
    assert [entry["marks"][0]["empty"] for entry in entries] == [[], [], []]


def test_an_entry_made_now_has_the_names_of_the_golden_ones() -> None:
    made = [entry_now(words, said) for words, said in made_now()]
    entries = _read(GOLDEN).entries

    # Version 7 added "manual" and "cash" and nothing else; the names of an entry
    # made now are checked against version 7's golden record, in test_golden_record_v7.py.
    assert RECORD_VERSION == 9
    for entry, now in zip(entries, made, strict=True):
        assert list(entry) == [name for name in now if name not in ("manual", "cash", "rates")]
        assert list(entry["marks"][0]) == list(now["marks"][0])  # type: ignore[index]
        assert list(entry["marks"][0]["price_check"]) == list(now["marks"][0]["price_check"])  # type: ignore[index]
    assert entries[0]["marks"] == made[0]["marks"]


def test_a_file_with_entries_of_all_six_versions_is_read_whole(tmp_path: Path) -> None:
    place = tmp_path / "assistant-record.jsonl"
    shutil.copyfile(EARLIER[0], place)
    with place.open("ab") as out:
        for earlier in EARLIER[1:]:
            out.write(earlier.read_bytes())
        out.write(GOLDEN.read_bytes())

    read = _read(place)

    versions = [entry["format_version"] for entry in read.entries]
    assert versions == [1] * 4 + [2] * 3 + [3] * 3 + [4] * 3 + [5] * 2 + [6] * 3
    assert all("marks" not in entry for entry in read.entries[:15])
    assert not read.cut_line
