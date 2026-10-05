"""Every number phrase the lookup lets through, held against the number reader, over many texts.

For a phrase to be read as a number (a quantity, a price, a total, a fee),
the lookup promises one thing: wherever it lets the phrase through, no
longer stretch of the passage around it reads, to the number reader of the
core, as a number of another value. These tests check that promise for every
phrase of every text they build, out of a set of characters that has digits
(also full-width ones), Chinese digits and places in several forms, points,
commas, counters, other words, the multiplier letters and three kinds of gap.

All texts of up to three characters are tried, and a fixed draw of longer
ones. Larger runs of the same check are made by hand.
"""

from __future__ import annotations

import itertools
import random
from collections.abc import Iterable, Iterator
from functools import cache

from ledger_hand.core.numbers import Recognised, read_number
from ledger_hand.extraction.passage import Passage, Piece

CHARACTERS = (
    "1509"
    "\N{FULLWIDTH DIGIT ONE}\N{FULLWIDTH DIGIT ZERO}"
    "零〇两一二十"
    "百千万亿"
    "萬仟拾"
    "点.,"
    "个個枚颗顆"
    "张笔天"
    "kw"
    " \t\N{IDEOGRAPHIC SPACE}"
)
SHORTEST_DRAWN, LONGEST_DRAWN, DRAWN = 4, 9, 4_000


@cache
def reading(text: str) -> object:
    return read_number(text)


def every_text(longest: int) -> Iterator[str]:
    for length in range(1, longest + 1):
        for characters in itertools.product(CHARACTERS, repeat=length):
            yield "".join(characters)


def drawn_texts(seed: int) -> Iterator[str]:
    draw = random.Random(seed)
    for _ in range(DRAWN):
        yield "".join(draw.choices(CHARACTERS, k=draw.randint(SHORTEST_DRAWN, LONGEST_DRAWN)))


def broken_promises(texts: Iterable[str]) -> list[tuple[str, str, str]]:
    """Every (text, phrase, wider stretch) where a phrase let through sits in a longer number."""
    broken: list[tuple[str, str, str]] = []
    for text in texts:
        passage = Passage(text)
        phrases = {text[i:j] for i in range(len(text)) for j in range(i + 1, len(text) + 1)}
        for phrase in phrases:
            found = passage.find_number(phrase)
            if not isinstance(found, Piece):
                continue
            own = reading(found.text)
            if not isinstance(own, Recognised):
                continue
            for start in range(found.start + 1):
                for end in range(found.end, len(text) + 1):
                    wider = reading(text[start:end])
                    if isinstance(wider, Recognised) and wider.value != own.value:
                        broken.append((text, phrase, text[start:end]))
    return broken


def test_no_number_phrase_let_through_in_a_short_text_is_part_of_a_longer_number() -> None:
    assert broken_promises(every_text(3)) == []


def test_no_number_phrase_let_through_in_a_longer_text_is_part_of_a_longer_number() -> None:
    assert broken_promises(drawn_texts(seed=67)) == []
