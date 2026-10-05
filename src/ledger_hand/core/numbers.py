"""Numbers as text: reading one the way people write or say it, writing one for the ledger.

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
or two words after it ("刀", "个", "USDT", "u", "个 BTC"). The unit is handed
back exactly as it was written and is not interpreted here.

Only a unit this program knows is handed back. The unit is cut into blocks at
gaps, and wherever Chinese characters meet anything else, so that "个BTC" is
个 and BTC. Chinese is written without gaps, so a block of Chinese characters
is cut once more, into known words that follow each other with no character
left over: "个比特币" is 个 and 比特币, while "个比特" and "个币" cannot be
cut that way and stay one block. Which characters are Chinese is listed
below: the one block of Unicode that holds the characters in use. Everything
else is on the side of the letters and is never cut, whatever it looks like:
"BTCUSDT" is one block whether its letters are ordinary or mathematical bold
ones, and so is a word in kana or in Cyrillic. A rare Chinese character from
another block, or a compatibility copy of one, is neither cut nor let into a
block: a unit that holds one is known only when the whole of it is a name.

Every block must be one of the following. Letter case does not count, and
each character is taken in its ordinary form, the way a name is looked up in
the coin table: a full-width, superscript, subscript or mathematical letter
is the letter it stands for. A block of letters must be in one kind of
letters, all with capitals or all without: ordinary letters with raised or
mathematical ones among them are two pieces of writing run together, and no
unit that holds such a block is known, not even as a whole.

- a word for USDT ("u", "刀", "美金", "$"): the list in ``coins``;
- the symbol or a name of a coin in the coin table ("BTC", "比特币");
- a counter that says how many and nothing about how much one of them is
  ("个", "枚"): the short list in this module, each with its reason;
- a word the caller passes in for this one call (``extra_units``), such as the
  name of a coin outside the table. A word this program itself reads as part
  of the number is not taken from the caller: a number character, and "k" or
  "w" standing as a word of its own.

Before any cutting, the unit as a whole is looked up among the same names: a
name of several words ("Bitcoin Cash", or one the caller allows) is known
only as a whole. "5 Bitcoin Cash" is five of that coin; "5 Cash" and
"5 Bitcoin Cashs" are not, because "Cash" alone is no known word.

A unit with any other block in it is a ``Doubt``: an unknown unit. That is
the whole rule, and it is why no list of words that change a number is kept
here: "5 mBTC", "100 ksats", "3个w", "2 thousands" and "5 BTCks" are all
turned away for the same reason as "三天", namely that a block is not known.
Nothing is remembered between calls, and a block is never matched in part: a
caller that allows "BONK" gets "500 BONK" read, and "5 kBONK" stays a doubt.

Two things are settled before the blocks are looked at. A word that holds a
Chinese number character is never a unit, so "3兆" and "三块五" are not
numbers with a unit: those characters are a closed set, listed once below.
And what follows the number must have the shape of a unit at all: one
currency sign, or words of letters no longer together than the longest coin
symbol the ledger allows; more than two words only when together they are
one known name.

Written digits may be followed by a multiplier: the letter "k" (thousand) or
"w" (ten thousand, from 万) directly after the last digit, or one of the words
千, 万, 十万, 百万, 千万, 亿, 十亿, 百亿, 千亿, 万亿. The letter "m" is not
read as a multiplier: it is a million to some and a thousandth (as in mBTC) to
others. A multiplier is applied only where its place leaves no doubt: where
letters go on after the "k" or the "w", what follows the digits is a unit
only when it is a known unit as it stands and is not a multiplier with a
known unit behind it. "50u" is fifty u; "1ku", which may be a thousand u, is
a ``Doubt``. Letters in another form or another alphabet go on a word just
as ordinary ones do: "5k" with a mathematical u behind it is the same doubt.
A "k" or "w" that is itself written in such a form is not a multiplier.

A number may be said in Chinese number words ("九万四千九", "零点五"). Two
habits of speech are read:

- A last digit with no unit takes the unit just below the one before it:
  "两万三" is 23000 and "三千五" is 3500. After 十, and after 零, it is a
  plain digit: "二十三" is 23 and "两千零五" is 2005. After a unit built on
  百 or 千, such as 百万 or 千亿, the short form is a ``Doubt``: "一百万五"
  may end in five thousand or in five hundred thousand.
- 两 stands for two before 百, 千, 万 and 亿, and alone.

Otherwise the words must follow each other the way a number is properly said.
Where a place is skipped there must be a 零, unless the skipped places are
the empty end of a four-digit section ("一百万五千"). Without that rule "一亿
五千" could be 100005000 or the everyday short form of 150000000; such words
are a ``Doubt``. So are two digits side by side ("两三千").

Digits may stand in for the number words: "9万4" is 94000 and "12万3" is
123000. A single digit behaves like the word for it. Several digits together
are a count that fills a four-digit section ("9万4900", "1亿5000万").

Commas count as thousands separators only in the strict form: one to three
digits, then groups of exactly three. Any other mix of commas, points and
gaps between digits is a ``Doubt``, because a comma is a decimal mark in much
of Europe. A point followed by exactly three digits is read as a decimal
point, with a ``Caution`` that it may have been meant to group thousands.

A text that names no single exact amount is a ``Doubt`` too: a range ("8万
到8万5"), an approximate amount ("大概两万", "两万多"), and a half, a share
or a multiple ("半个", "30%", "三成"). The word lists for these are a net,
not a grammar: a vague text they miss comes back as ``NotANumber`` or as an
unknown unit, never as a number.

A number with more decimal places or more digits than the ledger holds is a
``Doubt`` as well: it is never rounded or cut to fit. The limits apply to the
number after its multiplier.

A text of any length gets its answer in time that grows no faster than the
text: a unit is measured before anything is looked up in it, and a count of
thousands of digits is weighed by its length, not added up.

``write_number`` goes the other way: an exact decimal becomes the text the
ledger accepts for a number, which is plain digits with no exponent, no sign
and no needless zero in front. Zeros after the point are kept as they are.

This module does not decide whether a number is a price, a quantity or a fee,
and it does not look for numbers inside a sentence.

Names defined here: ``read_number``, ``write_number``, ``Reading``,
``Recognised``, ``Unsure``, ``NotANumber``, ``Doubt`` and ``Caution``.
"""

