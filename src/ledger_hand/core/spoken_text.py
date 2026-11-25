"""What the user said, tidied into the writing the rest of the program reads.

``tidy_spoken`` takes one thing the user said and the time zone trades are
recorded in, and gives back ``Tidied``: the words as they were said, the
words tidied, and every change made, in the order of the words said
(``Change``). It changes how a number or a time is written, never what it
is:

- a number said in number words becomes digits ("两千五百八十" is "2580");
- a decimal with number words after the point becomes digits
  ("0.0000五四二三八" is "0.000054238");
- in a time, a year of two digits followed by a month becomes a year of
  four ("二六年十月" is "2026年10月"), and a month, a day, an hour and a
  minute become digits ("零九号" is "9号", "八点五分" is "8点05分");
- seconds after a minute are dropped ("十二分三十一秒" is "12分");
- "的", "呢", "这个" and "然后" between two parts of a time are dropped;
- a time zone said with a time is dropped when it is the zone handed in
  (``SPOKEN_ZONES``).

Each change is checked before it is made, and a change that fails its check
is not made at all. A number said in words must read, with ``read_number``,
as the same value before and after, with no caution. A decimal with words
after the point must be written digit for digit, and read with no caution.
A time is checked as a whole: the time tidied must be read by ``read_time``
(or, a year and a month alone, by ``read_period``) as one time, and as the
same time the words said read as, when they read as one. A time that fails
is left exactly as it was said, its numbers too.

What is not sure is left as it was: a single number word ("两个"), a number
ending in 一 that may begin the next word ("四百一股"), a number with a
unit and then more of the amount ("二十块五"), an approximate amount, a
share, a point that may be a clock or a decimal ("八点二五"), a minute of one
word without 分 ("三点五"), a minute that goes on past a filler ("三点的五十
分"), money or a while in 分 ("零点五分", "二十点五分钟"), and every time of a
sentence that says another zone anywhere, or any zone not in
``SPOKEN_ZONES`` ("按北京时间算，……"). Words with no Chinese character in them are
handed back as they were: the way English is read was measured already.

This module reads no clock and no settings; the zone is handed in. It does
not decide what a number is for, and it does not change the words said: a
caller keeps them (``Tidied.said``) for the trade's own record of them.

Decided on 2026-11-25: the program tidies the words, the model is not asked
to, so a number or a time is never read by a model that may change it.

Names defined here: ``tidy_spoken``, ``Tidied``, ``Change``, ``ChangeKind``
and ``SPOKEN_ZONES``.
"""

from __future__ import annotations

import enum
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime

from ledger_hand.core.numbers import Recognised, read_number, write_number
from ledger_hand.core.time_range import Period, read_period
from ledger_hand.core.time_wording import Refusal
from ledger_hand.core.timeparse import TimeRecognised, TimeRefused, read_time
from ledger_hand.core.zones import is_zone_name, zone_named

# A time zone said aloud, and the zone it names. One more row is one more
# way of saying a zone; nothing else needs to change.
SPOKEN_ZONES: Mapping[str, str] = {
    "匈牙利时间": "Europe/Budapest",
    "布达佩斯时间": "Europe/Budapest",
    "北京时间": "Asia/Shanghai",
    "中国时间": "Asia/Shanghai",
}


class ChangeKind(enum.Enum):
    """What sort of change was made to the words said."""

    NUMBER = "a number said in number words, written in digits"
    MIXED_DECIMAL = "a decimal with number words after the point, written in digits"
    YEAR = "a year written in four digits"
    DATE = "a month or a day written in digits"
    CLOCK = "an hour or a minute written in digits"
    SECOND = "seconds dropped"
    FILLER = "a spoken word between two parts of a time dropped"
    ZONE = "a time zone said aloud, the one trades are recorded in, dropped"


@dataclass(frozen=True)
class Change:
    """One change: the words ``said`` at ``start`` to ``end`` became ``written``.

    ``written`` is empty for words dropped.
    """

    kind: ChangeKind
    said: str
    written: str
    start: int
    end: int


