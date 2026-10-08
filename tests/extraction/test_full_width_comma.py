"""Tests of a comma written full width between two numbers.

In Chinese writing "，" ends one clause and begins the next, so "63,000，1.5"
is two numbers: a price, then the next trade's quantity. Some also use it to
group thousands: "94，900" is one number. The number reader of the core
decides: the two sides are one number only when it is sure of them together.
A full-width comma used as a decimal mark ("1，5") is therefore read as two
numbers, as the module description of ``passage_numbers`` says. A comma
written half width is not affected. Every passage and reply below is
invented.
"""

from __future__ import annotations

import itertools
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from decimal import Decimal

import pytest

from ledger_hand.core.numbers import Recognised, read_number
from ledger_hand.extraction import passage as passage_module
from ledger_hand.extraction.extractor import Extracted
from ledger_hand.extraction.issues import Issue, IssueKind
from ledger_hand.extraction.passage import Passage, Piece, PieceMiss
from ledger_hand.extraction.passage_numbers import number_runs, number_spans
from ledger_hand.extraction.reply_table import Field
from tests.extraction.scripted_runs import row, run, table

TWO_TRADES = "0.1 BTC @ 63,000，1.5 ETH @ 2,410"
TWO_ROWS = (
    row(side="sell", coin="BTC", quantity="0.1 BTC", price="63,000"),
    row(side="sell", coin="ETH", quantity="1.5 ETH", price="2,410"),
)
PRICE_THEN_COUNT = "价格 3000，2 个"
PRICE_THEN_COUNT_ROW = row(side="buy", coin="ETH", quantity="2 个", price="3000")
HALF_WIDTH = "价格 3000,2 个"


def extracted(passage: str, *rows: dict[str, str]) -> Extracted:
    result, _ = run(passage, table(*rows))
    assert isinstance(result, Extracted), result
    return result


def kinds(result: Extracted) -> list[IssueKind]:
    return [issue.kind for issue in result.issues]


def numbers(text: str, commas: set[int]) -> list[str]:
    return [text[start:end] for start, end in number_spans(text, commas)]


@contextmanager
def without_full_width_places() -> Iterator[None]:
    """The passage lookup as it was before: told nothing about full-width commas."""
    with pytest.MonkeyPatch.context() as patch:
        for name, function in (("number_spans", number_spans), ("number_runs", number_runs)):
            patch.setattr(passage_module, name, _ignoring_commas(function))
        yield


def _ignoring_commas(
    function: Callable[[str], list[tuple[int, int]]],
) -> Callable[..., list[tuple[int, int]]]:
    return lambda text, _commas=(): function(text)


# --- where a number ends ----------------------------------------------------


@pytest.mark.parametrize(
    ("text", "commas", "expected"),
    [
        ("94,900", {2}, ["94,900"]),
        ("63,000,1.5", {6}, ["63,000", "1.5"]),
        ("3000,2", {4}, ["3000", "2"]),
        ("1,5", {1}, ["1", "5"]),
        ("1,234,567", {1, 5}, ["1,234,567"]),
        ("12,345,6", {2, 6}, ["12,345", "6"]),
        ("1,5,000", {1, 3}, ["1", "5,000"]),
        ("63,000,1.5", set(), ["63,000,1.5"]),
        ("3000,2", set(), ["3000,2"]),
    ],
)
def test_a_full_width_comma_ends_a_number_unless_the_reader_is_sure_of_both_sides(
    text: str, commas: set[int], expected: list[str]
) -> None:
    assert numbers(text, commas) == expected


def test_the_passage_finds_where_the_full_width_commas_stood() -> None:
    assert Passage(TWO_TRADES).numbers == (
        ("0.1", "0.1"),
        ("63,000", "63,000"),
        ("1.5", "1.5"),
        ("2,410", "2,410"),
    )
    assert Passage("价格 94，900").numbers == (("94，900", "94,900"),)
    assert Passage(HALF_WIDTH).numbers == (("3000,2", "3000,2"),)


# --- extraction with the model copying the right phrases --------------------


