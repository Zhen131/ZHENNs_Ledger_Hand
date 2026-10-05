"""The wording of a time phrase: which known parts it is made of, and what they say.

``read_phrase`` takes a short piece of text that is supposed to be one time,
such as "昨天晚上 9 点 40" or "last Friday 3pm", and says what its words say
without looking at any calendar or clock:

- ``RightNow``: the phrase means the present moment ("刚才", "just now");
- ``SpanBack``: a span of time back from the present ("20 分钟前", "2 hours
  ago");
- ``OnADay``: a day, named as words and not yet as a date ("yesterday", "the
  Friday of last week", "October 2"), with or without a clock time. The
  clock time already has the half of the day applied, so it is on a 24-hour
  clock;
- a ``Refusal``: the wording is not one this module reads, or it can mean
  more than one time.

Only wording made entirely of known parts is read. The text is taken apart
from left to right, and every part must be one of those listed here: a word
for the present, a span back, a day word, a weekday, a date, a half of the
day, a clock time, and the few small words that join them ("at", "on", a
comma). The parts must then stand in one of a few known orders. A single part
that is not known, or known parts in another order, make the whole text
unknown: nothing is skipped, and nothing is read from what is left over.

Before it is taken apart, the text is put in a plain form: full-width
characters become their ordinary forms, the ideographic space and the
no-break space become ordinary gaps, a typographic apostrophe becomes a
plain one, ordinary capital letters become small ones, and runs of gaps
become one gap. A gap next to a Chinese character is dropped, since Chinese
is written without gaps. Nothing else is changed: a letter in another form
(mathematical, superscript), a digit of another script, a zero-width
character and any other gap are not parts of any known word, so a text that
holds one is not read. A text longer than ``MAX_PHRASE_LENGTH`` is not read
at all; no time phrase is that long.

Chinese numbers in counts, clock times and dates are read by
``numbers.read_number``; a year written in Chinese digits ("二〇二六") is
read digit by digit, since it is not said as a number.

What this module decides from the words alone:

- A clock time without a half of the day is read on a 24-hour clock; when its
  hour is 12 or less, a ``TimeCaution`` says that no half was said.
- A clock time that may fall on either side of midnight is ambiguous:
  midnight itself ("晚上 12 点", "midnight", "12am", "24:00"), an evening
  word with an hour after midnight ("晚上 1 点"), and an evening word without
  any clock time ("昨天晚上", "last night"), because a night runs on past
  midnight into the next date.
- A half of the day that does not fit the hour ("早上 9pm", "下午 12 点") is
  ambiguous; so is a single-digit minute said without 分 ("九点五" may be
  9:05 or 9:50).
- A date written with slashes, points or dashes and without the year in
  front ("10/2", "2/10", "10.2") is ambiguous: places differ on whether the
  month or the day comes first.

Which actual date a day word means, and whether the time exists or lies in
the future, is decided by ``timeparse`` with the present moment in hand.

Names defined here: ``read_phrase``, ``MAX_PHRASE_LENGTH``, ``Refusal``,
``TimeCaution``, ``Half``, ``WeekReckoning``, ``DaysBack``, ``Weekday``,
``MonthDay``, ``DayOfMonth``, ``DaySpec``, ``Clock``, ``RightNow``,
``SpanBack``, ``OnADay`` and ``Phrase``.
"""

from __future__ import annotations

import enum
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import time, timedelta

from ledger_hand.core.numbers import Recognised, read_number

# Far longer than any time phrase, and short enough that a text of any length
# is turned away before anything else is done with it.
MAX_PHRASE_LENGTH = 80


class Refusal(enum.Enum):
    """Why a time phrase was not turned into a time."""

    UNKNOWN_WORDING = "the wording is not one this program reads"
    AMBIGUOUS = "the wording can mean more than one time"
    DOES_NOT_EXIST = "the clocks skipped that time on that day"
    IN_THE_FUTURE = "the time lies in the future"


class TimeCaution(enum.Enum):
    """Something to keep in mind about a time that was recognised."""

    NO_HALF_OF_DAY = "no half of the day was said, so the hour was read on a 24-hour clock"
    OTHER_PASS_TO_COME = (
        "the clocks showed this time twice that day; the second time is still to come"
    )


class Half(enum.Enum):
    """A part of the day said with a clock time, or the a.m. or p.m. after one."""

    SMALL_HOURS = "the small hours"
    MORNING = "morning"
    NOON = "noon"
    AFTERNOON = "afternoon"
    DUSK = "dusk"
    EVENING = "evening"
    AM = "a.m."
    PM = "p.m."


