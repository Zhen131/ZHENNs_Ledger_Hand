"""A stretch of time the user named ("10月", "last week", "最近7天") to two exact moments.

``read_period`` takes the words the model copied for a period, the current
moment and the name of the time zone, and gives back one of these:

- ``Period``: from ``start`` (inclusive) to ``end`` (exclusive), both
  midnight on the zone's wall clock, and the first and the last day of it;
- ``PeriodRefused``: the words are not read (``UNKNOWN_WORDING``), can mean
  more than one stretch of time (``AMBIGUOUS``), or the whole stretch lies
  after today (``IN_THE_FUTURE``).

It never guesses, and it never raises for a text it cannot read. It reads
neither the clock nor the machine's zone: both are handed in.

What it reads, in Chinese and in English:

- one day: whatever ``timeparse.read_time`` reads as a day ("今天",
  "10月6号", "Oct 6", "2026-10-06"). That reading is used as it stands, so
  what it finds ambiguous ("10/6") or in the future ("明天") is so here too.
  A phrase with a clock time, or a moment such as "刚才", names no stretch
  of days and is not read;
- one month: "10月", "10月份", "十月", "2026年10月", "上个月", "这个月",
  "本月", "October", "Oct 2026", "last month", "this month". "May" and
  "March" are also ordinary words ("May I ..."), so they count only with a
  year after them or "in", "during", "last", "this" before them, or as a
  side of a range that begins with "from" or "between";
- one year: "今年", "去年", "2026年", "this year", "last year", "in 2026",
  "the year 2026". Four digits alone ("2026") are not a year: a price or a
  quantity is written the same way (decided on 2026-11-24);
- one week, which starts on Monday: "这周", "本周", "上周", "this week",
  "last week";
- days counted back, today included: "最近7天", "过去30天", "近七天",
  "last 7 days", "past 30 days";
- a start and an end, each one of the above: "10月1号到10月15号",
  "10月1号到15号", "from Oct 1 to Oct 15". The stretch runs from the first
  day of the start to the last day of the end.

A month without its year is this year's when its first day has come, so
"11月" said on 24 November is all of November, its end still to come. When
this year's has not begun, the answer is ``AMBIGUOUS``: last year's may be
meant, and the program does not pick (the same rule as ``timeparse`` has
for a date without its year). "Next month" and "明年" lie wholly in the
future. A day is counted on the calendar: the day the clocks change is
from one midnight to the next, 23 or 25 hours long.

Before it is read, the text is tidied: compatibility forms become ordinary
characters, letter case does not count, runs of whitespace count as one,
whitespace beside a Chinese character goes, a full stop or question mark at
the end goes, and so do a few words around a period that say nothing more
("in", "during" in front; "的", "内", "里", "期间" behind).

A stretch that begins before ``EARLIEST_YEAR`` is not read, whoever wrote it.

``find_period_words`` looks through a whole sentence for the words that
name a stretch of time, so that the program can take the time from the
user's own words when the model did not copy it. Better to find nothing
than the wrong thing: a piece counts only when it has one of the shapes on
the list of ``period_list`` and ``read_period`` reads it as a stretch, or
as one with two meanings or in the future; a piece may not start or
end inside a run of Latin letters or digits, nor at a gap or a mark, nor
end with a word that says nothing more ("的"); the
longest pieces are kept first, and a piece that overlaps one already kept
is not ("10月6号" is one, and the "10月" inside it is not another).

Names defined here: ``PeriodRefusal``, ``Period``, ``PeriodRefused``,
``PeriodReading``, ``EARLIEST_YEAR``, ``read_period`` and
``find_period_words``.
"""

from __future__ import annotations

import enum
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from ledger_hand.core.period_list import on_the_list
from ledger_hand.core.time_wording import MAX_PHRASE_LENGTH
from ledger_hand.core.timeparse import TimeRecognised, TimeRefused, read_time
from ledger_hand.core.trade import TimePrecision
from ledger_hand.core.zones import zone_named


class PeriodRefusal(enum.Enum):
    """Why the words were not turned into a stretch of time."""

    UNKNOWN_WORDING = "the wording is not one this program reads as a stretch of time"
    AMBIGUOUS = "the wording can mean more than one stretch of time"
    IN_THE_FUTURE = "the whole stretch of time lies in the future"


@dataclass(frozen=True)
class Period:
    """From ``start`` (inclusive) to ``end`` (exclusive); its first and last day."""

    start: datetime
    end: datetime
    first_day: date
    last_day: date


@dataclass(frozen=True)
class PeriodRefused:
    """The words were not turned into a stretch of time, and why."""

    reason: PeriodRefusal


PeriodReading = Period | PeriodRefused

# This is one person's ledger of their own trades, which are of recent
# years; a stretch before this year is taken for a number misread, never
# for a time. (Decided on 2026-11-24.)
EARLIEST_YEAR = 2000