from __future__ import annotations

import enum
import itertools
import re
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

from ledger_hand.core.arithmetic import working_context
from ledger_hand.core.coins import BUILT_IN_TABLE, means_usdt, spoken_key
from ledger_hand.core.ledger_limits import (
    MAX_DECIMAL_PLACES,
    MAX_SIGNIFICANT_DIGITS,
    SYMBOL_MAX_LENGTH,
    decimal_places,
    fits_digit_limits,
    significant_digits,
)


class Doubt(enum.Enum):
    """Why a text that looks like a number was not given a value."""

    AMBIGUOUS_SEPARATOR = "the separators can be read in more than one way"
    UNCLEAR_MULTIPLIER = "a letter or word may or may not be meant as a multiplier"
    UNCLEAR_WORDING = "the number words do not add up to one reading"
    RANGE = "a range, not one amount"
    APPROXIMATE = "an approximate amount, not an exact one"
    HALF_OR_SHARE = "a half, a share or a multiple, not a plain amount"
    UNKNOWN_UNIT = "a unit word that is not on the list of units this program knows"
    TOO_MANY_DECIMAL_PLACES = "more decimal places than the ledger holds"
    TOO_MANY_DIGITS = "more digits than the ledger holds"


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

# The full-width forms of the ASCII characters and of two currency signs, each
# mapped to its ordinary form. One character maps to one character, so a
# position in the folded text is the same position in the original, and the
# unit can be handed back as it was written. Folding by Unicode's
# compatibility rules would also turn circled and superscript digits into
# plain ones, and those are not how anyone writes an amount.
_FOLDED = {code: code - 0xFEE0 for code in range(0xFF01, 0xFF5F)}
_FOLDED.update({0xFFE5: 0xA5, 0xFFE1: 0xA3})

