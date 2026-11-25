"""Generated numbers: tidying writes each in digits, and never changes what it is.

Two thousand numbers are drawn with a fixed seed, so that every run draws
the same ones and a failure can be run again: half whole numbers from 1 to
999999999, half decimals with a whole part from 0 to 99999 and one to eight
places. Each is written in number words the standard way (this file's own
writer) and said in three sentences. A number left as it was must be left
for one of two reasons, a point followed by exactly three digits or a last
一; at least seven in ten sentences must be tidied.
"""

from __future__ import annotations

import random
from decimal import Decimal

import pytest

from ledger_hand.core.ledger_limits import MAX_DECIMAL_PLACES
from ledger_hand.core.numbers import Recognised, read_number
from ledger_hand.core.spoken_text import ChangeKind, Tidied, tidy_spoken

ZONE = "Europe/Budapest"
SEED = 20261125
COUNT = 2000
WORDS = "零一二三四五六七八九"
SECTION_NAMES = ("", "万", "亿")


def _section(value: int, *, first: bool) -> str:
    """A section of up to four digits in words; a leading 一十 is said 十 at the very start."""
    digits = f"{value:04d}"
    said = ""
    zero = False
    for digit, place in zip(digits, ("千", "百", "十", ""), strict=True):
        if digit == "0":
            zero = bool(said)
            continue
        if zero:
            said += "零"
            zero = False
        said += WORDS[int(digit)] + place
    if first and said.startswith("一十"):
        said = said[1:]
    return said


def whole_in_words(value: int) -> str:
    """``value`` said the standard way: four-digit sections, 零 where places are skipped."""
    if value == 0:
        return "零"
    sections = []
    while value:
        sections.append(value % 10000)
        value //= 10000
    said = ""
    for position in range(len(sections) - 1, -1, -1):
        section = sections[position]
        if section == 0:
            continue
        higher = position < len(sections) - 1
        skipped = higher and (section < 1000 or sections[position + 1] == 0)
        if said and skipped:
            said += "零"
        said += _section(section, first=not said) + SECTION_NAMES[position]
    return said


def _digits_in_words(digits: str) -> str:
    return "".join(WORDS[int(digit)] for digit in digits)


def _drawn() -> list[tuple[Decimal, str, str | None]]:
    """The numbers: each value, its words, and for a decimal its digits after the point."""
    draw = random.Random(SEED)
    numbers: list[tuple[Decimal, str, str | None]] = []
    for _ in range(COUNT // 2):
        value = draw.randint(1, 999_999_999)
        numbers.append((Decimal(value), whole_in_words(value), None))
    for _ in range(COUNT // 2):
        whole = draw.randint(0, 99_999)
        places = draw.randint(1, 8)
        fraction = "".join(str(draw.randint(0, 9)) for _ in range(places))
        said = f"{whole_in_words(whole)}点{_digits_in_words(fraction)}"
        numbers.append((Decimal(f"{whole}.{fraction}"), said, fraction))
    return numbers


NUMBERS = _drawn()


def _sentences() -> list[tuple[str, str, Decimal, str, str]]:
    """(prefix, number as said, value, suffix, kind) for every sentence made."""
    made = []
    for value, words, fraction in NUMBERS:
        made.append(("买了", words, value, "个BTC", "words"))
        made.append(("均价是", words, value, "USDT", "words"))
        if fraction is not None:
            whole = str(value).split(".")[0]
            made.append(("花了", f"{whole}.{_digits_in_words(fraction)}", value, "U", "mixed"))
    return made


SENTENCES = _sentences()


def _left_for_a_reason(said: str, value: Decimal, kind: str) -> bool:
    """Whether a number left as it was is left for one of the two reasons allowed."""
    digits = format(value, "f")
    three_places = "." in digits and len(digits.split(".")[1]) == 3
    if three_places:
        reading = read_number(digits)
        if isinstance(reading, Recognised) and reading.cautions:
            return True
    return said.endswith("一")


def _applied(tidied: Tidied) -> str:
    text, position = "", 0
    for change in tidied.changes:
        assert change.start >= position
        text += tidied.said[position : change.start] + change.written
        position = change.end
    return text + tidied.said[position:]


def test_the_writer_of_this_test_writes_every_number_so_it_reads_back() -> None:
    unread = [
        words
        for value, words, _fraction in NUMBERS
        if not (isinstance(reading := read_number(words), Recognised) and reading.value == value)
    ]
    assert unread == []


def test_no_number_drawn_has_more_places_than_the_ledger_holds() -> None:
    assert all(-value.as_tuple().exponent <= MAX_DECIMAL_PLACES for value, _w, _f in NUMBERS)  # type: ignore[operator]


@pytest.mark.parametrize("chunk", range(10))
def test_tidying_never_changes_a_number(chunk: int) -> None:
    for prefix, said, value, suffix, kind in SENTENCES[chunk::10]:
        sentence = f"{prefix}{said}{suffix}"
        tidied = tidy_spoken(sentence, ZONE)
        assert _applied(tidied) == tidied.text
        assert tidy_spoken(tidied.text, ZONE).text == tidied.text
        if not tidied.changed:
            assert _left_for_a_reason(said, value, kind), sentence
            continue
        (change,) = tidied.changes
        written = read_number(change.written)
        assert isinstance(written, Recognised) and written.value == value, sentence
        assert not written.cautions
        if kind == "words":
            assert change.kind is ChangeKind.NUMBER
            before = read_number(change.said)
            assert isinstance(before, Recognised) and before.value == value, sentence
        else:
            assert change.kind is ChangeKind.MIXED_DECIMAL
            whole, fraction = said.split(".")
            assert change.written == whole + "." + "".join(
                str(WORDS.index(word)) for word in fraction
            )
        number = tidied.text[len(prefix) : len(tidied.text) - len(suffix)]
        reading = read_number(number)
        assert isinstance(reading, Recognised) and reading.value == value, sentence


def test_at_least_seven_in_ten_sentences_are_tidied() -> None:
    tidied = sum(
        tidy_spoken(f"{prefix}{said}{suffix}", ZONE).changed
        for prefix, said, _value, suffix, _kind in SENTENCES
    )
    assert tidied / len(SENTENCES) >= 0.7, (tidied, len(SENTENCES))