class WeekReckoning(enum.Enum):
    """Which one of the weekdays of that name is meant. A week starts on Monday."""

    LATEST = "the latest one, today included"
    LAST = "the latest one before today, but only where that is also the one of last week"
    LAST_WEEK = "the one in the calendar week before this one"
    TWO_WEEKS_AGO = "the one in the calendar week two before this one"
    THIS_WEEK = "the one in this calendar week"
    NEXT_WEEK = "the one in the calendar week after this one"


@dataclass(frozen=True)
class DaysBack:
    """A day counted back from today on the calendar: 0 is today, 1 yesterday, -1 tomorrow."""

    days: int


@dataclass(frozen=True)
class Weekday:
    """A day of the week (0 is Monday, 6 is Sunday) and which one of that name."""

    weekday: int
    reckoning: WeekReckoning


@dataclass(frozen=True)
class MonthDay:
    """A day of a month. The year is named, counted back from this one, or not said."""

    month: int
    day: int
    year: int | None = None
    years_back: int | None = None


@dataclass(frozen=True)
class DayOfMonth:
    """A day of a month that was not named: counted back from this month, or not said."""

    day: int
    months_back: int | None = None


DaySpec = DaysBack | Weekday | MonthDay | DayOfMonth


@dataclass(frozen=True)
class Clock:
    """A time of day on a 24-hour clock. ``second`` is ``None`` when no second was said."""

    hour: int
    minute: int
    second: int | None = None


@dataclass(frozen=True)
class RightNow:
    """The present moment."""


@dataclass(frozen=True)
class SpanBack:
    """A span of time back from the present moment."""

    span: timedelta


@dataclass(frozen=True)
class OnADay:
    """A day, and the time on it if one was said.

    ``not_before`` is the earliest time of day of a half of the day that was
    said without a clock time ("this afternoon"); it is ``None`` otherwise.
    """

    day: DaySpec
    clock: Clock | None = None
    not_before: time | None = None
    cautions: tuple[TimeCaution, ...] = ()


Phrase = RightNow | SpanBack | OnADay


@dataclass(frozen=True)
class _SaidClock:
    """A clock time as it was said: the hour (0 to 24) before any half is applied."""

    hour: int
    minute: int
    second: int | None = None
    suffix: Half | None = None


@dataclass(frozen=True)
class _Part:
    """One known part of a phrase.

    ``kind`` is the part's letter in the known orders (see ``_SHAPES``). A part
    whose own words can mean more than one thing carries ``Refusal.AMBIGUOUS``.
    """

    kind: str
    day: DaySpec | None = None
    half: Half | None = None
    said: _SaidClock | None = None
    span: timedelta | None = None
    refusal: Refusal | None = None


# The letters of the parts.
_NOW = "N"
_SPAN = "S"
_DAY = "D"
_DAY_AND_HALF = "X"
_HALF = "P"
_CLOCK = "C"
_BARE_HOUR = "H"
_AT = "A"
_ON = "O"
_COMMA = "K"

# The known orders. A clock part is a clock time with its own half of the day
# around it; a bare hour ("at 3") needs "at" in front of it or a half after
# it. The day comes first, or after the clock time as in "3pm on Friday".
_CLOCK_PART = f"(?:{_AT}?{_CLOCK}{_HALF}?|{_AT}?{_BARE_HOUR}{_HALF}|{_AT}{_BARE_HOUR})"
_DAY_PART = f"(?:{_ON}?{_DAY}|{_DAY_AND_HALF})"
_SHAPES = re.compile(
    f"{_NOW}|{_SPAN}"
    f"|(?:{_DAY_PART}{_COMMA}?)?{_HALF}?{_CLOCK_PART}"
    f"|{_CLOCK_PART}{_COMMA}?{_ON}?(?:{_DAY}|{_DAY_AND_HALF})"
    f"|{_DAY_PART}{_HALF}?"
    f"|{_HALF}"
)

# Full-width forms of the ASCII characters, and three characters that stand
# for a plain gap or apostrophe, each mapped to its plain form. Ordinary
# capitals become small letters; no other letter is touched, because some
# letters of other alphabets turn into ASCII ones when made small (the Kelvin
# sign becomes "k"), which would let them pass for ordinary words.
_PLAIN_FORMS = {code: code - 0xFEE0 for code in range(0xFF01, 0xFF5F)}
_PLAIN_FORMS.update(
    {
        ord("\N{IDEOGRAPHIC SPACE}"): ord(" "),
        ord("\N{NO-BREAK SPACE}"): ord(" "),
        ord("\N{RIGHT SINGLE QUOTATION MARK}"): ord("'"),
    }
)
_SMALL_LETTERS = {code: code + 32 for code in range(ord("A"), ord("Z") + 1)}
_GAPS = re.compile(r"[ \t]+")
# A gap beside any character outside ASCII, which in a known phrase is Chinese.
_GAP_BESIDE_CHINESE = re.compile(r" (?=[^\x00-\x7f])|(?<=[^\x00-\x7f]) ")

