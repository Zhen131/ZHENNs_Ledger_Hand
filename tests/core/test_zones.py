"""Tests of time zone names: only a name spelled exactly as the zone database lists it is taken.

On a disk that does not tell capitals from small letters, Python loads
"factory" or "europe/budapest" as readily as the listed names, and the ledger
refuses a trade recorded in such a spelling. These tests go through every
listed name and its other spellings, and through the three places that take a
zone name: ``zones`` itself, the time of a trade and the reading of a time
phrase.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import available_timezones

import pytest

from ledger_hand.core.timeparse import read_time
from ledger_hand.core.trade import OccurredTime, TimePrecision
from ledger_hand.core.zones import NOT_ZONE_NAMES, is_zone_name, zone_named

LISTED = sorted(available_timezones())
TAKEN = [name for name in LISTED if name not in NOT_ZONE_NAMES]
NOW = datetime(2026, 10, 4, 10, 0, tzinfo=timezone.utc)


def other_spellings(name: str) -> set[str]:
    """``name`` in small letters, in capitals and with each letter's case swapped."""
    return {name.lower(), name.upper(), name.swapcase()} - {name}


def refused_everywhere(name: object) -> None:
    assert not is_zone_name(name)
    with pytest.raises(ValueError, match="not a time zone name"):
        zone_named(name)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="not a time zone name"):
        OccurredTime(date(2026, 10, 3), TimePrecision.DAY, name)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="not a time zone name"):
        read_time("昨天", NOW, name)  # type: ignore[arg-type]


def test_the_zone_database_lists_hundreds_of_names() -> None:
    assert len(TAKEN) > 300


@pytest.mark.parametrize(
    "name", ["Europe/Budapest", "UTC", "Asia/Kathmandu", "America/St_Johns", "Etc/GMT-14"]
)
def test_a_listed_name_is_taken_everywhere(name: str) -> None:
    assert is_zone_name(name)
    assert zone_named(name).key == name
    assert OccurredTime(date(2026, 10, 3), TimePrecision.DAY, name).time_zone == name
    assert read_time("昨天", NOW, name)


def test_every_listed_name_but_the_three_is_taken() -> None:
    assert [name for name in LISTED if not is_zone_name(name)] == sorted(
        NOT_ZONE_NAMES & set(LISTED)
    )
    for name in TAKEN:
        assert zone_named(name).key == name


def test_no_other_spelling_of_a_listed_name_is_taken() -> None:
    taken = set(TAKEN)
    spellings = {other for name in LISTED for other in other_spellings(name)} - taken

    assert len(spellings) > 300
    assert [other for other in sorted(spellings) if is_zone_name(other)] == []


@pytest.mark.parametrize(
    "name",
    sorted({other for name in NOT_ZONE_NAMES for other in other_spellings(name)} | NOT_ZONE_NAMES)
    + ["europe/budapest", "EUROPE/BUDAPEST", "utc", "Utc", "asia/kathmandu", "America/St_johns"],
)
def test_a_name_spelled_otherwise_is_refused_everywhere(name: str) -> None:
    refused_everywhere(name)


@pytest.mark.parametrize(
    "name",
    [
        "",
        " Europe/Budapest",
        "Europe/Budapest ",
        "Europe//Budapest",
        "Europe/Budapest/",
        "/Europe/Budapest",
        "../zoneinfo/UTC",
        "Europe/Budapest\N{NULL}",
        "Europe/Bud\N{LATIN SMALL LETTER A WITH ACUTE}pest",
        "\N{FULLWIDTH LATIN CAPITAL LETTER U}TC",
        "+02:00",
        "GMT+2",
    ],
)
def test_text_that_is_no_listed_name_is_refused_everywhere(name: str) -> None:
    refused_everywhere(name)


@pytest.mark.parametrize("name", [None, 5, b"UTC"])
def test_a_name_that_is_not_text_is_no_zone_name(name: object) -> None:
    assert not is_zone_name(name)
    with pytest.raises(ValueError, match="not a time zone name"):
        zone_named(name)  # type: ignore[arg-type]


def test_the_answer_does_not_change_between_calls() -> None:
    assert [is_zone_name(name) for name in LISTED] == [is_zone_name(name) for name in LISTED]
