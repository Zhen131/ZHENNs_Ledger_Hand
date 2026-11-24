"""The only ways of saying a time the program takes when it looks for one in a whole sentence.

When the model's time is not the user's own words, the program looks for
the time in the user's sentence itself (``time_range.find_period_words``),
and uses it only when both name the same days. A
sentence holds many words that the time reader could read as a time but
that are not one: a price ("2446"), "May I ...", a coin named SUN, "sat"
for the smallest piece of a bitcoin, a person called Jan. So the rule here
is: **better to find nothing than to find the wrong thing.** A piece of a
sentence counts as a time only when it has one of the shapes on this list;
anything else counts as not found, and the model's time stays a wrong
step. (Decided on 2026-11-24.)

The list:

- Chinese: a year with "年" ("2026年"); a month, "N月" or "N月份", with
  its year in front or not; a day of a month, "N月N号" or "N月N日", with
  its year in front or not; 今天, 昨天, 前天; 这个月, 本月, 上个月; 今年,
  去年; 这周, 本周, 上周; "最近N天", "过去N天"; and "A到B" where A and B are
  both on the list. A day without its month ("8号") is not on it.
- English: a month's full name, with "in", "during", "last" or "this" in
  front or not, and a year after it or not ("May" and "March" also need
  one of those, which the reader checks); a month's full name or short
  name with a day or a year right after it ("Oct 6", "Oct 6, 2026", "Oct
  2026", "Jan 5"); today, yesterday; "this" or "last" with "week",
  "month" or "year"; "last N days", "past N days"; a year with "in",
  "during" or "year" in front ("in 2026", "the year 2026"); and "from A to
  B" or "between A and B" where A and B are both on the list. A month's
  short name alone ("Jan", "Oct") and every weekday, in full or short
  ("Monday", "Sun"), are not on it.

Letter case and full-width forms do not count. The list says only which
shapes may be taken; what a piece means is still the reader's to say, and
it refuses a year before ``time_range.EARLIEST_YEAR``.

A time the model copied itself is not held to this list.

Names defined here: ``on_the_list``.
"""

from __future__ import annotations

import re
import unicodedata

_CHINESE_NUMBER = "(?:[0-9]{1,2}|[一二两三四五六七八九十]{1,3})"
_YEAR = "[0-9]{4}"
_FULL_MONTHS = (
    "january|february|march|april|may|june|july|august|september|october|november|december"
)
_SHORT_MONTHS = "jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec"
_COUNT = "(?:[0-9]{1,4}|one|two|three|four|five|six|seven|eight|nine|ten)"
_DAY = "[0-9]{1,2}(?:st|nd|rd|th)?"

_SHAPES = (
    # Chinese
    rf"{_YEAR}年",
    rf"(?:{_YEAR}年)?{_CHINESE_NUMBER}月份?",
    rf"(?:{_YEAR}年)?{_CHINESE_NUMBER}月{_CHINESE_NUMBER}[号日]",
    "今天|昨天|前天|这个月|本月|上个月|今年|去年|这周|本周|上周",
    rf"(?:最近|过去){_CHINESE_NUMBER}天",
    # English
    rf"(?:(?:in|during|last|this) )?(?:{_FULL_MONTHS})(?:,? {_YEAR})?",
    rf"(?:{_FULL_MONTHS}|{_SHORT_MONTHS})\.? {_DAY}(?:,? {_YEAR})?",
    rf"(?:{_FULL_MONTHS}|{_SHORT_MONTHS})\.?,? {_YEAR}",
    "today|yesterday",
    "(?:this|last) (?:week|month|year)",
    rf"(?:the )?(?:last|past) {_COUNT} days",
    rf"(?:in|during|(?:the )?year) {_YEAR}",
)
_ONE = re.compile("|".join(f"(?:{shape})" for shape in _SHAPES))
_CHINESE_RANGE = re.compile("(?P<start>.+?)到(?P<end>.+)")
_ENGLISH_RANGE = re.compile("(?:from (?P<start>.+?) to|between (?P<first>.+?) and) (?P<end>.+)")
_GAP_BESIDE_CHINESE = re.compile(r" (?=[^\x00-\x7f])|(?<=[^\x00-\x7f]) ")


def _plain(piece: str) -> str:
    text = " ".join(unicodedata.normalize("NFKC", piece).casefold().split())
    return _GAP_BESIDE_CHINESE.sub("", text)


def on_the_list(piece: str) -> bool:
    """Whether ``piece`` has one of the shapes of a time the program may take from a sentence."""
    text = _plain(piece)
    if _ONE.fullmatch(text):
        return True
    found = _CHINESE_RANGE.fullmatch(text) or _ENGLISH_RANGE.fullmatch(text)
    if found is None:
        return False
    start = found.group("start") or found.group("first") or ""
    end = found.group("end")
    # "10月1号到15号": the end may be a bare day after a day of a month.
    bare_day = re.fullmatch(f"{_CHINESE_NUMBER}[号日]", end) is not None
    return bool(_ONE.fullmatch(start)) and (bool(_ONE.fullmatch(end)) or bare_day)