@dataclass(frozen=True)
class Tidied:
    """The words said, as they were (``said``) and tidied (``text``), and each change."""

    said: str
    text: str
    changes: tuple[Change, ...]

    @property
    def changed(self) -> bool:
        """Whether anything was changed."""
        return bool(self.changes)


# The moment a time is read as, to check it. It lies far ahead, so that no
# time said is turned away as in the future, and no date said without its
# year is ambiguous because this year's has not come yet.
_CHECK_MOMENT = (2100, 12, 31, 23, 59)

_CHINESE = re.compile("[一-鿿〇]")
_DIGIT_WORDS = "零一二三四五六七八九"
_DIGIT_VALUE = {word: value for value, word in enumerate(_DIGIT_WORDS)} | {"〇": 0, "两": 2}
_NUMBER_CHARACTERS = "零一二两三四五六七八九十百千万亿"
_SCALE_CHARACTERS = "百千万亿"
# Characters a part of a time may not follow, so that a part never begins
# inside a number ("五百三十点二" holds no clock).
_NOT_BEFORE_A_PART = f"0-9.:点〇{_NUMBER_CHARACTERS}"

_FILLERS = ("这个", "然后", "的", "呢")
_PUNCTUATION = "，,、。；;：:！!？?（）() \t"

_YEAR_WORDS = ("今年", "去年", "前年", "明年")
_MONTH_WORDS = ("这个月", "本月", "上个月", "上月", "下个月", "下月")
_DAY_WORDS = (
    "今天", "今日", "昨天", "昨日", "前天", "大前天", "明天", "明日", "后天", "大后天",
    "今早", "今晨", "今晚", "昨晚", "昨夜", "明早", "明晚",
)  # fmt: skip
_HALF_WORDS = (
    "凌晨", "早上", "早晨", "清晨", "早", "上午", "中午", "下午", "午后",
    "傍晚", "晚上", "晚间", "夜里", "夜晚", "晚", "半夜", "深夜", "午夜",
)  # fmt: skip


def _any_of(words: Sequence[str]) -> str:
    return "(?:" + "|".join(re.escape(word) for word in sorted(words, key=len, reverse=True)) + ")"


_CLOCK_NUMBER = "[零一二两三四五六七八九十]{1,3}"
_MINUTE_NUMBER = f"[0-9]{{1,2}}|零[0-9]|[{_DIGIT_WORDS}十]{{1,3}}"
_PART_SHAPES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("year", re.compile("(?P<number>[0-9]{4}|[〇零一二三四五六七八九]{4})年")),
    ("short_year", re.compile("(?P<number>[0-9]{2}|[〇零一二三四五六七八九]{2})年")),
    ("word", re.compile(_any_of((*_YEAR_WORDS, *_MONTH_WORDS, *_DAY_WORDS, *_HALF_WORDS)))),
    ("month", re.compile("(?P<number>[0-9]{1,2}|十[一二]|[一二三四五六七八九十])月")),
    (
        "day",
        re.compile(
            "(?P<number>[0-9]{1,2}|零[一二三四五六七八九]|三十一?"
            "|二十[一二三四五六七八九]?|十[一二三四五六七八九]?|[一二三四五六七八九])[号日]"
        ),
    ),
    (
        "word",
        re.compile("(?:上上个|上上|上个|上|这个|这|本|下个|下)?(?:星期|礼拜|周)[一二三四五六日天]"),
    ),
    (
        "clock",
        re.compile(
            f"(?P<hour>[0-9]{{1,2}}|{_CLOCK_NUMBER})(?P<mark>点钟|点|时)"
            f"(?:(?P<fixed>整|半|一刻|三刻)"
            f"|(?P<minute>{_MINUTE_NUMBER})(?:(?P<fen>分)(?:(?P<second>{_MINUTE_NUMBER})秒)?)?)?"
            "(?![0-9])"
        ),
    ),
    (
        "digital",
        re.compile("(?P<hour>[0-9]{1,2}):(?P<minute>[0-9]{2})(?P<second>:[0-9]{2})?(?![0-9])"),
    ),
)
# What only a year or a month says, read as a stretch of time when nothing else is said.
_PERIOD_KINDS = frozenset({"year", "short_year", "month", "month_word", "year_word"})

