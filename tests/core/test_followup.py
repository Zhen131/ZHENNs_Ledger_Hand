"""Tests of what to ask next about a draft.

Every problem the check of a draft can name has exactly one place in the
fixed order, and leads somewhere: a cell to ask, a coin to confirm, several
cells to choose from, or a trade that cannot be recorded. The order the
problems were found in makes no difference. Every trade below is invented.
"""

from __future__ import annotations

import dataclasses
import itertools
from collections import Counter
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from ledger_hand.core.coins import BUILT_IN_TABLE
from ledger_hand.core.followup import (
    AMOUNT_CELLS,
    FOLLOW_UP_ORDER,
    AskCell,
    AskWhichCell,
    CannotRecord,
    Cell,
    ConfirmCoin,
    Destination,
    FollowUp,
    next_follow_up,
    value_of,
    with_value,
)
from ledger_hand.core.trade import OccurredTime, Side, TimePrecision, TradeDraft, TradeRecord
from ledger_hand.core.validation import DraftProblems, Missing, Violation, check_draft

BUDAPEST = "Europe/Budapest"
NOW = datetime(2026, 10, 7, 21, 0, tzinfo=ZoneInfo(BUDAPEST))
EVENING = OccurredTime(
    datetime(2026, 10, 7, 20, 15, tzinfo=ZoneInfo(BUDAPEST)), TimePrecision.MINUTE, BUDAPEST
)
EVERY_PROBLEM: list[Missing | Violation] = [*Missing, *Violation]


def complete(**changes: object) -> TradeDraft:
    draft = TradeDraft(
        side=Side.BUY,
        coin="BTC",
        quantity=Decimal("0.02"),
        price=Decimal("94900"),
        fee=Decimal("1.5"),
        fee_coin="USDT",
        occurred=EVENING,
        raw_text="买了 0.02 BTC，94900，手续费 1.5 USDT",
    )
    return dataclasses.replace(draft, **changes)  # type: ignore[arg-type]


def only(problem: Missing | Violation) -> DraftProblems:
    if isinstance(problem, Missing):
        return DraftProblems(missing=(problem,), violations=())
    return DraftProblems(missing=(), violations=(problem,))


def check(draft: TradeDraft) -> TradeRecord | DraftProblems:
    return check_draft(draft, BUILT_IN_TABLE, NOW)


# --- every problem has a place, and only one --------------------------------


def test_every_missing_and_every_violation_has_exactly_one_place_in_the_order() -> None:
    placed = Counter(problem for problem, _ in FOLLOW_UP_ORDER)

    assert set(placed) == set(EVERY_PROBLEM)
    assert all(count == 1 for count in placed.values())


def test_the_order_and_its_destinations_are_as_written() -> None:
    assert [(problem.name, destination.name) for problem, destination in FOLLOW_UP_ORDER] == [
        ("RAW_TEXT_EMPTY", "CANNOT_RECORD"),
        ("RAW_TEXT_TOO_LONG", "CANNOT_RECORD"),
        ("RAW_TEXT", "CANNOT_RECORD"),
        ("COIN_IS_USDT", "CANNOT_RECORD"),
        ("UNSUPPORTED_QUOTE", "CANNOT_RECORD"),
        ("SIDE", "ASK_SIDE"),
        ("COIN", "ASK_COIN"),
        ("COIN_NOT_A_SYMBOL", "ASK_COIN"),
        ("COIN_CONFIRMATION", "CONFIRM_COIN"),
        ("QUANTITY_NOT_POSITIVE", "ASK_QUANTITY"),
        ("QUANTITY_TOO_MANY_DIGITS", "ASK_QUANTITY"),
        ("PRICE_NOT_POSITIVE", "ASK_PRICE"),
        ("PRICE_TOO_MANY_DIGITS", "ASK_PRICE"),
        ("TOTAL_NOT_POSITIVE", "ASK_TOTAL"),
        ("TOTAL_TOO_MANY_DIGITS", "ASK_TOTAL"),
        ("TWO_OF_QUANTITY_PRICE_TOTAL", "ASK_A_BLANK_AMOUNT"),
        ("ONE_MORE_OF_QUANTITY_PRICE_TOTAL", "ASK_A_BLANK_AMOUNT"),
        ("AMOUNTS_DISAGREE", "ASK_WHICH_AMOUNT_IS_WRONG"),
        ("FEE", "ASK_FEE"),
        ("FEE_NEGATIVE", "ASK_FEE"),
        ("FEE_TOO_MANY_DIGITS", "ASK_FEE"),
        ("FEE_COIN", "ASK_FEE_COIN"),
        ("FEE_COIN_NOT_A_SYMBOL", "ASK_FEE_COIN"),
        ("FEE_COIN_CONFIRMATION", "CONFIRM_FEE_COIN"),
        ("FEE_NOT_BELOW_QUANTITY", "ASK_WHICH_OF_FEE_AND_QUANTITY_IS_WRONG"),
        ("OCCURRED", "ASK_TIME"),
        ("IN_THE_FUTURE", "ASK_TIME"),
        ("OFFSET_HAS_SECONDS", "ASK_TIME"),
        ("PLATFORM_TOO_LONG", "ASK_PLATFORM"),
        ("NOTE_TOO_LONG", "ASK_NOTE"),
    ]


