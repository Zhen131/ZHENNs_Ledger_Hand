"""The README's table of model settings shows what the settings module holds, as written there.

What each variable sets and why its default is what it is are kept once, in
``settings.ABOUT``. The README repeats them in its table, one row per
variable; this test keeps the two from drifting apart, and checks that the
default the table names is the one the settings module uses.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ledger_hand.settings import ABOUT, ModelSettings, Variable, load_model_settings

README = Path(__file__).resolve().parents[1] / "README.md"


def row(variable: Variable) -> list[str]:
    """The cells of the README's row for ``variable``, without the outer bars."""
    start = f"| `{variable.value}` |"
    (line,) = [
        line for line in README.read_text(encoding="utf-8").splitlines() if line.startswith(start)
    ]
    return [cell.strip() for cell in line.strip().strip("|").split(" | ")]


@pytest.mark.parametrize("variable", list(Variable))
def test_the_readme_row_says_what_the_variable_sets_and_why_as_the_data_does(
    variable: Variable,
) -> None:
    name, _default, sets, reason = row(variable)

    assert name == f"`{variable.value}`"
    assert sets == ABOUT[variable].sets
    assert reason == ABOUT[variable].reason


@pytest.mark.parametrize("variable", [v for v in Variable if v is not Variable.KEY])
def test_the_readme_names_the_default_the_settings_use(variable: Variable) -> None:
    default = row(variable)[1].strip("`")
    field = ABOUT[variable].field

    assert getattr(load_model_settings({variable.value: default}), field) == getattr(
        ModelSettings(), field
    )


def test_the_readme_says_there_is_no_key_by_default() -> None:
    assert row(Variable.KEY)[1] == "(none)"
    assert ModelSettings().api_key is None