_LATIN_ZONE = "(?:UTC|GMT|EST|EDT|PST|PDT|CST|CET|CEST)(?:\\s*[+-]\\s*[0-9]{1,2}(?::?[0-9]{2})?)?"
_ZONE_MARK_AFTER = re.compile(
    f"(?P<named>[一-鿿]{{1,4}}?时间)|[一-鿿]{{0,4}}?时区"
    f"|[东西][{_NUMBER_CHARACTERS}0-9]{{1,3}}区|(?i:{_LATIN_ZONE})(?![A-Za-z])"
)
_ZONE_MARK_BEFORE = re.compile(
    f"(?:(?P<named>时间)|时区|[东西][{_NUMBER_CHARACTERS}0-9]{{1,3}}区"
    f"|(?<![A-Za-z])(?i:{_LATIN_ZONE}))$"
)

# A minute said after a filler: the time goes on past its parts.
_MINUTE_AFTER = re.compile(f"[0-9{_NUMBER_CHARACTERS}]+[分秒]")
# A zone said anywhere: 时区, 东X区 or 西X区, or a Latin name of one.
_OTHER_ZONE_MARK = re.compile(
    f"时区|[东西][{_NUMBER_CHARACTERS}0-9]{{1,3}}区"
    "|(?<![A-Za-z])(?i:UTC|GMT|EST|EDT|PST|PDT|CST|CET|CEST|JST|HKT|SGT|KST|AEST|AEDT)"
    "(?![A-Za-z])"
)
# How the zone trades are recorded in may be said with words between ("匈牙利那边的时间").
_SAME_ZONE_BETWEEN = ("", "的", "那边的", "这边的")

# Units a number may stand before. A number followed by one is an amount.
_UNITS = ("个", "股", "枚", "颗", "美金", "美元", "刀", "块", "欧", "欧元", "币", "份")
# Units after which more of the amount may follow ("二十块五", "十二个半").
_UNITS_WITH_CHANGE = (*_UNITS, "毛", "角", "分")
# Words before an amount of money: a point after them is a decimal point.
_MONEY_WORDS = (
    "均价", "价格", "成交价", "股价", "手续费", "成交额", "总额", "花了", "数量", "成交量",
)  # fmt: skip
_BETWEEN_MONEY_WORD_AND_NUMBER = "是在呢了为：: "
_ROUGHLY_BEFORE = ("大概", "大约", "约", "差不多", "将近")
_ROUGHLY_AFTER = ("多", "余", "来", "几", "左右")
# Words that hold number characters but say no amount, where the reading of
# numbers alone would still find one.
_NOT_AMOUNTS = ("十万火急", "一五一十", "千千万万", "万一", "千万")
# After a number, a character of a time: the time, not the number, is tidied.
_TIME_CHARACTERS = "月日号时分秒"

_MIXED_DECIMAL = re.compile(
    f"(?<![0-9A-Za-z.])(?P<whole>[0-9]+)\\.(?P<fraction>[0-9]*[{_DIGIT_WORDS}]+)"
    f"(?![0-9.点{_NUMBER_CHARACTERS}])"
)
# A unit after a number, then, gaps aside, more of the amount ("二十块 五", "二十U五").
_UNIT_THEN_MORE = re.compile(
    " *(?P<unit>[A-Za-z]+|\\$|"
    + "|".join(sorted(_UNITS_WITH_CHANGE, key=len, reverse=True))
    + f") *(?P<more>[{_NUMBER_CHARACTERS}半]*)"
)
_SAID_NUMBER = re.compile(f"[{_NUMBER_CHARACTERS}点]+")


