"""How many times apart a price and the market price are far: read like the step limit.

Not set or blank, it is the default of five; a decimal above 1 and at most
1000 is taken; anything else is refused, naming the variable. It is not one
of the model settings. The README's row for it names the variable and the
default this module holds.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ledger_hand.settings import (
    DEFAULT_PRICE_GAP_TIMES,
    ENV_PREFIX,
    PRICE_GAP_TIMES_VARIABLE,
    SettingsError,
    Variable,
    load_model_settings,
    load_price_gap_times,
)

README = Path(__file__).resolve().parents[1] / "README.md"


def test_not_set_or_blank_is_the_default_of_five() -> None:
    assert DEFAULT_PRICE_GAP_TIMES == Decimal(5)
    assert load_price_gap_times({}) == DEFAULT_PRICE_GAP_TIMES
    assert load_price_gap_times({PRICE_GAP_TIMES_VARIABLE: ""}) == DEFAULT_PRICE_GAP_TIMES
    assert load_price_gap_times({PRICE_GAP_TIMES_VARIABLE: "  "}) == DEFAULT_PRICE_GAP_TIMES


@pytest.mark.parametrize(("value", "times"), [("3", "3"), ("2.5", "2.5"), (" 1000 ", "1000")])
def test_a_decimal_above_one_and_at_most_a_thousand_is_taken(value: str, times: str) -> None:
    assert load_price_gap_times({PRICE_GAP_TIMES_VARIABLE: value}) == Decimal(times)


@pytest.mark.parametrize(
    "value", ["1", "0.5", "1001", "five", "５", "5 0", "-5", "5e1", "1.0", "NaN", "Infinity"]
)
def test_anything_else_is_refused_naming_the_variable(value: str) -> None:
    with pytest.raises(SettingsError) as caught:
        load_price_gap_times({PRICE_GAP_TIMES_VARIABLE: value})

    assert PRICE_GAP_TIMES_VARIABLE in str(caught.value)


def test_it_is_not_a_model_setting() -> None:
    assert not PRICE_GAP_TIMES_VARIABLE.startswith(ENV_PREFIX)
    assert PRICE_GAP_TIMES_VARIABLE not in {variable.value for variable in Variable}
    assert load_model_settings({PRICE_GAP_TIMES_VARIABLE: "3"}) == load_model_settings({})


def test_the_readme_row_names_the_variable_and_the_default_held_here() -> None:
    start = f"| `{PRICE_GAP_TIMES_VARIABLE}` |"
    (line,) = [
        line for line in README.read_text(encoding="utf-8").splitlines() if line.startswith(start)
    ]
    name, default, _sets, _why = (cell.strip() for cell in line.strip().strip("|").split(" | "))

    assert name == f"`{PRICE_GAP_TIMES_VARIABLE}`"
    assert Decimal(default.strip("`")) == DEFAULT_PRICE_GAP_TIMES
