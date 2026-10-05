"""Tests of turning a time phrase into a definite time, and of writing a time for the ledger.

Every "now" here is fixed and written into the test that uses it; nothing reads
the clock. Two zones are used throughout: one with summer time
(Europe/Budapest) and one without (Asia/Shanghai).

Each kind of wording has a section. In each, the cases named "contract" are
the examples the specification lists, and the cases named "own" are further
ones chosen for these tests.

An outcome is written as one short line: the time as the ledger writes it and
its precision, both candidates, or the reason for a refusal. Cautions are
checked in sections of their own.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from ledger_hand.core.timeparse import (
    TimeCaution,
    TimeReading,
    TimeRecognised,
    TwoCandidates,
    read_time,
    write_time,
)
from ledger_hand.core.trade import TimePrecision

BUDAPEST = "Europe/Budapest"
SHANGHAI = "Asia/Shanghai"

# A Wednesday afternoon.
NOW = datetime(2026, 10, 7, 15, 30, 20, tzinfo=ZoneInfo(SHANGHAI))
NOW_IN_BUDAPEST = datetime(2026, 10, 7, 15, 30, 20, tzinfo=ZoneInfo(BUDAPEST))


def described(reading: TimeReading) -> str:
    """One line for an outcome: what the ledger would be given, or why nothing."""
    if isinstance(reading, TimeRecognised):
        return f"{write_time(reading.time)} {reading.time.precision.value}"
    if isinstance(reading, TwoCandidates):
        return f"{write_time(reading.earlier)} | {write_time(reading.later)}"
    return reading.reason.name


def outcome(text: str, now: datetime = NOW, zone: str = SHANGHAI) -> str:
    return described(read_time(text, now, zone))


def cautions(text: str, now: datetime = NOW, zone: str = SHANGHAI) -> tuple[TimeCaution, ...]:
    reading = read_time(text, now, zone)
    assert isinstance(reading, TimeRecognised | TwoCandidates), f"{text!r}: {reading!r}"
    return reading.cautions


def local(zone: str, *fields: int, fold: int = 0) -> datetime:
    """A moment on the wall clock of ``zone``."""
    return datetime(*fields, tzinfo=ZoneInfo(zone), fold=fold)


def contract(text: str, expected: str) -> object:
    return pytest.param(text, expected, id=f"contract: {text}")


def own(text: str, expected: str) -> object:
    return pytest.param(text, expected, id=f"own: {text}")


# --- the present moment -----------------------------------------------------

RIGHT_NOW = [
    contract("刚才", "2026-10-07T15:30:00+08:00 minute"),
    contract("刚刚", "2026-10-07T15:30:00+08:00 minute"),
    contract("现在", "2026-10-07T15:30:00+08:00 minute"),
    contract("just now", "2026-10-07T15:30:00+08:00 minute"),
    own("此刻", "2026-10-07T15:30:00+08:00 minute"),
    own("right now", "2026-10-07T15:30:00+08:00 minute"),
    own("now", "2026-10-07T15:30:00+08:00 minute"),
    own("  刚才 ", "2026-10-07T15:30:00+08:00 minute"),
    own("Just Now", "2026-10-07T15:30:00+08:00 minute"),
    own("ＪＵＳＴ ＮＯＷ", "2026-10-07T15:30:00+08:00 minute"),
]


@pytest.mark.parametrize(("text", "expected"), RIGHT_NOW)
def test_the_present_moment_is_now_cut_to_the_minute(text: str, expected: str) -> None:
    assert outcome(text) == expected


def test_the_present_moment_is_on_the_wall_clock_of_the_zone_handed_in() -> None:
    assert outcome("现在", NOW_IN_BUDAPEST, BUDAPEST) == "2026-10-07T15:30:00+02:00 minute"


# --- a span back from now ---------------------------------------------------

SPANS_BACK = [
    contract("20 分钟前", "2026-10-07T15:10:00+08:00 minute"),
    contract("3 小时前", "2026-10-07T12:30:00+08:00 minute"),
    contract("2 hours ago", "2026-10-07T13:30:00+08:00 minute"),
    own("二十分钟前", "2026-10-07T15:10:00+08:00 minute"),
    own("两个小时前", "2026-10-07T13:30:00+08:00 minute"),
    own("半小时前", "2026-10-07T15:00:00+08:00 minute"),
    own("半个小时前", "2026-10-07T15:00:00+08:00 minute"),
    own("一个半小时前", "2026-10-07T14:00:00+08:00 minute"),
    own("3个钟头之前", "2026-10-07T12:30:00+08:00 minute"),
    own("90 分钟以前", "2026-10-07T14:00:00+08:00 minute"),
    own("5 minutes ago", "2026-10-07T15:25:00+08:00 minute"),
    own("a minute ago", "2026-10-07T15:29:00+08:00 minute"),
    own("an hour ago", "2026-10-07T14:30:00+08:00 minute"),
    own("half an hour ago", "2026-10-07T15:00:00+08:00 minute"),
    own("45 mins ago", "2026-10-07T14:45:00+08:00 minute"),
    own("three hrs ago", "2026-10-07T12:30:00+08:00 minute"),
    own("9999 小时前", "2025-08-17T00:30:00+08:00 minute"),
]


@pytest.mark.parametrize(("text", "expected"), SPANS_BACK)
def test_a_span_back_counts_real_time_back_from_now(text: str, expected: str) -> None:
    assert outcome(text) == expected


def test_a_span_back_is_on_the_wall_clock_of_the_zone_handed_in() -> None:
    assert outcome("20分钟前", NOW_IN_BUDAPEST, BUDAPEST) == "2026-10-07T15:10:00+02:00 minute"


# --- a number of days back --------------------------------------------------

DAYS_BACK = [
    contract("3 天前", "2026-10-04 day"),
    contract("3 days ago", "2026-10-04 day"),
    own("三天前", "2026-10-04 day"),
    own("1 天前", "2026-10-06 day"),
    own("两天以前", "2026-10-05 day"),
    own("30 天之前", "2026-09-07 day"),
    own("a day ago", "2026-10-06 day"),
    own("ten days ago", "2026-09-27 day"),
    own("3天前晚上9点", "2026-10-04T21:00:00+08:00 minute"),
    own("3 days ago at 9:40pm", "2026-10-04T21:40:00+08:00 minute"),
]


@pytest.mark.parametrize(("text", "expected"), DAYS_BACK)
def test_days_back_count_calendar_days(text: str, expected: str) -> None:
    assert outcome(text) == expected


# --- words for a day --------------------------------------------------------

DAY_WORDS = [
    contract("今天", "2026-10-07 day"),
    contract("昨天", "2026-10-06 day"),
    contract("前天", "2026-10-05 day"),
    contract("today", "2026-10-07 day"),
    contract("yesterday", "2026-10-06 day"),
    own("今日", "2026-10-07 day"),
    own("昨日", "2026-10-06 day"),
    own("大前天", "2026-10-04 day"),
    own("the day before yesterday", "2026-10-05 day"),
    own("Yesterday", "2026-10-06 day"),
    own("昨天下午", "2026-10-06 day"),
    own("yesterday morning", "2026-10-06 day"),
    own("this morning", "2026-10-07 day"),
    own("今天下午", "2026-10-07 day"),
    own("明天", "IN_THE_FUTURE"),
    own("后天", "IN_THE_FUTURE"),
    own("tomorrow", "IN_THE_FUTURE"),
]


@pytest.mark.parametrize(("text", "expected"), DAY_WORDS)
def test_day_words_count_calendar_days(text: str, expected: str) -> None:
    assert outcome(text) == expected


# --- weekdays ---------------------------------------------------------------

WEEKDAYS = [
    contract("周五", "2026-10-02 day"),
    contract("上周五", "2026-10-02 day"),
    contract("星期三", "2026-10-07 day"),
    contract("last Friday", "2026-10-02 day"),
    contract("on Monday", "2026-10-05 day"),
    own("礼拜五", "2026-10-02 day"),
    own("周日", "2026-10-04 day"),
    own("星期天", "2026-10-04 day"),
    own("上周日", "2026-10-04 day"),
    own("上星期五", "2026-10-02 day"),
    own("上个星期五", "2026-10-02 day"),
    own("上礼拜五", "2026-10-02 day"),
    own("上个周五", "2026-10-02 day"),
    own("上上周五", "2026-09-25 day"),
    own("这周一", "2026-10-05 day"),
    own("本周五", "IN_THE_FUTURE"),
    own("下周一", "IN_THE_FUTURE"),
    own("fri", "2026-10-02 day"),
    own("on Fri.", "2026-10-02 day"),
    own("last Sunday", "2026-10-04 day"),
    own("Friday 3pm", "2026-10-02T15:00:00+08:00 minute"),
    own("星期三下午三点", "2026-10-07T15:00:00+08:00 minute"),
]


@pytest.mark.parametrize(("text", "expected"), WEEKDAYS)
def test_weekdays(text: str, expected: str) -> None:
    assert outcome(text) == expected


# The weekday rules, seen from each day of one week and the Monday after it.
# Columns: today, then 周五, 上周五, last Friday, last Monday, 上个周五.
WEEK_OF_DAYS = [
    (date(2026, 10, 5), "2026-10-02", "2026-10-02", "2026-10-02", "2026-09-28", "2026-10-02"),
    (date(2026, 10, 6), "2026-10-02", "2026-10-02", "2026-10-02", "AMBIGUOUS", "2026-10-02"),
    (date(2026, 10, 7), "2026-10-02", "2026-10-02", "2026-10-02", "AMBIGUOUS", "2026-10-02"),
    (date(2026, 10, 8), "2026-10-02", "2026-10-02", "2026-10-02", "AMBIGUOUS", "2026-10-02"),
    (date(2026, 10, 9), "2026-10-09", "2026-10-02", "2026-10-02", "AMBIGUOUS", "2026-10-02"),
    (date(2026, 10, 10), "2026-10-09", "2026-10-02", "AMBIGUOUS", "AMBIGUOUS", "AMBIGUOUS"),
    (date(2026, 10, 11), "2026-10-09", "2026-10-02", "AMBIGUOUS", "AMBIGUOUS", "AMBIGUOUS"),
    (date(2026, 10, 12), "2026-10-09", "2026-10-09", "2026-10-09", "2026-10-05", "2026-10-09"),
]


@pytest.mark.parametrize("zone", [BUDAPEST, SHANGHAI])
@pytest.mark.parametrize("row", WEEK_OF_DAYS, ids=lambda row: row[0].strftime("%a %d"))
def test_weekdays_from_every_day_of_a_week(row: tuple[date | str, ...], zone: str) -> None:
    today, friday, friday_of_last_week, last_friday, last_monday, previous_friday = row
    assert isinstance(today, date)
    now = local(zone, today.year, today.month, today.day, 12, 0)

    def day_of(text: str) -> str:
        return outcome(text, now, zone).removesuffix(" day")

    assert day_of("周五") == friday
    assert day_of("Friday") == friday
    assert day_of("on Friday") == friday
    assert day_of("上周五") == friday_of_last_week
    assert day_of("last Friday") == last_friday
    assert day_of("last Monday") == last_monday
    assert day_of("上个周五") == previous_friday


# --- dates written out ------------------------------------------------------

DATES = [
    contract("10 月 2 号", "2026-10-02 day"),
    contract("2026 年 10 月 2 日", "2026-10-02 day"),
    contract("2026-10-02", "2026-10-02 day"),
    contract("Oct 2", "2026-10-02 day"),
    contract("2 October", "2026-10-02 day"),
    own("十月二日", "2026-10-02 day"),
    own("二〇二六年十月二日", "2026-10-02 day"),
    own("2026/10/2", "2026-10-02 day"),
    own("2026.10.02", "2026-10-02 day"),
    own("October 2nd, 2026", "2026-10-02 day"),
    own("the 2nd of October", "2026-10-02 day"),
    own("2nd Oct 2026", "2026-10-02 day"),
    own("Sept. 30", "2026-09-30 day"),
    own("去年10月2号", "2025-10-02 day"),
    own("今年1月1日", "2026-01-01 day"),
    own("12月25号", "2025-12-25 day"),
    own("Dec 25", "2025-12-25 day"),
    own("10月8号", "2025-10-08 day"),
    own("2号", "2026-10-02 day"),
    own("8号", "2026-09-08 day"),
    own("上个月15号", "2026-09-15 day"),
    own("这个月8号", "IN_THE_FUTURE"),
    own("2月29号", "2024-02-29 day"),
    own("2027-01-01", "IN_THE_FUTURE"),
    own("今年10月8号", "IN_THE_FUTURE"),
    own("2月30号", "UNKNOWN_WORDING"),
    own("2026年2月29日", "UNKNOWN_WORDING"),
    own("上个月31号", "UNKNOWN_WORDING"),
    own("13月1号", "UNKNOWN_WORDING"),
    own("Oct 32", "UNKNOWN_WORDING"),
    own("2th Oct", "UNKNOWN_WORDING"),
    own("10月2", "UNKNOWN_WORDING"),
    own("2026年10月", "UNKNOWN_WORDING"),
    own("10月2号下午3点", "2026-10-02T15:00:00+08:00 minute"),
]


@pytest.mark.parametrize(("text", "expected"), DATES)
def test_dates_written_out(text: str, expected: str) -> None:
    assert outcome(text) == expected


# --- clock times ------------------------------------------------------------

CLOCK_TIMES = [
    contract("9:40", "2026-10-07T09:40:00+08:00 minute"),
    contract("9 点 40", "2026-10-07T09:40:00+08:00 minute"),
    contract("九点四十", "2026-10-07T09:40:00+08:00 minute"),
    contract("三点半", "2026-10-07T03:30:00+08:00 minute"),
    contract("三点一刻", "2026-10-07T03:15:00+08:00 minute"),
    contract("3pm", "2026-10-07T15:00:00+08:00 minute"),
    contract("15:05:30", "2026-10-07T15:05:30+08:00 second"),
    own("九点零五", "2026-10-07T09:05:00+08:00 minute"),
    own("9点05", "2026-10-07T09:05:00+08:00 minute"),
    own("九点五分", "2026-10-07T09:05:00+08:00 minute"),
    own("九点十", "2026-10-07T09:10:00+08:00 minute"),
    own("9点40分30秒", "2026-10-07T09:40:30+08:00 second"),
    own("十二点", "2026-10-07T12:00:00+08:00 minute"),
    own("两点", "2026-10-07T02:00:00+08:00 minute"),
    own("零点", "2026-10-07T00:00:00+08:00 minute"),
    own("零点零分", "2026-10-07T00:00:00+08:00 minute"),
    own("零点零分零秒", "2026-10-07T00:00:00+08:00 second"),
    own("三点三刻", "2026-10-07T03:45:00+08:00 minute"),
    own("9点整", "2026-10-07T09:00:00+08:00 minute"),
    own("九点钟", "2026-10-07T09:00:00+08:00 minute"),
    own("9时40分", "2026-10-07T09:40:00+08:00 minute"),
    own("９：４０", "2026-10-07T09:40:00+08:00 minute"),
    own("3 PM", "2026-10-07T15:00:00+08:00 minute"),
    own("3:20 p.m.", "2026-10-07T15:20:00+08:00 minute"),
    own("11 o'clock", "2026-10-07T11:00:00+08:00 minute"),
    own("at 3", "2026-10-07T03:00:00+08:00 minute"),
    own("noon", "2026-10-07T12:00:00+08:00 minute"),
    own("12 noon", "2026-10-07T12:00:00+08:00 minute"),
    own("12:30pm", "2026-10-07T12:30:00+08:00 minute"),
    own("0:00", "2026-10-07T00:00:00+08:00 minute"),
    own("15:30", "2026-10-07T15:30:00+08:00 minute"),
    own("23:59", "IN_THE_FUTURE"),
    own("9:60", "UNKNOWN_WORDING"),
    own("25点", "UNKNOWN_WORDING"),
    own("15pm", "UNKNOWN_WORDING"),
    own("9点40分钟", "UNKNOWN_WORDING"),
]


@pytest.mark.parametrize(("text", "expected"), CLOCK_TIMES)
def test_clock_times(text: str, expected: str) -> None:
    assert outcome(text) == expected


# --- halves of the day ------------------------------------------------------

HALVES_OF_THE_DAY = [
    contract("早上 9 点", "2026-10-07T09:00:00+08:00 minute"),
    contract("上午 10 点", "2026-10-07T10:00:00+08:00 minute"),
    contract("中午 12 点", "2026-10-07T12:00:00+08:00 minute"),
    contract("下午 3 点", "2026-10-07T15:00:00+08:00 minute"),
    contract("昨天晚上 9 点", "2026-10-06T21:00:00+08:00 minute"),
    contract("凌晨 2 点", "2026-10-07T02:00:00+08:00 minute"),
    contract("9am", "2026-10-07T09:00:00+08:00 minute"),
    contract("3 pm", "2026-10-07T15:00:00+08:00 minute"),
    contract("9 in the morning", "2026-10-07T09:00:00+08:00 minute"),
    contract("yesterday evening at 8", "2026-10-06T20:00:00+08:00 minute"),
    own("中午1点", "2026-10-07T13:00:00+08:00 minute"),
    own("昨天傍晚6点", "2026-10-06T18:00:00+08:00 minute"),
    own("早8点", "2026-10-07T08:00:00+08:00 minute"),
    own("昨晚8点", "2026-10-06T20:00:00+08:00 minute"),
    own("今早7点半", "2026-10-07T07:30:00+08:00 minute"),
    own("下午15点", "2026-10-07T15:00:00+08:00 minute"),
    own("下午 1:30", "2026-10-07T13:30:00+08:00 minute"),
    own("3 in the afternoon", "2026-10-07T15:00:00+08:00 minute"),
    own("last night at 11pm", "2026-10-06T23:00:00+08:00 minute"),
    own("11 at night yesterday", "2026-10-06T23:00:00+08:00 minute"),
    own("this morning at 9:15", "2026-10-07T09:15:00+08:00 minute"),
    own("晚8点", "IN_THE_FUTURE"),
    own("tonight at 9", "IN_THE_FUTURE"),
    own("下午 12 点", "AMBIGUOUS"),
    own("上午 12 点", "AMBIGUOUS"),
    own("晚上 1 点", "AMBIGUOUS"),
    own("早上 9pm", "AMBIGUOUS"),
    own("昨天晚上", "AMBIGUOUS"),
    own("last night", "AMBIGUOUS"),
    own("半夜两点", "AMBIGUOUS"),
]


@pytest.mark.parametrize(("text", "expected"), HALVES_OF_THE_DAY)
def test_halves_of_the_day(text: str, expected: str) -> None:
    assert outcome(text) == expected


# --- combinations -----------------------------------------------------------

COMBINATIONS = [
    contract("昨天晚上 9 点 40", "2026-10-06T21:40:00+08:00 minute"),
    contract("上周五下午三点", "2026-10-02T15:00:00+08:00 minute"),
    contract("yesterday at 9:40pm", "2026-10-06T21:40:00+08:00 minute"),
    own("前天上午10点", "2026-10-05T10:00:00+08:00 minute"),
    own("10月2号晚上9点半", "2026-10-02T21:30:00+08:00 minute"),
    own("2026年10月2日15:05:30", "2026-10-02T15:05:30+08:00 second"),
    own("2026年10月2日下午3点15分30秒", "2026-10-02T15:15:30+08:00 second"),
    own("3pm on Friday", "2026-10-02T15:00:00+08:00 minute"),
    own("9:40pm yesterday", "2026-10-06T21:40:00+08:00 minute"),
    own("on Oct 2 at 3pm", "2026-10-02T15:00:00+08:00 minute"),
    own("Oct 2, 3pm", "2026-10-02T15:00:00+08:00 minute"),
    own("yesterday, 9:40pm", "2026-10-06T21:40:00+08:00 minute"),
    own("昨天，晚上9点", "2026-10-06T21:00:00+08:00 minute"),
    own("last Friday at 3pm", "2026-10-02T15:00:00+08:00 minute"),
    own("星期一早上8点", "2026-10-05T08:00:00+08:00 minute"),
    own("the day before yesterday at noon", "2026-10-05T12:00:00+08:00 minute"),
    own("noon yesterday", "2026-10-06T12:00:00+08:00 minute"),
    own("Friday afternoon", "2026-10-02 day"),
]


@pytest.mark.parametrize(("text", "expected"), COMBINATIONS)
def test_combinations(text: str, expected: str) -> None:
    assert outcome(text) == expected


# --- precision ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "precision"),
    [
        ("昨天", TimePrecision.DAY),
        ("Oct 2", TimePrecision.DAY),
        ("昨天晚上9点", TimePrecision.MINUTE),
        ("9:40pm yesterday", TimePrecision.MINUTE),
        ("刚才", TimePrecision.MINUTE),
        ("3 hours ago", TimePrecision.MINUTE),
        ("15:05:30", TimePrecision.SECOND),
        ("15:05:00", TimePrecision.SECOND),
        ("昨天下午3点15分30秒", TimePrecision.SECOND),
    ],
)
def test_precision_follows_what_was_said(text: str, precision: TimePrecision) -> None:
    reading = read_time(text, NOW, SHANGHAI)

    assert isinstance(reading, TimeRecognised)
    assert reading.time.precision is precision


def test_now_and_spans_back_are_cut_to_the_minute_never_rounded() -> None:
    late_in_the_minute = datetime(2026, 10, 7, 15, 30, 59, 999999, tzinfo=ZoneInfo(SHANGHAI))

    assert outcome("刚才", late_in_the_minute) == "2026-10-07T15:30:00+08:00 minute"
    assert outcome("1 分钟前", late_in_the_minute) == "2026-10-07T15:29:00+08:00 minute"


# --- the three settled readings: no half said, midnight, slashes -------------


@pytest.mark.parametrize("text", ["9 点 40", "9:40", "九点四十", "十二点", "零点", "at 3", "12:30"])
def test_a_clock_time_of_twelve_or_less_without_a_half_is_read_with_a_caution(text: str) -> None:
    assert cautions(text) == (TimeCaution.NO_HALF_OF_DAY,)


@pytest.mark.parametrize(
    "text", ["13:05", "15:05:30", "下午3点", "9am", "3 in the afternoon", "noon"]
)
def test_a_clock_time_past_twelve_or_with_a_half_needs_no_caution(text: str) -> None:
    assert cautions(text) == ()


@pytest.mark.parametrize(
    "text",
    [
        "晚上 12 点",
        "midnight",
        "12 midnight",
        "12am",
        "12:30am",
        "24:00",
        "24点",
        "凌晨12点",
        "子夜",
    ],
)
def test_midnight_is_ambiguous_about_its_day(text: str) -> None:
    assert outcome(text) == "AMBIGUOUS"


@pytest.mark.parametrize(
    "text", ["10/2", "2/10", "10/2/2026", "2/10/26", "10.2", "10-02", "10/2 晚上9点", "10/2 3pm"]
)
def test_a_date_without_the_year_in_front_written_with_marks_is_ambiguous(text: str) -> None:
    assert outcome(text) == "AMBIGUOUS"


@pytest.mark.parametrize("text", ["九点五", "9点5", "9点0"])
def test_a_single_digit_minute_without_fen_is_ambiguous(text: str) -> None:
    assert outcome(text) == "AMBIGUOUS"


# --- turning a month, a year, and a leap day ---------------------------------

TURNS_OF_THE_CALENDAR = [
    # today, then 昨天, 前天, 上周五, 3 天前
    (date(2026, 10, 1), "2026-09-30", "2026-09-29", "2026-09-25", "2026-09-28"),
    (date(2027, 1, 1), "2026-12-31", "2026-12-30", "2026-12-25", "2026-12-29"),
    (date(2028, 3, 1), "2028-02-29", "2028-02-28", "2028-02-25", "2028-02-27"),
    (date(2028, 3, 2), "2028-03-01", "2028-02-29", "2028-02-25", "2028-02-28"),
    (date(2027, 3, 1), "2027-02-28", "2027-02-27", "2027-02-26", "2027-02-26"),
]


@pytest.mark.parametrize("zone", [BUDAPEST, SHANGHAI])
@pytest.mark.parametrize("row", TURNS_OF_THE_CALENDAR, ids=lambda row: row[0].isoformat())
def test_counting_back_across_a_month_a_year_and_a_leap_day(
    row: tuple[date | str, ...], zone: str
) -> None:
    today, yesterday, day_before, friday_of_last_week, three_days_ago = row
    assert isinstance(today, date)
    now = local(zone, today.year, today.month, today.day, 10, 0)

    assert outcome("昨天", now, zone) == f"{yesterday} day"
    assert outcome("yesterday", now, zone) == f"{yesterday} day"
    assert outcome("前天", now, zone) == f"{day_before} day"
    assert outcome("上周五", now, zone) == f"{friday_of_last_week} day"
    assert outcome("3 天前", now, zone) == f"{three_days_ago} day"
    assert outcome("3 days ago", now, zone) == f"{three_days_ago} day"


def test_a_leap_day_without_a_year_is_the_latest_one_not_after_today() -> None:
    now = local(SHANGHAI, 2028, 3, 1, 10, 0)

    assert outcome("2月29号", now) == "2028-02-29 day"
    assert outcome("Feb 29", local(SHANGHAI, 2028, 2, 28, 10, 0)) == "2024-02-29 day"


# --- summer time: the days the clocks change ---------------------------------


def clock_changes(zone: str, year: int) -> list[tuple[datetime, timedelta, timedelta]]:
    """Each instant in ``year`` at which the offset of ``zone`` changes, from the zone data.

    Each comes with the offset before it and the offset after it. Nothing
    about which days these are is written into the tests by hand.
    """
    info = ZoneInfo(zone)
    instant = datetime(year, 1, 1, tzinfo=timezone.utc)
    before = instant.astimezone(info).utcoffset()
    changes: list[tuple[datetime, timedelta, timedelta]] = []
    while instant.year == year:
        instant += timedelta(minutes=15)
        after = instant.astimezone(info).utcoffset()
        if after != before:
            assert before is not None and after is not None
            changes.append((instant, before, after))
            before = after
    return changes


def wall_reading(instant: datetime, offset: timedelta) -> datetime:
    """What a clock running at ``offset`` showed at ``instant``, without a zone."""
    return instant.astimezone(timezone(offset)).replace(tzinfo=None)


YEARS = [2025, 2026, 2027, 2030]


@pytest.mark.parametrize("year", YEARS)
def test_the_zone_with_summer_time_changes_its_clocks_twice_a_year(year: int) -> None:
    changes = clock_changes(BUDAPEST, year)

    assert [after > before for _, before, after in changes] == [True, False]
    assert clock_changes(SHANGHAI, year) == []


@pytest.mark.parametrize("year", YEARS)
def test_a_clock_time_the_clocks_skipped_does_not_exist(year: int) -> None:
    instant, before, after = clock_changes(BUDAPEST, year)[0]
    skipped = wall_reading(instant, before) + (after - before) / 2
    now = local(BUDAPEST, skipped.year, skipped.month, skipped.day, 12, 0)
    clock = f"{skipped.hour}:{skipped.minute:02d}"

    assert outcome(clock, now, BUDAPEST) == "DOES_NOT_EXIST"
    assert outcome(f"{skipped.date().isoformat()} {clock}", now, BUDAPEST) == "DOES_NOT_EXIST"
    assert outcome(f"今天凌晨{skipped.hour}点{skipped.minute}分", now, BUDAPEST) == "DOES_NOT_EXIST"
    # The minute before the gap and the first one after it exist.
    first_after = wall_reading(instant, after)
    last_before = wall_reading(instant, before) - timedelta(minutes=1)
    for wall in (last_before, first_after):
        expected = f"{wall.isoformat()}{'+01:00' if wall < skipped else '+02:00'} minute"
        assert outcome(f"{wall.hour}:{wall.minute:02d}", now, BUDAPEST) == expected


@pytest.mark.parametrize("year", YEARS)
def test_a_clock_time_shown_twice_gives_both_moments_the_earlier_first(year: int) -> None:
    instant, before, after = clock_changes(BUDAPEST, year)[1]
    repeated = wall_reading(instant, after) + (before - after) / 2
    now = local(BUDAPEST, repeated.year, repeated.month, repeated.day, 12, 0)

    reading = read_time(f"{repeated.hour}:{repeated.minute:02d}", now, BUDAPEST)

    assert isinstance(reading, TwoCandidates)
    assert reading.earlier.value.utcoffset() == before
    assert reading.later.value.utcoffset() == after
    for candidate in (reading.earlier, reading.later):
        assert isinstance(candidate.value, datetime)
        assert candidate.value.replace(tzinfo=None) == repeated
    assert reading.later.value - reading.earlier.value == before - after
    assert reading.cautions == (TimeCaution.NO_HALF_OF_DAY,)


@pytest.mark.parametrize("year", YEARS)
def test_when_the_second_showing_is_still_to_come_the_first_is_the_only_one(year: int) -> None:
    instant, before, after = clock_changes(BUDAPEST, year)[1]
    start = wall_reading(instant, after)
    # During the second showing of the hour, ten minutes into it.
    now = (instant + timedelta(minutes=10)).astimezone(ZoneInfo(BUDAPEST))
    said = start + timedelta(minutes=40)

    reading = read_time(f"{said.hour}:{said.minute:02d}", now, BUDAPEST)

    assert isinstance(reading, TimeRecognised)
    assert reading.time.value.utcoffset() == before
    assert TimeCaution.OTHER_PASS_TO_COME in reading.cautions
    # During the first showing, a time later in the hour is simply in the future.
    first_showing = (instant - timedelta(minutes=50)).astimezone(ZoneInfo(BUDAPEST))
    assert outcome(f"{said.hour}:{said.minute:02d}", first_showing, BUDAPEST) == "IN_THE_FUTURE"


@pytest.mark.parametrize("year", YEARS)
@pytest.mark.parametrize("change", [0, 1], ids=["clocks forward", "clocks back"])
def test_hours_back_across_a_change_count_real_time(year: int, change: int) -> None:
    instant, _, _ = clock_changes(BUDAPEST, year)[change]
    now = (instant + timedelta(hours=1, minutes=20)).astimezone(ZoneInfo(BUDAPEST))
    expected = (instant - timedelta(hours=1, minutes=40)).astimezone(ZoneInfo(BUDAPEST))

    reading = read_time("3 小时前", now, BUDAPEST)

    assert isinstance(reading, TimeRecognised)
    assert reading.time.value == expected
    assert reading.time.value.utcoffset() == expected.utcoffset()
    assert read_time("3 hours ago", now, BUDAPEST) == reading
    # On the wall clock the gap is not three hours: that is the point.
    wall_gap = now.replace(tzinfo=None) - expected.replace(tzinfo=None)
    assert wall_gap != timedelta(hours=3)


@pytest.mark.parametrize("year", YEARS)
def test_the_zone_without_summer_time_has_one_moment_for_every_clock_time(year: int) -> None:
    for instant, _, _ in clock_changes(BUDAPEST, year):
        day = instant.date()
        now = local(SHANGHAI, day.year, day.month, day.day, 12, 0)
        for hour in range(12):
            assert outcome(f"{hour}:30", now, SHANGHAI) == (
                f"{day.isoformat()}T{hour:02d}:30:00+08:00 minute"
            )