@dataclass(frozen=True)
class _Part:
    kind: str
    match: re.Match[str]

    @property
    def start(self) -> int:
        return self.match.start()

    @property
    def end(self) -> int:
        return self.match.end()


@dataclass(frozen=True)
class _Segment:
    """Parts of one time said one after the other, and the fillers between them."""

    parts: tuple[_Part, ...]
    fillers: tuple[tuple[int, int], ...]

    @property
    def start(self) -> int:
        return self.parts[0].start

    @property
    def end(self) -> int:
        return self.parts[-1].end


def tidy_spoken(text: str, zone: str) -> Tidied:
    """``text`` tidied, for trades recorded in the zone named ``zone``.

    Raises ``ValueError`` when ``zone`` is not a time zone name: that is a
    mistake of the calling code.
    """
    if not is_zone_name(zone):
        raise ValueError(f"not a time zone name: {zone!r}")
    if _CHINESE.search(text) is None:
        return Tidied(said=text, text=text, changes=())
    changes: list[Change] = []
    kept: list[tuple[int, int]] = []
    other_zone = _other_zone_said(text, zone)
    for segment in _segments(text):
        found, span = _time_changes(text, segment, zone)
        if other_zone:
            found = []
        changes.extend(found)
        kept.append(span)
    changes.extend(_number_changes(text, kept))
    changes.sort(key=lambda change: change.start)
    return Tidied(said=text, text=_applied(text, changes), changes=tuple(changes))


def _applied(text: str, changes: Sequence[Change]) -> str:
    pieces: list[str] = []
    position = 0
    for change in changes:
        if change.start < position:
            raise AssertionError("two changes overlap")  # pragma: no cover
        pieces.append(text[position : change.start])
        pieces.append(change.written)
        position = change.end
    pieces.append(text[position:])
    return "".join(pieces)


# --- Times ---------------------------------------------------------------


def _segments(text: str) -> list[_Segment]:
    segments: list[_Segment] = []
    position = 0
    while position < len(text):
        first = _part_at(text, position)
        if first is None:
            position += 1
            continue
        parts = [first]
        fillers: list[tuple[int, int]] = []
        while True:
            after, gap = _after_fillers(text, parts[-1].end)
            following = _part_at(text, after)
            if following is None:
                break
            parts.append(following)
            fillers.extend(gap)
        segment = _Segment(tuple(parts), tuple(fillers))
        if _is_a_time(segment):
            segments.append(segment)
        position = segment.end
    return segments


def _after_fillers(text: str, position: int) -> tuple[int, list[tuple[int, int]]]:
    """Where the words after ``position`` go on once the fillers there are passed."""
    gap: list[tuple[int, int]] = []
    while True:
        filler = next((word for word in _FILLERS if text.startswith(word, position)), None)
        if filler is None or _part_at(text, position) is not None:
            return position, gap
        gap.append((position, position + len(filler)))
        position += len(filler)


def _part_at(text: str, position: int) -> _Part | None:
    """The longest part of a time that begins at ``position``, if any does."""
    if position > 0 and re.match(f"[{_NOT_BEFORE_A_PART}]", text[position - 1]):
        return None
    best: _Part | None = None
    for kind, shape in _PART_SHAPES:
        match = shape.match(text, position)
        if match is None or (best is not None and match.end() <= best.end):
            continue
        if kind == "short_year" and not _month_follows(text, match.end()):
            continue
        if kind == "word" and match[0] in (*_YEAR_WORDS, *_MONTH_WORDS):
            kind = "year_word" if match[0] in _YEAR_WORDS else "month_word"
        best = _Part(kind, match)
    return best


def _month_follows(text: str, position: int) -> bool:
    after, _gap = _after_fillers(text, position)
    following = _part_at(text, after)
    return following is not None and following.kind == "month"


