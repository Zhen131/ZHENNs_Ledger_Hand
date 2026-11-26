"""Tests of a figure worked out put back to the number said, when it only rounds to it.

Each case is invented: a total worked out as 150.00078 where 150 was said,
a quantity worked out as 0.23145469 where 0.2314547 was said, a price
worked out a hair off the one said; and the cases where nothing changes.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ledger_hand.core.said_numbers import said_instead
from ledger_hand.core.trade import Amount

GAP = Decimal("0.0001")
D = Decimal


def test_a_total_worked_out_a_hair_off_the_total_said_is_put_back() -> None:
    found = said_instead(
        derived=Amount.TOTAL,
        quantity=D("0.94"),
        price=D("159.575"),
        total=D("150.0005"),
        left_over=[("150", D("150"))],
        gap=GAP,
    )

    assert found is not None and found.said == D("150") and found.amount is Amount.TOTAL
    assert found.reason == "worked out as 150.0005, but you said 150; your figure is kept"


def test_a_quantity_worked_out_to_more_places_is_put_back_to_the_one_said() -> None:
    found = said_instead(
        derived=Amount.QUANTITY,
        quantity=D("0.41296148"),
        price=D("242.155"),
        total=D("100"),
        left_over=[("0.4129615", D("0.4129615"))],
        gap=GAP,
    )

    assert found is not None and found.said == D("0.4129615")


def test_a_price_worked_out_a_hair_off_is_put_back() -> None:
    found = said_instead(
        derived=Amount.PRICE,
        quantity=D("3"),
        price=D("66.66666667"),
        total=D("200"),
        left_over=[("66.67", D("66.67"))],
        gap=GAP,
    )

    assert found is not None and found.said == D("66.67")


@pytest.mark.parametrize(
    ("worked", "left_over"),
    [
        # Further apart than one ten-thousandth, though it rounds to it.
        (D("0.2314"), [("0.23", D("0.23"))]),
        # Two numbers it rounds to: none is picked.
        (D("150.00004"), [("150", D("150")), ("150.0", D("150.0"))]),
        # No number left over: every number said was used by a cell.
        (D("150.00004"), []),
        # A number that does not round to it.
        (D("150.4"), [("151", D("151"))]),
    ],
)
def test_nothing_changes_without_exactly_one_number_close_enough(
    worked: Decimal, left_over: list[tuple[str, Decimal]]
) -> None:
    found = said_instead(
        derived=Amount.TOTAL,
        quantity=D("1"),
        price=worked,
        total=worked,
        left_over=left_over,
        gap=GAP,
    )

    assert found is None


def test_nothing_changes_when_the_three_figures_would_no_longer_agree() -> None:
    # 1 × 1000000.4 is 1000000.4; 1000000 said rounds from it and is near enough as a
    # part, but put back the total would be 0.4 off quantity × price, past the ledger's 0.01.
    found = said_instead(
        derived=Amount.TOTAL,
        quantity=D("1"),
        price=D("1000000.4"),
        total=D("1000000.4"),
        left_over=[("1000000", D("1000000"))],
        gap=GAP,
    )

    assert found is None


def test_a_gap_of_zero_or_below_is_a_mistake() -> None:
    with pytest.raises(ValueError, match="above 0"):
        said_instead(
            derived=Amount.TOTAL,
            quantity=D("1"),
            price=D("1"),
            total=D("1"),
            left_over=[],
            gap=D("0"),
        )