# Digits are spelled out as 0-9 throughout: the shorthand for "a digit" would
# also match the digits of every other script.
_CHINESE_DIGITS = "一二两三四五六七八九"
_CHINESE_CLOCK_NUMBER = f"[零{_CHINESE_DIGITS}十]{{1,3}}"
_CHINESE_DATE_NUMBER = "[一二三四五六七八九十]{1,3}"
_CHINESE_COUNT = f"[零{_CHINESE_DIGITS}十百]{{1,6}}"
_DIGIT_COUNT = "[1-9][0-9]{0,3}"
_CHINESE_YEAR_DIGITS: Mapping[str, int] = {
    "〇": 0,
    **dict(zip("零一二三四五六七八九", range(10), strict=True)),
}
_AGO = "(?:以前|之前|前)"

_ENGLISH_COUNTS: Mapping[str, int] = {
    "a": 1,
    "an": 1,
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
    "eleven": 11,
    "twelve": 12,
}

_NOW_WORDS = ("刚才", "刚刚", "现在", "此刻", "just now", "right now", "now")

_DAYS_BACK: Mapping[str, int] = {
    "今天": 0,
    "今日": 0,
    "昨天": 1,
    "昨日": 1,
    "前天": 2,
    "大前天": 3,
    "明天": -1,
    "明日": -1,
    "后天": -2,
    "大后天": -3,
    "today": 0,
    "yesterday": 1,
    "the day before yesterday": 2,
    "tomorrow": -1,
    "the day after tomorrow": -2,
}

_DAYS_BACK_WITH_HALF: Mapping[str, tuple[int, Half]] = {
    "今早": (0, Half.MORNING),
    "今晨": (0, Half.MORNING),
    "今晚": (0, Half.EVENING),
    "昨晚": (1, Half.EVENING),
    "昨夜": (1, Half.EVENING),
    "明早": (-1, Half.MORNING),
    "明晚": (-1, Half.EVENING),
    "this morning": (0, Half.MORNING),
    "this afternoon": (0, Half.AFTERNOON),
    "this evening": (0, Half.EVENING),
    "tonight": (0, Half.EVENING),
    "last night": (1, Half.EVENING),
}

_HALF_WORDS: Mapping[str, Half] = {
    "凌晨": Half.SMALL_HOURS,
    "早上": Half.MORNING,
    "早晨": Half.MORNING,
    "清晨": Half.MORNING,
    "早": Half.MORNING,
    "上午": Half.MORNING,
    "中午": Half.NOON,
    "下午": Half.AFTERNOON,
    "午后": Half.AFTERNOON,
    "傍晚": Half.DUSK,
    "晚上": Half.EVENING,
    "晚间": Half.EVENING,
    "夜里": Half.EVENING,
    "夜晚": Half.EVENING,
    "晚": Half.EVENING,
    "in the morning": Half.MORNING,
    "morning": Half.MORNING,
    "in the afternoon": Half.AFTERNOON,
    "afternoon": Half.AFTERNOON,
    "in the evening": Half.EVENING,
    "evening": Half.EVENING,
    "at night": Half.EVENING,
    "night": Half.EVENING,
}

# Halves of the night that never say on which side of midnight they are.
_UNCLEAR_HALF_WORDS = ("半夜", "深夜", "午夜")

_SUFFIXES: Mapping[str, Half] = {"am": Half.AM, "a.m": Half.AM, "pm": Half.PM, "p.m": Half.PM}

# The hour on a 24-hour clock that each said hour stands for after a half of
# the day. A said hour that is missing does not fit that half.
_HOURS_IN_HALF: Mapping[Half, Mapping[int, int]] = {
    Half.SMALL_HOURS: {hour: hour for hour in range(7)},
    Half.MORNING: {hour: hour for hour in range(1, 12)},
    Half.NOON: {11: 11, 12: 12, 1: 13, 2: 14, 13: 13, 14: 14},
    Half.AFTERNOON: {
        **{hour: hour + 12 for hour in range(1, 12)},
        **{hour: hour for hour in range(13, 24)},
    },
    Half.DUSK: {
        **{hour: hour + 12 for hour in range(4, 9)},
        **{hour: hour for hour in range(16, 21)},
    },
    Half.EVENING: {
        **{hour: hour + 12 for hour in range(5, 12)},
        **{hour: hour for hour in range(17, 24)},
    },
    Half.AM: {hour: hour for hour in range(1, 12)},
    Half.PM: {**{hour: hour + 12 for hour in range(1, 12)}, 12: 12},
}

