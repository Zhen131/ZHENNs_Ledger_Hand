"""Tests of judging a number phrase by the number reader: is it part of a longer number?

Every passage below is invented.
"""

from __future__ import annotations

import random
import time

import pytest

from ledger_hand.extraction import longer_numbers
from ledger_hand.extraction.longer_numbers import WIDEST, LongerNumbers
from ledger_hand.extraction.passage import Passage, Piece, PieceMiss


def judged(passage: str, phrase: str, allowed: tuple[str, ...] = ()) -> Piece | PieceMiss:
    return Passage(passage).find_number(phrase, allowed)


GAPS = [" ", "\t", "\N{IDEOGRAPHIC SPACE}", "\N{NO-BREAK SPACE}", "  \n "]


@pytest.mark.parametrize("gap", GAPS)
@pytest.mark.parametrize(
    ("before", "phrase", "after"),
    [
        ("BTC 9万", "4900", "一个，买了 0.1 个"),
        ("ETH 两千", "5", "一个，买了 2 个"),
        ("买了 2 个 BTC，1万", "5000", "一个"),
        ("BTC 9万", "4900", "，买了 0.1 个"),
        ("1千零", "5", " 个"),
        ("十", "5", "一个"),
    ],
)
def test_the_part_after_a_gap_in_a_number_is_cut(
    gap: str, before: str, phrase: str, after: str
) -> None:
    passage = before + gap + phrase + after

    assert judged(passage, phrase) is PieceMiss.CUTS_A_NUMBER
    # The rule of runs alone lets it through; the reader is what catches it.
    assert isinstance(Passage(passage).find(phrase), Piece)


@pytest.mark.parametrize(
    ("passage", "phrase"),
    [
        ("1.2k", "1.2"),
        ("100 万", "100"),
        ("8.5万", "8.5"),
        ("2 千 个", "2"),
        ("5 十", "5"),
        ("1千零5", "5"),
        ("94900", "9490"),
        ("3万5", "3万"),
    ],
)
def test_a_number_the_reader_reads_as_a_longer_one_of_another_value_is_cut(
    passage: str, phrase: str
) -> None:
    assert judged(passage, phrase) is PieceMiss.CUTS_A_NUMBER


@pytest.mark.parametrize(
    ("passage", "phrase"),
    [
        ("3000 个", "3000"),
        ("3000u", "3000"),
        ("0.02 个 BTC", "0.02"),
        ("2 USDT", "2"),
        ("$ 3000", "3000"),
        ("3000一个", "3000"),
        ("13.2一个", "13.2"),
        ("150一枚", "150"),
        ("94900一个BTC", "94900"),
        ("0.42 一个", "0.42"),
        ("3000 一个", "3000"),
        ("BTC 9万 4900一个", "9万 4900"),
        ("BTC 9万 4900", "9万 4900"),
        ("BTC 0.02 94900", "0.02"),
        ("BTC 0.02 94900", "94900"),
        ("价格 94,900，数量 0.02", "94,900"),
        ("10 月 2 号买了 3 个", "3 个"),
    ],
)
def test_a_wider_stretch_of_the_same_value_or_no_number_at_all_is_no_cut(
    passage: str, phrase: str
) -> None:
    found = judged(passage, phrase)

    assert isinstance(found, Piece), found
    assert found.text == phrase


def test_two_numbers_with_only_a_gap_between_are_two_numbers_to_the_reader() -> None:
    # The reader reads "0.02 94900" as unsure (two numbers side by side), not
    # as one number, so neither part is taken as cut.
    assert isinstance(judged("BTC 0.02 94900", "0.02"), Piece)
    assert isinstance(judged("BTC 0.02 94900", "94900"), Piece)


def test_a_gap_the_reader_does_not_read_across_is_not_judged() -> None:
    # The reader takes "3 w" and "1.2 k" for a number with a unit it does not
    # know, not for 30000 or 1200, so they are no longer number of another value.
    assert isinstance(judged("3 w", "3"), Piece)
    assert isinstance(judged("1.2 k", "1.2"), Piece)


def test_a_phrase_the_reader_cannot_read_is_left_to_the_conversion() -> None:
    assert isinstance(judged("大概 9 点多", "9 点多"), Piece)


def test_the_unit_words_allowed_are_the_readers_too() -> None:
    passage = "买了 500 BONK"

    assert isinstance(judged(passage, "500", ("BONK",)), Piece)
    assert isinstance(judged(passage, "500"), Piece)


def test_the_same_phrase_with_other_unit_words_is_judged_again() -> None:
    passage = Passage("9万 4900")

    assert passage.find_number("4900", ()) is passage.find_number("4900", ())
    assert passage.find_number("4900", ("BTC",)) is PieceMiss.CUTS_A_NUMBER
    assert isinstance(passage.find("4900"), Piece)


def test_a_later_place_that_passes_is_taken() -> None:
    found = judged("9万 4900，又一笔 4900", "4900")

    assert isinstance(found, Piece)
    assert found.start == len("9万 4900，又一笔 ")


def test_a_piece_says_where_it_stands_in_the_passage() -> None:
    found = judged("买了 ０.５  ＥＴＨ", "0.5 ETH")

    assert isinstance(found, Piece)
    assert (found.start, found.end) == (3, 3 + len("０.５  ＥＴＨ"))


def test_widening_stops_at_the_widest_and_at_characters_of_no_number() -> None:
    tidy = "1" * 100 + " 5 个 BTC"
    judge = LongerNumbers(tidy)
    phrase_start = tidy.index("5")

    starts = judge._starts(phrase_start)
    ends = judge._ends(phrase_start + 1)

    assert min(starts) == phrase_start - WIDEST
    assert ends == [phrase_start + 1]


def test_once_the_readings_are_used_up_every_question_is_answered_cut(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(longer_numbers, "MAX_READINGS", 2)

    passage = Passage("1 2 3 4 5")

    assert passage.find_number("3") is PieceMiss.CUTS_A_NUMBER


def test_a_long_passage_of_nothing_but_numbers_and_gaps_is_judged_quickly() -> None:
    draw = random.Random(67)
    text = " ".join(f"{draw.randint(0, 9999)}.{draw.randint(0, 99)}" for _ in range(3000))[:16_000]
    phrases = sorted(set(text.split()))[:1000]
    passage = Passage(text)
    started = time.monotonic()

    found = [passage.find_number(phrase, ("BTC",)) for phrase in phrases]

    assert time.monotonic() - started < 5.0
    assert all(isinstance(result, Piece | PieceMiss) for result in found)


def test_one_number_in_parts_repeated_through_a_long_passage_is_judged_quickly() -> None:
    passage = Passage(("9万 4900 买了；" * 2000)[:16_000])
    started = time.monotonic()

    assert passage.find_number("4900") is PieceMiss.CUTS_A_NUMBER
    assert isinstance(passage.find_number("9万 4900"), Piece)
    assert time.monotonic() - started < 5.0
