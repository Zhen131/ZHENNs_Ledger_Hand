"""Tests of reading a stretch of time: every wording, every edge, each with its dates."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from ledger_hand.core.time_range import (
    Period,
    PeriodRefusal,
    PeriodRefused,
    read_period,
)

ZONE = "Europe/Budapest"
BUDAPEST = ZoneInfo(ZONE)
# Tuesday, 24 November 2026, 23:55: the invented book's "now".
NOW = datetime(2026, 11, 24, 23, 55, tzinfo=BUDAPEST)


def days(text: str, now: datetime = NOW, zone: str = ZONE) -> tuple[date, date]:
    reading = read_period(text, now, zone)
    assert isinstance(reading, Period), f"{text!r}: {reading}"
    return reading.first_day, reading.last_day


def refused(text: str, now: datetime = NOW) -> PeriodRefusal:
    reading = read_period(text, now, ZONE)
    assert isinstance(reading, PeriodRefused), f"{text!r}: {reading}"
    return reading.reason


def elapsed(period: Period) -> timedelta:
    """Real time from start to end; subtracting in one zone would count wall-clock time."""
    return period.end.astimezone(UTC) - period.start.astimezone(UTC)


OCTOBER = (date(2026, 10, 1), date(2026, 10, 31))
NOVEMBER = (date(2026, 11, 1), date(2026, 11, 30))
YEAR_2026 = (date(2026, 1, 1), date(2026, 12, 31))
YEAR_2025 = (date(2025, 1, 1), date(2025, 12, 31))
THIS_WEEK = (date(2026, 11, 23), date(2026, 11, 29))
LAST_WEEK = (date(2026, 11, 16), date(2026, 11, 22))
SEVEN_DAYS = (date(2026, 11, 18), date(2026, 11, 24))
THIRTY_DAYS = (date(2026, 10, 26), date(2026, 11, 24))


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("今天", (date(2026, 11, 24), date(2026, 11, 24))),
        ("today", (date(2026, 11, 24), date(2026, 11, 24))),
        ("昨天", (date(2026, 11, 23), date(2026, 11, 23))),
        ("yesterday", (date(2026, 11, 23), date(2026, 11, 23))),
        ("前天", (date(2026, 11, 22), date(2026, 11, 22))),
        ("10月6号", (date(2026, 10, 6), date(2026, 10, 6))),
        ("2026年10月6日", (date(2026, 10, 6), date(2026, 10, 6))),
        ("Oct 6", (date(2026, 10, 6), date(2026, 10, 6))),
        ("2026-10-06", (date(2026, 10, 6), date(2026, 10, 6))),
        ("10月", OCTOBER),
        ("10月份", OCTOBER),
        ("十月", OCTOBER),
        ("2026年10月", OCTOBER),
        ("上个月", OCTOBER),
        ("上月", OCTOBER),
        ("这个月", NOVEMBER),
        ("本月", NOVEMBER),
        ("October", OCTOBER),
        ("Oct 2026", OCTOBER),
        ("last month", OCTOBER),
        ("this month", NOVEMBER),
        ("in October", OCTOBER),
        ("10月份的", OCTOBER),
        ("今年", YEAR_2026),
        ("去年", YEAR_2025),
        ("2026年", YEAR_2026),
        ("in 2026", YEAR_2026),
        ("during 2026", YEAR_2026),
        ("year 2026", YEAR_2026),
        ("Oct 6, 2026", (date(2026, 10, 6), date(2026, 10, 6))),
        ("in May", (date(2026, 5, 1), date(2026, 5, 31))),
        ("during March", (date(2026, 3, 1), date(2026, 3, 31))),
        ("last May", (date(2026, 5, 1), date(2026, 5, 31))),
        ("this March", (date(2026, 3, 1), date(2026, 3, 31))),
        ("May 2026", (date(2026, 5, 1), date(2026, 5, 31))),
        ("May 5", (date(2026, 5, 5), date(2026, 5, 5))),
        ("from May to June", (date(2026, 5, 1), date(2026, 6, 30))),
        ("between March and May", (date(2026, 3, 1), date(2026, 5, 31))),
        ("this year", YEAR_2026),
        ("This Year", YEAR_2026),
        ("last year", YEAR_2025),
        ("这周", THIS_WEEK),
        ("本周", THIS_WEEK),
        ("this week", THIS_WEEK),
        ("上周", LAST_WEEK),
        ("上个星期", LAST_WEEK),
        ("last week", LAST_WEEK),
        ("最近7天", SEVEN_DAYS),
        ("近七天", SEVEN_DAYS),
        ("last 7 days", SEVEN_DAYS),
        ("the past seven days", SEVEN_DAYS),
        ("过去30天", THIRTY_DAYS),
        ("past 30 days", THIRTY_DAYS),
        ("10月1号到10月15号", (date(2026, 10, 1), date(2026, 10, 15))),
        ("10月1号到15号", (date(2026, 10, 1), date(2026, 10, 15))),
        ("from Oct 1 to Oct 15", (date(2026, 10, 1), date(2026, 10, 15))),
        ("9月到10月", (date(2026, 9, 1), date(2026, 10, 31))),
        ("ＯＣＴＯＢＥＲ", OCTOBER),
    ],
)
def test_each_wording_names_its_days(text: str, expected: tuple[date, date]) -> None:
    assert days(text) == expected


def test_last_month_runs_from_midnight_on_the_first_to_midnight_after_the_last_day() -> None:
    reading = read_period("上个月", NOW, ZONE)

    assert isinstance(reading, Period)
    assert reading.start == datetime(2026, 10, 1, tzinfo=BUDAPEST)
    assert reading.end == datetime(2026, 11, 1, tzinfo=BUDAPEST)
    assert reading.start.isoformat() == "2026-10-01T00:00:00+02:00"
    assert reading.end.isoformat() == "2026-11-01T00:00:00+01:00"


def test_one_day_runs_from_its_midnight_to_the_next() -> None:
    reading = read_period("10月6号", NOW, ZONE)

    assert isinstance(reading, Period)
    assert reading.start == datetime(2026, 10, 6, tzinfo=BUDAPEST)
    assert reading.end == datetime(2026, 10, 7, tzinfo=BUDAPEST)


@pytest.mark.parametrize("text", ["12月", "December", "12月份", "10/6", "6/10"])
def test_a_month_or_date_this_year_has_not_reached_is_ambiguous(text: str) -> None:
    assert refused(text) is PeriodRefusal.AMBIGUOUS


def test_the_month_now_is_this_years_with_its_end_still_to_come() -> None:
    assert days("11月") == NOVEMBER


@pytest.mark.parametrize(
    "text", ["明天", "明年", "next year", "下个月", "next month", "下周", "next week", "2027年"]
)
def test_a_stretch_wholly_after_today_is_in_the_future(text: str) -> None:
    assert refused(text) is PeriodRefusal.IN_THE_FUTURE


@pytest.mark.parametrize(
    "text",
    [
        "blah",
        "",
        "刚才",
        "3小时前",
        "昨天晚上9点",
        "最近0天",
        "13月",
        "10月20号到10月1号",
        "10月31号到40号",
        "的",
        "x" * 200,
    ],
)
def test_words_that_name_no_stretch_of_days_are_not_read(text: str) -> None:
    assert refused(text) is PeriodRefusal.UNKNOWN_WORDING


def test_a_year_given_with_a_month_is_used_as_it_stands() -> None:
    assert days("2025年12月") == (date(2025, 12, 1), date(2025, 12, 31))
    assert days("December 2025") == (date(2025, 12, 1), date(2025, 12, 31))


def test_last_month_and_last_week_cross_into_the_year_before() -> None:
    now = datetime(2027, 1, 3, 10, 0, tzinfo=BUDAPEST)  # a Sunday

    assert days("上个月", now) == (date(2026, 12, 1), date(2026, 12, 31))
    assert days("上周", now) == (date(2026, 12, 21), date(2026, 12, 27))
    assert days("这周", now) == (date(2026, 12, 28), date(2027, 1, 3))
    assert days("最近7天", now) == (date(2026, 12, 28), date(2027, 1, 3))
    assert days("去年", now) == (date(2026, 1, 1), date(2026, 12, 31))


def test_last_month_from_the_end_of_a_month_is_the_whole_month_before() -> None:
    now = datetime(2026, 3, 31, 12, 0, tzinfo=BUDAPEST)

    assert days("上个月", now) == (date(2026, 2, 1), date(2026, 2, 28))


def test_february_of_a_leap_year_ends_on_the_29th() -> None:
    now = datetime(2028, 3, 10, 12, 0, tzinfo=BUDAPEST)

    assert days("上个月", now) == (date(2028, 2, 1), date(2028, 2, 29))
    assert days("2月", now) == (date(2028, 2, 1), date(2028, 2, 29))


def test_on_a_monday_this_week_starts_today() -> None:
    now = datetime(2026, 11, 23, 0, 30, tzinfo=BUDAPEST)

    assert days("这周", now) == (date(2026, 11, 23), date(2026, 11, 29))
    assert days("上周", now) == (date(2026, 11, 16), date(2026, 11, 22))


def test_the_day_the_clocks_go_forward_is_23_hours_long() -> None:
    reading = read_period("2026年3月29日", NOW, ZONE)

    assert isinstance(reading, Period)
    assert reading.start.isoformat() == "2026-03-29T00:00:00+01:00"
    assert reading.end.isoformat() == "2026-03-30T00:00:00+02:00"
    assert elapsed(reading) == timedelta(hours=23)


def test_the_day_the_clocks_go_back_is_25_hours_long() -> None:
    reading = read_period("2026年10月25日", NOW, ZONE)

    assert isinstance(reading, Period)
    assert reading.start.isoformat() == "2026-10-25T00:00:00+02:00"
    assert reading.end.isoformat() == "2026-10-26T00:00:00+01:00"
    assert elapsed(reading) == timedelta(hours=25)


def test_a_current_moment_in_another_zone_is_read_in_the_zone_handed_in() -> None:
    # 23:30 in UTC on the 24th is already the 25th in Budapest.
    now = datetime(2026, 11, 24, 23, 30, tzinfo=ZoneInfo("UTC"))

    assert days("今天", now) == (date(2026, 11, 25), date(2026, 11, 25))


def test_a_moment_without_an_offset_is_the_callers_mistake() -> None:
    with pytest.raises(ValueError, match="offset"):
        read_period("上个月", datetime(2026, 11, 24, 23, 55), ZONE)


@pytest.mark.parametrize(
    "text", ["2026", "1000", "2446", "may", "May", "march", "mar", "March to April"]
)
def test_four_digits_alone_and_may_or_march_alone_are_not_read(text: str) -> None:
    assert refused(text) is PeriodRefusal.UNKNOWN_WORDING


@pytest.mark.parametrize("text", ["1999年", "in 1999", "Oct 1999", "1999年10月6日", "Oct 6, 1999"])
def test_a_year_before_2000_is_not_read_whoever_wrote_it(text: str) -> None:
    assert refused(text) is PeriodRefusal.UNKNOWN_WORDING
