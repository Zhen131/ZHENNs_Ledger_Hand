"""Tests of the settings as data and of changes made on the settings page.

Every variable says what it sets and why its default is what it is, once,
in ``ABOUT``. ``apply_changes`` puts changes into settings already read,
reading and checking each value exactly as the same variable is read from
the environment: the same values pass, the same ones are refused with the
same message. A blank value takes the default; the key cannot be changed;
what is not changed stays as it was, and nothing is written back to the
environment. Every value below is invented.
"""

from __future__ import annotations

import dataclasses
import os

import pytest

from ledger_hand.settings import (
    ABOUT,
    DEFAULT_TEMPERATURE,
    ModelSettings,
    Secret,
    SettingsError,
    Variable,
    apply_changes,
    load_model_settings,
)

KEY = "sk-invented-page-0123456789"
CHANGEABLE = [variable for variable in Variable if variable is not Variable.KEY]

# Texts that pass and texts that are refused, tried for every variable.
SAMPLES = [
    "0",
    "0.3",
    "  0.3  ",
    "1",
    "45",
    "120.5",
    "1.0000000001",
    "-1",
    "abc",
    "1e3",
    "+2",
    "0.",
    "11",
    "9999999999",
    "qwen2.5:14b",
    "has space",
    "http://127.0.0.1:59999",
    "http://127.0.0.1:59999/",
    "https://model.invalid/v1",
    "http://user:secret@127.0.0.1:11434",
    "http://127.0.0.1:11434?x=1",
    "ftp://127.0.0.1",
    "http://127.0.0.1:0",
    "中文",
]


def outcome(read: object) -> object:
    """What reading gave: the settings, or the message of the refusal."""
    try:
        return read() if callable(read) else read
    except SettingsError as error:
        return ("refused", str(error))


# --- the settings as data --------------------------------------------------


def test_every_variable_says_what_it_sets_and_why_its_default() -> None:
    assert set(ABOUT) == set(Variable)
    for variable, about in ABOUT.items():
        assert about.sets.strip(), variable
        assert about.reason.strip(), variable
        assert about.sets.endswith("."), variable
        assert about.reason.endswith("."), variable


def test_each_variable_names_its_own_field_of_the_settings() -> None:
    fields = [about.field for about in ABOUT.values()]

    assert sorted(fields) == sorted(field.name for field in dataclasses.fields(ModelSettings))
    assert len(set(fields)) == len(fields)


# For each variable, a value that is not its default.
NOT_THE_DEFAULT = {
    Variable.PLUG: "cloud",
    Variable.URL: "http://192.0.2.7:8080",
    Variable.NAME: "another-model",
    Variable.KEY: KEY,
    Variable.TEMPERATURE: "0.4",
    Variable.TOP_P: "0.5",
    Variable.MAX_REPLY_TOKENS: "7",
    Variable.CONTEXT_TOKENS: "7",
    Variable.TIMEOUT_SECONDS: "7",
    Variable.RETRIES: "7",
    Variable.RETRY_WAIT_SECONDS: "7",
    Variable.QUESTION_TEMPERATURE: "0.1",
}


@pytest.mark.parametrize("variable", list(Variable))
def test_the_field_named_is_the_one_the_environment_sets(variable: Variable) -> None:
    loaded = load_model_settings({variable.value: NOT_THE_DEFAULT[variable]})

    changed = [
        field.name
        for field in dataclasses.fields(ModelSettings)
        if getattr(loaded, field.name) != getattr(ModelSettings(), field.name)
    ]
    assert changed == [ABOUT[variable].field]


# --- changes are read as the environment is read ----------------------------


@pytest.mark.parametrize("text", SAMPLES)
@pytest.mark.parametrize("variable", CHANGEABLE)
def test_a_change_is_read_and_checked_as_the_environment_is(variable: Variable, text: str) -> None:
    from_the_page = outcome(lambda: apply_changes(ModelSettings(), {variable: text}))
    from_the_environment = outcome(lambda: load_model_settings({variable.value: text}))

    assert from_the_page == from_the_environment


@pytest.mark.parametrize("variable", CHANGEABLE)
@pytest.mark.parametrize("blank", ["", "   ", "\t"])
def test_a_blank_change_takes_the_default(variable: Variable, blank: str) -> None:
    started = load_model_settings(
        {variable.value: text for variable, text in NOT_THE_DEFAULT.items()}
    )
    field = ABOUT[variable].field

    changed = apply_changes(started, {variable: blank})

    assert getattr(changed, field) == getattr(ModelSettings(), field)
    for other in dataclasses.fields(ModelSettings):
        if other.name != field:
            assert getattr(changed, other.name) == getattr(started, other.name)