# The earliest time of each half that may be said without a clock time. The
# evening is missing on purpose: a night runs on past midnight, so a date
# with an evening word and no clock time may be meant as the next date.
_EARLIEST_IN_HALF: Mapping[Half, time] = {
    Half.SMALL_HOURS: time(0),
    Half.MORNING: time(0),
    Half.NOON: time(11),
    Half.AFTERNOON: time(12),
    Half.DUSK: time(16),
}

_WEEKDAYS: Mapping[str, int] = {
    **dict(zip("一二三四五六", range(6), strict=True)),
    "日": 6,
    "天": 6,
    "monday": 0,
    "mon": 0,
    "tuesday": 1,
    "tues": 1,
    "tue": 1,
    "wednesday": 2,
    "wed": 2,
    "thursday": 3,
    "thurs": 3,
    "thur": 3,
    "thu": 3,
    "friday": 4,
    "fri": 4,
    "saturday": 5,
    "sat": 5,
    "sunday": 6,
    "sun": 6,
}

_MONTHS: Mapping[str, int] = {
    "january": 1,
    "jan": 1,
    "february": 2,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sept": 9,
    "sep": 9,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
}

_YEARS_BACK: Mapping[str, int] = {"今年": 0, "去年": 1, "前年": 2, "明年": -1}
_MONTHS_BACK: Mapping[str, int] = {
    "这个月": 0,
    "本月": 0,
    "上个月": 1,
    "上月": 1,
    "下个月": -1,
    "下月": -1,
}

# The fixed minutes after 点: on the hour, half past, a quarter, three quarters.
_FIXED_MINUTES: Mapping[str, int] = {"整": 0, "半": 30, "一刻": 15, "三刻": 45}


def _any_of(words: Iterable[str]) -> str:
    """A pattern for any one of ``words``, the longest tried first."""
    return "(?:" + "|".join(re.escape(word) for word in sorted(words, key=len, reverse=True)) + ")"


def _english(pattern: str) -> str:
    """``pattern`` that may not run on into more letters."""
    return f"(?:{pattern})(?![a-z])"


_COUNT = f"(?P<count>{_DIGIT_COUNT}|{_CHINESE_COUNT})"
_ENGLISH_COUNT = f"(?P<count>{_DIGIT_COUNT}|{_any_of(_ENGLISH_COUNTS)})"
_SUFFIX = r"(?P<suffix>a\.m\.?|am|p\.m\.?|pm)(?![a-z])"
_YEAR_AFTER = r"(?:,? (?P<year>[1-9][0-9]{3})(?![0-9]))?"
_ORDINAL_DAY = "(?P<day>[0-9]{1,2})(?P<ordinal>st|nd|rd|th)?(?![0-9a-z])"
_MONTH_NAME = rf"(?P<month>{_any_of(_MONTHS)})(?![a-z])\.?"

_Reader = Callable[[re.Match[str]], _Part | None]


def read_phrase(text: str) -> Phrase | Refusal:
    """What the words of ``text`` say about a time, or why they say no single time."""
    if len(text) > MAX_PHRASE_LENGTH:
        return Refusal.UNKNOWN_WORDING
    plain = _GAPS.sub(" ", text.translate(_PLAIN_FORMS).translate(_SMALL_LETTERS)).strip()
    parts = _parts(_GAP_BESIDE_CHINESE.sub("", plain))
    if not parts or _SHAPES.fullmatch("".join(part.kind for part in parts)) is None:
        return Refusal.UNKNOWN_WORDING
    for part in parts:
        if part.refusal is not None:
            return part.refusal
    if not _on_stands_before_a_weekday_or_date(parts):
        return Refusal.UNKNOWN_WORDING
    return _phrase(parts)


def _parts(text: str) -> list[_Part] | None:
    """``text`` taken apart into known parts; ``None`` when some stretch is no known part."""
    parts: list[_Part] = []
    position = 0
    while position < len(text):
        if text[position] == " ":
            position += 1
            continue
        found = _part_at(text, position)
        if found is None:
            return None
        part, position = found
        parts.append(part)
    return parts


def _part_at(text: str, position: int) -> tuple[_Part, int] | None:
    """The first known part that begins at ``position``, and where it ends."""
    for pattern, reader in _READERS:
        match = pattern.match(text, position)
        if match is not None:
            part = reader(match)
            return None if part is None else (part, match.end())
    return None


