"""Whether the user named a time zone other than the ledger's, so that the time can be marked.

A trade's time is always written in the ledger's zone (``Setting.zone``):
the program never converts it. When the user names another zone ("按北京时间
算，下午3点……"), the time written may be hours off, so the cell is marked
suspicious and the user is told (``flows/proposing.py``,
``flows/record_words.py``). Nothing is changed and nothing is asked.

``other_zone_words`` reads the words as the user said them, before they were
tidied, and gives back the first saying of another zone it finds, or
``None``. It finds four kinds, wherever they stand:

1. a place of ``PLACE_ZONES`` followed, in the same clause, by 时间 or 时区,
   at most ``MOST_BETWEEN`` characters later and with no digit between
   ("北京时间", "按纽约那个时间", "北京的成交时间"); in English, a place
   followed by "time" with at most one word between ("Beijing local time").
   A clause runs from one punctuation mark to the next; a point or a colon
   between two digits ("0.1", "15:00") does not end one. An English place is
   a whole word: "US" is never found in "USDT";
2. 东X区 or 西X区 ("东八区");
3. a Latin name of a zone, with or without an offset ("UTC+8", "EST"), but
   not the two names the ledger's own zone goes by in winter and in summer
   (``own_zone_names``: CET and CEST for Europe/Budapest), which name the
   ledger's zone itself;
4. 时区 or 当地时间, in a clause that names no place in the ledger's zone.

A place in the ledger's zone ("匈牙利时间", "按布达佩斯的时间") is not another
zone. 时间 with no place before it ("成交时间是……") is not either, and
neither is a place with no 时间 after it ("按国内算", "北京下午三点"):
those are not found, a known gap.

The words given back are, for a place, from its first character to the last
of 时间, 时区 or "time" ("北京的成交时间"); for the other kinds, the words
themselves ("东八区", "UTC+8", "当地时间").

This module reads no clock: the year whose names of the zone are wanted is
handed in.

Why at most three characters between a place and 时间 (decided on
2026-11-27 by the session that hands out the work, on review): the sayings
meant reach that far ("按北京那边的时间"), while four would take a share's
name such as "中国平安成交时间" for a zone, in speech with no punctuation.

Names defined here: ``PLACE_ZONES``, ``MOST_BETWEEN``, ``other_zone_words``
and ``own_zone_names``.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime

from ledger_hand.core.zones import zone_named

# A place said with 时间 or 时区, and the zone it names. One more row is one
# more place; nothing else needs to change. Every place of ``SPOKEN_ZONES``
# is here, with the same zone (a test holds it).
PLACE_ZONES: Mapping[str, str] = {
    "匈牙利": "Europe/Budapest",  # Hungary
    "布达佩斯": "Europe/Budapest",  # Budapest
    "北京": "Asia/Shanghai",  # Beijing: China has one zone
    "中国": "Asia/Shanghai",  # China
    "国内": "Asia/Shanghai",  # "at home", said by a speaker from China
    "大陆": "Asia/Shanghai",  # mainland China
    "上海": "Asia/Shanghai",  # Shanghai
    "香港": "Asia/Hong_Kong",  # Hong Kong
    "台湾": "Asia/Taipei",  # Taiwan
    "东京": "Asia/Tokyo",  # Tokyo
    "日本": "Asia/Tokyo",  # Japan
    "新加坡": "Asia/Singapore",  # Singapore
    "首尔": "Asia/Seoul",  # Seoul
    "韩国": "Asia/Seoul",  # South Korea
    "纽约": "America/New_York",  # New York
    "美国": "America/New_York",  # the United States, taken as its eastern zone
    "美东": "America/New_York",  # the eastern United States
    "美西": "America/Los_Angeles",  # the western United States
    "美国东部": "America/New_York",  # the eastern United States
    "美国西部": "America/Los_Angeles",  # the western United States
    "美股": "America/New_York",  # the US stock market's hours: New York
    "华尔街": "America/New_York",  # Wall Street: New York
    "伦敦": "Europe/London",  # London
    "英国": "Europe/London",  # the United Kingdom
    "悉尼": "Australia/Sydney",  # Sydney
    "澳洲": "Australia/Sydney",  # Australia, taken as Sydney's zone
    "迪拜": "Asia/Dubai",  # Dubai
    "Beijing": "Asia/Shanghai",  # Beijing
    "China": "Asia/Shanghai",  # China
    "Shanghai": "Asia/Shanghai",  # Shanghai
    "Hong Kong": "Asia/Hong_Kong",  # Hong Kong
    "Tokyo": "Asia/Tokyo",  # Tokyo
    "Japan": "Asia/Tokyo",  # Japan
    "Singapore": "Asia/Singapore",  # Singapore
    "Seoul": "Asia/Seoul",  # Seoul
    "New York": "America/New_York",  # New York
    "US": "America/New_York",  # the United States, taken as its eastern zone
    "Eastern": "America/New_York",  # US Eastern time: New York
    "Pacific": "America/Los_Angeles",  # US Pacific time: Los Angeles
    "London": "Europe/London",  # London
    "UK": "Europe/London",  # the United Kingdom
    "Sydney": "Australia/Sydney",  # Sydney
    "Hungary": "Europe/Budapest",  # Hungary
    "Budapest": "Europe/Budapest",  # Budapest
}

# How many characters may stand between a place and 时间 or 时区.
MOST_BETWEEN = 3

_LATIN_NAMES = "UTC|GMT|EST|EDT|PST|PDT|CST|CET|CEST|JST|HKT|SGT|KST|AEST|AEDT"
_LATIN_ZONE = re.compile(
    f"(?<![A-Za-z])(?i:(?P<name>{_LATIN_NAMES}))"
    "(?P<offset>\\s*[+-]\\s*[0-9]{1,2}(?::?[0-9]{2})?)?(?![A-Za-z])"
)
_EAST_WEST = re.compile("[东西][零〇一二两三四五六七八九十0-9]{1,3}区")
_ZONE_WORDS = re.compile("时区|当地时间")
# The marks that end a clause; a point or a colon only when not between two digits.
_CLAUSE_END = re.compile("[，,。；;！!？?、（）()\\n]|(?<![0-9])[.:：]|[.:：](?![0-9])")
_DIGIT = re.compile("[0-9０-９]")


def own_zone_names(zone: str, year: int) -> frozenset[str]:
    """The names the zone ``zone`` goes by in January and in July of ``year``.

    Example: Europe/Budapest in 2026 gives CET and CEST. A zone named by an
    offset only ("+08") gives that text, which no Latin name matches.
    """
    info = zone_named(zone)
    names = {datetime(year, month, 15, 12, tzinfo=info).tzname() for month in (1, 7)}
    return frozenset(name.upper() for name in names if name)


def other_zone_words(said: str, zone: str, own_names: frozenset[str]) -> str | None:
    """The first saying of a zone other than ``zone`` in ``said``, as said, or ``None``.

    ``own_names`` are the Latin names of ``zone`` itself (``own_zone_names``).
    Example: "按北京时间算，下午3点买了0.1个ETH" with Europe/Budapest gives
    "北京时间"; "按匈牙利时间算，……" gives ``None``.
    """
    found: list[tuple[int, str]] = []
    for start, clause in _clauses(said):
        found.extend((start + at, words) for at, words in _in_clause(clause, zone))
    for match in _EAST_WEST.finditer(said):
        found.append((match.start(), match[0]))
    for match in _LATIN_ZONE.finditer(said):
        if match["offset"] is None and match["name"].upper() in own_names:
            continue
        found.append((match.start(), match[0]))
    if not found:
        return None
    return min(found, key=lambda one: one[0])[1]


def _clauses(said: str) -> list[tuple[int, str]]:
    """Each clause of ``said``, with where it starts."""
    clauses: list[tuple[int, str]] = []
    start = 0
    for mark in _CLAUSE_END.finditer(said):
        clauses.append((start, said[start : mark.start()]))
        start = mark.end()
    clauses.append((start, said[start:]))
    return clauses


def _in_clause(clause: str, zone: str) -> list[tuple[int, str]]:
    """Each place said with 时间 or 时区 in ``clause`` naming another zone, and 时区 or 当地时间
    said where no place of ``zone`` is, with where each starts."""
    found: list[tuple[int, str]] = []
    own_place = False
    for place, named in sorted(PLACE_ZONES.items(), key=lambda row: -len(row[0])):
        for start in _places(clause, place):
            if named == zone:
                own_place = True
                continue
            end = _zone_word_after(clause, start + len(place), english=place.isascii())
            if end is not None:
                found.append((start, clause[start:end]))
    if not own_place:
        found.extend((match.start(), match[0]) for match in _ZONE_WORDS.finditer(clause))
    return found


def _places(clause: str, place: str) -> list[int]:
    """Where ``place`` starts in ``clause``; an English place only as a whole word.

    A place of two letters ("US", "UK") is matched in capitals only, so that
    "us" in "give us time" is not one.
    """
    if not place.isascii():
        return [match.start() for match in re.finditer(re.escape(place), clause)]
    shape = f"(?<![A-Za-z]){re.escape(place)}(?![A-Za-z])"
    flags = re.IGNORECASE if len(place) > 2 else 0
    return [match.start() for match in re.finditer(shape, clause, flags)]


def _zone_word_after(clause: str, position: int, *, english: bool) -> int | None:
    """Where 时间, 时区 or "time" after a place at ``position`` ends, when it is near enough."""
    if english:
        match = re.compile("(?:\\s+[A-Za-z]+)?\\s+time(?![A-Za-z])", re.IGNORECASE).match(
            clause, position
        )
        return match.end() if match is not None else None
    for gap in range(MOST_BETWEEN + 1):
        at = position + gap
        if _DIGIT.search(clause, position, at) is not None:
            return None
        if clause.startswith(("时间", "时区"), at):
            return at + 2
    return None