def _is_a_time(segment: _Segment) -> bool:
    """Whether the parts surely say a time: two or more, or a clock that can be nothing else."""
    if len(segment.parts) > 1:
        return True
    part = segment.parts[0]
    if part.kind == "digital":
        return True
    if part.kind != "clock":
        return False
    match = part.match
    if match["fen"] is not None:
        # "零点五分" may be money, "二十点五分钟" a while: one word after 点 is not sure.
        return len(match["minute"]) > 1 or match["minute"] == "十"
    return match["mark"] != "时" and (match["fixed"] is not None or match["mark"] == "点钟")


def _time_changes(text: str, segment: _Segment, zone: str) -> tuple[list[Change], tuple[int, int]]:
    """The changes to one time, and the stretch of words to keep out of the numbers' way."""
    before = _zone_before(text, segment.start)
    after = _zone_after(text, segment.end)
    start = before[1] if before is not None else segment.start
    end = after[2] if after is not None else segment.end
    span = (start, end)
    zones = [said for said in (before, after) if said is not None]
    if any(said[0] != zone for said in zones):
        return [], span
    if _goes_on_unsure(text, segment):
        return [], span
    changes = _part_changes(text, segment)
    if changes is None or not _same_time(text, segment, changes, zone):
        return [], span
    for _named, zone_start, zone_end in zones:
        changes.append(_zone_dropped(text, zone_start, zone_end))
    if not changes:
        return [], span
    return changes, span


def _goes_on_unsure(text: str, segment: _Segment) -> bool:
    """Whether the time may go on past where its parts end, or may be a while, not a time.

    "三点的五十分" stops at "三点" for the parts, so the minute after the
    filler would be lost; "二十点十五分钟" is a while. Either way the time is
    left as said.
    """
    after, _gap = _after_fillers(text, segment.end)
    if _MINUTE_AFTER.match(text, after) is not None:
        return True
    return any(
        part.kind == "clock" and part.match["fen"] is not None and text.startswith("钟", part.end)
        for part in segment.parts
    )


def _other_zone_said(text: str, zone: str) -> bool:
    """Whether ``text`` says, or may say, a zone other than ``zone``, anywhere in it.

    Any such words leave every time of the sentence as said: tidied, its
    year would read, and the model might copy the time without the zone,
    to be read in ``zone``, hours off. 时区, 东X区, 西X区 or a Latin name of a
    zone always count. So does every 时间, unless it is the zone ``zone``
    itself as ``SPOKEN_ZONES`` says it (with 的, 那边的 or 这边的 between
    allowed: "匈牙利的时间"). A time of a trade said with 时间 ("成交的时间
    是……") is left as said too, and asked about.
    (Decided on 2026-11-25: none is let through but the ledger's own zone.)
    """
    if _OTHER_ZONE_MARK.search(text) is not None:
        return True
    return any(not _the_same_zone(text, found.start(), zone) for found in re.finditer("时间", text))


def _the_same_zone(text: str, position: int, zone: str) -> bool:
    """Whether the 时间 at ``position`` ends the zone ``zone`` as ``SPOKEN_ZONES`` says it."""
    head = text[:position]
    for said, named in SPOKEN_ZONES.items():
        place = said.removesuffix("时间")
        if named == zone and head.endswith(tuple(place + way for way in _SAME_ZONE_BETWEEN)):
            return True
    return False


def _zone_before(text: str, position: int) -> tuple[str, int, int] | None:
    """A zone said just before a time: the zone it names ("" for one not known), where it is."""
    end = position
    while end > 0:
        filler = next((word for word in _FILLERS if text.endswith(word, 0, end)), None)
        if filler is not None:
            end -= len(filler)
        elif text[end - 1] in _PUNCTUATION:
            end -= 1
        else:
            break
    head = text[:end]
    for said, named in SPOKEN_ZONES.items():
        if head.endswith(said):
            return named, end - len(said), _with_its_de(text, end)
    mark = _ZONE_MARK_BEFORE.search(head)
    if mark is None:
        return None
    if mark["named"] is not None:
        # Whether a word ending in 时间 is a zone is judged for the whole sentence.
        return None
    start = mark.start() if mark["named"] is None else max(0, mark.start() - 4)
    return "", start, end


