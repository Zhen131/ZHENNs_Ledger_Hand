"""Tests of the setting for the largest screenshot taken, in MB.

It is read from the environment and from the settings page in the same way,
as a whole number from 1 to ``MAX_SCREENSHOT_MB``; a blank value takes the
default; anything else is refused, naming the variable. The highest limit a
setting may ask for is no more than Streamlit's own upload limit, so that a
file between the two is turned away by the program's check, in its words,
and not by Streamlit's. Every value below is invented.
"""

from __future__ import annotations

import pytest
from streamlit import config

from ledger_hand.settings import (
    ABOUT,
    DEFAULT_SCREENSHOT_MAX_MB,
    MAX_SCREENSHOT_MB,
    ModelSettings,
    SettingsError,
    Variable,
    apply_changes,
    load_model_settings,
)

LIMIT = Variable.SCREENSHOT_MAX_MB


def from_the_environment(text: str) -> object:
    try:
        return load_model_settings({LIMIT.value: text}).screenshot_max_mb
    except SettingsError as error:
        return ("refused", str(error))


def from_the_page(text: str) -> object:
    try:
        return apply_changes(ModelSettings(), {LIMIT: text}).screenshot_max_mb
    except SettingsError as error:
        return ("refused", str(error))


@pytest.mark.parametrize(
    "text", ["1", "7", "200", " 35 ", "0", "201", "-3", "2.5", "abc", "1e2", "", "   "]
)
def test_the_environment_and_the_page_read_it_alike(text: str) -> None:
    assert from_the_environment(text) == from_the_page(text)


@pytest.mark.parametrize("blank", ["", "   ", "\t"])
def test_a_blank_value_takes_the_default(blank: str) -> None:
    started = load_model_settings({LIMIT.value: "7"})

    assert load_model_settings({LIMIT.value: blank}).screenshot_max_mb == DEFAULT_SCREENSHOT_MAX_MB
    assert apply_changes(started, {LIMIT: blank}).screenshot_max_mb == DEFAULT_SCREENSHOT_MAX_MB


def test_nothing_set_is_the_named_default() -> None:
    assert ModelSettings().screenshot_max_mb == DEFAULT_SCREENSHOT_MAX_MB
    assert load_model_settings({}).screenshot_max_mb == DEFAULT_SCREENSHOT_MAX_MB
    assert 1 <= DEFAULT_SCREENSHOT_MAX_MB <= MAX_SCREENSHOT_MB


@pytest.mark.parametrize("text", ["1", str(MAX_SCREENSHOT_MB)])
def test_the_lowest_and_the_highest_are_taken(text: str) -> None:
    assert load_model_settings({LIMIT.value: text}).screenshot_max_mb == int(text)


@pytest.mark.parametrize(
    ("text", "rule"),
    [
        ("0", "1 or more"),
        (str(MAX_SCREENSHOT_MB + 1), f"at most {MAX_SCREENSHOT_MB}"),
        ("2.5", "not a whole number"),
        ("abc", "not a whole number"),
        ("-3", "not a whole number"),
    ],
)
def test_a_value_out_of_range_or_not_whole_is_refused_naming_the_variable(
    text: str, rule: str
) -> None:
    with pytest.raises(SettingsError) as raised:
        load_model_settings({LIMIT.value: text})

    assert str(raised.value).startswith(f"{LIMIT.value}: ")
    assert rule in str(raised.value)


@pytest.mark.parametrize("value", [0, MAX_SCREENSHOT_MB + 1, 2.5, "20", True])
def test_settings_made_in_code_are_checked_too(value: object) -> None:
    with pytest.raises(SettingsError) as raised:
        ModelSettings(screenshot_max_mb=value)  # type: ignore[arg-type]

    assert LIMIT.value in str(raised.value)


def test_it_says_what_it_sets_and_why_its_default() -> None:
    about = ABOUT[LIMIT]

    assert about.field == "screenshot_max_mb"
    assert "1,048,576 bytes" in about.sets
    assert str(MAX_SCREENSHOT_MB) in about.sets
    assert "phone" in about.reason


def test_the_highest_limit_is_no_more_than_streamlits_own() -> None:
    assert config.get_option("server.maxUploadSize") >= MAX_SCREENSHOT_MB