_CURRENCY_SIGNS = "$¥€£"

# The Chinese characters: the block Unicode calls "CJK Unified Ideographs",
# which holds the characters in use. Only a run of these is cut into known
# words. Nothing is taken for Chinese because of what it is not: kana, Hangul,
# the letters of every alphabet, and the mathematical, superscript and
# subscript forms of Latin letters, which have no capitals either, all stay
# on the side of the letters.
_FIRST_CHINESE_CHARACTER = "\u4e00"
_LAST_CHINESE_CHARACTER = "\u9fff"
# Chinese characters that Unicode keeps elsewhere: the rare ones of the
# extension blocks, and the copies kept for compatibility. Whether these count
# as Chinese characters for cutting is drawn differently by different people,
# so this program takes neither side: a unit that holds one is known only as
# a whole, never block by block.
_NAMES_OF_OTHER_IDEOGRAPHS = ("CJK UNIFIED IDEOGRAPH-", "CJK COMPATIBILITY IDEOGRAPH-")

# The counters: words that say "this many of them" and nothing about how much
# one of them is, each with the reason it leaves the number as it is. Together
# with the words for USDT and the names in the coin table, they are the only
# unit words this program hands back without being told to.
_COUNTERS: Mapping[str, str] = {
    "个": "the general counter: 0.5个 is half of one, whatever is counted",
    "個": "the same counter in its traditional form",
    "枚": "the counter for coins and other small flat things",
    "颗": "a counter for small round things, said of coins as well",
    "顆": "the same counter in its traditional form",
    "COIN": "the thing counted itself, one at a time",
    "COINS": "the plural of the same word",
    "TOKEN": "another word for the thing counted itself",
    "TOKENS": "the plural of the same word",
}

# Every character that says a number in Chinese writing, listed once. The set
# is closed: nothing is added to it as new words come into use. A word holding
# any of these is never a unit, whether or not this program can read the
# character where it stands. (半 and 几 belong to the same family and are
# turned away wherever they stand, by the wording hints further down.)
_NUMBER_WORDS = frozenset(
    # the digits and the places up to 亿, which this program reads
    "零〇一二三四五六七八九十百千万亿"
    # the places after 亿
    "兆京垓秭穰沟涧正载极"
    # two, a pair, three of something, twenty (in two forms), thirty (in two
    # forms), forty, two hundred, the spoken "one", and the decimal point
    "两俩仨廿卄卅丗卌皕幺点"
    # the formal forms used on cheques and contracts, and their old variants
    "壹贰叁肆伍陆柒捌玖拾佰仟陌阡弌弍弎壱弐貮"
    # the traditional forms of all of the above, and the Japanese forms of 兩
    # and 穰
    "萬億兩倆貳參叄参陸溝澗載極點幾両穣"
    # the circle written for zero, as in 二○二六
    "\N{WHITE CIRCLE}"
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
    **{str(digit): digit for digit in range(1, 10)},
}
_SMALL_UNITS: Mapping[str, int] = {"十": 1, "百": 2, "千": 3}
# The unit a last digit takes when it is said without one: "两万三" ends in 三千.
_UNIT_BELOW: Mapping[str, str] = {"百": "十", "千": "百", "万": "千", "亿": "千万"}

