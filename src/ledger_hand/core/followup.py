"""What to ask next about a draft that is not a record yet.

``next_follow_up`` takes a draft and the problems the check of a draft found
in it (``validation.DraftProblems``) and gives back one ``FollowUp``:

- ``AskCell``: ask for the value of one cell of the draft;
- ``ConfirmCoin``: ask whether the word for the coin (or for the fee's coin)
  is the symbol of a coin, since the coin table does not know it;
- ``AskWhichCell``: the problem lies between several cells (quantity times
  price does not match the total; a buy fee in the bought coin is not below
  the quantity). The question shows those cells and their values, and the
  answer names the one that is wrong with its right value, or says the
  passage did not give it, which empties that cell;
- ``CannotRecord``: the trade cannot be recorded at all, and why.

Which problem is taken up first is fixed by one table, ``FOLLOW_UP_ORDER``,
not by the order the check found them in. Every ``Missing`` and every
``Violation`` has exactly one place in it, with where it leads
(``Destination``); a test checks that, so a new kind of problem cannot be
added without saying where it goes. Problems that make a trade impossible to
record come first, since asking anything else about such a trade is
pointless; the rest follow the order a trade is told in: the side, the coin,
the amounts, the fee, the time, then the platform and the note.

Only one question comes back at a time, and only for one cell (or one set of
cells that one problem lies between). What happens to the answer is not
decided here.

``value_of`` gives the value a cell holds, for showing it in a question, and
``with_value`` gives the draft with one cell replaced.

Names defined here: ``Cell``, ``Destination``, ``FOLLOW_UP_ORDER``,
``AMOUNT_CELLS``, ``AskCell``, ``ConfirmCoin``, ``AskWhichCell``,
``CannotRecord``, ``FollowUp``, ``next_follow_up``, ``value_of`` and
``with_value``.
"""

from __future__ import annotations

import dataclasses
import enum
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from ledger_hand.core.trade import OccurredTime, Side, TradeDraft
from ledger_hand.core.validation import DraftProblems, Missing, Violation


class Cell(enum.Enum):
    """A cell of a draft the user can be asked about; the value names it in words."""

    SIDE = "side"
    COIN = "coin"
    QUANTITY = "quantity"
    PRICE = "price"
    TOTAL = "total"
    FEE = "fee"
    FEE_COIN = "fee coin"
    OCCURRED = "time"
    PLATFORM = "platform"
    NOTE = "note"


# The draft's field behind each cell.
_FIELD_OF = {
    Cell.SIDE: "side",
    Cell.COIN: "coin",
    Cell.QUANTITY: "quantity",
    Cell.PRICE: "price",
    Cell.TOTAL: "total",
    Cell.FEE: "fee",
    Cell.FEE_COIN: "fee_coin",
    Cell.OCCURRED: "occurred",
    Cell.PLATFORM: "platform",
    Cell.NOTE: "note",
}

# Quantity, price and total, in the order a blank one of them is asked for.
AMOUNT_CELLS = (Cell.QUANTITY, Cell.PRICE, Cell.TOTAL)


class Destination(enum.Enum):
    """Where a problem leads; the value says it in words."""

    CANNOT_RECORD = "the trade cannot be recorded; say why"
    ASK_SIDE = "ask whether it was a buy or a sell"
    ASK_COIN = "ask which coin was traded"
    CONFIRM_COIN = "ask whether the word for the coin is a coin's symbol"
    ASK_QUANTITY = "ask the quantity"
    ASK_PRICE = "ask the price"
    ASK_TOTAL = "ask the total"
    ASK_A_BLANK_AMOUNT = "ask the first blank of quantity, price and total, in that order"
    ASK_WHICH_AMOUNT_IS_WRONG = (
        "show quantity, price and total; ask which one is wrong and its right value"
    )
    ASK_FEE = "ask the fee"
    ASK_FEE_COIN = "ask which coin the fee was paid in"
    CONFIRM_FEE_COIN = "ask whether the word for the fee's coin is a coin's symbol"
    ASK_WHICH_OF_FEE_AND_QUANTITY_IS_WRONG = (
        "show the fee and the quantity; ask which one is wrong and its right value"
    )
    ASK_TIME = "ask when the trade happened"
    ASK_PLATFORM = "ask the platform again, or for nothing"
    ASK_NOTE = "ask the note again, or for nothing"