EXPECTED: dict[Missing | Violation, FollowUp] = {
    Violation.RAW_TEXT_EMPTY: CannotRecord(Violation.RAW_TEXT_EMPTY),
    Violation.RAW_TEXT_TOO_LONG: CannotRecord(Violation.RAW_TEXT_TOO_LONG),
    Missing.RAW_TEXT: CannotRecord(Missing.RAW_TEXT),
    Violation.COIN_IS_USDT: CannotRecord(Violation.COIN_IS_USDT),
    Violation.UNSUPPORTED_QUOTE: CannotRecord(Violation.UNSUPPORTED_QUOTE),
    Missing.SIDE: AskCell(Cell.SIDE, Missing.SIDE),
    Missing.COIN: AskCell(Cell.COIN, Missing.COIN),
    Violation.COIN_NOT_A_SYMBOL: AskCell(Cell.COIN, Violation.COIN_NOT_A_SYMBOL),
    Missing.COIN_CONFIRMATION: ConfirmCoin(Cell.COIN, Missing.COIN_CONFIRMATION),
    Violation.QUANTITY_NOT_POSITIVE: AskCell(Cell.QUANTITY, Violation.QUANTITY_NOT_POSITIVE),
    Violation.QUANTITY_TOO_MANY_DIGITS: AskCell(Cell.QUANTITY, Violation.QUANTITY_TOO_MANY_DIGITS),
    Violation.PRICE_NOT_POSITIVE: AskCell(Cell.PRICE, Violation.PRICE_NOT_POSITIVE),
    Violation.PRICE_TOO_MANY_DIGITS: AskCell(Cell.PRICE, Violation.PRICE_TOO_MANY_DIGITS),
    Violation.TOTAL_NOT_POSITIVE: AskCell(Cell.TOTAL, Violation.TOTAL_NOT_POSITIVE),
    Violation.TOTAL_TOO_MANY_DIGITS: AskCell(Cell.TOTAL, Violation.TOTAL_TOO_MANY_DIGITS),
    # The complete draft has no blank amount; these are tested with blanks below.
    Missing.TWO_OF_QUANTITY_PRICE_TOTAL: AskCell(Cell.TOTAL, Missing.TWO_OF_QUANTITY_PRICE_TOTAL),
    Missing.ONE_MORE_OF_QUANTITY_PRICE_TOTAL: AskCell(
        Cell.TOTAL, Missing.ONE_MORE_OF_QUANTITY_PRICE_TOTAL
    ),
    Violation.AMOUNTS_DISAGREE: AskWhichCell(AMOUNT_CELLS, Violation.AMOUNTS_DISAGREE),
    Missing.FEE: AskCell(Cell.FEE, Missing.FEE),
    Violation.FEE_NEGATIVE: AskCell(Cell.FEE, Violation.FEE_NEGATIVE),
    Violation.FEE_TOO_MANY_DIGITS: AskCell(Cell.FEE, Violation.FEE_TOO_MANY_DIGITS),
    Missing.FEE_COIN: AskCell(Cell.FEE_COIN, Missing.FEE_COIN),
    Violation.FEE_COIN_NOT_A_SYMBOL: AskCell(Cell.FEE_COIN, Violation.FEE_COIN_NOT_A_SYMBOL),
    Missing.FEE_COIN_CONFIRMATION: ConfirmCoin(Cell.FEE_COIN, Missing.FEE_COIN_CONFIRMATION),
    Violation.FEE_NOT_BELOW_QUANTITY: AskWhichCell(
        (Cell.FEE, Cell.QUANTITY), Violation.FEE_NOT_BELOW_QUANTITY
    ),
    Missing.OCCURRED: AskCell(Cell.OCCURRED, Missing.OCCURRED),
    Violation.IN_THE_FUTURE: AskCell(Cell.OCCURRED, Violation.IN_THE_FUTURE),
    Violation.OFFSET_HAS_SECONDS: AskCell(Cell.OCCURRED, Violation.OFFSET_HAS_SECONDS),
    Violation.PLATFORM_TOO_LONG: AskCell(Cell.PLATFORM, Violation.PLATFORM_TOO_LONG),
    Violation.NOTE_TOO_LONG: AskCell(Cell.NOTE, Violation.NOTE_TOO_LONG),
}


def test_the_expectations_below_cover_every_problem() -> None:
    assert set(EXPECTED) == set(EVERY_PROBLEM)


@pytest.mark.parametrize("problem", EVERY_PROBLEM, ids=lambda problem: problem.name)
def test_each_problem_alone_leads_where_the_order_says(problem: Missing | Violation) -> None:
    draft = complete(total=None)

    assert next_follow_up(draft, only(problem)) == EXPECTED[problem]