# Digits are spelled out as 0-9 throughout: the shorthand for "a digit" would
# also match the digits of every other script.
_DIGIT = "一二两三四五六七八九1-9"
_SCALE = "十百千万亿"
_SAID = f"零{_DIGIT}{_SCALE}点"
# Nowhere in these patterns do two stretches of optional gaps stand side by
# side: a long run of spaces would be shared out between them in every way.
_SHAPE = re.compile(
    rf"\s*(?:(?P<sign>[{_CURRENCY_SIGNS}])\s*)?"
    rf"(?P<body>[0-9{_SAID}](?:[0-9.,\s{_SAID}]*[0-9{_SAID}])?)"
    r"(?P<letters>[A-Za-z]*)(?P<rest>.*)",
    re.DOTALL,
)
_SAID_WHOLE = re.compile(rf"[0-9零{_DIGIT}{_SCALE}]+")
_SAID_DECIMAL = re.compile(
    rf"(?P<whole>[零一二两三四五六七八九{_SCALE}]+)点"
    rf"(?P<fraction>[零一二三四五六七八九]+)(?P<scale>[{_SCALE}]*)"
)
_MISPLACED_TWO = re.compile(r"两(?![百千万亿])")
_SHORTENED = re.compile(rf"[百千万亿][{_DIGIT}]")
_COUNT = re.compile(r"[1-9][0-9]+")
_SECTION = re.compile(rf"(?:零?[{_DIGIT}][十百千]?)*")
_TERM = re.compile(rf"(零?)([{_DIGIT}])([十百千]?)")
_EXPONENT = re.compile(r"[0-9]\.?[eE][+-]?[0-9]")
_SPLIT_DIGITS = re.compile(r"[0-9.,]\s+[0-9.,]")
_DIGITS_THEN_SCALE = re.compile(rf"(?P<digits>[0-9][0-9.,]*)(?P<scale>[{_SCALE}]*)")
_PLAIN = re.compile(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?")
_GROUPED = re.compile(r"[1-9][0-9]{0,2}(?:,[0-9]{3})+(?:\.[0-9]+)?")
_GROUP_LIKE_FRACTION = re.compile(r"[1-9][0-9]{0,2}\.[0-9]{3}")
_LEADING_ZERO = re.compile(r"0[0-9]")


# Wording that says the text names no single exact amount. Each pattern is
# tried only on a text that holds a digit or a number word at all.
_NUMBER_LIKE = re.compile(rf"[0-9零{_DIGIT}{_SCALE}半几]")
_IN_NUMBER = f"0-9零一二两三四五六七八九{_SCALE}"
# Latin letters, with and without accents: a hint word counts only where it is
# not part of a longer word in these letters.
_LATIN = r"a-z\u00c0-\u024f"
_VAGUE_WORDS = (
    "about|around|roughly|approx|approximately|nearly|almost|maybe|over|under|ish"
    "|or so|or more|or less|at most|at least"
)
_WORDING_HINTS: tuple[tuple[Doubt, re.Pattern[str]], ...] = (
    (
        Doubt.HALF_OR_SHARE,
        re.compile(
            rf"半|[%‰]|分之|部分|[{_IN_NUMBER}]\s*[成倍折层](?!交)|[0-9]\s*/\s*[0-9]"
            rf"|(?<![{_LATIN}])(?:half|percent|pct)(?![{_LATIN}])",
            re.IGNORECASE,
        ),
    ),
    (
        Doubt.RANGE,
        re.compile(
            rf"[{_IN_NUMBER}]\s*(?:[^\W\d_]{{1,8}}\s*)?"
            rf"(?:[到至~〜\-–—]|(?<![{_LATIN}])to(?![{_LATIN}]))"
            rf"\s*(?:[{_CURRENCY_SIGNS}]\s*)?[{_IN_NUMBER}]",
            re.IGNORECASE,
        ),
    ),
    (
        Doubt.APPROXIMATE,
        re.compile(
            r"大概|大约|约|差不多|左右|上下|多|来|余|几|些|近|不到|超过|至少|最多|起码|出头"
            r"|以上|以下|以内|[~〜≈±<>≤≥]|[0-9]\s*\+"
            rf"|(?<![{_LATIN}])(?:{_VAGUE_WORDS})(?![{_LATIN}])",
            re.IGNORECASE,
        ),
    ),
)


@dataclass(frozen=True)
class _Tail:
    """What follows the number: a letter multiplier as a power of ten, and a unit."""

    power: int
    unit: str | None


@dataclass(frozen=True)
class _Amount:
    """What the number itself says: a value, times ten to the ``power``."""

    value: Decimal
    power: int = 0
    cautions: tuple[Caution, ...] = ()


@dataclass(frozen=True)
class _Place:
    """A digit, or a count written in digits, in a number said in words.

    ``top`` and ``bottom`` are the powers of ten of its highest digit and of
    its lowest digit that is not zero; for a single digit they are the same.
    ``digits`` are the digits from the one to the other.
    """

    digits: str
    top: int
    bottom: int
    after_zero: bool


def read_number(text: str, extra_units: Iterable[str] = ()) -> Reading:
    """Read ``text`` as one number, or say why it cannot be read as one.

    ``extra_units`` are unit words the caller allows for this one call, on top
    of the ones this program knows: the name of a coin outside the table, for
    instance. The whole unit or a block of it must equal one of them, letter
    case aside and with every character in its ordinary form. Only a name
    made of words of letters is taken, or one currency sign. A word this
    program itself reads as part of the number is not taken either, as if it
    had not been passed: one that holds a number character, and one in which
    "k" or "w" stands as a word of its own.
    """
    if isinstance(extra_units, str):
        raise TypeError("pass the extra unit words as a collection, not as one string")
    allowed = frozenset(spoken_key(word) for word in extra_units if _may_be_allowed(word))
    folded = text.translate(_FOLDED)
    if _EXPONENT.search(folded):
        return NotANumber()
    reading = _strictly_read(folded, text, allowed)
    if reading is None:
        doubt = _wording_doubt(folded)
        return NotANumber() if doubt is None else Unsure(doubt)
    if isinstance(reading, Recognised) and reading.unit is not None:
        # A word like 多 or 左右 says more than "a unit this program does not
        # know", so the wording is looked at first.
        doubt = _wording_doubt(folded)
        if doubt is None and not _is_known_unit(reading.unit, allowed):
            doubt = Doubt.UNKNOWN_UNIT
        if doubt is not None:
            return Unsure(doubt)
    return reading


def write_number(value: Decimal) -> str:
    """``value`` as the ledger wants a number written.

    Raises ``ValueError`` for a value the ledger cannot hold as it stands: one
    that is not finite, is below zero, or has more digits than the ledger's
    limits. Nothing is rounded to make it fit. A draft with such a number is
    turned away by ``validation``, so one arriving here is a mistake in the
    calling code.
    """
    if not value.is_finite():
        raise ValueError(f"the ledger holds only finite numbers, not {value}")
    if value < 0:
        raise ValueError(f"the ledger holds no number below zero, such as {value}")
    if not fits_digit_limits(value):
        raise ValueError(f"{value} has more digits than the ledger holds")
    # Python's own text for a decimal switches to an exponent for small
    # numbers, and writes a zero that carries a sign with that sign.
    return format(value.copy_abs(), "f")


def _may_be_allowed(name: str) -> bool:
    """Whether ``name``, as the caller wrote it, may be a unit the caller allows.

    It must be what a unit can be: one currency sign, or words that are still
    words of letters once they are in ordinary characters. And this program
    must not read it as part of the number. "5k" is five thousand, so "5 k"
    must not be five of something called k; and a number character is never
    a unit. A name that only holds such a letter ("kBONK") is a name like any
    other.
    """
    words = [_plain(word) for word in name.split()]
    if len(words) == 1 and words[0] in _CURRENCY_SIGNS:
        return True
    if not words or not all(word.isalpha() for word in words):
        return False
    if any(character in _NUMBER_WORDS for word in words for character in word):
        return False
    blocks = ("".join(run) for word in words for _, run in itertools.groupby(word, key=_is_chinese))
    return not any(block.lower() in _LETTER_MULTIPLIERS for block in blocks)


def _wording_doubt(folded: str) -> Doubt | None:
    """The first reason the wording gives for not naming one exact amount, if any."""
    if _NUMBER_LIKE.search(folded) is None:
        return None
    for doubt, pattern in _WORDING_HINTS:
        if pattern.search(folded):
            return doubt
    return None


def _strictly_read(folded: str, original: str, allowed: frozenset[str]) -> Reading | None:
    """Read a text of the one accepted shape: a sign, the number, a multiplier, a unit.

    ``None`` means the text does not have that shape.
    """
    shape = _SHAPE.fullmatch(folded)
    if shape is None:
        return None
    tail = _tail(shape, original, allowed)
    if isinstance(tail, Doubt):
        return Unsure(tail)
    sign = original[shape.start("sign") : shape.end("sign")] if shape["sign"] else ""
    if tail is None or (sign and tail.unit):
        return None
    amount = _amount(shape["body"], tail.power)
    if amount is None:
        return None
    if isinstance(amount, Doubt):
        return Unsure(amount)
    value = _within_limits(amount)
    if isinstance(value, Doubt):
        return Unsure(value)
    return Recognised(value, sign or tail.unit, amount.cautions)


def _tail(shape: re.Match[str], original: str, allowed: frozenset[str]) -> _Tail | Doubt | None:
    """The multiplier letter and the unit after the number.

    ``None`` when what follows the number is not one unit.
    """
    letters = shape["letters"].lower()
    # Letters may go on in another form or another alphabet ("5k" and then a
    # mathematical bold u). Whatever is a letter and not Chinese carries on
    # the word that the "k" began.
    next_character = _plain(shape["rest"][:1])[:1]
    go_on = next_character.isalpha() and not _is_chinese(next_character)
    power = 0 if go_on else _LETTER_MULTIPLIERS.get(letters, 0)
    if not power and letters[:1] in _LETTER_MULTIPLIERS:
        # "5ku" may be five thousand u or five of a coin called ku. What follows
        # the digits is a unit only when it is a known unit as it stands, and
        # is not a multiplier with a known unit behind it.
        after_digits = shape.string[shape.start("letters") :].strip()
        is_unit_as_it_stands = _is_known_unit(after_digits, allowed)
        is_multiplier_and_unit = _is_known_unit(after_digits[1:].strip(), allowed)
        if is_multiplier_and_unit or not is_unit_as_it_stands:
            return Doubt.UNCLEAR_MULTIPLIER
    start = shape.end("letters") if power else shape.start("letters")
    unit = shape.string[start:].strip()
    if not unit:
        return _Tail(power, unit=None)
    if _is_unit(unit, allowed):
        return _Tail(power, unit=original[start:].strip())
    return None


def _is_unit(text: str, allowed: frozenset[str]) -> bool:
    """Whether ``text`` is a currency sign, or one or two short words of letters.

    No word may hold a number word. More than two words are a unit only when
    together they are one name this program knows or the caller allows.
    """
    if len(text) > SYMBOL_MAX_LENGTH:
        return False
    if len(text) == 1 and text in _CURRENCY_SIGNS:
        return True
    words = text.split()
    letters = "".join(words)
    if not all(letter.isalpha() for letter in letters):
        return False
    # A number character is one in whatever form it is written.
    if any(letter in _NUMBER_WORDS for letter in _plain(letters)):
        return False
    return len(words) <= 2 or _is_known_word(text, allowed)


def _is_known_unit(unit: str, allowed: frozenset[str]) -> bool:
    """Whether ``unit`` is one this program knows or the caller allows.

    It is when the whole of it is one known name, which may have several
    words ("Bitcoin Cash"), or when every block of it is a known word. The
    unit is cut at its gaps, and each word is put in ordinary characters. The
    blocks are what is left when a word is then cut wherever Chinese
    characters meet anything else. Chinese is written without gaps, so a
    block of Chinese characters also counts when it is known words one after
    another, from end to end. A block of anything else is one word, whatever
    it holds, and must be in one kind of letters wherever it stands. A unit
    that holds a Chinese character from outside the listed block is not
    judged block by block at all.
    """
    if len(unit) > SYMBOL_MAX_LENGTH:
        # Asked first: nothing below is done to a text of any length.
        return False
    words = [_plain(word) for word in unit.split()]
    if len(words) == 1 and words[0] in _CURRENCY_SIGNS:
        return _is_known_word(words[0], allowed)
    # A word must still be a word of letters once it is in ordinary
    # characters: some characters come apart into a gap and a mark, and a gap
    # that was not written must not cut the word in two.
    if not words or not all(word.isalpha() for word in words):
        return False
    blocks = [
        (is_chinese, "".join(run))
        for word in unit.split()
        for is_chinese, run in itertools.groupby(word, key=_is_chinese)
    ]
    if not all(is_chinese or _is_in_one_kind_of_letters(block) for is_chinese, block in blocks):
        return False
    if _is_known_word(" ".join(words), allowed):
        return True
    if any(map(_is_ideograph_kept_elsewhere, unit)):
        return False
    return all(
        _is_run_of_known_words(block, allowed) if is_chinese else _is_known_word(block, allowed)
        for is_chinese, block in blocks
    )


def _is_in_one_kind_of_letters(block: str) -> bool:
    """Whether the letters of ``block`` all have capitals, or all have none.

    A word is written in one kind of letters. Ordinary letters with
    superscript or mathematical ones among them ("BT" and a raised "C") are
    two pieces of writing run together, and no known word, whether the block
    is part of the unit or the whole of it.
    """
    return len({letter.lower() != letter.upper() for letter in block}) == 1


def _is_run_of_known_words(run: str, allowed: frozenset[str]) -> bool:
    """Whether ``run`` can be cut into known words with no character left over."""
    # The places in the run that a row of known words, begun at its start, can
    # end at. No word is longer than a unit may be, so each place looks back
    # over a fixed stretch only, and the work grows no faster than the run.
    ends = {0}
    for end in range(1, len(run) + 1):
        starts = range(max(0, end - SYMBOL_MAX_LENGTH), end)
        if any(start in ends and _is_known_word(run[start:end], allowed) for start in starts):
            ends.add(end)
    return len(run) in ends


def _is_known_word(text: str, allowed: frozenset[str]) -> bool:
    """Whether ``text`` is a word for USDT, a name in the coin table, a counter or allowed.

    A name may have several words; the gaps between them may be of any width.
    """
    word = spoken_key(text)
    if word in _COUNTERS or word in allowed or means_usdt(text):
        return True
    return BUILT_IN_TABLE.find(text) is not None


def _is_chinese(character: str) -> bool:
    """Whether ``character`` is a Chinese character of the block listed for them."""
    return _FIRST_CHINESE_CHARACTER <= character <= _LAST_CHINESE_CHARACTER


def _is_ideograph_kept_elsewhere(character: str) -> bool:
    """Whether ``character`` is a Chinese character outside that block, by its Unicode name."""
    return not _is_chinese(character) and unicodedata.name(character, "").startswith(
        _NAMES_OF_OTHER_IDEOGRAPHS
    )


def _plain(text: str) -> str:
    """``text`` with every character in its ordinary form, the way names are looked up.

    Full-width, superscript, subscript and mathematical letters become the
    ordinary letters they stand for, and a Chinese character from the
    compatibility blocks becomes the character it is a copy of.
    """
    return unicodedata.normalize("NFKC", text)


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
        if _GROUP_LIKE_FRACTION.fullmatch(digits):
            caution = Caution.POINT_MAY_BE_THOUSANDS_SEPARATOR
            return _Amount(Decimal(digits), power, (caution,))
        return _Amount(Decimal(digits), power)
    if _GROUPED.fullmatch(digits):
        return _Amount(Decimal(digits.replace(",", "")), power)
    if _LEADING_ZERO.match(digits):
        # Nobody writes an amount with zeros in front; this is a code or a clock time.
        return None
    return Doubt.AMBIGUOUS_SEPARATOR


def _said(numeral: str) -> _Amount | Doubt | None:
    """Read a number said in number words; ``None`` when they have no single reading."""
    decimal = _SAID_DECIMAL.fullmatch(numeral)
    if decimal is None:
        whole = _said_whole(numeral)
        return whole if whole is None or isinstance(whole, Doubt) else _Amount(Decimal(whole))
    if decimal["scale"] not in _SCALE_WORDS or _is_shortened(decimal["whole"]):
        return None
    whole = _said_whole(decimal["whole"])
    if whole is None or isinstance(whole, Doubt):
        return whole
    fraction = "".join(str(_SAID_DIGITS[digit]) for digit in decimal["fraction"])
    return _Amount(Decimal(f"{whole}.{fraction}"), _SCALE_WORDS[decimal["scale"]])


def _said_whole(numeral: str) -> int | Doubt | None:
    """The whole number said by ``numeral``; ``None`` when it has no single reading."""
    if numeral == "零":
        return 0
    if _SAID_WHOLE.fullmatch(numeral) is None:
        return None
    if numeral != "两" and _MISPLACED_TWO.search(numeral):
        return None
    places = _all_places(_spelled_out(numeral))
    if places is None or not _reads_one_way(places):
        return None
    if _is_shortened(numeral) and places[-2].bottom - places[-1].top > 2:
        # "一百万五" may end in five thousand or in five hundred thousand.
        return None
    if places[0].top - places[-1].bottom >= MAX_SIGNIFICANT_DIGITS:
        # The places lie one below the other, so the number has a digit at the
        # top of the first and at the bottom of the last. It is not added up:
        # a count of thousands of digits would take long, and Python refuses
        # to turn more than a few thousand digits into a whole number.
        return Doubt.TOO_MANY_DIGITS
    whole: int = sum(int(place.digits) * 10**place.bottom for place in places)
    return whole


def _all_places(numeral: str) -> list[_Place] | None:
    """Every digit of ``numeral`` at its place; ``None`` when a section cannot be read."""
    sections = _sections(numeral)
    if sections is None:
        return None
    places: list[_Place] = []
    for words, base in sections:
        if _COUNT.fullmatch(words):
            places.append(_counted(words, base))
        elif _SECTION.fullmatch(words):
            places.extend(_places(words, base))
        else:
            return None
    return places


def _is_shortened(numeral: str) -> bool:
    """Whether ``numeral`` ends in a digit that borrows its unit, as "两万三" does."""
    return _SHORTENED.fullmatch(numeral[-2:]) is not None


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
    when a unit has nothing in front of it to count. A unit said twice stays
    inside a section, where nothing can read it.
    """
    high, yi, low = numeral.partition("亿")
    if yi and not high:
        return None
    sections: list[tuple[str, int]] = []
    for words, base in [(high, 8), (low, 0)] if yi else [(numeral, 0)]:
        upper, wan, lower = words.partition("万")
        if wan and not upper:
            return None
        sections.extend([(upper, base + 4), (lower, base)] if wan else [(words, base)])
    return sections


def _places(words: str, base: int) -> list[_Place]:
    """The digits of one section, each at the place its unit gives it."""
    places: list[_Place] = []
    for zero, digit, unit in _TERM.findall(words):
        rank = base + _SMALL_UNITS.get(unit, 0)
        places.append(_Place(str(_SAID_DIGITS[digit]), rank, rank, after_zero=bool(zero)))
    return places


def _counted(count: str, base: int) -> _Place:
    """A whole section written as digits, like the 12 of "12万" or the 4900 of "9万4900"."""
    digits = count.rstrip("0")
    return _Place(
        digits,
        top=base + len(count) - 1,
        bottom=base + len(count) - len(digits),
        after_zero=False,
    )


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
            if below.top >= above.bottom - 1:
                return False
        elif below.top not in (above.bottom - 1, 4 * (above.bottom // 4) - 1):
            return False
    return True


def _within_limits(amount: _Amount) -> Decimal | Doubt:
    """The value with its multiplier applied, if the ledger can hold it as it stands."""
    if significant_digits(amount.value) > MAX_SIGNIFICANT_DIGITS:
        # Multiplying never makes a number shorter, and turning away the
        # longest ones here keeps the multiplication below exact.
        return Doubt.TOO_MANY_DIGITS
    value = _scaled(amount.value, amount.power)
    if decimal_places(value) > MAX_DECIMAL_PLACES:
        return Doubt.TOO_MANY_DECIMAL_PLACES
    if significant_digits(value) > MAX_SIGNIFICANT_DIGITS:
        return Doubt.TOO_MANY_DIGITS
    return value


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