type Problem = Missing | Violation

FOLLOW_UP_ORDER: tuple[tuple[Problem, Destination], ...] = (
    # A trade that cannot be recorded at all.
    (Violation.RAW_TEXT_EMPTY, Destination.CANNOT_RECORD),
    (Violation.RAW_TEXT_TOO_LONG, Destination.CANNOT_RECORD),
    (Missing.RAW_TEXT, Destination.CANNOT_RECORD),
    (Violation.COIN_IS_USDT, Destination.CANNOT_RECORD),
    (Violation.UNSUPPORTED_QUOTE, Destination.CANNOT_RECORD),
    # The side and the coin.
    (Missing.SIDE, Destination.ASK_SIDE),
    (Missing.COIN, Destination.ASK_COIN),
    (Violation.COIN_NOT_A_SYMBOL, Destination.ASK_COIN),
    (Missing.COIN_CONFIRMATION, Destination.CONFIRM_COIN),
    # The amounts: a stated amount that is wrong in itself, then the blanks,
    # then whether the three agree.
    (Violation.QUANTITY_NOT_POSITIVE, Destination.ASK_QUANTITY),
    (Violation.QUANTITY_TOO_MANY_DIGITS, Destination.ASK_QUANTITY),
    (Violation.PRICE_NOT_POSITIVE, Destination.ASK_PRICE),
    (Violation.PRICE_TOO_MANY_DIGITS, Destination.ASK_PRICE),
    (Violation.TOTAL_NOT_POSITIVE, Destination.ASK_TOTAL),
    (Violation.TOTAL_TOO_MANY_DIGITS, Destination.ASK_TOTAL),
    (Missing.TWO_OF_QUANTITY_PRICE_TOTAL, Destination.ASK_A_BLANK_AMOUNT),
    (Missing.ONE_MORE_OF_QUANTITY_PRICE_TOTAL, Destination.ASK_A_BLANK_AMOUNT),
    (Violation.AMOUNTS_DISAGREE, Destination.ASK_WHICH_AMOUNT_IS_WRONG),
    # The fee.
    (Missing.FEE, Destination.ASK_FEE),
    (Violation.FEE_NEGATIVE, Destination.ASK_FEE),
    (Violation.FEE_TOO_MANY_DIGITS, Destination.ASK_FEE),
    (Missing.FEE_COIN, Destination.ASK_FEE_COIN),
    (Violation.FEE_COIN_NOT_A_SYMBOL, Destination.ASK_FEE_COIN),
    (Missing.FEE_COIN_CONFIRMATION, Destination.CONFIRM_FEE_COIN),
    (Violation.FEE_NOT_BELOW_QUANTITY, Destination.ASK_WHICH_OF_FEE_AND_QUANTITY_IS_WRONG),
    # The time. A time whose offset has seconds in it is said again.
    (Missing.OCCURRED, Destination.ASK_TIME),
    (Violation.IN_THE_FUTURE, Destination.ASK_TIME),
    (Violation.OFFSET_HAS_SECONDS, Destination.ASK_TIME),
    # The free text the ledger limits.
    (Violation.PLATFORM_TOO_LONG, Destination.ASK_PLATFORM),
    (Violation.NOTE_TOO_LONG, Destination.ASK_NOTE),
)

