"""How close a figure worked out must be to a number said: read like the price gap.

Not set or blank, it is the default of one ten-thousandth; a decimal above
0 and at most one hundredth is taken; anything else is refused, naming the
variable. It is not a model setting. The README's row names the variable
and the default held here.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ledger_hand.settings import (
    DEFAULT_SAID_NUMBER_GAP,
    ENV_PREFIX,
    SAID_NUMBER_GAP_VARIABLE,
    SettingsError,
    Variable,
    load_said_number_gap,
)

README = Path(__file__).resolve().parents[1] / "README.md"


def test_not_set_or_blank_is_one_ten_thousandth() -> None:
    assert Decimal("0.0001") == DEFAULT_SAID_NUMBER_GAP
    assert load_said_number_gap({}) == DEFAULT_SAID_NUMBER_GAP
    assert load_said_number_gap({SAID_NUMBER_GAP_VARIABLE: " "}) == DEFAULT_SAID_NUMBER_GAP


@pytest.mark.parametrize("value", ["0.0001", "0.00005", " 0.01 "])
def test_a_decimal_above_zero_and_at_most_a_hundredth_is_taken(value: str) -> None:
    assert load_said_number_gap({SAID_NUMBER_GAP_VARIABLE: value}) == Decimal(value.strip())


@pytest.mark.parametrize("value", ["0", "0.0", "0.02", "1", "1e-4", "-0.0001", "abc", "０.0001"])
def test_anything_else_is_refused_naming_the_variable(value: str) -> None:
    with pytest.raises(SettingsError) as caught:
        load_said_number_gap({SAID_NUMBER_GAP_VARIABLE: value})

    assert SAID_NUMBER_GAP_VARIABLE in str(caught.value)


def test_it_is_not_a_model_setting() -> None:
    assert not SAID_NUMBER_GAP_VARIABLE.startswith(ENV_PREFIX)
    assert SAID_NUMBER_GAP_VARIABLE not in {variable.value for variable in Variable}


def test_the_readme_row_names_the_variable_and_the_default_held_here() -> None:
    start = f"| `{SAID_NUMBER_GAP_VARIABLE}` |"
    (line,) = [
        line for line in README.read_text(encoding="utf-8").splitlines() if line.startswith(start)
    ]
    name, default, _sets, _why = (cell.strip() for cell in line.strip().strip("|").split(" | "))

    assert name == f"`{SAID_NUMBER_GAP_VARIABLE}`"
    assert Decimal(default.strip("`")) == DEFAULT_SAID_NUMBER_GAP
