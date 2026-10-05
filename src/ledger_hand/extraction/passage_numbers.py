"""The numbers written in a text: where each one begins and ends.

``number_spans`` finds every number written in a text, in digits or in
Chinese number characters, and gives back where each one begins and ends.
Two things are built on it: a phrase copied from the passage may not cut a
number in two, and a number of the passage that no trade used is reported.

Both lean towards finding too much rather than too little, so a number here
is any run that could be one:

- it begins with a decimal digit of any script, or with a Chinese digit
  (零 to 九, 十, 两 and the like, and their formal and traditional forms);
- it goes on with more of these, with the Chinese words for the places
  (百, 千, 万, 亿 and their other forms), with 点 when a digit follows, and
  with a point or a comma that stands between two decimal digits;
- it may end in a ``k`` or ``w`` written right after a decimal digit, when
  no letter follows, since "1.2k" and "3w" are one number each.

So "94,900", "1.2k", "8万", "两万三", "9点40" and "零点五" are one number
each; "9:40" and "2026-10-03" are several. Chinese number characters also
stand in words that are not numbers ("一下", "十分"); they are found all the
same.

The text is expected with full-width digits and letters already in their
ordinary forms. Nothing here reads a number's value; that is the core's job.

Names defined here: ``number_spans``.
"""

from __future__ import annotations

import re

# Chinese digits, including the formal forms written on cheques and the
# traditional and spoken forms of two and three, and the circle for zero.
_CHINESE_DIGITS = "零〇○一二两兩俩倆三仨四五六七八九十壹贰貳叁參肆伍陆陸柒捌玖拾"
_CHINESE_PLACES = "百千万萬亿億佰仟"

_NUMBER = re.compile(
    rf"(?:\d|[{_CHINESE_DIGITS}])"
    rf"(?:\d|[{_CHINESE_DIGITS}{_CHINESE_PLACES}]"
    rf"|(?<=\d)[.,](?=\d)"
    rf"|[点點](?=\d|[{_CHINESE_DIGITS}]))*"
    r"(?:(?<=\d)[kKwW](?![A-Za-z]))?"
)


def number_spans(text: str) -> list[tuple[int, int]]:
    """Where each number written in ``text`` begins and ends, in order."""
    return [match.span() for match in _NUMBER.finditer(text)]
