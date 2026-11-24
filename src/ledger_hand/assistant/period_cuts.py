"""Whether a period the model copied was cut out of a longer time the user said.

Judging a copy (``judging``) only makes sure that the period is a piece of
the user's words and that no number is cut in two. "9月" is such a piece
of "把9月13号那笔BTC的时间改成…", and taken as it stands it covers all of
September: a lookup is wider than asked, and a change or a deletion finds
another trade than the one the user meant. So a period is also checked
here: wherever the copied words stand in what the user said, they are
stretched to the left and to the right, a character at a time, up to
``MOST_STRETCHED`` characters each way, and each stretch is read whole as
a stretch of time (``core.time_range.read_period``). When some stretch
reads as days other than the copied words do (or the copied words read as
none at all), the words stand there cut out of a longer time. Only when
they stand so everywhere they are found is the period cut
(``is_cut``); words found once on their own are a fair copy. "10月" in
"10月份" or "今年10月" reads as the same days stretched, and is not cut.

This only looks around the words the model copied. When the model gives
no period, nothing is looked for in what the user said, and a longer time
found by stretching is never used in place of the model's words: a cut
period is a wrong step (``cut_misstep``), told to the model as any period
that is not the user's words is. (Decided on 2026-11-25, after a change
found a trade on 12 September for words that named 13 September.)

Names defined here: ``MOST_STRETCHED``, ``is_cut`` and ``cut_misstep``.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Sequence
from datetime import datetime

from ledger_hand.assistant.judging import Misstep, MisstepKind
from ledger_hand.core.time_range import Period, read_period

# How far the copied words are stretched each way. It must reach across
# the other end of a range, such as "到10月15号" (7 characters) or
# " to October 15" (14), and the word before one, such as "from ".
MOST_STRETCHED = 16


def _plain(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).split())


def _days(text: str, now: datetime, zone: str) -> tuple[object, object] | None:
    reading = read_period(text, now, zone)
    return (reading.first_day, reading.last_day) if isinstance(reading, Period) else None


def _cut_here(said: str, start: int, end: int, own: object, now: datetime, zone: str) -> bool:
    """Whether the words at ``start:end`` of ``said`` stand cut out of a longer time."""
    for left in range(MOST_STRETCHED + 1):
        if start - left < 0:
            break
        for right in range(MOST_STRETCHED + 1):
            if (left, right) == (0, 0):
                continue
            if end + right > len(said):
                break
            days = _days(said[start - left : end + right], now, zone)
            if days is not None and days != own:
                return True
    return False


def is_cut(words: str, user_said: Sequence[str], now: datetime, zone: str) -> bool:
    """Whether the period ``words`` stands, wherever it is found, cut out of a longer time."""
    piece = _plain(words)
    if not piece:
        return False
    own = _days(piece, now, zone)
    found = False
    for said in user_said:
        text = _plain(said)
        start = text.find(piece)
        while start != -1:
            found = True
            if not _cut_here(text, start, start + len(piece), own, now, zone):
                return False
            start = text.find(piece, start + 1)
    return found


def cut_misstep(words: str) -> Misstep:
    """The wrong step a cut period is; worded as any period that is not the user's words."""
    return Misstep(
        kind=MisstepKind.NOT_COPIED,
        detail=(
            f"'period' is {words!r}, which is cut out of a longer time the user said. "
            "Copy the user's whole time exactly; never shorten, convert or rewrite it."
        ),
    )
