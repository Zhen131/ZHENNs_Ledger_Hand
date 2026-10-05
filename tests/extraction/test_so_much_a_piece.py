"""The cut of "so much a piece", held against the number reader by trying every short text.

A run of digits and Chinese number characters is one number to the passage
lookup, except in one way of writing: a run that ends in a decimal digit and
then "一", with a counter right after ("3000一个"). There the number before
"一" may be copied on its own. These tests build every short text out of a
small set of characters and check two things:

- runs are cut exactly where that way of writing stands, and nowhere else;
- wherever the cut lets a copied phrase through that the whole runs did not,
  the number reader reads no longer stretch of the text around the phrase
  as one number, so the phrase is not part of a longer number. And no phrase
  the whole runs let through is refused now.

If the number reader ever reads such a longer stretch as one number, the
second test fails, and the cut in ``passage_numbers`` has to follow it.
"""

from __future__ import annotations

import itertools
import re
from collections.abc import Iterator
from functools import cache

import pytest

from ledger_hand.core.numbers import Recognised, read_number
from ledger_hand.extraction import passage as passage_module
from ledger_hand.extraction.passage import Passage, Piece
from ledger_hand.extraction.passage_numbers import number_runs, number_spans

# Digits, Chinese digits with zero (in two forms), two and one, the places,
# the point in both writings, the comma, and two counters.
ARABIC = "150"
CHINESE = "零〇两一五"
PLACES = "十百千万亿"
POINTS = "点.,"
COUNTERS = "个枚"
ALPHABET = ARABIC + CHINESE + PLACES + POINTS + COUNTERS
LONGEST = 5
SO_MUCH_A_PIECE = re.compile(rf"\d一[{COUNTERS}]")


@cache
def read_as_one_number(text: str) -> bool:
    return isinstance(read_number(text), Recognised)


def every_text(longest: int) -> Iterator[str]:
    for length in range(1, longest + 1):
        for characters in itertools.product(ALPHABET, repeat=length):
            yield "".join(characters)


def texts_with_so_much_a_piece(longest: int) -> Iterator[str]:
    """Every text of up to ``longest`` characters that holds a digit, 一 and a counter."""
    seen: set[str] = set()
    for length in range(3, longest + 1):
        for place in range(length - 2):
            for digit, counter in itertools.product(ARABIC, COUNTERS):
                for rest in itertools.product(ALPHABET, repeat=length - 3):
                    text = "".join(rest[:place]) + digit + "一" + counter + "".join(rest[place:])
                    if text not in seen:
                        seen.add(text)
                        yield text


def inside(spans: list[tuple[int, int]], length: int) -> list[bool]:
    marks = [False] * (length + 1)
    for start, end in spans:
        for place in range(start + 1, end):
            marks[place] = True
    return marks


def test_runs_are_cut_exactly_where_a_digit_one_and_a_counter_stand() -> None:
    wrong = [
        text
        for text in every_text(LONGEST)
        if (number_runs(text) != number_spans(text)) != bool(SO_MUCH_A_PIECE.search(text))
    ]

    assert wrong == []


def test_what_the_cut_lets_through_is_never_part_of_a_longer_number(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    let_through = 0
    refused_now: list[tuple[str, str]] = []
    longer_numbers: list[tuple[str, str, str]] = []
    for text in texts_with_so_much_a_piece(LONGEST):
        with monkeypatch.context() as patch:
            # The lookup as it was with whole runs only.
            patch.setattr(passage_module, "number_spans", number_runs)
            before = Passage(text)
        now = Passage(text)
        no_start = inside(number_runs(text), len(text))
        no_end = inside(number_spans(text), len(text))
        for phrase in {text[i:j] for i in range(len(text)) for j in range(i + 1, len(text) + 1)}:
            was, found = before.find(phrase), now.find(phrase)
            if isinstance(was, Piece) and not isinstance(found, Piece):
                refused_now.append((text, phrase))
            if isinstance(was, Piece) or not isinstance(found, Piece):
                continue
            let_through += 1
            places = [
                (start, start + len(phrase))
                for start in range(len(text) - len(phrase) + 1)
                if text.startswith(phrase, start)
                and not (no_start[start] or no_end[start + len(phrase)])
            ]
            assert places, (text, phrase)
            for start, end in places:
                for wider_start in range(start + 1):
                    for wider_end in range(end, len(text) + 1):
                        wider = text[wider_start:wider_end]
                        if (wider_start, wider_end) != (start, end) and read_as_one_number(wider):
                            longer_numbers.append((text, phrase, wider))

    assert let_through > 0
    assert refused_now == []
    assert longer_numbers == []