def _with_its_de(text: str, end: int) -> int:
    return end + 1 if text.startswith("的", end) else end


def _zone_after(text: str, position: int) -> tuple[str, int, int] | None:
    """A zone said just after a time: the zone it names ("" for one not known), where it is."""
    start = position
    while start < len(text):
        filler = next((word for word in _FILLERS if text.startswith(word, start)), None)
        if filler is not None:
            start += len(filler)
        elif text[start] in _PUNCTUATION:
            start += 1
        else:
            break
    for said, named in SPOKEN_ZONES.items():
        if text.startswith(said, start):
            return named, start, start + len(said)
    mark = _ZONE_MARK_AFTER.match(text, start)
    if mark is None:
        return None
    if mark["named"] is not None:
        # Whether a word ending in 时间 is a zone is judged for the whole sentence.
        return None
    return "", start, mark.end()


def _zone_dropped(text: str, start: int, end: int) -> Change:
    """The change that drops a zone said, and a mark left beside another one with it."""
    before = text[start - 1] if start > 0 else ""
    after = text[end] if end < len(text) else ""
    if after and after in _PUNCTUATION and (start == 0 or (before and before in _PUNCTUATION)):
        if start == 0:
            end += 1
        else:
            start -= 1
    return Change(ChangeKind.ZONE, text[start:end], "", start, end)


def _part_changes(text: str, segment: _Segment) -> list[Change] | None:
    """The changes to the parts of a time and the fillers between; ``None`` when one is unsure."""
    changes: list[Change] = []
    for part in segment.parts:
        found = _changes_in(part)
        if found is None:
            return None
        changes.extend(found)
    for start, end in segment.fillers:
        changes.append(Change(ChangeKind.FILLER, text[start:end], "", start, end))
    changes.sort(key=lambda change: change.start)
    return changes


def _changes_in(part: _Part) -> list[Change] | None:
    match = part.match
    if part.kind == "short_year":
        written = "20" + "".join(str(_DIGIT_VALUE.get(c, c)) for c in match["number"])
        return [_change(ChangeKind.YEAR, match, "number", written)]
    if part.kind == "year":
        return _written_out(ChangeKind.YEAR, match, "number", _year_digits(match["number"]))
    if part.kind in ("month", "day"):
        value = _small_number(match["number"])
        return None if value is None else _written_out(ChangeKind.DATE, match, "number", value)
    if part.kind == "clock":
        return _clock_changes(match)
    if part.kind == "digital" and match["second"] is not None:
        return [_change(ChangeKind.SECOND, match, "second", "")]
    return []


def _year_digits(said: str) -> str:
    return "".join(str(_DIGIT_VALUE.get(character, character)) for character in said)


def _written_out(
    kind: ChangeKind, match: re.Match[str], group: str, value: int | str
) -> list[Change]:
    """One change for a group said in words; none for one written in digits already."""
    said = match[group]
    if said.isascii():
        return []
    return [_change(kind, match, group, str(value))]


def _change(kind: ChangeKind, match: re.Match[str], group: str, written: str) -> Change:
    return Change(kind, match[group], written, match.start(group), match.end(group))


def _clock_changes(match: re.Match[str]) -> list[Change] | None:
    changes: list[Change] = []
    if not match["hour"].isascii():
        hour = _small_number(match["hour"])
        if hour is None:
            return None
        changes.append(_change(ChangeKind.CLOCK, match, "hour", str(hour)))
    minute = match["minute"]
    if minute is not None and not minute.isascii():
        if match["fen"] is None and len(minute) < 2:
            # "三点五" may be 3:05 or 3:50; it is asked about, not decided here.
            return None
        value = _small_number(minute)
        if value is None:
            return None
        changes.append(_change(ChangeKind.CLOCK, match, "minute", f"{value:02d}"))
    if match["second"] is not None:
        changes.append(
            Change(
                ChangeKind.SECOND,
                match.string[match.start("second") : match.end()],
                "",
                match.start("second"),
                match.end(),
            )
        )
    return changes