def _on_stands_before_a_weekday_or_date(parts: Sequence[_Part]) -> bool:
    """Whether every "on" is followed by a weekday or a date, as in "on Friday"."""
    for part, after in zip(parts, parts[1:], strict=False):
        if part.kind == _ON and not isinstance(after.day, Weekday | MonthDay | DayOfMonth):
            return False
    return True


def _phrase(parts: Sequence[_Part]) -> Phrase | Refusal:
    """The phrase that parts in a known order make up."""
    first = parts[0]
    if first.kind == _NOW:
        return RightNow()
    if first.span is not None:
        return SpanBack(first.span)
    day = next((part.day for part in parts if part.day is not None), DaysBack(0))
    halves = [part.half for part in parts if part.half is not None]
    said = next((part.said for part in parts if part.said is not None), None)
    if said is None:
        return _without_clock(day, halves)
    return _with_clock(day, halves, said)


def _without_clock(day: DaySpec, halves: Sequence[Half]) -> OnADay | Refusal:
    """A day, perhaps with a half of it, and no clock time."""
    if not halves:
        return OnADay(day)
    if len(set(halves)) > 1:
        return Refusal.AMBIGUOUS
    earliest = _EARLIEST_IN_HALF.get(halves[0])
    if earliest is None:
        return Refusal.AMBIGUOUS
    return OnADay(day, not_before=earliest)


def _with_clock(day: DaySpec, halves: Sequence[Half], said: _SaidClock) -> OnADay | Refusal:
    """A day and a clock time, with every half of the day that was said around it."""
    constraints = [*halves, *([said.suffix] if said.suffix is not None else [])]
    if not constraints:
        clock = Clock(said.hour, said.minute, said.second)
        caution = (TimeCaution.NO_HALF_OF_DAY,) if said.hour <= 12 else ()
        return OnADay(day, clock, cautions=caution)
    hours = {_hour_in(half, said.hour) for half in constraints}
    if Refusal.UNKNOWN_WORDING in hours:
        return Refusal.UNKNOWN_WORDING
    if len(hours) > 1 or Refusal.AMBIGUOUS in hours:
        return Refusal.AMBIGUOUS
    hour = hours.pop()
    if isinstance(hour, Refusal):
        return hour
    return OnADay(day, Clock(hour, said.minute, said.second))


def _hour_in(half: Half, said_hour: int) -> int | Refusal:
    """The hour on a 24-hour clock that ``said_hour`` stands for in ``half``."""
    if half in (Half.AM, Half.PM) and not 1 <= said_hour <= 12:
        # "15pm" and "0am" are no way of writing a time.
        return Refusal.UNKNOWN_WORDING
    hour = _HOURS_IN_HALF[half].get(said_hour)
    return Refusal.AMBIGUOUS if hour is None else hour


# --- reading single parts ---------------------------------------------------


def _whole(text: str) -> int | None:
    """A whole number written in digits or said in Chinese number words."""
    if text[0] in "0123456789":
        return int(text)
    reading = read_number(text)
    if not isinstance(reading, Recognised) or reading.unit is not None or reading.cautions:
        return None
    exponent = reading.value.as_tuple().exponent
    if not isinstance(exponent, int) or exponent < 0:
        return None
    return int(reading.value)


def _count(text: str) -> int | None:
    """A count of at least one: digits, Chinese number words, or an English word."""
    count = _ENGLISH_COUNTS.get(text)
    if count is None:
        count = _whole(text)
    return count if count is not None and count >= 1 else None


def _read_now(_match: re.Match[str]) -> _Part | None:
    return _Part(_NOW)


def _read_span(match: re.Match[str]) -> _Part | None:
    count = _count(match["count"])
    if count is None:
        return None
    minutes = count if match["unit"].startswith(("分", "m")) else 60 * count
    return _Part(_SPAN, span=timedelta(minutes=minutes))


def _read_span_with_half(match: re.Match[str]) -> _Part | None:
    """A span of half an hour, or of a whole number of hours and a half."""
    said_count = match.groupdict().get("count")
    hours = 0 if said_count is None else _count(said_count)
    if hours is None:
        return None
    return _Part(_SPAN, span=timedelta(minutes=60 * hours + 30))


def _read_days_ago(match: re.Match[str]) -> _Part | None:
    count = _count(match["count"])
    return None if count is None else _Part(_DAY, day=DaysBack(count))


def _read_day_word(match: re.Match[str]) -> _Part | None:
    return _Part(_DAY, day=DaysBack(_DAYS_BACK[match[0]]))


def _read_day_with_half(match: re.Match[str]) -> _Part | None:
    days, half = _DAYS_BACK_WITH_HALF[match[0]]
    return _Part(_DAY_AND_HALF, day=DaysBack(days), half=half)


