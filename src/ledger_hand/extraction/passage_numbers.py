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
  (十, 百, 千, 万, 亿 and their other forms), with 点 when a digit follows,
  and with a point or a comma that stands between two decimal digits;
- it may end in a ``k`` or ``w`` written right after a decimal digit, when
  no letter follows, since "1.2k" and "3w" are one number each;
- but a decimal digit and a Chinese digit (零 to 九 and their other forms,
  not the places) never stand side by side in one number. The two kinds of
  writing join only through a place or 点: "9万4", "30万一", "5十" and
  "3点五" are one number each, while "3000一个" is the number "3000" and
  then "一", and so are "13.2一个", "150一枚" and "94900一个BTC".

That last rule comes from the number reader of the core: it reads no text in
which a decimal digit and a Chinese digit stand side by side as one number,
so such a run is never one number to it either. A test tries every Chinese
digit here next to digits written in several ways, and fails if the reader
ever starts to read one of them as a number; this rule must then follow.

So "94,900", "1.2k", "8万", "两万三", "9点40" and "零点五" are one number
each; "9:40" and "2026-10-03" are several. Chinese number characters also
stand in words that are not numbers ("一下", "十分"); they are found all the
same, and a run of nothing but Chinese number characters ("两三千",
"一亿五千") is one number however it reads.

The text is expected with full-width digits and letters already in their
ordinary forms. Nothing here reads a number's value; that is the core's job.

Names defined here: ``number_spans``, ``CHINESE_DIGITS`` and
``CHINESE_PLACES``.
"""

from __future__ import annotations

import re

# Chinese digits, including the formal forms written on cheques and the
# traditional and spoken forms of two and three, and the circle for zero.
CHINESE_DIGITS = "零〇○一二两兩俩倆三仨四五六七八九壹贰貳叁參肆伍陆陸柒捌玖"
# The places: ten, a hundred, a thousand, ten thousand, a hundred million,
# in their everyday, formal and traditional forms.
CHINESE_PLACES = "十拾百千万萬亿億佰仟"
# What may begin a number: a Chinese digit, or ten said alone ("十个").
_CHINESE_START = CHINESE_DIGITS + "十拾"

_NUMBER = re.compile(
    rf"(?:\d|[{_CHINESE_START}])"
    rf"(?:\d|[{CHINESE_DIGITS}{CHINESE_PLACES}]"
    rf"|(?<=\d)[.,](?=\d)"
    rf"|[点點](?=\d|[{_CHINESE_START}]))*"
    r"(?:(?<=\d)[kKwW](?![A-Za-z]))?"
)


def number_spans(text: str) -> list[tuple[int, int]]:
    """Where each number written in ``text`` begins and ends, in order."""
    spans: list[tuple[int, int]] = []
    for match in _NUMBER.finditer(text):
        start, end = match.span()
        piece_start = start
        for place in range(start + 1, end):
            if _writings_meet(text[place - 1], text[place]):
                spans.append((piece_start, place))
                piece_start = place
        spans.append((piece_start, end))
    return spans


def _writings_meet(before: str, after: str) -> bool:
    """Whether a decimal digit and a Chinese digit stand side by side here."""
    return (before.isdecimal() and after in CHINESE_DIGITS) or (
        before in CHINESE_DIGITS and after.isdecimal()
    )
