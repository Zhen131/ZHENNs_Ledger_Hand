"""Numbers as text: reading a number the way people write it.

``read_number`` takes a short piece of text that is supposed to be one number
and gives back one of these:

- ``Recognised``: the exact value, the unit word that stood with it, and any
  cautions about how it was read;
- ``Unsure``: the text looks like a number but cannot be pinned to one value;
  the reason is a ``Doubt``;
- ``NotANumber``: the text is not a number this program reads.

It never guesses, and it never raises for a text it cannot read.

The text is checked against this module's own rules before any decimal is
built from it. Python's decimal type would by itself accept spellings that are
refused here on purpose: an exponent, an underscore between digits, a sign,
"NaN", "Infinity", and digits of other scripts.

Full-width characters are read as their ordinary forms.

A number may come with one unit: a currency sign before or after it, or one
word after it ("刀", "个", "USDT", "u"). The unit is handed back exactly as it
was written and is not interpreted here. A word that itself holds a number
word is never taken for a unit.

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
    """A number that was read with certainty.

    ``unit`` is the currency sign or the word that stood with the number,
    exactly as it was written, or ``None`` when there was none.
    """

    value: Decimal
    unit: str | None = None
    cautions: tuple[Caution, ...] = ()


@dataclass(frozen=True)
class Unsure:
    """The text looks like a number, but which number is not certain."""

    reason: Doubt


@dataclass(frozen=True)
class NotANumber:
    """The text is not a number this program reads."""


Reading = Recognised | Unsure | NotANumber

# The full-width forms of the ASCII characters, of two currency signs and of
# the space, each mapped to its ordinary form. One character maps to one
# character, so a position in the folded text is the same position in the
# original, and the unit can be handed back as it was written. Folding by
# Unicode's compatibility rules would also turn circled and superscript digits
# into plain ones, and those are not how anyone writes an amount.
_FOLDED = {code: code - 0xFEE0 for code in range(0xFF01, 0xFF5F)}
_FOLDED.update({0x3000: 0x20, 0xFFE5: 0xA5, 0xFFE1: 0xA3})

_CURRENCY_SIGNS = "$¥€£"

# Characters that say a number, in everyday and in formal writing. A word
# holding one of them is never a unit.
_NUMBER_WORDS = frozenset(
    "零〇一二两三四五六七八九十百千万亿点壹贰叁肆伍陆柒捌玖拾佰仟萬億兩貳參陸廿卅俩仨"
)

# Digits are spelled out as 0-9 throughout: the shorthand for "a digit" would
# also match the digits of every other script.
_SHAPE = re.compile(
    rf"\s*(?P<sign>[{_CURRENCY_SIGNS}]?)\s*"
    r"(?P<body>[0-9](?:[0-9.,\s]*[0-9])?)"
    r"(?P<tail>.*)",
    re.DOTALL,
)
_SPLIT_DIGITS = re.compile(r"[0-9.,]\s+[0-9.,]")
_PLAIN = re.compile(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?")
_GROUPED = re.compile(r"[1-9][0-9]{0,2}(?:,[0-9]{3})+(?:\.[0-9]+)?")
_GROUP_LIKE_FRACTION = re.compile(r"[1-9][0-9]{0,2}\.[0-9]{3}")
_LEADING_ZERO = re.compile(r"0[0-9]")


@dataclass(frozen=True)
class _Tail:
    """What follows the digits."""

    unit: str | None


@dataclass(frozen=True)
class _Amount:
    """A value read from the digits, before its unit is attached."""

    value: Decimal
    cautions: tuple[Caution, ...] = ()


def read_number(text: str) -> Reading:
    """Read ``text`` as one number, or say why it cannot be read as one."""
    reading = _strictly_read(text.translate(_FOLDED), text)
    return NotANumber() if reading is None else reading


def _strictly_read(folded: str, original: str) -> Reading | None:
    """Read a text of the one accepted shape: a sign, the number, a unit.

    ``None`` means the text does not have that shape.
    """
    shape = _SHAPE.fullmatch(folded)
    if shape is None:
        return None
    tail = _tail(shape, original)
    sign = original[shape.start("sign") : shape.end("sign")]
    if tail is None or (sign and tail.unit):
        return None
    amount = _written(shape["body"])
    if amount is None:
        return None
    if isinstance(amount, Doubt):
        return Unsure(amount)
    return Recognised(amount.value, sign or tail.unit, amount.cautions)


def _tail(shape: re.Match[str], original: str) -> _Tail | None:
    """The unit after the number; ``None`` when what follows is not one unit."""
    start = shape.start("tail")
    unit = shape.string[start:].strip()
    if not unit:
        return _Tail(unit=None)
    if unit in _CURRENCY_SIGNS or _is_unit_word(unit):
        return _Tail(unit=original[start:].strip())
    return None


def _is_unit_word(word: str) -> bool:
    """Whether ``word`` is one run of letters with no number word in it."""
    return all(letter.isalpha() and letter not in _NUMBER_WORDS for letter in word)


def _written(numeral: str) -> _Amount | Doubt | None:
    """Read digits written with points and commas; ``None`` when they are not a number."""
    if _SPLIT_DIGITS.search(numeral):
        return Doubt.AMBIGUOUS_SEPARATOR
    if _PLAIN.fullmatch(numeral):
        if _GROUP_LIKE_FRACTION.fullmatch(numeral):
            return _Amount(Decimal(numeral), (Caution.POINT_MAY_BE_THOUSANDS_SEPARATOR,))
        return _Amount(Decimal(numeral))
    if _GROUPED.fullmatch(numeral):
        return _Amount(Decimal(numeral.replace(",", "")))
    if _LEADING_ZERO.match(numeral):
        # Nobody writes an amount with zeros in front; this is a code or a clock time.
        return None
    return Doubt.AMBIGUOUS_SEPARATOR