def test_a_price_and_the_next_quantity_are_no_longer_taken_for_one_number() -> None:
    result = extracted(TWO_TRADES, *TWO_ROWS)

    assert IssueKind.CUTS_A_NUMBER not in kinds(result)
    assert IssueKind.NUMBERS_LEFT_OVER not in kinds(result)
    assert [(draft.quantity, draft.price) for draft in result.drafts] == [
        (Decimal("0.1"), Decimal("63000")),
        (Decimal("1.5"), Decimal("2410")),
    ]


def test_before_the_rule_the_same_reply_cut_numbers() -> None:
    with without_full_width_places():
        result = extracted(TWO_TRADES, *TWO_ROWS)

    assert (
        Issue(kind=IssueKind.CUTS_A_NUMBER, draft=0, field=Field.PRICE, phrase="63,000")
        in result.issues
    )
    assert Issue(kind=IssueKind.NUMBERS_LEFT_OVER, numbers=("63,000，1.5",)) in result.issues


def test_a_price_and_then_a_count_are_two_numbers() -> None:
    result = extracted(PRICE_THEN_COUNT, PRICE_THEN_COUNT_ROW)

    assert IssueKind.CUTS_A_NUMBER not in kinds(result)
    assert IssueKind.NUMBERS_LEFT_OVER not in kinds(result)
    assert (result.drafts[0].price, result.drafts[0].quantity) == (Decimal("3000"), Decimal("2"))


@pytest.mark.parametrize("copied", ["94，900", "94,900"])
def test_a_full_width_comma_grouping_thousands_still_makes_one_number(copied: str) -> None:
    result = extracted("价格 94，900", row(side="buy", coin="BTC", price=copied))

    assert result.drafts[0].price == Decimal("94900")
    assert IssueKind.NUMBERS_LEFT_OVER not in kinds(result)
    assert Passage("价格 94，900").find_number("900") is PieceMiss.CUTS_A_NUMBER


def test_a_half_width_comma_gives_what_it_gave_before() -> None:
    now = extracted(HALF_WIDTH, PRICE_THEN_COUNT_ROW)
    with without_full_width_places():
        before = extracted(HALF_WIDTH, PRICE_THEN_COUNT_ROW)

    assert now == before
    assert IssueKind.CUTS_A_NUMBER in kinds(now)


def test_a_full_width_comma_as_a_decimal_mark_gives_two_numbers() -> None:
    passage = Passage("价格 1，5")

    assert passage.numbers == (("1", "1"), ("5", "5"))
    assert isinstance(passage.find_number("1"), Piece)
    assert isinstance(passage.find_number("5"), Piece)

    whole = extracted("价格 1，5", row(side="buy", coin="BTC", price="1，5"))
    assert whole.drafts[0].price is None
    assert IssueKind.NUMBER_UNSURE in kinds(whole)

    first = extracted("价格 1，5", row(side="buy", coin="BTC", price="1"))
    assert first.drafts[0].price == Decimal("1")
    assert Issue(kind=IssueKind.NUMBERS_LEFT_OVER, numbers=("5",)) in first.issues


# --- every short text -------------------------------------------------------

ALPHABET = ("1", "0", "5", ".", ",", "，")
LONGEST = 6


def every_text() -> Iterator[str]:
    for length in range(1, LONGEST + 1):
        for characters in itertools.product(ALPHABET, repeat=length):
            yield "".join(characters)


def test_a_number_spans_a_full_width_comma_only_when_the_reader_is_sure_of_it() -> None:
    wrong: list[tuple[str, str]] = []
    for text in every_text():
        for written, _ in Passage(text).numbers:
            if "，" in written and not isinstance(read_number(written), Recognised):
                wrong.append((text, written))

    assert wrong == []


def test_the_full_width_rule_only_ever_cuts_a_run_and_never_joins_one() -> None:
    wrong: list[str] = []
    for text in every_text():
        tidy = text.replace("，", ",")
        commas = {place for place, character in enumerate(text) if character == "，"}
        old_runs = number_runs(tidy)
        for start, end in number_runs(tidy, commas):
            if not any(old_start <= start and end <= old_end for old_start, old_end in old_runs):
                wrong.append(text)

    assert wrong == []