def _small_number(said: str) -> int | None:
    """A number from 0 to 99 said in words or written in digits; ``None`` when unsure."""
    if said.isascii():
        return int(said) if said.isdigit() else None
    shape = re.fullmatch(
        "零?([一二两三四五六七八九零])|([二三四五六七八九]?)十([一二三四五六七八九]?)", said
    )
    if shape is None:
        return None
    if shape[1] is not None:
        value = _DIGIT_VALUE[shape[1]]
    else:
        value = 10 * (_DIGIT_VALUE[shape[2]] if shape[2] else 1)
        value += _DIGIT_VALUE[shape[3]] if shape[3] else 0
    # The reading of numbers says the same, wherever it reads the words at all.
    reading = read_number(said.lstrip("零") or said)
    if isinstance(reading, Recognised) and reading.value != value:
        return None
    return value


def _same_time(text: str, segment: _Segment, changes: Sequence[Change], zone: str) -> bool:
    """Whether the time tidied reads as one time, the same one the words said read as, if any."""
    if not changes:
        return True
    said = text[segment.start : segment.end]
    inside = [
        Change(c.kind, c.said, c.written, c.start - segment.start, c.end - segment.start)
        for c in changes
    ]
    tidied = _applied(said, inside)
    now = datetime(*_CHECK_MOMENT, tzinfo=zone_named(zone))
    if all(part.kind in _PERIOD_KINDS for part in segment.parts):
        period = read_period(tidied, now, zone)
        if not isinstance(period, Period):
            return False
        before = read_period(said, now, zone)
        return not isinstance(before, Period) or before == period
    reading = read_time(tidied, now, zone)
    if not isinstance(reading, TimeRecognised):
        return False
    before_reading = read_time(said, now, zone)
    if isinstance(before_reading, TimeRecognised):
        return _to_the_minute(before_reading.time.value) == _to_the_minute(reading.time.value)
    # Words that read as more than one time are asked about; tidying must not settle them.
    return isinstance(before_reading, TimeRefused) and (
        before_reading.reason is Refusal.UNKNOWN_WORDING
    )


def _to_the_minute(value: date) -> date:
    """A moment without its seconds, since seconds are dropped; a day as it is."""
    return value.replace(second=0) if isinstance(value, datetime) else value


# --- Numbers -------------------------------------------------------------


def _number_changes(text: str, kept: list[tuple[int, int]]) -> list[Change]:
    changes: list[Change] = []
    for match in _MIXED_DECIMAL.finditer(text):
        if _inside(kept, match.start(), match.end()):
            continue
        kept.append((match.start(), match.end()))
        change = _mixed_decimal(text, match)
        if change is not None:
            changes.append(change)
    for match in _SAID_NUMBER.finditer(text):
        if _inside(kept, match.start(), match.end()):
            continue
        change = _said_number(text, match.start(), match.end(), kept)
        if change is not None:
            changes.append(change)
    return changes


def _inside(kept: Sequence[tuple[int, int]], start: int, end: int) -> bool:
    return any(start < kept_end and kept_start < end for kept_start, kept_end in kept)


def _mixed_decimal(text: str, match: re.Match[str]) -> Change | None:
    fraction = match["fraction"]
    if fraction.endswith("一") or _left_alone(text, match.start(), match.end(), []):
        return None
    written = f"{match['whole']}.{''.join(str(_DIGIT_VALUE.get(c, c)) for c in fraction)}"
    reading = read_number(written)
    if not isinstance(reading, Recognised) or reading.cautions or reading.unit is not None:
        return None
    return Change(ChangeKind.MIXED_DECIMAL, match[0], written, match.start(), match.end())


