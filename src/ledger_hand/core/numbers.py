"""Numbers as text: reading a number the way people write it.

``read_number`` takes a short piece of text that is supposed to be one number
and gives back one of these:

- ``Recognised``: the exact value;
- ``NotANumber``: the text is not a number this program reads.

It never guesses, and it never raises for a text it cannot read.

The text is checked against this module's own rules before any decimal is
built from it. Python's decimal type would by itself accept spellings that are
refused here on purpose: an exponent, an underscore between digits, a sign,
"NaN", "Infinity", and digits of other scripts.

This module does not decide whether a number is a price, a quantity or a fee,
and it does not look for numbers inside a sentence.

Names defined here: ``read_number``, ``Reading``, ``Recognised`` and
``NotANumber``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Recognised:
    """A number that was read with certainty."""

    value: Decimal


@dataclass(frozen=True)
class NotANumber:
    """The text is not a number this program reads."""


Reading = Recognised | NotANumber

# Digits are spelled out as 0-9 throughout: the shorthand for "a digit" would
# also match the digits of every other script.
_PLAIN = re.compile(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?")


def read_number(text: str) -> Reading:
    """Read ``text`` as one number."""
    numeral = text.strip()
    if _PLAIN.fullmatch(numeral) is None:
        return NotANumber()
    return Recognised(Decimal(numeral))
