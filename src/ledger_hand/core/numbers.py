"""Numbers as text: reading a number the way people write it.

``read_number`` takes a short piece of text that is supposed to be one number
and gives back one of these:

- ``Recognised``: the exact value, and any cautions about how it was read;
- ``Unsure``: the text looks like a number but cannot be pinned to one value;
  the reason is a ``Doubt``;
- ``NotANumber``: the text is not a number this program reads.

It never guesses, and it never raises for a text it cannot read.

The text is checked against this module's own rules before any decimal is
built from it. Python's decimal type would by itself accept spellings that are
refused here on purpose: an exponent, an underscore between digits, a sign,
"NaN", "Infinity", and digits of other scripts.

Commas count as thousands separators only in the strict form: one to three
digits, then groups of exactly three. Any other mix of commas, points and
gaps between digits is a ``Doubt``, because a comma is a decimal mark in much
of Europe. A point followed by exactly three digits is read as a decimal
point, with a ``Caution`` that it may have been meant to group thousands.

This module does not decide whether a number is a price, a quantity or a fee,
and it does not look for numbers inside a sentence.

Names defined here: ``read_number``, ``Reading``, ``Recognised``, ``Unsure``,
``NotANumber``, ``Doubt`` and ``Caution``.
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass
from decimal import Decimal


class Doubt(enum.Enum):
    """Why a text that looks like a number was not given a value."""

    AMBIGUOUS_SEPARATOR = "the separators can be read in more than one way"


class Caution(enum.Enum):
    """Something to keep in mind about a number that was recognised."""

    POINT_MAY_BE_THOUSANDS_SEPARATOR = "the point may have been meant to group thousands"


@dataclass(frozen=True)
class Recognised:
    """A number that was read with certainty."""

    value: Decimal
    cautions: tuple[Caution, ...] = ()


@dataclass(frozen=True)
class Unsure:
    """The text looks like a number, but which number is not certain."""

    reason: Doubt


@dataclass(frozen=True)
class NotANumber:
    """The text is not a number this program reads."""


Reading = Recognised | Unsure | NotANumber

# Digits are spelled out as 0-9 throughout: the shorthand for "a digit" would
# also match the digits of every other script.
_SHAPE = re.compile(r"\s*(?P<body>[0-9](?:[0-9.,\s]*[0-9])?)\s*")
_SPLIT_DIGITS = re.compile(r"[0-9.,]\s+[0-9.,]")
_PLAIN = re.compile(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?")
_GROUPED = re.compile(r"[1-9][0-9]{0,2}(?:,[0-9]{3})+(?:\.[0-9]+)?")
_GROUP_LIKE_FRACTION = re.compile(r"[1-9][0-9]{0,2}\.[0-9]{3}")
_LEADING_ZERO = re.compile(r"0[0-9]")


def read_number(text: str) -> Reading:
    """Read ``text`` as one number."""
    shape = _SHAPE.fullmatch(text)
    if shape is None:
        return NotANumber()
    return _written(shape["body"])


def _written(numeral: str) -> Reading:
    """Read digits written with points and commas."""
    if _SPLIT_DIGITS.search(numeral):
        return Unsure(Doubt.AMBIGUOUS_SEPARATOR)
    if _PLAIN.fullmatch(numeral):
        if _GROUP_LIKE_FRACTION.fullmatch(numeral):
            return Recognised(Decimal(numeral), (Caution.POINT_MAY_BE_THOUSANDS_SEPARATOR,))
        return Recognised(Decimal(numeral))
    if _GROUPED.fullmatch(numeral):
        return Recognised(Decimal(numeral.replace(",", "")))
    if _LEADING_ZERO.match(numeral):
        # Nobody writes an amount with zeros in front; this is a code or a clock time.
        return NotANumber()
    return Unsure(Doubt.AMBIGUOUS_SEPARATOR)