def test_only_what_is_changed_changes_and_the_key_and_address_stay() -> None:
    started = load_model_settings(
        {Variable.KEY.value: KEY, Variable.URL.value: "http://192.0.2.7:8080"}
    )

    changed = apply_changes(started, {Variable.TEMPERATURE: "0.4"})

    assert changed == dataclasses.replace(started, temperature=0.4)
    assert changed.api_key == Secret(KEY)
    assert changed.base_url == "http://192.0.2.7:8080"


def test_several_changes_are_put_in_together() -> None:
    changed = apply_changes(
        ModelSettings(),
        {
            Variable.TEMPERATURE: "0.2",
            Variable.URL: "http://127.0.0.1:59999/",
            Variable.RETRIES: "0",
        },
    )

    assert (changed.temperature, changed.base_url, changed.retries) == (
        0.2,
        "http://127.0.0.1:59999",
        0,
    )


def test_no_change_gives_the_same_settings() -> None:
    started = load_model_settings({Variable.KEY.value: KEY})

    assert apply_changes(started, {}) == started


# --- refused changes ----------------------------------------------------------


@pytest.mark.parametrize(
    ("variable", "text", "rule"),
    [
        (Variable.TEMPERATURE, "-1", "no sign or exponent"),
        (Variable.TEMPERATURE, "abc", "is not a plain number"),
        (Variable.URL, "http://user:secret@127.0.0.1:11434", "may not hold a user name"),
        (Variable.TOP_P, "1.5", "at most 1"),
        (Variable.RETRIES, "11", "at most 10"),
        (Variable.TIMEOUT_SECONDS, "0", "above 0"),
    ],
)
def test_a_refused_change_names_the_variable_and_its_rule(
    variable: Variable, text: str, rule: str
) -> None:
    started = ModelSettings()

    with pytest.raises(SettingsError) as refused:
        apply_changes(started, {variable: text})

    assert str(refused.value).startswith(f"{variable.value}: ")
    assert rule in str(refused.value)
    assert started == ModelSettings()


def test_one_refused_change_refuses_them_all() -> None:
    with pytest.raises(SettingsError):
        apply_changes(ModelSettings(), {Variable.TOP_P: "0.5", Variable.TEMPERATURE: "warm"})


def test_the_key_cannot_be_changed_and_the_refusal_does_not_repeat_it() -> None:
    started = load_model_settings({Variable.KEY.value: KEY})

    with pytest.raises(SettingsError) as refused:
        apply_changes(started, {Variable.KEY: "sk-invented-other-key"})

    message = str(refused.value)
    assert message.startswith(f"{Variable.KEY.value}: ")
    assert "sk-invented" not in message


@pytest.mark.parametrize("name", ["LEDGER_HAND_MODEL_TEMPERATURE", "temperature", None])
def test_a_name_that_is_not_a_variable_is_refused(name: object) -> None:
    with pytest.raises(SettingsError) as refused:
        apply_changes(ModelSettings(), {name: "0.3"})  # type: ignore[dict-item]

    assert "unknown setting" in str(refused.value)


def test_a_value_that_is_not_text_is_refused() -> None:
    with pytest.raises(SettingsError) as refused:
        apply_changes(ModelSettings(), {Variable.TEMPERATURE: 0.3})  # type: ignore[dict-item]

    assert str(refused.value).startswith(f"{Variable.TEMPERATURE.value}: ")


def test_settings_that_are_not_settings_are_a_mistake_of_the_caller() -> None:
    with pytest.raises(TypeError):
        apply_changes({"temperature": 0.0}, {})  # type: ignore[arg-type]


# --- nothing is written anywhere -----------------------------------------------


def test_a_change_writes_nothing_back_to_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    assert DEFAULT_TEMPERATURE != 0.6
    monkeypatch.setenv(Variable.TEMPERATURE.value, "0.6")
    before = dict(os.environ)

    changed = apply_changes(load_model_settings(), {Variable.TEMPERATURE: "0.1"})

    assert changed.temperature == 0.1
    assert dict(os.environ) == before
    assert load_model_settings().temperature == 0.6