def _said_number(text: str, start: int, end: int, kept: list[tuple[int, int]]) -> Change | None:
    said = text[start:end]
    before = text[start - 1] if start > 0 else ""
    after = text[end] if end < len(text) else ""
    if (before and before in "0123456789.") or (after and after in "0123456789."):
        return None
    if "点" in said:
        if not _is_decimal(text, start, end):
            return None
        if said.split("点")[1].endswith("一"):
            return None
    elif len(said) < 2 or _may_begin_next_word(said, after):
        return None
    if _left_alone(text, start, end, kept):
        return None
    if any(_within(text, start, end, word) for word in _NOT_AMOUNTS):
        return None
    reading = read_number(said)
    if not isinstance(reading, Recognised) or reading.cautions or reading.unit is not None:
        return None
    written = write_number(reading.value)
    again = read_number(written)
    if not isinstance(again, Recognised) or again.cautions or again.value != reading.value:
        return None  # pragma: no cover - digits always read back as written
    return Change(ChangeKind.NUMBER, said, written, start, end)


def _may_begin_next_word(said: str, after: str) -> bool:
    """Whether a last 一 may be the start of the next word ("四百一股", "二十一个")."""
    if not said.endswith("一"):
        return False
    return not said[:-1].endswith(("十", "零")) or _CHINESE.fullmatch(after) is not None


def _is_decimal(text: str, start: int, end: int) -> bool:
    """Whether the one 点 in the words at ``start`` to ``end`` is surely a decimal point."""
    said = text[start:end]
    if said.count("点") != 1:
        return False
    whole, fraction = said.split("点")
    if not whole or not fraction or any(c not in _DIGIT_WORDS for c in fraction):
        return False
    point = start + len(whole)
    if _is_clock(text, start, end, point):
        return False
    whole_reading = read_number(whole)
    if not isinstance(whole_reading, Recognised):
        return False
    return (
        whole_reading.value > 24
        or any(c in _SCALE_CHARACTERS for c in whole)
        or len(fraction) >= 3
        or _unit_at(text, end) is not None
        or _after_money_word(text, start)
    )


def _is_clock(text: str, start: int, end: int, point: int) -> bool:
    if text.startswith("分", end):
        return True
    if text.startswith(("整", "半", "一刻", "三刻", "钟"), point + 1):
        return True
    head = text[:start]
    while True:
        filler = next((word for word in _FILLERS if head.endswith(word)), None)
        if filler is None:
            break
        head = head[: -len(filler)]
    return head.endswith(("号", "日", *_HALF_WORDS))


def _unit_at(text: str, position: int, units: Sequence[str] = _UNITS) -> str | None:
    rest = text[position:].lstrip(" ")
    if rest[:1].isascii() and rest[:1].isalpha() or rest.startswith("$"):
        return rest[0]
    return next(
        (unit for unit in sorted(units, key=len, reverse=True) if rest.startswith(unit)), None
    )


def _after_money_word(text: str, start: int) -> bool:
    head = text[:start].rstrip(_BETWEEN_MONEY_WORD_AND_NUMBER)
    return head.endswith(_MONEY_WORDS)


def _within(text: str, start: int, end: int, word: str) -> bool:
    """Whether the words at ``start`` to ``end`` lie inside an occurrence of ``word``."""
    found = text.find(word, max(0, end - len(word)))
    while found != -1 and found <= start:
        if found + len(word) >= end:
            return True
        found = text.find(word, found + 1)
    return False


def _left_alone(text: str, start: int, end: int, kept: list[tuple[int, int]]) -> bool:
    """Whether a number is left as it was said: roughly, a share, a time, or more after a unit."""
    after = text[end:]
    if text[:start].endswith("分之") or after.startswith(("%", "％", "成")):
        return True
    if after[:1] and after[0] in _TIME_CHARACTERS:
        return True
    if after.startswith(_ROUGHLY_AFTER):
        return True
    for word in _ROUGHLY_BEFORE:
        if word in text[max(0, start - 3 - len(word)) : start]:
            return True
    unit = _UNIT_THEN_MORE.match(text, end)
    if unit is not None and (unit["more"] or unit["unit"] in ("毛", "角")):
        kept.append((start, unit.end()))
        return True
    return False
