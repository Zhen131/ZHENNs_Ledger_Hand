"""How many times the assistant may ask the model in one turn, read like the data folder.

Not set or blank, it is the default; a whole number within the bounds is
taken; anything else is refused, naming the variable. It is not one of the
model settings, so the settings page and its tables do not change.
"""

from __future__ import annotations

import pytest

from ledger_hand.settings import (
    ASSISTANT_STEPS_VARIABLE,
    DEFAULT_ASSISTANT_STEPS,
    ENV_PREFIX,
    FEWEST_ASSISTANT_STEPS,
    MOST_ASSISTANT_STEPS,
    SettingsError,
    Variable,
    load_assistant_steps,
    load_model_settings,
)


def test_not_set_or_blank_is_the_default_of_six() -> None:
    assert DEFAULT_ASSISTANT_STEPS == 6
    assert load_assistant_steps({}) == DEFAULT_ASSISTANT_STEPS
    assert load_assistant_steps({ASSISTANT_STEPS_VARIABLE: "  "}) == DEFAULT_ASSISTANT_STEPS


@pytest.mark.parametrize("steps", [FEWEST_ASSISTANT_STEPS, 9, MOST_ASSISTANT_STEPS])
def test_a_whole_number_within_the_bounds_is_taken(steps: int) -> None:
    assert load_assistant_steps({ASSISTANT_STEPS_VARIABLE: f" {steps} "}) == steps


@pytest.mark.parametrize(
    "value",
    [str(FEWEST_ASSISTANT_STEPS - 1), str(MOST_ASSISTANT_STEPS + 1), "six", "6.0", "-6", "１０"],
)
def test_anything_else_is_refused_naming_the_variable(value: str) -> None:
    with pytest.raises(SettingsError) as caught:
        load_assistant_steps({ASSISTANT_STEPS_VARIABLE: value})

    assert ASSISTANT_STEPS_VARIABLE in str(caught.value)


def test_it_is_not_a_model_setting() -> None:
    assert not ASSISTANT_STEPS_VARIABLE.startswith(ENV_PREFIX)
    assert ASSISTANT_STEPS_VARIABLE not in {variable.value for variable in Variable}
    assert load_model_settings({ASSISTANT_STEPS_VARIABLE: "9"}) == load_model_settings({})
