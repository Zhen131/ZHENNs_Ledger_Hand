"""Time phrases to definite times, and definite times written the way the ledger writes them.

``read_time`` takes a short piece of text that is supposed to be one time
("昨天晚上 9 点 40", "last Friday 3pm"), the current moment and the name of
the time zone, and gives back one of these:

- ``TimeRecognised``: one ``OccurredTime`` (a date for day precision, a moment
  with its offset for minute and second precision) and any cautions;
- ``TwoCandidates``: the clock time was shown twice that day, because the
  clocks went back an hour, and both moments are handed back, the earlier
  first;
- ``TimeRefused``: the reason is a ``Refusal``. The wording is unknown or
  ambiguous, the time did not exist that day because the clocks skipped it,
  or the time lies in the future.

It never guesses, and it never raises for a text it cannot read. It raises
only for a mistake of the calling code: a current moment without an offset, a
grace below zero, or a name that is not a time zone.

The current moment and the zone are always handed in; this module reads
neither the clock nor the machine's time zone. A current moment in another
zone is first moved to the zone that was handed in, and "today" is its date
there.

The wording is read by ``time_wording``. This module then works out the
date and the moment:

- The present moment and a span back from it ("3 小时前") count real elapsed
  time, so they come out right across a change of the clocks. They have
  minute precision.
- Day words, weekdays and dates count calendar days, and a clock time is
  then put on that day's wall clock. Without a clock time the result has day
  precision; with one it has minute precision, or second precision when a
  second was said.
- A weekday without anything before it ("周五", "Friday", "on Friday") is the
  latest such weekday, today included. A week starts on Monday; "上周五" is
  the Friday of the week before this one. "last Friday" may mean the latest
  Friday before today or the Friday of last week: where the two are the same
  day it is that day, and where they differ the answer is ambiguous.
- A date without a year ("10月8号", "Dec 25") is this year's when that day
  has come. When this year's is still to come, the answer is "ambiguous": the
  user may mean last year's, or may have said the wrong day, and the program
  does not pick one. Only when this year has no such day at all (29 February)
  is it looked for further back: the latest one that is not after today. A
  day of the month without a month ("8号") works the same way with months:
  this month's when it has come, "ambiguous" when it is still to come, and
  the latest one before when this month has no such day ("31号"). A clock
  time without a day is on today. The date is settled first and the clock
  time put on it after; when that lands after the current moment, the answer
  is "in the future". It is never moved back a day, a week or a year to make
  it fit.
- In the future means what it means to ``OccurredTime.is_in_the_future``:
  for a moment, later than the current moment plus the grace; for a day,
  after today's date. A date after today is in the future whatever clock time
  comes with it. A half of the day said without a clock time ("昨天晚上",
  "今天下午") gives the day, with a caution; it may not begin after the
  current moment either, so "今天晚上" said in the afternoon is in the
  future, and so is "晚上" alone.
- The present moment and a span back are cut to the whole minute, never
  rounded. A clock time has no seconds unless they were said.
- A clock time the clocks skipped that day does not exist. One they showed
  twice gives two candidates; where one of the two is still to come, the
  other is the only one that can be meant, and it comes back with a caution.
- A moment whose offset is not a whole number of minutes, which some zones
  had before the 1970s, cannot be written for the ledger and is not read.

``write_time`` writes an ``OccurredTime`` the way the ledger takes it: a date
as ``2026-10-03``; a moment always with its seconds and its offset, as
``2026-10-04T09:40:00+02:00``.

Names defined here: ``read_time``, ``write_time``, ``TimeReading``,
``TimeRecognised``, ``TwoCandidates`` and ``TimeRefused``. ``Refusal`` and
``TimeCaution`` come from ``time_wording`` and are named here as well.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from ledger_hand.core.time_wording import (
    Clock,
    DayOfMonth,
    DaysBack,
    DaySpec,
    MonthDay,
    OnADay,
    Refusal,
    SpanBack,
    TimeCaution,
    Weekday,
    WeekReckoning,
    read_phrase,
)
from ledger_hand.core.trade import OccurredTime, TimePrecision
from ledger_hand.core.validation import DEFAULT_FUTURE_GRACE
from ledger_hand.core.zones import zone_named

__all__ = [
    "Refusal",
    "TimeCaution",
    "TimeReading",
    "TimeRecognised",
    "TimeRefused",
    "TwoCandidates",
    "read_time",
    "write_time",
]

# A date without a year is looked for this many years back, today's year
# included: a 29 February can lie up to eight years back, across a year like
# 2100 that has none.
_YEARS_TO_LOOK_BACK = 9
_MONTHS_TO_LOOK_BACK = 12
_ONE_MINUTE = timedelta(minutes=1)


@dataclass(frozen=True)
class TimeRecognised:
    """One definite time."""

    time: OccurredTime
    cautions: tuple[TimeCaution, ...] = ()


@dataclass(frozen=True)
class TwoCandidates:
    """A clock time the clocks showed twice that day: both moments, the earlier first."""

    earlier: OccurredTime
    later: OccurredTime
    cautions: tuple[TimeCaution, ...] = ()


@dataclass(frozen=True)
class TimeRefused:
    """The phrase was not turned into a time."""

    reason: Refusal


TimeReading = TimeRecognised | TwoCandidates | TimeRefused


@dataclass(frozen=True)
class _Setting:
    """What every step needs: the current moment in the zone, the zone, and the grace."""

    local_now: datetime
    zone: ZoneInfo
    zone_name: str
    grace: timedelta

    @property
    def current_day(self) -> date:
        return self.local_now.date()


def read_time(
    text: str, now: datetime, zone: str, grace: timedelta = DEFAULT_FUTURE_GRACE
) -> TimeReading:
    """Turn ``text`` into a definite time, as seen from ``now`` in the zone named ``zone``.

    ``grace`` is how far after ``now`` a moment may lie and still count as not
    in the future, to allow for clocks that differ a little.
    """
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ValueError("the current moment must be a datetime that carries an offset")
    if grace < timedelta(0):
        raise ValueError("the grace cannot be negative")
    zone_info = zone_named(zone)
    phrase = read_phrase(text)
    if isinstance(phrase, Refusal):
        return TimeRefused(phrase)
    try:
        setting = _Setting(now.astimezone(zone_info), zone_info, zone, grace)
        if isinstance(phrase, OnADay):
            return _on_a_day(phrase, setting)
        span = phrase.span if isinstance(phrase, SpanBack) else timedelta(0)
        return _moment_back(span, setting)
    except OverflowError:
        # Counted back or ahead past the first or the last date Python holds.
        return TimeRefused(Refusal.UNKNOWN_WORDING)


def write_time(occurred: OccurredTime) -> str:
    """``occurred`` as the ledger writes a time: a date, or a moment with seconds and offset.

    Raises ``ValueError`` for a moment whose offset is not a whole number of
    minutes, which the ledger's way of writing cannot hold.
    """
    value = occurred.value
    if not isinstance(value, datetime):
        return value.isoformat()
    offset = value.utcoffset()
    if offset is None or offset % _ONE_MINUTE:
        raise ValueError(f"the offset of {value!r} is not a whole number of minutes")
    return value.isoformat(timespec="seconds")


def _moment_back(span: timedelta, setting: _Setting) -> TimeReading:
    """The moment ``span`` of real time before the current one, cut to the minute."""
    instant = setting.local_now.astimezone(timezone.utc) - span
    moment = instant.replace(second=0, microsecond=0).astimezone(setting.zone)
    return _from_passes([moment], TimePrecision.MINUTE, (), setting)


def _on_a_day(phrase: OnADay, setting: _Setting) -> TimeReading:
    day = _date_of(phrase.day, setting.current_day)
    if isinstance(day, Refusal):
        return TimeRefused(day)
    whole_day = OccurredTime(day, TimePrecision.DAY, setting.zone_name)
    if whole_day.is_in_the_future(setting.local_now, setting.grace):
        return TimeRefused(Refusal.IN_THE_FUTURE)
    if phrase.clock is None:
        if phrase.not_before is not None and _begins_later(day, phrase.not_before, setting):
            return TimeRefused(Refusal.IN_THE_FUTURE)
        return TimeRecognised(whole_day, phrase.cautions)
    return _at_clock(day, phrase.clock, phrase.cautions, setting)


def _begins_later(day: date, start: time, setting: _Setting) -> bool:
    """Whether ``start`` on ``day`` is later than the current moment and the grace."""
    begins = datetime.combine(day, start, tzinfo=setting.zone).astimezone(timezone.utc)
    return begins > setting.local_now.astimezone(timezone.utc) + setting.grace


def _at_clock(
    day: date, clock: Clock, cautions: tuple[TimeCaution, ...], setting: _Setting
) -> TimeReading:
    wall = datetime.combine(day, time(clock.hour, clock.minute, clock.second or 0))
    passes = _passes(wall, setting.zone)
    if not passes:
        return TimeRefused(Refusal.DOES_NOT_EXIST)
    precision = TimePrecision.MINUTE if clock.second is None else TimePrecision.SECOND
    return _from_passes(passes, precision, cautions, setting)


def _passes(wall: datetime, zone: ZoneInfo) -> list[datetime]:
    """The moments at which the clocks of ``zone`` showed ``wall``, in order.

    None where the clocks skipped it, two where they showed it twice. Each
    reading is taken through UTC and back: a reading the clocks never showed
    does not come back as itself.
    """
    readings = [wall.replace(tzinfo=zone, fold=fold) for fold in (0, 1)]
    shown = [
        reading
        for reading in readings
        if reading.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None) == wall
    ]
    instants = sorted({reading.astimezone(timezone.utc): reading for reading in shown}.items())
    return [reading for _, reading in instants]


def _from_passes(
    passes: list[datetime],
    precision: TimePrecision,
    cautions: tuple[TimeCaution, ...],
    setting: _Setting,
) -> TimeReading:
    """The answer for the one or two moments a phrase came to."""
    if any(_offset_has_seconds(moment) for moment in passes):
        return TimeRefused(Refusal.UNKNOWN_WORDING)
    times = [OccurredTime(moment, precision, setting.zone_name) for moment in passes]
    past = [one for one in times if not one.is_in_the_future(setting.local_now, setting.grace)]
    if not past:
        return TimeRefused(Refusal.IN_THE_FUTURE)
    if len(past) == 2:
        return TwoCandidates(past[0], past[1], cautions)
    if len(times) == 2:
        return TimeRecognised(past[0], (*cautions, TimeCaution.OTHER_PASS_TO_COME))
    return TimeRecognised(past[0], cautions)


def _offset_has_seconds(moment: datetime) -> bool:
    offset = moment.utcoffset()
    return offset is None or bool(offset % _ONE_MINUTE)


# --- which date a day spec means ---------------------------------------------


def _date_of(spec: DaySpec, today: date) -> date | Refusal:
    if isinstance(spec, DaysBack):
        return today - timedelta(days=spec.days)
    if isinstance(spec, Weekday):
        return _weekday_date(spec, today)
    if isinstance(spec, MonthDay):
        return _month_day_date(spec, today)
    return _day_of_month_date(spec, today)


def _weekday_date(spec: Weekday, today: date) -> date | Refusal:
    monday = today - timedelta(days=today.weekday())
    in_week = {
        WeekReckoning.LAST_WEEK: -7,
        WeekReckoning.TWO_WEEKS_AGO: -14,
        WeekReckoning.THIS_WEEK: 0,
        WeekReckoning.NEXT_WEEK: 7,
    }
    if spec.reckoning in in_week:
        return monday + timedelta(days=in_week[spec.reckoning] + spec.weekday)
    if spec.reckoning is WeekReckoning.LATEST:
        return today - timedelta(days=(today.weekday() - spec.weekday) % 7)
    # "last Friday": the latest Friday before today, and the Friday of last week.
    latest_before = today - timedelta(days=(today.weekday() - spec.weekday - 1) % 7 + 1)
    of_last_week = monday + timedelta(days=spec.weekday - 7)
    return latest_before if latest_before == of_last_week else Refusal.AMBIGUOUS


def _month_day_date(spec: MonthDay, today: date) -> date | Refusal:
    if spec.year is not None or spec.years_back is not None:
        year = spec.year if spec.year is not None else today.year - (spec.years_back or 0)
        return _valid_date(year, spec.month, spec.day) or Refusal.UNKNOWN_WORDING
    if _still_to_come(_valid_date(today.year, spec.month, spec.day), today):
        return Refusal.AMBIGUOUS
    for back in range(_YEARS_TO_LOOK_BACK):
        found = _valid_date(today.year - back, spec.month, spec.day)
        if found is not None and found <= today:
            return found
    # A day no year has, such as 30 February.
    return Refusal.UNKNOWN_WORDING


def _day_of_month_date(spec: DayOfMonth, today: date) -> date | Refusal:
    if spec.months_back is not None:
        year, month = _month_back(today, spec.months_back)
        return _valid_date(year, month, spec.day) or Refusal.UNKNOWN_WORDING
    if _still_to_come(_valid_date(today.year, today.month, spec.day), today):
        return Refusal.AMBIGUOUS
    for back in range(_MONTHS_TO_LOOK_BACK):
        found = _valid_date(*_month_back(today, back), spec.day)
        if found is not None and found <= today:
            return found
    return Refusal.UNKNOWN_WORDING


def _still_to_come(day: date | None, today: date) -> bool:
    """Whether ``day`` exists and lies after today.

    A date said without its year (or a day without its month) whose day this
    year (this month) is still to come may mean the one before, or a slip of
    the tongue; neither is guessed.
    """
    return day is not None and day > today


def _month_back(today: date, months: int) -> tuple[int, int]:
    """The year and month that lie ``months`` months before today's month."""
    index = today.year * 12 + today.month - 1 - months
    return index // 12, index % 12 + 1


def _valid_date(year: int, month: int, day: int) -> date | None:
    """The date, or ``None`` when there is no such day."""
    try:
        return date(year, month, day)
    except ValueError:
        return None
