"""Whether a number copied out of the passage is part of a longer number of another value.

The passage lookup keeps a phrase from cutting a run of number characters in
two (``passage_numbers``). Some numbers are not one run: the number reader
of the core also reads a number in parts with gaps between them ("9万 4900"
is 94900, "1万 5000" is 15000, "100 万" is a million). Copied as "4900",
"5000" or "100", such a phrase cuts no run, yet it is only part of the
number the user wrote. Here the number reader itself is the judge, so that
no rule has to guess which parts belong together.

``LongerNumbers`` is built once for the tidied text of a passage.
``reaches_further`` takes a stretch of it, from ``start`` to ``end``, and the
unit words the caller allows (the same ones the later conversion is given),
and says whether the stretch is part of a longer number of another value:

1. The stretch is read with ``read_number``. If it is not a number the
   reader recognises, there is nothing to judge: the answer is no, and the
   conversion afterwards says what is wrong with it.
2. Otherwise the stretch is widened, to the left and to the right, over the
   characters that can stand in a number (decimal digits, the Chinese digits
   and places, 点, the point, the comma and gaps; on the right also ``k`` and
   ``w``, which multiply a number written right before them). Every wider
   stretch that begins and ends on such a character, not on a gap, is read
   with ``read_number``. If one of them is a number the reader recognises
   and its value is not the stretch's own value, the answer is yes.

A wider stretch that only adds a unit, a counter or a gap reads as the same
value ("3000" and "3000 个", "3000u") and does not count. Neither does one the
reader does not recognise as a number at all ("3000 一个", "0.02 94900",
which it reads as two numbers side by side, or "3 w", whose gap it does not
read across). Units and words of other kinds are not widened over: they never
change the value of the number before them.

How far: at most ``WIDEST`` characters to each side, counted in the tidied
text, where a run of gaps is one character. The number reader reads no
number of more than 40 significant digits, so 40 characters of digits next
to the phrase already reach beyond any number it reads; a number in words
or in parts with gaps that is longer still shows a different value in a
shorter stretch already, since a tail of it that begins with a digit reads
as a number of its own ("2345万 6789" next to "6789").

The tidied text is what is read. It reads as the passage's own text does:
the number reader takes full-width forms as ordinary ones, and a run of gaps
the way it takes one gap.

Every reading is remembered, so the same stretch is never read twice. A
passage gets at most ``MAX_READINGS`` readings in all; once they are used up,
every further question is answered yes, the safe side, which leaves the field
empty. A reading takes a few millionths of a second, so the whole allowance
is well under a second. A passage of trades written in words uses a few
dozen; only text made of nothing but numbers and gaps, copied from in
hundreds of places, comes near it.

Names defined here: ``LongerNumbers``, ``WIDEST`` and ``MAX_READINGS``.
"""

from __future__ import annotations

from ledger_hand.core.numbers import Reading, Recognised, read_number
from ledger_hand.extraction.passage_numbers import NUMBER_CHARACTERS

WIDEST = 40
# Well under a second of reading in all; far more than any real passage needs.
MAX_READINGS = 100_000

_GAP = " "
_MULTIPLIER_LETTERS = "kKwW"


def _may_stand_in_a_number(character: str) -> bool:
    return character.isdecimal() or character in NUMBER_CHARACTERS


class LongerNumbers:
    """The judge of one passage's tidied text, with what it has read so far."""

    def __init__(self, tidy: str) -> None:
        self._tidy = tidy
        self._readings: dict[tuple[str, tuple[str, ...]], Reading] = {}

    def reaches_further(self, start: int, end: int, allowed: tuple[str, ...]) -> bool:
        """Whether ``tidy[start:end]`` is part of a longer number of another value."""
        own = self._read(start, end, allowed)
        if own is None:
            return True
        if not isinstance(own, Recognised):
            return False
        for wider_start in self._starts(start):
            for wider_end in self._ends(end):
                if (wider_start, wider_end) == (start, end):
                    continue
                wider = self._read(wider_start, wider_end, allowed)
                if wider is None:
                    return True
                if isinstance(wider, Recognised) and wider.value != own.value:
                    return True
        return False

    def _starts(self, start: int) -> list[int]:
        """Where a wider stretch may begin: ``start``, then leftwards, nearest first."""
        starts = [start]
        place = start
        while place > 0 and start - place < WIDEST:
            place -= 1
            character = self._tidy[place]
            if character == _GAP:
                continue
            if not _may_stand_in_a_number(character):
                break
            starts.append(place)
        return starts

    def _ends(self, end: int) -> list[int]:
        """Where a wider stretch may end: ``end``, then rightwards, nearest first."""
        ends = [end]
        place = end
        while place < len(self._tidy) and place - end < WIDEST:
            character = self._tidy[place]
            place += 1
            if character == _GAP:
                continue
            if not (_may_stand_in_a_number(character) or character in _MULTIPLIER_LETTERS):
                break
            ends.append(place)
        return ends

    def _read(self, start: int, end: int, allowed: tuple[str, ...]) -> Reading | None:
        """The reading of a stretch; ``None`` once the readings are used up."""
        key = (self._tidy[start:end], allowed)
        if key not in self._readings:
            if len(self._readings) >= MAX_READINGS:
                return None
            self._readings[key] = read_number(key[0], extra_units=allowed)
        return self._readings[key]