# What a prefix before 周, 星期 or 礼拜 says about which weekday of that name
# is meant. "上周五" and "上个星期五" are the Friday of last week.
_WEEK_PREFIXES: Mapping[str, WeekReckoning] = {
    "": WeekReckoning.LATEST,
    "上": WeekReckoning.LAST_WEEK,
    "上个": WeekReckoning.LAST_WEEK,
    "上上": WeekReckoning.TWO_WEEKS_AGO,
    "上上个": WeekReckoning.TWO_WEEKS_AGO,
    "这": WeekReckoning.THIS_WEEK,
    "这个": WeekReckoning.THIS_WEEK,
    "本": WeekReckoning.THIS_WEEK,
    "下": WeekReckoning.NEXT_WEEK,
    "下个": WeekReckoning.NEXT_WEEK,
}


def _chinese_reckoning(prefix: str, word: str) -> WeekReckoning | None:
    """Which weekday of that name a Chinese prefix means.

    With 周 the measure word 个 does not belong to the week but to the day:
    "上个周五" is "the previous Friday", which has the same two readings as
    "last Friday", and "上上个周五", the Friday before that, is not read.
    """
    if word == "周" and prefix == "上个":
        return WeekReckoning.LAST
    if word == "周" and prefix == "上上个":
        return None
    return _WEEK_PREFIXES[prefix]


def _read_chinese_weekday(match: re.Match[str]) -> _Part | None:
    reckoning = _chinese_reckoning(match["prefix"] or "", match["word"])
    if reckoning is None:
        return None
    return _Part(_DAY, day=Weekday(_WEEKDAYS[match["weekday"]], reckoning))


def _read_english_weekday(match: re.Match[str]) -> _Part | None:
    reckoning = WeekReckoning.LAST if match["last"] else WeekReckoning.LATEST
    return _Part(_DAY, day=Weekday(_WEEKDAYS[match["weekday"]], reckoning))


def _in_range(value: int | None, low: int, high: int) -> int | None:
    return value if value is not None and low <= value <= high else None


def _chinese_year(text: str) -> int | None:
    """A year in digits, or in Chinese digits read one by one ("二〇二六")."""
    if text[0] in "0123456789":
        return int(text)
    digits = [_CHINESE_YEAR_DIGITS[character] for character in text]
    if digits[0] == 0:
        return None
    return int("".join(map(str, digits)))


def _read_chinese_date(match: re.Match[str]) -> _Part | None:
    month = _in_range(_whole(match["month"]), 1, 12)
    day = _in_range(_whole(match["day"]), 1, 31)
    if month is None or day is None:
        return None
    year = None if match["year"] is None else _chinese_year(match["year"])
    if match["year"] is not None and year is None:
        return None
    years_back = None if match["years"] is None else _YEARS_BACK[match["years"]]
    return _Part(_DAY, day=MonthDay(month, day, year=year, years_back=years_back))


def _read_chinese_day_of_month(match: re.Match[str]) -> _Part | None:
    day = _in_range(_whole(match["day"]), 1, 31)
    if day is None:
        return None
    months_back = None if match["months"] is None else _MONTHS_BACK[match["months"]]
    return _Part(_DAY, day=DayOfMonth(day, months_back=months_back))


def _read_numeric_date(match: re.Match[str]) -> _Part | None:
    """A date with its year in front, as in 2026-10-02, 2026/10/2 or 2026.10.2."""
    month = _in_range(int(match["month"]), 1, 12)
    day = _in_range(int(match["day"]), 1, 31)
    if month is None or day is None:
        return None
    return _Part(_DAY, day=MonthDay(month, day, year=int(match["year"])))


def _read_unclear_date(_match: re.Match[str]) -> _Part | None:
    return _Part(_DAY, refusal=Refusal.AMBIGUOUS)


def _ordinal_fits(day: int, ordinal: str | None) -> bool:
    """Whether the ending written after a day number is the right one: 1st, 2nd, 11th."""
    if ordinal is None:
        return True
    endings = {1: "st", 2: "nd", 3: "rd"}
    right = "th" if 11 <= day % 100 <= 13 else endings.get(day % 10, "th")
    return ordinal == right


def _read_english_date(match: re.Match[str]) -> _Part | None:
    day = _in_range(int(match["day"]), 1, 31)
    if day is None or not _ordinal_fits(day, match["ordinal"]):
        return None
    year = None if match["year"] is None else int(match["year"])
    return _Part(_DAY, day=MonthDay(_MONTHS[match["month"]], day, year=year))


def _read_half(match: re.Match[str]) -> _Part | None:
    return _Part(_HALF, half=_HALF_WORDS[match[0]])


def _read_unclear_half(_match: re.Match[str]) -> _Part | None:
    return _Part(_HALF, refusal=Refusal.AMBIGUOUS)