# A count of days back longer than this is taken as a slip, not read.
_MOST_DAYS_BACK = 3660

_UNKNOWN = PeriodRefusal.UNKNOWN_WORDING
_AMBIGUOUS = PeriodRefusal.AMBIGUOUS
_FUTURE = PeriodRefusal.IN_THE_FUTURE

type _Days = tuple[date, date] | PeriodRefusal


def read_period(text: str, now: datetime, zone: str) -> PeriodReading:
    """The stretch of time ``text`` names, as seen from ``now`` in the zone named ``zone``."""
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ValueError("the current moment must be a datetime that carries an offset")
    zone_info = zone_named(zone)
    if not isinstance(text, str) or len(text) > MAX_PHRASE_LENGTH:
        return PeriodRefused(_UNKNOWN)
    local_now = now.astimezone(zone_info)
    try:
        days = _days(_tidy(text), local_now, zone)
        if isinstance(days, PeriodRefusal):
            return PeriodRefused(days)
        first, last = days
        if first.year < EARLIEST_YEAR:
            return PeriodRefused(_UNKNOWN)
        return Period(
            start=_midnight(first, zone_info),
            end=_midnight(last + timedelta(days=1), zone_info),
            first_day=first,
            last_day=last,
        )
    except OverflowError:
        # Counted past the first or the last date Python holds.
        return PeriodRefused(_UNKNOWN)


def _midnight(day: date, zone: ZoneInfo) -> datetime:
    """The first moment of ``day`` on the zone's wall clock, even where midnight was skipped."""
    wall = datetime(day.year, day.month, day.day, tzinfo=zone)
    return wall.astimezone(timezone.utc).astimezone(zone)


# --- tidying ------------------------------------------------------------------

_GAPS = re.compile(r"\s+")
_GAP_BESIDE_CHINESE = re.compile(r" (?=[^\x00-\x7f])|(?<=[^\x00-\x7f]) ")
_IN_FRONT = re.compile(r"^(?:in|during|over|for|within)\s+")
_BEHIND = ("期间", "的", "内", "里")
_ENDING_MARKS = ".?!。？！"


# What only counts as a time with "in" or "during" before it: a bare year
# and the month names that are also other words. The word is kept for them.
_NEEDS_A_MARK = re.compile(r"^(?:[1-9][0-9]{3}|may|march|mar)$")


def _tidy(text: str) -> str:
    plain = unicodedata.normalize("NFKC", text).casefold()
    plain = _GAP_BESIDE_CHINESE.sub("", _GAPS.sub(" ", plain).strip())
    plain = plain.rstrip(_ENDING_MARKS).strip()
    while True:
        shorter = _IN_FRONT.sub("", plain)
        if _NEEDS_A_MARK.match(shorter) and plain.startswith(("in ", "during ")):
            shorter = plain
        for word in _BEHIND:
            if shorter.endswith(word) and len(shorter) > len(word):
                shorter = shorter[: -len(word)]
        if shorter == plain:
            return plain
        plain = shorter


# --- a start and an end --------------------------------------------------------

_CHINESE_RANGE = re.compile(r"^(?:从)?(?P<start>.+?)(?:到|至|~)(?P<end>.+)$")
_ENGLISH_RANGE = re.compile(
    r"^(?:from (?P<start>.+?) (?:to|until|till|through)"
    r"|between (?P<first>.+?) and"
    r"|(?P<bare>.+?) (?:to|until|till|through)) (?P<end>.+)$"
)
_BARE_DAY = re.compile(r"^(?P<day>[0-9]{1,2})(?:号|日)$")


def _days(text: str, local_now: datetime, zone: str) -> _Days:
    found = _CHINESE_RANGE.match(text) or _ENGLISH_RANGE.match(text)
    if found is None:
        return _span(text, local_now, zone)
    words = dict(found.groupdict())
    start_words = words.get("start") or words.get("first") or words.get("bare") or ""
    # "from May to June", "between March and May": the range's words mark the
    # months; a bare "March to ..." does not.
    marked = words.get("bare") is None
    start = _span(_marked(start_words, marked), local_now, zone)
    if isinstance(start, PeriodRefusal):
        return start
    bare = _BARE_DAY.match(found["end"])
    if bare is not None and start[0] == start[1]:
        end = _same_month(start[0], int(bare["day"]))
    else:
        end = _span(_marked(found["end"], marked), local_now, zone)
    if isinstance(end, PeriodRefusal):
        return end
    if end[1] < start[0]:
        return _UNKNOWN
    if start[0] > local_now.date():
        return _FUTURE
    return start[0], end[1]


