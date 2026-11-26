"""How far apart a rate and the last such rate are far: read like the price gap.

Not set or blank, it is the default of ten in a hundred; a decimal above 0
and at most 1000 is taken; anything else is refused, naming the variable.
It is not one of the model settings. The README's row for it names the
variable and the default this module holds.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ledger_hand.settings import (
    DEFAULT_RATE_GAP_PERCENT,
    ENV_PREFIX,
    RATE_GAP_PERCENT_VARIABLE,
    SettingsError,
    Variable,
    load_model_settings,
    load_rate_gap_percent,
)

README = Path(__file__).resolve().parents[1] / "README.md"


def test_not_set_or_blank_is_the_default_of_ten() -> None:
    assert Decimal(10) == DEFAULT_RATE_GAP_PERCENT
    assert load_rate_gap_percent({}) == DEFAULT_RATE_GAP_PERCENT
    assert load_rate_gap_percent({RATE_GAP_PERCENT_VARIABLE: ""}) == DEFAULT_RATE_GAP_PERCENT
    assert load_rate_gap_percent({RATE_GAP_PERCENT_VARIABLE: "  "}) == DEFAULT_RATE_GAP_PERCENT


@pytest.mark.parametrize(
    ("value", "percent"), [("10", "10"), ("2.5", "2.5"), ("0.1", "0.1"), (" 1000 ", "1000")]
)
def test_a_decimal_above_zero_and_at_most_a_thousand_is_taken(value: str, percent: str) -> None:
    assert load_rate_gap_percent({RATE_GAP_PERCENT_VARIABLE: value}) == Decimal(percent)


@pytest.mark.parametrize("value", ["0", "0.0", "1001", "ten", "１０", "1 0", "-5", "1e1", "NaN"])
def test_anything_else_is_refused_naming_the_variable(value: str) -> None:
    with pytest.raises(SettingsError) as caught:
        load_rate_gap_percent({RATE_GAP_PERCENT_VARIABLE: value})

    assert RATE_GAP_PERCENT_VARIABLE in str(caught.value)


def test_it_is_not_a_model_setting() -> None:
    assert not RATE_GAP_PERCENT_VARIABLE.startswith(ENV_PREFIX)
    assert RATE_GAP_PERCENT_VARIABLE not in {variable.value for variable in Variable}
    assert load_model_settings({RATE_GAP_PERCENT_VARIABLE: "3"}) == load_model_settings({})


def test_the_readme_row_names_the_variable_and_the_default_held_here() -> None:
    start = f"| `{RATE_GAP_PERCENT_VARIABLE}` |"
    (line,) = [
        line for line in README.read_text(encoding="utf-8").splitlines() if line.startswith(start)
    ]
    name, default, _sets, _why = (cell.strip() for cell in line.strip().strip("|").split(" | "))

    assert name == f"`{RATE_GAP_PERCENT_VARIABLE}`"
    assert Decimal(default.strip("`")) == DEFAULT_RATE_GAP_PERCENT