@pytest.mark.parametrize(
    ("blanks", "asked"),
    [
        (("quantity", "price", "total"), Cell.QUANTITY),
        (("price", "total"), Cell.PRICE),
        (("quantity", "total"), Cell.QUANTITY),
        (("quantity", "price"), Cell.QUANTITY),
    ],
)
def test_a_blank_amount_is_asked_quantity_first_then_price_then_total(
    blanks: tuple[str, ...], asked: Cell
) -> None:
    draft = complete(**dict.fromkeys(blanks))
    problems = check(draft)
    assert isinstance(problems, DraftProblems)

    follow_up = next_follow_up(draft, problems)

    assert isinstance(follow_up, AskCell)
    assert follow_up.cell is asked


# --- the order the problems were found in makes no difference ---------------

SEVERAL: list[Missing | Violation] = [
    Missing.FEE,
    Violation.IN_THE_FUTURE,
    Missing.SIDE,
    Violation.NOTE_TOO_LONG,
    Missing.COIN_CONFIRMATION,
    Violation.AMOUNTS_DISAGREE,
]


def test_the_same_problems_in_any_order_give_the_same_question() -> None:
    draft = complete()
    answers = set()
    for order in itertools.permutations(SEVERAL):
        problems = DraftProblems(
            missing=tuple(item for item in order if isinstance(item, Missing)),
            violations=tuple(item for item in order if isinstance(item, Violation)),
        )
        answers.add(next_follow_up(draft, problems))

    assert answers == {AskCell(Cell.SIDE, Missing.SIDE)}


def test_one_question_at_a_time_walks_the_order() -> None:
    draft = complete()
    asked: list[FollowUp] = []
    left = list(SEVERAL)
    while left:
        problems = DraftProblems(
            missing=tuple(item for item in left if isinstance(item, Missing)),
            violations=tuple(item for item in left if isinstance(item, Violation)),
        )
        follow_up = next_follow_up(draft, problems)
        asked.append(follow_up)
        left.remove(follow_up.because)

    assert [follow_up.because for follow_up in asked] == [
        Missing.SIDE,
        Missing.COIN_CONFIRMATION,
        Violation.AMOUNTS_DISAGREE,
        Missing.FEE,
        Violation.IN_THE_FUTURE,
        Violation.NOTE_TOO_LONG,
    ]


def test_a_draft_without_problems_has_nothing_to_ask() -> None:
    with pytest.raises(ValueError, match="nothing to ask"):
        next_follow_up(complete(), DraftProblems(missing=(), violations=()))


def test_an_empty_draft_is_asked_its_side_first() -> None:
    draft = TradeDraft(raw_text="记一笔")
    problems = check(draft)
    assert isinstance(problems, DraftProblems)

    assert next_follow_up(draft, problems) == AskCell(Cell.SIDE, Missing.SIDE)


# --- the total put in as the price: one right answer settles it -------------

TOTAL_AS_PRICE = complete(
    quantity=Decimal("0.02"), price=Decimal("1898"), total=Decimal("1898"), fee=Decimal("0")
)


def test_a_total_copied_into_the_price_asks_which_amount_is_wrong() -> None:
    problems = check(TOTAL_AS_PRICE)
    assert problems == DraftProblems(missing=(), violations=(Violation.AMOUNTS_DISAGREE,))

    follow_up = next_follow_up(TOTAL_AS_PRICE, problems)

    assert follow_up == AskWhichCell(AMOUNT_CELLS, Violation.AMOUNTS_DISAGREE)
    assert [value_of(TOTAL_AS_PRICE, cell) for cell in follow_up.cells] == [
        Decimal("0.02"),
        Decimal("1898"),
        Decimal("1898"),
    ]


@pytest.mark.parametrize("right_price", [Decimal("94900"), None], ids=["the price", "not said"])
def test_one_right_answer_about_the_price_settles_it(right_price: Decimal | None) -> None:
    fixed = with_value(TOTAL_AS_PRICE, Cell.PRICE, right_price)

    record = check(fixed)

    assert isinstance(record, TradeRecord)
    assert (record.quantity, record.price, record.total) == (
        Decimal("0.02"),
        Decimal("94900"),
        Decimal("1898"),
    )


# --- reading and replacing a cell -------------------------------------------


@pytest.mark.parametrize("cell", list(Cell), ids=lambda cell: cell.name)
def test_a_cell_can_be_read_emptied_and_filled_again(cell: Cell) -> None:
    draft = complete(total=Decimal("1898"), platform="OKX", note="fine")
    value = value_of(draft, cell)
    assert value is not None

    emptied = with_value(draft, cell, None)

    assert value_of(emptied, cell) is None
    assert with_value(emptied, cell, value) == draft


def test_a_value_of_the_wrong_type_is_a_mistake_of_the_caller() -> None:
    with pytest.raises(TypeError, match="price"):
        with_value(complete(), Cell.PRICE, "94900")
    with pytest.raises(TypeError, match="side"):
        with_value(complete(), Cell.SIDE, "buy")


def test_every_destination_is_used() -> None:
    assert {destination for _, destination in FOLLOW_UP_ORDER} == set(Destination)