def _marked(side: str, marked: object) -> str:
    """A side of a range that is a month name like "may", marked when the range is."""
    if marked and side.strip() in _OTHER_WORDS:
        return f"in {side.strip()}"
    return side


def _same_month(start: date, day: int) -> _Days:
    """``day`` of the month ``start`` is in, as in "10月1号到15号"."""
    try:
        end = start.replace(day=day)
    except ValueError:
        return _UNKNOWN
    return (end, end) if end >= start else _UNKNOWN


# --- one stretch ---------------------------------------------------------------


def _span(text: str, local_now: datetime, zone: str) -> _Days:
    today = local_now.date()
    for reader in (_month, _year, _week, _days_back):
        found = reader(text.strip(), today)
        if found is not None:
            return found
    return _one_day(text.strip(), local_now, zone)


def _one_day(text: str, local_now: datetime, zone: str) -> _Days:
    reading = read_time(text, local_now, zone)
    if isinstance(reading, TimeRefused):
        refusal = reading.reason.name
        return PeriodRefusal[refusal] if refusal in ("AMBIGUOUS", "IN_THE_FUTURE") else _UNKNOWN
    if not isinstance(reading, TimeRecognised) or reading.time.precision is not TimePrecision.DAY:
        return _UNKNOWN
    day = reading.time.value
    if isinstance(day, datetime) or not isinstance(day, date):
        return _UNKNOWN
    return day, day


# --- numbers -------------------------------------------------------------------

_CHINESE_DIGITS = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7}
_CHINESE_DIGITS.update({"八": 8, "九": 9})
_CHINESE_NUMBER = "[一二两三四五六七八九十]{1,3}"
_ENGLISH_COUNTS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}


def _whole(text: str) -> int | None:
    """A count of 1 to 99 written in digits, in Chinese or as an English word."""
    if text.isascii() and text.isdigit():
        return int(text)
    if text in _ENGLISH_COUNTS:
        return _ENGLISH_COUNTS[text]
    tens, ten, ones = text.partition("十")
    if not ten:
        return _CHINESE_DIGITS.get(text) if len(text) == 1 else None
    high = 1 if not tens else _CHINESE_DIGITS.get(tens)
    low = 0 if not ones else _CHINESE_DIGITS.get(ones)
    if high is None or low is None or len(tens) > 1 or len(ones) > 1:
        return None
    return high * 10 + low


# --- months --------------------------------------------------------------------

_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}
_MONTHS.update({name[:3]: number for name, number in list(_MONTHS.items())})
_MONTHS["sept"] = 9
_MONTH_NAMES = "|".join(sorted(_MONTHS, key=len, reverse=True))

_CHINESE_MONTH = re.compile(
    rf"^(?:(?P<year>[1-9][0-9]{{3}})年)?(?P<month>[0-9]{{1,2}}|{_CHINESE_NUMBER})月份?$"
)
_ENGLISH_MONTH = re.compile(
    rf"^(?P<mark>in |during |last |this |the month of )?(?P<name>{_MONTH_NAMES})\.?"
    rf"(?:,? (?P<year>[1-9][0-9]{{3}}))?$"
)
# Month names that are also ordinary words ("May I ...", "march"): a time only
# with a year after them or a word such as "in" before them.
_OTHER_WORDS = frozenset({"may", "march", "mar"})
_MONTHS_AWAY = {
    "上上个月": -2,
    "上个月": -1,
    "上月": -1,
    "这个月": 0,
    "这月": 0,
    "本月": 0,
    "当月": 0,
    "下个月": 1,
    "下月": 1,
    "last month": -1,
    "this month": 0,
    "next month": 1,
}