_ONE_CELL = {
    Destination.ASK_SIDE: Cell.SIDE,
    Destination.ASK_COIN: Cell.COIN,
    Destination.ASK_QUANTITY: Cell.QUANTITY,
    Destination.ASK_PRICE: Cell.PRICE,
    Destination.ASK_TOTAL: Cell.TOTAL,
    Destination.ASK_FEE: Cell.FEE,
    Destination.ASK_FEE_COIN: Cell.FEE_COIN,
    Destination.ASK_TIME: Cell.OCCURRED,
    Destination.ASK_PLATFORM: Cell.PLATFORM,
    Destination.ASK_NOTE: Cell.NOTE,
}
_CONFIRMED_CELL = {
    Destination.CONFIRM_COIN: Cell.COIN,
    Destination.CONFIRM_FEE_COIN: Cell.FEE_COIN,
}
_SEVERAL_CELLS = {
    Destination.ASK_WHICH_AMOUNT_IS_WRONG: AMOUNT_CELLS,
    Destination.ASK_WHICH_OF_FEE_AND_QUANTITY_IS_WRONG: (Cell.FEE, Cell.QUANTITY),
}


@dataclass(frozen=True)
class AskCell:
    """Ask for the value of one cell."""

    cell: Cell
    because: Problem


@dataclass(frozen=True)
class ConfirmCoin:
    """Ask whether the word in ``cell`` (the coin or the fee's coin) is a coin's symbol."""

    cell: Cell
    because: Missing


@dataclass(frozen=True)
class AskWhichCell:
    """Show ``cells`` and their values; ask which one is wrong and its right value."""

    cells: tuple[Cell, ...]
    because: Violation


@dataclass(frozen=True)
class CannotRecord:
    """The trade cannot be recorded; ``because`` says why."""

    because: Problem


FollowUp = AskCell | ConfirmCoin | AskWhichCell | CannotRecord


def next_follow_up(draft: TradeDraft, problems: DraftProblems) -> FollowUp:
    """The one thing to take up next about ``draft``, given what the check found.

    Raises ``ValueError`` when ``problems`` lists nothing: such a draft is a
    record, and there is nothing to ask.
    """
    found = set(problems.missing) | set(problems.violations)
    for problem, destination in FOLLOW_UP_ORDER:
        if problem in found:
            return _follow_up(destination, problem, draft)
    raise ValueError("there is nothing to ask about a draft without problems")


def _follow_up(destination: Destination, problem: Problem, draft: TradeDraft) -> FollowUp:
    if destination is Destination.CANNOT_RECORD:
        return CannotRecord(problem)
    if destination is Destination.ASK_A_BLANK_AMOUNT:
        blank = next(cell for cell in AMOUNT_CELLS if value_of(draft, cell) is None)
        return AskCell(blank, problem)
    if destination in _ONE_CELL:
        return AskCell(_ONE_CELL[destination], problem)
    if destination in _CONFIRMED_CELL and isinstance(problem, Missing):
        return ConfirmCoin(_CONFIRMED_CELL[destination], problem)
    if destination in _SEVERAL_CELLS and isinstance(problem, Violation):
        return AskWhichCell(_SEVERAL_CELLS[destination], problem)
    raise AssertionError(f"{destination} does not fit {problem}")


def value_of(draft: TradeDraft, cell: Cell) -> Side | str | Decimal | OccurredTime | None:
    """What ``cell`` of ``draft`` holds; ``None`` when it is blank."""
    value: Side | str | Decimal | OccurredTime | None = getattr(draft, _FIELD_OF[cell])
    return value


def with_value(
    draft: TradeDraft, cell: Cell, value: Side | str | Decimal | OccurredTime | None
) -> TradeDraft:
    """``draft`` with ``cell`` holding ``value``; ``None`` empties the cell.

    A value of the wrong type for the cell is a mistake of the caller.
    """
    expected = _TYPE_OF[cell]
    if value is not None and not isinstance(value, expected):
        raise TypeError(f"the {cell.value} holds {expected.__name__}, not {type(value).__name__}")
    changes: dict[str, Any] = {_FIELD_OF[cell]: value}
    return dataclasses.replace(draft, **changes)


_TYPE_OF: dict[Cell, type] = {
    Cell.SIDE: Side,
    Cell.COIN: str,
    Cell.QUANTITY: Decimal,
    Cell.PRICE: Decimal,
    Cell.TOTAL: Decimal,
    Cell.FEE: Decimal,
    Cell.FEE_COIN: str,
    Cell.OCCURRED: OccurredTime,
    Cell.PLATFORM: str,
    Cell.NOTE: str,
}
