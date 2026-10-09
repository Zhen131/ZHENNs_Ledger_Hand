"""The writings set: sentences whose numbers are written in ways the number reader finds hard.

Besides the debug and the final set there is a third, small set of invented
sentences (``sets/writings.json``, read as the ``writings`` set). Each holds
a number written in one of these ways, in Chinese and in English passages:

- a gap before a letter multiplier: ``3 w``, ``1.5 k``;
- a gap before a Chinese multiplier: ``100 万``;
- a space between thousands: ``94 900``;
- two numbers one space apart, which look like the one above: ``0.02 94900``;
- a full-width comma between digits: ``94，900`` (one number) and
  ``63,000，1.5`` (two numbers).

Its gold answers keep the same rules as the other two sets: a number the
core is unsure of is empty. It is scored the same way, but apart: its runs
are not part of the main scores of a prompt version.

``writings_of`` tells which of the ways a sentence shows, from its gold
answer and its text, so a sentence cannot be filed under a way it does not
show. ``writings_table`` counts them for Chinese and English passages.

Names defined here: ``WRITINGS_SET``, ``Writing``, ``Context``,
``writings_of``, ``context_of`` and ``writings_table``.
"""

from __future__ import annotations

import enum
import itertools
import re
from collections.abc import Iterable

from evals.gold import SETS_DIR, Language, Sentence
from ledger_hand.extraction.reply_table import Field

WRITINGS_SET = SETS_DIR / "writings.json"

_NUMBER_FIELDS = (Field.QUANTITY, Field.PRICE, Field.TOTAL, Field.FEE)
_GAP_LETTER = re.compile(r"\d\s+[kKwW](?![A-Za-z])")
_GAP_CHINESE = re.compile(r"\d\s+(?:千|万|亿)")
_SPACE_GROUPS = re.compile(r"\d{1,3} \d{3}(?!\d)")
_FULL_WIDTH_COMMA = re.compile(r"\d，\d")


class Writing(enum.Enum):
    """One way of writing a number that the number reader finds hard."""

    GAP_LETTER_MULTIPLIER = "a gap before a letter multiplier (3 w, 1.5 k)"
    GAP_CHINESE_MULTIPLIER = "a gap before a Chinese multiplier (100 万)"
    SPACE_THOUSANDS = "a space between thousands (94 900)"
    ADJACENT_NUMBERS = "two numbers one space apart (0.02 94900)"
    FULL_WIDTH_COMMA = "a full-width comma between digits (94，900; 63,000，1.5)"


class Context(enum.Enum):
    """Whether a passage is written in Chinese (alone or mixed) or in English."""

    CHINESE = "Chinese or mixed"
    ENGLISH = "English"


def context_of(sentence: Sentence) -> Context:
    """The context of ``sentence``: English, or Chinese for Chinese and mixed passages."""
    return Context.ENGLISH if sentence.language is Language.ENGLISH else Context.CHINESE


def writings_of(sentence: Sentence) -> frozenset[Writing]:
    """The ways of writing a number that ``sentence`` shows."""
    found: set[Writing] = set()
    for trade in sentence.trades:
        phrases = [
            phrase for field in _NUMBER_FIELDS if (phrase := trade.cell(field).phrase) is not None
        ]
        for phrase in phrases:
            if _GAP_LETTER.search(phrase):
                found.add(Writing.GAP_LETTER_MULTIPLIER)
            if _GAP_CHINESE.search(phrase):
                found.add(Writing.GAP_CHINESE_MULTIPLIER)
            if _SPACE_GROUPS.search(phrase):
                found.add(Writing.SPACE_THOUSANDS)
        pairs = itertools.permutations(phrases, 2)
        if any(f"{one} {other}" in sentence.text for one, other in pairs):
            found.add(Writing.ADJACENT_NUMBERS)
    if _FULL_WIDTH_COMMA.search(sentence.text):
        found.add(Writing.FULL_WIDTH_COMMA)
    return frozenset(found)


def writings_table(sentences: Iterable[Sentence]) -> dict[Writing, dict[Context, int]]:
    """For each way of writing, how many sentences of each context show it."""
    table = {writing: dict.fromkeys(Context, 0) for writing in Writing}
    for sentence in sentences:
        for writing in writings_of(sentence):
            table[writing][context_of(sentence)] += 1
    return table
