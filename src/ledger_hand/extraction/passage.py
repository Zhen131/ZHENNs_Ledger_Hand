"""The passage: finding a phrase the model copied in it, and the numbers it holds.

A ``Passage`` is built once from the text the user typed. ``find`` takes a
phrase the model copied and gives back the ``Piece`` of the passage it is,
or a ``PieceMiss`` saying why it is not one.

A phrase is compared with the passage after the same tidying on both sides,
and the tidying never changes what a character says:

- a character written full width or half width is taken in its other width,
  where Unicode marks the two as the same character in another width ("０"
  and "0", "ＢＴＣ" and "BTC", the ideographic space and the space);
- a run of whitespace of any kind and length counts as one space;
- the phrase's own whitespace at either end is left out.

Nothing else is tidied. Letter case, a letter in another form (mathematical,
superscript), punctuation, a zero-width character, a digit of another script
and a missing or added gap between two characters all count: "btc" is not a
piece of a passage that says "BTC", and neither is "0.02BTC" of one that says
"0.02 BTC".

A phrase is a piece only where it does not cut a number of the passage in
two (``passage_numbers`` says what a number is). "94" is not a piece of
"94,900", "1.2" is not one of "1.2k", and "8" is not one of "8万": copied that
way, the number would come out as another number. When the phrase stands in
the passage more than once, the first place where it cuts no number is the
piece.

The one place where a number is followed by something that is not part of
it, "so much a piece" ("3000一个": the number "3000", then "一个"), lets a
phrase end there but not begin there: "3000" copied out of "3000一个" is a
piece, while "一" or "一个" copied out of it is still taken as cutting the
run "3000一". Only the number before "一个" is let go; nothing else is.

A phrase is looked for in at most ``MAX_PLACES_TRIED`` places. One that
stands in the passage more often than that, each time as part of a longer
number, is taken as cutting a number: looking further would let one reply
cost work without bound, and leaving the field empty is the safe side.

A ``Piece`` holds the text exactly as the passage has it there, so what goes
on into a draft is always the user's own writing, never the model's copy of
it. It also holds the numbers written inside it, which tell which numbers of
the passage some trade has used.

Names defined here: ``Passage``, ``Piece``, ``PieceMiss`` and ``MAX_PLACES_TRIED``.
"""

from __future__ import annotations

import bisect
import enum
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass

from ledger_hand.extraction.passage_numbers import number_runs, number_spans

# Far more places than a phrase of a real passage stands in as part of other
# numbers before it stands alone.
MAX_PLACES_TRIED = 256


class PieceMiss(enum.Enum):
    """Why a phrase the model copied is not a piece of the passage."""

    NOT_IN_PASSAGE = "the phrase is not a piece of the passage"
    CUTS_A_NUMBER = "the phrase is in the passage only as part of a longer number"


@dataclass(frozen=True)
class Piece:
    """A phrase found in the passage.

    ``text`` is the passage's own text there. ``numbers`` are the numbers
    written inside it, each in the tidied form, in order.
    """

    text: str
    numbers: tuple[str, ...]


def _width_pairs() -> Mapping[int, int]:
    """Characters Unicode marks as another width of one other character, and that character."""
    pairs: dict[int, int] = {}
    for code in (0x3000, *range(0xFF00, 0xFFF0)):
        tag, _, target = unicodedata.decomposition(chr(code)).partition(" ")
        if tag in ("<wide>", "<narrow>") and target and " " not in target:
            pairs[code] = int(target, 16)
    return pairs


_OTHER_WIDTH = _width_pairs()


def _tidied(text: str) -> tuple[str, list[int]]:
    """``text`` tidied, and for each tidied character the position it came from."""
    characters: list[str] = []
    origins: list[int] = []
    in_gap = False
    for position, character in enumerate(text.translate(_OTHER_WIDTH)):
        if character.isspace():
            if not in_gap:
                characters.append(" ")
                origins.append(position)
            in_gap = True
            continue
        in_gap = False
        characters.append(character)
        origins.append(position)
    return "".join(characters), origins


def _inside(spans: list[tuple[int, int]], length: int) -> list[bool]:
    """For each place between two characters, whether it lies inside one of ``spans``."""
    inside = [False] * (length + 1)
    for start, end in spans:
        for place in range(start + 1, end):
            inside[place] = True
    return inside


class Passage:
    """The text the user typed, ready to have phrases looked up in it."""

    def __init__(self, text: str) -> None:
        self.text = text
        self._tidy, self._origins = _tidied(text)
        self._numbers = number_spans(self._tidy)
        self._number_starts = [start for start, _ in self._numbers]
        # A phrase may not begin inside a run that could be a number, and may
        # not end inside a number; the two differ only where "so much a
        # piece" follows a number.
        self._start_cuts = _inside(number_runs(self._tidy), len(self._tidy))
        self._end_cuts = _inside(self._numbers, len(self._tidy))
        # resume[i]: the first place from i on where a phrase may begin.
        self._resume = list(range(len(self._tidy) + 1))
        for place in range(len(self._tidy) - 1, -1, -1):
            if self._start_cuts[place]:
                self._resume[place] = self._resume[place + 1]
        self._found: dict[str, Piece | PieceMiss] = {}

    @property
    def numbers(self) -> tuple[tuple[str, str], ...]:
        """Every number written in the passage, in order: as written, and tidied."""
        return tuple(
            (self.text[self._origins[start] : self._origins[end - 1] + 1], self._tidy[start:end])
            for start, end in self._numbers
        )

    def find(self, phrase: str) -> Piece | PieceMiss:
        """The piece of the passage that ``phrase`` is, or why it is not one."""
        wanted = _tidied(phrase)[0].strip(" ")
        if wanted not in self._found:
            # Remembered: a reply may copy the same phrase into many rows.
            self._found[wanted] = self._search(wanted)
        return self._found[wanted]

    def _search(self, wanted: str) -> Piece | PieceMiss:
        if not wanted:
            return PieceMiss.NOT_IN_PASSAGE
        start = self._tidy.find(wanted)
        if start == -1:
            return PieceMiss.NOT_IN_PASSAGE
        for _ in range(MAX_PLACES_TRIED):
            end = start + len(wanted)
            if not (self._start_cuts[start] or self._end_cuts[end]):
                return self._piece(start, end)
            # A start inside a number is passed over to the number's end.
            start = self._tidy.find(wanted, self._resume[start + 1])
            if start == -1:
                break
        return PieceMiss.CUTS_A_NUMBER

    def _piece(self, start: int, end: int) -> Piece:
        text = self.text[self._origins[start] : self._origins[end - 1] + 1]
        numbers: list[str] = []
        # The numbers lie in order and never overlap, so the ones inside the
        # piece follow each other from the first that begins in it.
        index = bisect.bisect_left(self._number_starts, start)
        while index < len(self._numbers) and self._numbers[index][1] <= end:
            number_start, number_end = self._numbers[index]
            numbers.append(self._tidy[number_start:number_end])
            index += 1
        return Piece(text, tuple(numbers))