def _chinese_minute(text: str) -> int | None:
    """A minute or second said after 点 or 分: digits, 零 and a digit, or number words."""
    if text[0] == "零" and len(text) == 2:
        return _whole(text[1])
    if text.startswith("零"):
        return 0 if text == "零" else None
    return _whole(text)


def _is_single_digit(text: str) -> bool:
    """Whether ``text`` is one digit, which after 点 may stand for a minute or for tens."""
    return len(text) == 1 and text != "十"


def _read_chinese_clock(match: re.Match[str]) -> _Part | None:
    hour = _in_range(_whole(match["hour"]), 0, 24)
    minute = _chinese_clock_minute(match)
    if minute is None:
        return None
    if isinstance(minute, Refusal):
        return _Part(_CLOCK, refusal=minute)
    second = None
    if match["second"] is not None:
        # A second is said only after a minute that ends in 分.
        second = _in_range(_chinese_minute(match["second"]), 0, 59)
        if second is None or match["fen"] is None:
            return None
    return _clock_part(hour, minute, second, None)


def _chinese_clock_minute(match: re.Match[str]) -> int | Refusal | None:
    """The minute after 点 or 时; ``None`` when what follows is no minute."""
    said = match["minute"]
    if match["mark"] == "点钟":
        # "九点钟" is nine o'clock and nothing more.
        return None if match["fixed"] or said else 0
    if match["fixed"] is not None:
        return _FIXED_MINUTES[match["fixed"]]
    if said is None:
        return 0
    if _is_single_digit(said) and match["fen"] is None:
        return Refusal.AMBIGUOUS
    return _in_range(_chinese_minute(said), 0, 59)


def _read_digital_clock(match: re.Match[str]) -> _Part | None:
    hour = _in_range(int(match["hour"]), 0, 24)
    minute = _in_range(int(match["minute"]), 0, 59)
    second = None if match["second"] is None else _in_range(int(match["second"]), 0, 59)
    if minute is None or (match["second"] is not None and second is None):
        return None
    return _clock_part(hour, minute, second, _suffix(match["suffix"]))


def _read_suffixed_hour(match: re.Match[str]) -> _Part | None:
    hour = _in_range(int(match["hour"]), 0, 24)
    return _clock_part(hour, 0, None, _suffix(match["suffix"]))


def _suffix(text: str | None) -> Half | None:
    """The half that an a.m. or p.m. stands for; ``None`` for none, or for "o'clock"."""
    if text is None:
        return None
    return _SUFFIXES.get(text.rstrip("."))


def _clock_part(
    hour: int | None, minute: int, second: int | None, suffix: Half | None
) -> _Part | None:
    """A clock part; 24 o'clock is the end of the day, which is midnight again."""
    if hour is None:
        return None
    if hour == 24:
        # "24pm" is no way of writing a time, and nor is "24:30".
        if minute or second or suffix in (Half.AM, Half.PM):
            return None
        return _Part(_CLOCK, refusal=Refusal.AMBIGUOUS)
    return _Part(_CLOCK, said=_SaidClock(hour, minute, second, suffix))


def _read_noon(_match: re.Match[str]) -> _Part | None:
    return _Part(_CLOCK, said=_SaidClock(12, 0, suffix=Half.NOON))


def _read_midnight(_match: re.Match[str]) -> _Part | None:
    return _Part(_CLOCK, refusal=Refusal.AMBIGUOUS)


def _read_bare_hour(match: re.Match[str]) -> _Part | None:
    hour = _in_range(int(match["hour"]), 0, 23)
    return None if hour is None else _Part(_BARE_HOUR, said=_SaidClock(hour, 0))


def _read_at(_match: re.Match[str]) -> _Part | None:
    return _Part(_AT)


def _read_on(_match: re.Match[str]) -> _Part | None:
    return _Part(_ON)


def _read_comma(_match: re.Match[str]) -> _Part | None:
    return _Part(_COMMA)


def _english_only(words: Iterable[str]) -> list[str]:
    return [word for word in words if word.isascii()]


def _chinese_only(words: Iterable[str]) -> list[str]:
    return [word for word in words if not word.isascii()]