def _month(text: str, today: date) -> _Days | None:
    if text in _MONTHS_AWAY:
        index = today.year * 12 + today.month - 1 + _MONTHS_AWAY[text]
        return _whole_month(index // 12, index % 12 + 1, today)
    found = _CHINESE_MONTH.match(text)
    if found is not None:
        month = _whole(found["month"])
    else:
        found = _ENGLISH_MONTH.match(text)
        if found is None:
            return _UNKNOWN if text in _OTHER_WORDS else None
        if found["name"] in _OTHER_WORDS and not (found["mark"] or found["year"]):
            return _UNKNOWN
        month = _MONTHS[found["name"]]
    if month is None or not 1 <= month <= 12:
        return _UNKNOWN
    if found["year"] is not None:
        return _whole_month(int(found["year"]), month, today)
    if month > today.month:
        # This year's has not begun; last year's may be meant. Not picked.
        return _AMBIGUOUS
    return _whole_month(today.year, month, today)


def _whole_month(year: int, month: int, today: date) -> _Days:
    first = date(year, month, 1)
    if first > today:
        return _FUTURE
    following = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return first, following - timedelta(days=1)


# --- years ---------------------------------------------------------------------

_YEARS_AWAY = {
    "前年": -2,
    "去年": -1,
    "今年": 0,
    "本年": 0,
    "明年": 1,
    "last year": -1,
    "this year": 0,
    "next year": 1,
}
# A year is read only with a mark: "年" after it, or "in", "during" or "year"
# before it. Four digits alone are as often a price or a quantity ("1000个ADA").
_YEAR = re.compile(r"^(?P<mark>in |during |(?:the )?year )?(?P<year>[1-9][0-9]{3})(?P<nian>年)?$")


def _year(text: str, today: date) -> _Days | None:
    if text in _YEARS_AWAY:
        year = today.year + _YEARS_AWAY[text]
    else:
        found = _YEAR.match(text)
        if found is None:
            return None
        if not (found["mark"] or found["nian"]):
            return _UNKNOWN
        year = int(found["year"])
    first = date(year, 1, 1)
    if first > today:
        return _FUTURE
    return first, date(year, 12, 31)


# --- weeks ---------------------------------------------------------------------

_WEEK_WORDS = ("周", "星期", "个星期", "礼拜", "个礼拜")
_WEEKS_AWAY: dict[str, int] = {"last week": -1, "this week": 0, "next week": 1}
for _word in _WEEK_WORDS:
    _WEEKS_AWAY.update({f"上{_word}": -1, f"这{_word}": 0, f"本{_word}": 0, f"下{_word}": 1})
_WEEKS_AWAY["这一周"] = 0


def _week(text: str, today: date) -> _Days | None:
    if text not in _WEEKS_AWAY:
        return None
    monday = today - timedelta(days=today.weekday()) + timedelta(weeks=_WEEKS_AWAY[text])
    if monday > today:
        return _FUTURE
    return monday, monday + timedelta(days=6)


# --- days counted back -----------------------------------------------------------

_CHINESE_BACK = re.compile(rf"^(?:最近|过去|近)(?P<count>[0-9]{{1,4}}|{_CHINESE_NUMBER})(?:天|日)$")
_ENGLISH_BACK = re.compile(r"^(?:the )?(?:last|past) (?P<count>[0-9]{1,4}|[a-z]+) days$")


def _days_back(text: str, today: date) -> _Days | None:
    found = _CHINESE_BACK.match(text) or _ENGLISH_BACK.match(text)
    if found is None:
        return None
    count = _whole(found["count"])
    if count is None or not 1 <= count <= _MOST_DAYS_BACK:
        return _UNKNOWN
    return today - timedelta(days=count - 1), today


# --- finding the words in a sentence ---------------------------------------------

# A time said in a sentence is far shorter than this; longer pieces are not tried.
_LONGEST_PIECE = 40
_DECIMAL = re.compile(r"[0-9]+(?:\.[0-9]+)+")
_EDGE_MARKS = " ,.;:!?，。；：！？、()（）\"'“”‘’"


def _is_latin(character: str) -> bool:
    return character.isascii() and character.isalnum()


def _may_stand_alone(text: str, start: int, end: int) -> bool:
    """Whether ``text[start:end]`` starts and ends at a word's edge, with no mark at either end.

    A piece that is only a number with points ("0.02") is never one, though
    the time reader may take it for a date written with points; nor is one
    that ends with a word that says nothing more ("的").
    """
    piece = text[start:end]
    if piece[0] in _EDGE_MARKS or piece[-1] in _EDGE_MARKS or _DECIMAL.fullmatch(piece):
        return False
    if piece.endswith(_BEHIND):
        return False
    if start > 0 and _is_latin(text[start - 1]) and _is_latin(piece[0]):
        return False
    return not (end < len(text) and _is_latin(text[end]) and _is_latin(piece[-1]))


def _names_a_stretch(piece: str, now: datetime, zone: str) -> bool:
    reading = read_period(piece, now, zone)
    return not (isinstance(reading, PeriodRefused) and reading.reason is _UNKNOWN)


def find_period_words(text: str, now: datetime, zone: str) -> tuple[str, ...]:
    """The pieces of ``text`` that name a stretch of time, longest first kept, in their order."""
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ValueError("the current moment must be a datetime that carries an offset")
    zone_named(zone)
    found: list[tuple[int, int]] = []
    for start in range(len(text)):
        for end in range(start + 1, min(len(text), start + _LONGEST_PIECE) + 1):
            piece = text[start:end]
            if (
                _may_stand_alone(text, start, end)
                and on_the_list(piece)
                and _names_a_stretch(piece, now, zone)
            ):
                found.append((start, end))
    kept: list[tuple[int, int]] = []
    for start, end in sorted(found, key=lambda span: (span[0] - span[1], span[0])):
        if all(end <= other_start or start >= other_end for other_start, other_end in kept):
            kept.append((start, end))
    return tuple(text[start:end] for start, end in sorted(kept))
