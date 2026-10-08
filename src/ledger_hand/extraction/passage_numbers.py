"""The numbers written in a text: where each one begins and ends.

``number_spans`` finds every number written in a text, in digits or in
Chinese number characters, and gives back where each one begins and ends.
Two things are built on it: a phrase copied from the passage may not cut a
number in two, and a number of the passage that no trade used is reported.

Both lean towards finding too much rather than too little, so a number here
is any run that could be one (``number_runs``):

- it begins with a decimal digit of any script, or with a Chinese digit
  (零 to 九, 十, 两 and the like, and their formal and traditional forms);
- it goes on with more of these, with the Chinese words for the places
  (百, 千, 万, 亿 and their other forms), with 点 when a digit follows, and
  with a point or a comma that stands between two decimal digits;
- it may end in a ``k`` or ``w`` written right after a decimal digit, when
  no letter follows, since "1.2k" and "3w" are one number each.

Digits and Chinese number characters that stand side by side belong to one
run, whatever they are: the number reader of the core reads some such
mixtures as one number ("1千零5" is 1005, "9万4" is 94000), so none is cut
apart on a guess.

One way of writing is known to be two things, and only that one is cut: a
run that ends in a decimal digit and then "一", where a Chinese counter of
the number reader's own list (个, 枚, 颗 and their traditional forms) comes
right after the "一". That is "so much a piece": "3000一个" is the number
"3000" and then "一" of "一个", and so are "13.2一个", "150一枚", "3点5一个"
and "94900一个BTC". A run that ends in a place before the "一" ("30万一个")
stays whole, because the number reader reads "30万一" as one number.

A test builds every short text out of a small set of digits, Chinese number
characters, places, points and counters, and checks that wherever this cut
lets a copied phrase through, the number reader reads no longer stretch of
the text around that phrase as one number.

A comma written full width ("，") is where Chinese writing ends one clause
and begins the next, and it is also used by some as a thousands separator.
The text arrives tidied, with that comma already turned into an ordinary
one, so the caller says where the full-width ones stood
(``full_width_commas``). A run is cut at a full-width comma unless the
number reader of the core reads the two sides together as one number it is
sure of: "94，900" is one number (94900), while "63,000，1.5" and "3000，2"
are two, because the reader is not sure what they are as one. The reader is
the only judge; nothing here guesses which side a comma belongs to. The parts
are joined from the left, one comma at a time, as long as the reader is
sure. The price of this rule: someone who writes the full-width comma as a
decimal mark ("1，5" for 1.5) gets two numbers, 1 and 5, the way the number
reader leaves "1,5" unsettled; in Chinese writing that use is rare. A comma
written half width is not affected: "3000,2" stays one run.

So "94,900", "1.2k", "8万", "两万三", "9点40" and "零点五" are one number
each; "9:40" and "2026-10-03" are several. Chinese number characters also
stand in words that are not numbers ("一下", "十分"); they are found all the
same.

The text is expected with full-width digits and letters already in their
ordinary forms. Nothing here reads a number's value; that is the core's job.

Names defined here: ``number_spans``, ``number_runs``, ``CHINESE_COUNTERS``
and ``NUMBER_CHARACTERS``.
"""

from __future__ import annotations

import re
from collections.abc import Collection

# The counter table is private to the number reader, and the reader is not
# changed here; it is used as it is, so the two always agree on what a
# counter is.
from ledger_hand.core.numbers import _COUNTERS, Recognised, read_number

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

# Every character other than a decimal digit that can stand inside a number:
# the Chinese digits and places, 点 in both its forms, the point and the comma.
NUMBER_CHARACTERS = _CHINESE_DIGITS + _CHINESE_PLACES + "点點.,"

# The counters of the number reader that are written in Chinese characters.
CHINESE_COUNTERS: tuple[str, ...] = tuple(
    sorted(word for word in _COUNTERS if all("一" <= c <= "鿿" for c in word))
)
_ONE = "一"


def number_runs(text: str, full_width_commas: Collection[int] = ()) -> list[tuple[int, int]]:
    """Every run that could be a number, before "so much a piece" is cut off.

    ``full_width_commas`` are the places in ``text`` of the commas that were
    written full width before the text was tidied.
    """
    runs: list[tuple[int, int]] = []
    for match in _NUMBER.finditer(text):
        runs.extend(_cut_at_full_width_commas(text, *match.span(), full_width_commas))
    return runs


def number_spans(text: str, full_width_commas: Collection[int] = ()) -> list[tuple[int, int]]:
    """Where each number written in ``text`` begins and ends, in order.

    ``full_width_commas`` is as for ``number_runs``.
    """
    spans: list[tuple[int, int]] = []
    for start, end in number_runs(text, full_width_commas):
        if _ends_so_much_a_piece(text, start, end):
            spans.extend([(start, end - 1), (end - 1, end)])
        else:
            spans.append((start, end))
    return spans


def _ends_so_much_a_piece(text: str, start: int, end: int) -> bool:
    """Whether the run ends in a decimal digit, then "一", with a counter right after."""
    return (
        end - start >= 2
        and text[end - 1] == _ONE
        and text[end - 2].isdecimal()
        and any(text.startswith(counter, end) for counter in CHINESE_COUNTERS)
    )


def _cut_at_full_width_commas(
    text: str, start: int, end: int, full_width_commas: Collection[int]
) -> list[tuple[int, int]]:
    """The run from ``start`` to ``end``, cut at each full-width comma the reader does not bridge.

    From the left, the number so far is joined across the next full-width
    comma only when ``read_number`` is sure of the joined text as one number.
    """
    commas = sorted(place for place in full_width_commas if start < place < end)
    if not commas:
        return [(start, end)]
    parts: list[tuple[int, int]] = []
    begin = start
    for comma, next_end in zip(commas, [*commas[1:], end], strict=True):
        if isinstance(read_number(text[begin:next_end]), Recognised):
            continue
        parts.append((begin, comma))
        begin = comma + 1
    parts.append((begin, end))
    return parts