# Every known part, in the order they are tried at each place in the text.
# Where one part could begin like another, the longer or more particular one
# comes first.
_READERS: tuple[tuple[re.Pattern[str], _Reader], ...] = tuple(
    (re.compile(pattern), reader)
    for pattern, reader in (
        (
            f"{_any_of(_chinese_only(_NOW_WORDS))}|{_english(_any_of(_english_only(_NOW_WORDS)))}",
            _read_now,
        ),
        (f"{_COUNT}(?P<unit>分钟|个小时|小时|个钟头|钟头){_AGO}", _read_span),
        (f"(?:{_COUNT}个半|半个?)(?:小时|钟头){_AGO}", _read_span_with_half),
        (
            f"{_ENGLISH_COUNT} {_english('(?P<unit>minutes|minute|mins|min|hours|hour|hrs|hr)')}"
            f" {_english('ago')}",
            _read_span,
        ),
        (_english("half an hour ago"), _read_span_with_half),
        (f"{_COUNT}天{_AGO}", _read_days_ago),
        (f"{_ENGLISH_COUNT} {_english('days|day')} {_english('ago')}", _read_days_ago),
        (
            f"{_any_of(_chinese_only(_DAYS_BACK_WITH_HALF))}"
            f"|{_english(_any_of(_english_only(_DAYS_BACK_WITH_HALF)))}",
            _read_day_with_half,
        ),
        (
            f"{_any_of(_chinese_only(_DAYS_BACK))}|{_english(_any_of(_english_only(_DAYS_BACK)))}",
            _read_day_word,
        ),
        (
            "(?P<prefix>上上个|上上|上个|上|这个|这|本|下个|下)?(?P<word>星期|礼拜|周)"
            "(?P<weekday>[一二三四五六日天])",
            _read_chinese_weekday,
        ),
        (
            rf"(?P<last>last )?(?P<weekday>{_any_of(_english_only(_WEEKDAYS))})(?![a-z])\.?",
            _read_english_weekday,
        ),
        (
            r"(?P<year>[1-9][0-9]{3})(?P<separator>[-/.])(?P<month>[0-9]{1,2})"
            r"(?P=separator)(?P<day>[0-9]{1,2})(?![0-9])",
            _read_numeric_date,
        ),
        (
            f"(?:(?P<year>[1-9][0-9]{{3}}|[〇零一二三四五六七八九]{{4}})年"
            f"|(?P<years>{_any_of(_YEARS_BACK)}))?"
            f"(?P<month>[0-9]{{1,2}}|{_CHINESE_DATE_NUMBER})月"
            f"(?P<day>[0-9]{{1,2}}|{_CHINESE_DATE_NUMBER})[日号]",
            _read_chinese_date,
        ),
        (
            f"(?P<months>{_any_of(_MONTHS_BACK)})?(?P<day>[0-9]{{1,2}}|{_CHINESE_DATE_NUMBER})[日号]",
            _read_chinese_day_of_month,
        ),
        (f"{_MONTH_NAME} {_ORDINAL_DAY}{_YEAR_AFTER}", _read_english_date),
        (f"(?:the )?{_ORDINAL_DAY}(?: of)? {_MONTH_NAME}{_YEAR_AFTER}", _read_english_date),
        (
            r"[0-9]{1,2}(?P<separator>[-/.])[0-9]{1,2}(?:(?P=separator)[0-9]{2,4})?(?![0-9])",
            _read_unclear_date,
        ),
        (
            f"{_any_of(_chinese_only(_HALF_WORDS))}|{_english(_any_of(_english_only(_HALF_WORDS)))}",
            _read_half,
        ),
        (_any_of(_UNCLEAR_HALF_WORDS), _read_unclear_half),
        (
            f"(?P<hour>[0-9]{{1,2}}|{_CHINESE_CLOCK_NUMBER})(?P<mark>点钟|点|时)"
            f"(?:(?P<fixed>{_any_of(_FIXED_MINUTES)})"
            f"|(?P<minute>[0-9]{{1,2}}|零[0-9]|{_CHINESE_CLOCK_NUMBER})(?P<fen>分)?"
            f"(?:(?P<second>[0-9]{{1,2}}|零[0-9]|{_CHINESE_CLOCK_NUMBER})秒)?)?"
            "(?![0-9])",
            _read_chinese_clock,
        ),
        (
            r"(?P<hour>[0-9]{1,2}):(?P<minute>[0-9]{2})(?::(?P<second>[0-9]{2}))?(?![0-9])"
            f"(?: ?{_SUFFIX})?",
            _read_digital_clock,
        ),
        (
            rf"(?P<hour>[0-9]{{1,2}}) ?(?:{_SUFFIX}|(?P<oclock>o'clock)(?![a-z]))",
            _read_suffixed_hour,
        ),
        (_english("(?:12 ?)?noon|midday"), _read_noon),
        (f"{_english('(?:12 ?)?midnight')}|子夜", _read_midnight),
        (r"(?P<hour>[0-9]{1,2})(?![0-9:.])", _read_bare_hour),
        (_english("at"), _read_at),
        (_english("on"), _read_on),
        (",", _read_comma),
    )
)
