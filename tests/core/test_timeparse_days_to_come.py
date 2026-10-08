"""Tests of a date said without its year, or a day without its month, that is still to come.

Said on 7 October, "10月8号" may mean last year's 8 October or be a slip of
the tongue; the program does not pick one and answers "ambiguous". The same
goes for "8号" said on the 7th. Only when this year (this month) has no such
day at all is it looked for further back, as before. The current moment is
always passed in; every phrase below is invented.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from ledger_hand.core.timeparse import (
    Refusal,
    TimeRecognised,
    TimeRefused,
    read_time,
    write_time,
)

BUDAPEST = "Europe/Budapest"
# A morning in Budapest.
NOW = datetime(2026, 10, 7, 9, 15, tzinfo=ZoneInfo(BUDAPEST))


def day_of(text: str, now: datetime = NOW) -> str:
    reading = read_time(text, now, BUDAPEST)
    if isinstance(reading, TimeRefused):
        return reading.reason.name
    assert isinstance(reading, TimeRecognised), reading
    return f"{write_time(reading.time)} {reading.time.precision.value}"


@pytest.mark.parametrize(
    "text", ["10月8号", "Dec 25", "8号", "Oct 8", "12月25号", "8 October", "31号", "10月8号 9点"]
)
def test_a_day_still_to_come_this_year_or_this_month_is_ambiguous(text: str) -> None:
    assert read_time(text, NOW, BUDAPEST) == TimeRefused(Refusal.AMBIGUOUS)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("10月7号", "2026-10-07 day"),
        ("10月6号", "2026-10-06 day"),
        ("9月8号", "2026-09-08 day"),
        ("7号", "2026-10-07 day"),
        ("1号", "2026-10-01 day"),
        ("Jan 1", "2026-01-01 day"),
        ("10月6号晚上9点", "2026-10-06T21:00:00+02:00 minute"),
    ],
)
def test_a_day_that_has_come_is_read_as_before(text: str, expected: str) -> None:
    assert day_of(text) == expected


def test_a_leap_day_in_a_year_without_one_is_still_looked_for_further_back() -> None:
    assert day_of("2月29号") == "2024-02-29 day"
    assert day_of("Feb 29", datetime(2027, 1, 15, 12, 0, tzinfo=ZoneInfo(BUDAPEST))) == (
        "2024-02-29 day"
    )


def test_a_day_this_month_does_not_have_is_still_looked_for_further_back() -> None:
    mid_september = datetime(2026, 9, 15, 12, 0, tzinfo=ZoneInfo(BUDAPEST))

    assert day_of("31号", mid_september) == "2026-08-31 day"


@pytest.mark.parametrize("text", ["今年10月8号", "这个月8号", "2026年10月8号"])
def test_a_day_whose_year_or_month_was_said_is_in_the_future_as_before(text: str) -> None:
    assert read_time(text, NOW, BUDAPEST) == TimeRefused(Refusal.IN_THE_FUTURE)


def test_today_said_without_its_year_is_today() -> None:
    assert day_of("10月7号") == "2026-10-07 day"
    assert day_of("7号") == "2026-10-07 day"
    assert day_of("10月7号 9点") == "2026-10-07T09:00:00+02:00 minute"
    assert read_time("10月7号 10点", NOW, BUDAPEST) == TimeRefused(Refusal.IN_THE_FUTURE)
