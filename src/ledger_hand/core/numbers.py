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

Written digits may be followed by a multiplier: the letter "k" (thousand) or
"w" (ten thousand, from 万) directly after the last digit, or one of the words
千, 万, 十万, 百万, 千万, 亿, 十亿, 百亿, 千亿, 万亿. The letter "m" is not
read as a multiplier: it is a million to some and a thousandth (as in mBTC) to
others. That, any other magnitude letter or word, and a word that only starts
like a multiplier ("1ku") are a ``Doubt``.

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
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from ledger_hand.core.arithmetic import working_context


class Doubt(enum.Enum):
    """Why a text that looks like a number was not given a value."""

    AMBIGUOUS_SEPARATOR = "the separators can be read in more than one way"
    UNCLEAR_MULTIPLIER = "a letter or word may or may not be meant as a multiplier"


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

# Multipliers, as powers of ten. A letter counts only directly after the last
# digit. The empty word stands for no multiplier at all.
_LETTER_MULTIPLIERS: Mapping[str, int] = {"k": 3, "w": 4}
_SCALE_WORDS: Mapping[str, int] = {
    "": 0,
    "千": 3,
    "万": 4,
    "十万": 5,
    "百万": 6,
    "千万": 7,
    "亿": 8,
    "十亿": 9,
    "百亿": 10,
    "千亿": 11,
    "万亿": 12,
}

# Words in the place of a unit that change how large the number is. Taking
# one for a unit would hand back a number that is wrong by orders of magnitude.
_MAGNITUDE_WORDS = frozenset(
    {"k", "w", "m", "b", "t", "bn", "mn", "mm", "kk", "kw", "mil", "mio"}
    | {"hundred", "thousand", "million", "billion", "trillion", "grand"}
)

# Digits are spelled out as 0-9 throughout: the shorthand for "a digit" would
# also match the digits of every other script.
_SCALE = "十百千万亿"
_SHAPE = re.compile(
    rf"\s*(?P<sign>[{_CURRENCY_SIGNS}]?)\s*"
    rf"(?P<body>[0-9](?:[0-9.,\s{_SCALE}]*[0-9{_SCALE}])?)"
    r"(?P<letters>[A-Za-z]*)(?P<rest>.*)",
    re.DOTALL,
)
_SPLIT_DIGITS = re.compile(r"[0-9.,]\s+[0-9.,]")
_DIGITS_THEN_SCALE = re.compile(rf"(?P<digits>[0-9][0-9.,]*)(?P<scale>[{_SCALE}]*)")
_PLAIN = re.compile(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?")
_GROUPED = re.compile(r"[1-9][0-9]{0,2}(?:,[0-9]{3})+(?:\.[0-9]+)?")
_GROUP_LIKE_FRACTION = re.compile(r"[1-9][0-9]{0,2}\.[0-9]{3}")
_LEADING_ZERO = re.compile(r"0[0-9]")


@dataclass(frozen=True)
class _Tail:
    """What follows the number: a letter multiplier as a power of ten, and a unit."""

    power: int
    unit: str | None


@dataclass(frozen=True)
class _Amount:
    """A value read from the number itself, before its unit is attached."""

    value: Decimal
    cautions: tuple[Caution, ...] = ()


def read_number(text: str) -> Reading:
    """Read ``text`` as one number, or say why it cannot be read as one."""
    reading = _strictly_read(text.translate(_FOLDED), text)
    return NotANumber() if reading is None else reading


def _strictly_read(folded: str, original: str) -> Reading | None:
    """Read a text of the one accepted shape: a sign, the number, a multiplier, a unit.

    ``None`` means the text does not have that shape.
    """
    shape = _SHAPE.fullmatch(folded)
    if shape is None:
        return None
    tail = _tail(shape, original)
    if isinstance(tail, Doubt):
        return Unsure(tail)
    sign = original[shape.start("sign") : shape.end("sign")]
    if tail is None or (sign and tail.unit):
        return None
    amount = _amount(shape["body"], tail.power)
    if amount is None:
        return None
    if isinstance(amount, Doubt):
        return Unsure(amount)
    return Recognised(amount.value, sign or tail.unit, amount.cautions)


def _tail(shape: re.Match[str], original: str) -> _Tail | Doubt | None:
    """The multiplier letter and the unit after the number.

    ``None`` when what follows the number is not one unit.
    """
    letters = shape["letters"].lower()
    power = _LETTER_MULTIPLIERS.get(letters, 0)
    if not power and letters[:1] in _LETTER_MULTIPLIERS:
        # "1ku" may be a thousand u or one of a coin called ku.
        return Doubt.UNCLEAR_MULTIPLIER
    start = shape.end("letters") if power else shape.start("letters")
    unit = shape.string[start:].strip()
    if not unit:
        return _Tail(power, unit=None)
    if unit.lower() in _MAGNITUDE_WORDS:
        return Doubt.UNCLEAR_MULTIPLIER
    if unit in _CURRENCY_SIGNS or _is_unit_word(unit):
        return _Tail(power, unit=original[start:].strip())
    return None


def _is_unit_word(word: str) -> bool:
    """Whether ``word`` is one run of letters with no number word in it."""
    return all(letter.isalpha() and letter not in _NUMBER_WORDS for letter in word)


def _amount(body: str, letter_power: int) -> _Amount | Doubt | None:
    """The value of the number itself; ``None`` when it is not a number after all."""
    if _SPLIT_DIGITS.search(body):
        return Doubt.AMBIGUOUS_SEPARATOR
    written = _DIGITS_THEN_SCALE.fullmatch("".join(body.split()))
    if written is None or written["scale"] not in _SCALE_WORDS:
        return None
    if letter_power and written["scale"]:
        return Doubt.UNCLEAR_MULTIPLIER
    amount = _written(written["digits"])
    if not isinstance(amount, _Amount):
        return amount
    power = _SCALE_WORDS[written["scale"]] + letter_power
    return _Amount(_scaled(amount.value, power), amount.cautions)


def _written(digits: str) -> _Amount | Doubt | None:
    """Read digits written with points and commas; ``None`` when they are not a number."""
    if _PLAIN.fullmatch(digits):
        if _GROUP_LIKE_FRACTION.fullmatch(digits):
            return _Amount(Decimal(digits), (Caution.POINT_MAY_BE_THOUSANDS_SEPARATOR,))
        return _Amount(Decimal(digits))
    if _GROUPED.fullmatch(digits):
        return _Amount(Decimal(digits.replace(",", "")))
    if _LEADING_ZERO.match(digits):
        # Nobody writes an amount with zeros in front; this is a code or a clock time.
        return None
    return Doubt.AMBIGUOUS_SEPARATOR


def _scaled(value: Decimal, power: int) -> Decimal:
    """``value`` times ten to the ``power``, without the zeros that leaves after the point.

    A number that was not multiplied is handed back untouched, zeros and all:
    it is what the user wrote.
    """
    if power == 0:
        return value
    product = working_context().multiply(value, Decimal((0, (1,), power)))
    text = format(product, "f")
    return Decimal(text.rstrip("0").rstrip(".") if "." in text else text)
