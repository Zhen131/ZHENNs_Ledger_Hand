"""Tests of the two settings for screenshots and thinking: the vision model and ``think``.

``LEDGER_HAND_MODEL_THINK`` takes one of three words (on, off, model), each
of which can be typed in the environment and on the settings page; a blank
value takes the default, and any other word is refused, naming the variable.
``LEDGER_HAND_MODEL_VISION_NAME`` names the model that reads a screenshot,
checked as the model name is. Both are read on the settings page exactly as
they are from the environment. Every model name here is invented.
"""

from __future__ import annotations

import pytest

from ledger_hand.settings import (
    ABOUT,
    DEFAULT_THINK,
    DEFAULT_VISION_MODEL,
    ModelSettings,
    SettingsError,
    Thinking,
    Variable,
    apply_changes,
    load_model_settings,
)
from ledger_hand.ui.setting_text import shown, written


def test_the_three_thinking_settings_are_these_words() -> None:
    assert [thinking.value for thinking in Thinking] == ["on", "off", "model"]
    assert issubclass(Thinking, str)


def test_the_variables_are_named_as_the_others() -> None:
    assert Variable.THINK.value == "LEDGER_HAND_MODEL_THINK"
    assert Variable.VISION_NAME.value == "LEDGER_HAND_MODEL_VISION_NAME"


def test_the_defaults_are_the_named_constants() -> None:
    settings = load_model_settings({})

    assert settings.think is DEFAULT_THINK
    assert settings.vision_model == DEFAULT_VISION_MODEL
    assert DEFAULT_VISION_MODEL == "qwen3-vl:8b"
    assert DEFAULT_THINK in (Thinking.MODEL, Thinking.OFF)


@pytest.mark.parametrize("thinking", list(Thinking))
def test_each_thinking_word_is_read_from_the_environment(thinking: Thinking) -> None:
    assert load_model_settings({Variable.THINK.value: f" {thinking.value} "}).think is thinking


@pytest.mark.parametrize("thinking", list(Thinking))
def test_each_thinking_word_is_read_on_the_settings_page_as_the_environment_reads_it(
    thinking: Thinking,
) -> None:
    changed = apply_changes(ModelSettings(), {Variable.THINK: thinking.value})

    assert changed.think is thinking
    assert changed == load_model_settings({Variable.THINK.value: thinking.value})


@pytest.mark.parametrize("blank", ["", "  ", "\t"])
def test_a_blank_thinking_setting_takes_the_default(blank: str) -> None:
    assert load_model_settings({Variable.THINK.value: blank}).think is DEFAULT_THINK
    on = ModelSettings(think=Thinking.ON)
    assert apply_changes(on, {Variable.THINK: blank}).think is DEFAULT_THINK


@pytest.mark.parametrize("text", ["true", "false", "ON", "Off", "yes", "1", "none", "default"])
def test_any_other_word_is_refused_naming_the_variable_and_the_words(text: str) -> None:
    with pytest.raises(SettingsError) as from_environment:
        load_model_settings({Variable.THINK.value: text})
    with pytest.raises(SettingsError) as from_page:
        apply_changes(ModelSettings(), {Variable.THINK: text})

    said = str(from_environment.value)
    assert said == str(from_page.value)
    assert said.startswith("LEDGER_HAND_MODEL_THINK: ")
    assert repr(text) in said
    assert "on, off, model" in said


@pytest.mark.parametrize("value", ["on", True, None, 1])
def test_a_thinking_setting_built_in_code_must_be_a_thinking(value: object) -> None:
    with pytest.raises(SettingsError, match="LEDGER_HAND_MODEL_THINK"):
        ModelSettings(think=value)  # type: ignore[arg-type]


def test_the_vision_model_is_read_from_the_environment_and_the_page_alike() -> None:
    from_environment = load_model_settings({Variable.VISION_NAME.value: " invented-vl:2b "})
    from_page = apply_changes(ModelSettings(), {Variable.VISION_NAME: "invented-vl:2b"})

    assert from_environment.vision_model == "invented-vl:2b"
    assert from_page == from_environment
    assert from_environment.model == ModelSettings().model


def test_a_blank_vision_model_takes_the_default() -> None:
    other = ModelSettings(vision_model="invented-vl:2b")

    assert apply_changes(other, {Variable.VISION_NAME: " "}).vision_model == DEFAULT_VISION_MODEL
    assert load_model_settings({Variable.VISION_NAME.value: ""}).vision_model == (
        DEFAULT_VISION_MODEL
    )


@pytest.mark.parametrize("text", ["invented vl", "invented\tvl", "视觉"])
def test_a_vision_model_name_is_checked_as_the_model_name_is(text: str) -> None:
    with pytest.raises(SettingsError) as vision:
        load_model_settings({Variable.VISION_NAME.value: text})
    with pytest.raises(SettingsError) as name:
        load_model_settings({Variable.NAME.value: text})

    assert str(vision.value).startswith("LEDGER_HAND_MODEL_VISION_NAME: ")
    assert str(vision.value).removeprefix(Variable.VISION_NAME.value) == str(
        name.value
    ).removeprefix(Variable.NAME.value)


def test_both_say_what_they_set_and_why_their_default() -> None:
    assert ABOUT[Variable.THINK].field == "think"
    assert ABOUT[Variable.VISION_NAME].field == "vision_model"
    sets = ABOUT[Variable.THINK].sets
    for word in ("on", "off", "model", "cloud plug never sends it", "400"):
        assert word in sets
    assert "local plug only" in ABOUT[Variable.VISION_NAME].sets
    assert Variable.NAME.value in ABOUT[Variable.VISION_NAME].sets


@pytest.mark.parametrize("thinking", list(Thinking))
def test_the_settings_page_writes_each_thinking_setting_as_it_is_typed(thinking: Thinking) -> None:
    settings = ModelSettings(think=thinking)

    assert written(thinking) == thinking.value
    assert shown(settings, Variable.THINK) == thinking.value
    assert shown(settings, Variable.VISION_NAME) == DEFAULT_VISION_MODEL
