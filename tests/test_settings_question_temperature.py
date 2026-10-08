"""Tests of the temperature for wording a follow-up question.

It is the one setting above 0 by default: wording a question may vary,
while judging a passage, extraction and reading an answer stay at the
temperature of every other call.
"""

from __future__ import annotations

import pytest

from ledger_hand.settings import (
    DEFAULT_QUESTION_TEMPERATURE,
    DEFAULT_TEMPERATURE,
    ModelSettings,
    SettingsError,
    Variable,
    load_model_settings,
)


def test_the_question_temperature_is_its_own_default_and_above_the_other() -> None:
    loaded = load_model_settings({})

    assert loaded.question_temperature == DEFAULT_QUESTION_TEMPERATURE
    assert DEFAULT_QUESTION_TEMPERATURE > DEFAULT_TEMPERATURE == 0


def test_the_question_temperature_is_read_from_its_variable_alone() -> None:
    loaded = load_model_settings({Variable.QUESTION_TEMPERATURE.value: "1.2"})

    assert loaded.question_temperature == 1.2
    assert loaded.temperature == DEFAULT_TEMPERATURE
    assert Variable.QUESTION_TEMPERATURE.value == "LEDGER_HAND_MODEL_QUESTION_TEMPERATURE"


@pytest.mark.parametrize("text", ["-0.1", "warm", "1e1", "nan"])
def test_a_malformed_question_temperature_is_refused_by_name(text: str) -> None:
    with pytest.raises(SettingsError, match="QUESTION_TEMPERATURE"):
        load_model_settings({Variable.QUESTION_TEMPERATURE.value: text})


@pytest.mark.parametrize("value", [-1.0, float("inf"), True])
def test_a_question_temperature_out_of_range_is_refused(value: float) -> None:
    with pytest.raises(SettingsError, match="QUESTION_TEMPERATURE"):
        ModelSettings(question_temperature=value)
