"""Tests of the plain file of names the user answered: read, kept, and left alone when broken.

Every file is in a temporary folder; the data folder is never touched.
Every name and figure is invented.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from ledger_hand.core.stock_names import RememberedName
from ledger_hand.flows.asset_names import NAMES_VERSION, NamesFile, read_names, remember
from ledger_hand.flows.standing import LedgerKind

DAY = date(2026, 11, 20)


def demo(place: Path) -> NamesFile:
    return NamesFile(place, LedgerKind.DEMO)


def test_no_file_gives_no_answer_and_may_be_written(tmp_path: Path) -> None:
    read = read_names(demo(tmp_path / "asset-names.json"))

    assert read.names == ()
    assert read.writable


def test_an_answer_kept_is_read_back_on_the_same_kind_of_ledger_only(tmp_path: Path) -> None:
    place = tmp_path / "folder" / "asset-names.json"

    assert remember(demo(place), "小可", "KO", DAY)

    assert read_names(demo(place)).names == (RememberedName("小可", "KO", DAY),)
    assert read_names(NamesFile(place, LedgerKind.PAGE)).names == ()
    assert json.loads(place.read_text(encoding="utf-8")) == {
        "version": NAMES_VERSION,
        "demo": [{"name": "小可", "code": "KO", "day": "2026-11-20"}],
        "page": [],
    }


def test_a_later_answer_for_the_same_name_takes_the_place_of_the_earlier(tmp_path: Path) -> None:
    place = tmp_path / "asset-names.json"
    remember(demo(place), "小可", "KO", DAY)
    remember(demo(place), "大可", "KO", DAY)

    remember(demo(place), "小可", "PEP", date(2026, 11, 21))

    assert read_names(demo(place)).names == (
        RememberedName("大可", "KO", DAY),
        RememberedName("小可", "PEP", date(2026, 11, 21)),
    )


def test_an_entry_written_by_hand_that_may_not_be_remembered_is_passed_over(
    tmp_path: Path,
) -> None:
    place = tmp_path / "asset-names.json"
    place.write_text(
        json.dumps(
            {
                "version": 1,
                "demo": [
                    {"name": "股票", "code": "MSFT", "day": "2026-11-01"},
                    {"name": "小可", "code": "KO", "day": "2026-11-02"},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    read = read_names(demo(place))

    assert read.names == (RememberedName("小可", "KO", date(2026, 11, 2)),)
    assert read.writable


@pytest.mark.parametrize(
    "text",
    [
        "not json at all",
        json.dumps({"version": 2, "demo": [{"name": "小可", "code": "KO", "day": "2026-11-02"}]}),
        json.dumps({"version": True, "demo": []}),
        json.dumps(["小可", "KO"]),
        json.dumps({"version": 1, "demo": {"小可": "KO"}}),
    ],
)
def test_a_file_that_cannot_be_read_is_taken_as_empty_and_never_written(
    tmp_path: Path, text: str
) -> None:
    place = tmp_path / "asset-names.json"
    place.write_text(text, encoding="utf-8")
    before = place.read_bytes()

    read = read_names(demo(place))

    assert read.names == ()
    assert not read.writable
    assert not remember(demo(place), "大可", "KO", DAY)
    assert place.read_bytes() == before


@pytest.mark.parametrize(
    "entry",
    [
        {"name": "大可", "day": "2026-11-02"},
        {"name": "大可", "code": "BRK.B", "day": "2026-11-02"},
        {"name": "大可", "code": "KO", "day": "the second"},
        "大可 KO",
    ],
)
def test_a_bad_entry_is_passed_over_the_rest_used_and_the_file_never_written(
    tmp_path: Path, entry: object
) -> None:
    place = tmp_path / "asset-names.json"
    good = {"name": "小可", "code": "KO", "day": "2026-11-02"}
    place.write_text(
        json.dumps({"version": 1, "demo": [entry, good]}, ensure_ascii=False), encoding="utf-8"
    )
    before = place.read_bytes()

    read = read_names(demo(place))

    assert read.names == (RememberedName("小可", "KO", date(2026, 11, 2)),)
    assert not read.writable
    assert not remember(demo(place), "老可", "PEP", DAY)
    assert place.read_bytes() == before


def test_the_answers_of_the_other_kind_of_ledger_are_kept_as_they_were(tmp_path: Path) -> None:
    place = tmp_path / "asset-names.json"
    remember(NamesFile(place, LedgerKind.PAGE), "小可", "KO", DAY)

    remember(demo(place), "小可", "PEP", DAY)

    assert read_names(NamesFile(place, LedgerKind.PAGE)).names == (
        RememberedName("小可", "KO", DAY),
    )
    assert read_names(demo(place)).names == (RememberedName("小可", "PEP", DAY),)
    assert not list(tmp_path.glob(".*partial"))
