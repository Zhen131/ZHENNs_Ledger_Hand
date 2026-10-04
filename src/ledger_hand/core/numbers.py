"""Numbers as text: reading a number the way people write or say it.

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

A number may be said in Chinese number words ("九万四千九", "零点五"). Two
habits of speech are read:

- A last digit with no unit takes the unit just below the one before it:
  "两万三" is 23000 and "三千五" is 3500. After 十, and after 零, it is a
  plain digit: "二十三" is 23 and "两千零五" is 2005.
- 两 stands for two before 百, 千, 万 and 亿, and alone.

Otherwise the words must follow each other the way a number is properly said.
Where a place is skipped there must be a 零, unless the skipped places are
the empty end of a four-digit section ("一百万五千"). Without that rule "一亿
五千" could be 100005000 or the everyday short form of 150000000; such words
are a ``Doubt``. So are two digits side by side ("两三千").

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
import itertools
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

from ledger_hand.core.arithmetic import working_context


class Doubt(enum.Enum):
    """Why a text that looks like a number was not given a value."""

    AMBIGUOUS_SEPARATOR = "the separators can be read in more than one way"
    UNCLEAR_MULTIPLIER = "a letter or word may or may not be meant as a multiplier"
    UNCLEAR_WORDING = "the number words do not add up to one reading"


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

# Number words as they are said.
_SAID_DIGITS: Mapping[str, int] = {
    "零": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}
_SMALL_UNITS: Mapping[str, int] = {"十": 1, "百": 2, "千": 3}
# The unit a last digit takes when it is said without one: "两万三" ends in 三千.
_UNIT_BELOW: Mapping[str, str] = {"百": "十", "千": "百", "万": "千", "亿": "千万"}

# Digits are spelled out as 0-9 throughout: the shorthand for "a digit" would
# also match the digits of every other script.
_DIGIT = "一二两三四五六七八九"
_SCALE = "十百千万亿"
_SAID = f"零{_DIGIT}{_SCALE}点"
_SHAPE = re.compile(
    rf"\s*(?P<sign>[{_CURRENCY_SIGNS}]?)\s*"
    rf"(?P<body>[0-9{_SAID}](?:[0-9.,\s{_SAID}]*[0-9{_SAID}])?)"
    r"(?P<letters>[A-Za-z]*)(?P<rest>.*)",
    re.DOTALL,
)
_SAID_WHOLE = re.compile(rf"[零{_DIGIT}{_SCALE}]+")
_SAID_DECIMAL = re.compile(
    rf"(?P<whole>[零{_DIGIT}{_SCALE}]+)点(?P<fraction>[零一二三四五六七八九]+)(?P<scale>[{_SCALE}]*)"
)
_MISPLACED_TWO = re.compile(r"两(?![百千万亿])")
_SECTION = re.compile(rf"(?:零?[{_DIGIT}][十百千]?)*")
_TERM = re.compile(rf"(零?)([{_DIGIT}])([十百千]?)")
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


@dataclass(frozen=True)
class _Place:
    """One digit of a number said in words, at the power of ten its units give it."""

    amount: int
    rank: int
    after_zero: bool


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
    numeral = "".join(body.split())
    written = _DIGITS_THEN_SCALE.fullmatch(numeral)
    if written is not None and written["scale"] in _SCALE_WORDS:
        if letter_power and written["scale"]:
            return Doubt.UNCLEAR_MULTIPLIER
        return _written(written["digits"], _SCALE_WORDS[written["scale"]] + letter_power)
    if letter_power:
        return Doubt.UNCLEAR_MULTIPLIER
    return _said(numeral) or Doubt.UNCLEAR_WORDING


def _written(digits: str, power: int) -> _Amount | Doubt | None:
    """Read digits written with points and commas, times ten to the ``power``.

    ``None`` when the digits are not a number.
    """
    if _PLAIN.fullmatch(digits):
        value = _scaled(Decimal(digits), power)
        if _GROUP_LIKE_FRACTION.fullmatch(digits):
            return _Amount(value, (Caution.POINT_MAY_BE_THOUSANDS_SEPARATOR,))
        return _Amount(value)
    if _GROUPED.fullmatch(digits):
        return _Amount(_scaled(Decimal(digits.replace(",", "")), power))
    if _LEADING_ZERO.match(digits):
        # Nobody writes an amount with zeros in front; this is a code or a clock time.
        return None
    return Doubt.AMBIGUOUS_SEPARATOR


def _said(numeral: str) -> _Amount | None:
    """Read a number said in number words; ``None`` when they have no single reading."""
    decimal = _SAID_DECIMAL.fullmatch(numeral)
    if decimal is None:
        whole = _said_whole(numeral)
        return None if whole is None else _Amount(Decimal(whole))
    if decimal["scale"] not in _SCALE_WORDS or _is_shortened(decimal["whole"]):
        return None
    whole = _said_whole(decimal["whole"])
    if whole is None:
        return None
    fraction = "".join(str(_SAID_DIGITS[digit]) for digit in decimal["fraction"])
    return _Amount(_scaled(Decimal(f"{whole}.{fraction}"), _SCALE_WORDS[decimal["scale"]]))


def _said_whole(numeral: str) -> int | None:
    """The whole number said by ``numeral``; ``None`` when it has no single reading."""
    if numeral == "零":
        return 0
    if _SAID_WHOLE.fullmatch(numeral) is None:
        return None
    if numeral != "两" and _MISPLACED_TWO.search(numeral):
        return None
    sections = _sections(_spelled_out(numeral))
    if sections is None:
        return None
    places: list[_Place] = []
    for words, base in sections:
        if _SECTION.fullmatch(words) is None:
            return None
        places.extend(_places(words, base))
    if not _reads_one_way(places):
        return None
    return sum(place.amount for place in places)


def _is_shortened(numeral: str) -> bool:
    """Whether ``numeral`` ends in a digit that borrows its unit, as "两万三" does."""
    return len(numeral) > 1 and numeral[-1] in _DIGIT and numeral[-2] in _UNIT_BELOW


def _spelled_out(numeral: str) -> str:
    """``numeral`` with the two things speech leaves out put back.

    A leading 十 gets its 一, and a shortened ending gets its unit.
    """
    if numeral.startswith("十"):
        numeral = "一" + numeral
    if _is_shortened(numeral):
        numeral += _UNIT_BELOW[numeral[-2]]
    return numeral


def _sections(numeral: str) -> list[tuple[str, int]] | None:
    """Split ``numeral`` at 亿 and 万 into the words of each four-digit section.

    Each section comes with the power of ten of its lowest place. ``None``
    when a unit is repeated or has nothing in front of it to count.
    """
    high, yi, low = numeral.partition("亿")
    if yi and (not high or "亿" in low):
        return None
    sections: list[tuple[str, int]] = []
    for words, base in [(high, 8), (low, 0)] if yi else [(numeral, 0)]:
        upper, wan, lower = words.partition("万")
        if wan and (not upper or "万" in lower):
            return None
        sections.extend([(upper, base + 4), (lower, base)] if wan else [(words, base)])
    return sections


def _places(words: str, base: int) -> list[_Place]:
    """The digits of one section, each at the place its unit gives it."""
    places: list[_Place] = []
    for zero, digit, unit in _TERM.findall(words):
        rank = base + _SMALL_UNITS.get(unit, 0)
        places.append(_Place(_SAID_DIGITS[digit] * 10**rank, rank, after_zero=bool(zero)))
    return places


def _reads_one_way(places: Sequence[_Place]) -> bool:
    """Whether the digits follow each other the way a number is properly said.

    Each digit sits one place below the digit before it. Where places are
    skipped a 零 says so, except that the empty end of a four-digit section is
    passed over in silence. Anything else has more than one reading.
    """
    if not places or places[0].after_zero:
        return False
    for above, below in itertools.pairwise(places):
        if below.after_zero:
            if below.rank >= above.rank - 1:
                return False
        elif below.rank not in (above.rank - 1, 4 * (above.rank // 4) - 1):
            return False
    return True


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
