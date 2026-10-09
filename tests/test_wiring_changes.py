"""Tests of building the parts again with the changes made on the settings page.

The environment is read first and the changes are put in on top, read as the
environment's values are: what the page does not change, the key among it,
stays as the environment set it. The parts carry the settings and the data
places they were built from, and every part that comes from a setting
follows a change. A refused change is told apart from a refused environment
variable. Nothing is opened, made or written back. Every value is invented.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import tzlocal

from ledger_hand import wiring
from ledger_hand.flows.recording import tuning_from
from ledger_hand.ports import ModelPort
from ledger_hand.settings import (
    DATA_DIRECTORY_VARIABLE,
    ENV_PREFIX,
    ModelSettings,
    Secret,
    Variable,
    load_data_places,
)
from ledger_hand.wiring import AssemblyError, AssemblyProblem, assemble

KEY = "sk-invented-wiring-0123456789"
ADDRESS = "http://192.0.2.7:8080"


@pytest.fixture
def machine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A machine in Europe/Budapest, with no model setting and the data in a temp folder."""
    for name in list(os.environ):
        if name.startswith(ENV_PREFIX):
            monkeypatch.delenv(name)
    data = tmp_path / "data"
    monkeypatch.setenv(DATA_DIRECTORY_VARIABLE, str(data))
    monkeypatch.setattr(tzlocal, "get_localzone_name", lambda: "Europe/Budapest")
    monkeypatch.chdir(tmp_path)
    return data


@pytest.fixture
def plugs(monkeypatch: pytest.MonkeyPatch) -> list[ModelSettings]:
    """The settings each model plug is built from, in order."""
    built: list[ModelSettings] = []
    real = wiring.connect_model

    def connect(settings: ModelSettings) -> ModelPort:
        built.append(settings)
        return real(settings)

    monkeypatch.setattr(wiring, "connect_model", connect)
    return built


def test_the_parts_carry_the_settings_and_the_places_they_were_built_from(machine: Path) -> None:
    parts = assemble()

    assert parts.settings == ModelSettings()
    assert parts.places == load_data_places()
    assert parts.places is not None
    assert parts.places.directory == machine


def test_a_change_reaches_the_model_the_tuning_and_the_settings(
    machine: Path, plugs: list[ModelSettings]
) -> None:
    parts = assemble({Variable.TEMPERATURE: "0.3", Variable.QUESTION_TEMPERATURE: "0.2"})

    (plug,) = plugs
    assert plug.temperature == 0.3
    assert parts.settings == plug
    assert parts.tuning == tuning_from(plug)
    assert parts.tuning.question_parameters is not None
    assert parts.tuning.question_parameters.temperature == 0.2


def test_what_the_page_does_not_change_stays_as_the_environment_set_it(
    machine: Path, monkeypatch: pytest.MonkeyPatch, plugs: list[ModelSettings]
) -> None:
    monkeypatch.setenv(Variable.KEY.value, KEY)
    monkeypatch.setenv(Variable.URL.value, ADDRESS)

    parts = assemble({Variable.TEMPERATURE: "0.4"})

    assert parts.settings.temperature == 0.4
    assert parts.settings.base_url == ADDRESS
    assert parts.settings.api_key == Secret(KEY)
    assert plugs[-1] == parts.settings


def test_no_changes_build_what_the_environment_names(
    machine: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(Variable.URL.value, ADDRESS)

    assert assemble({}).settings == assemble().settings
    assert assemble().settings.base_url == ADDRESS


@pytest.mark.parametrize(
    "changes",
    [
        {Variable.TEMPERATURE: "-1"},
        {Variable.TEMPERATURE: "abc"},
        {Variable.URL: "http://user:secret@127.0.0.1:11434"},
        {Variable.KEY: "sk-invented-other"},
    ],
)
def test_a_refused_change_is_told_apart_and_names_the_variable(
    machine: Path, changes: dict[Variable, str]
) -> None:
    with pytest.raises(AssemblyError) as raised:
        assemble(changes)

    assert raised.value.problem is AssemblyProblem.CHANGE_REFUSED
    (variable,) = changes
    assert variable.value in str(raised.value)
    assert "sk-invented" not in str(raised.value)


def test_a_refused_environment_variable_stays_a_refused_setting_whatever_the_changes(
    machine: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(Variable.TEMPERATURE.value, "warm")

    with pytest.raises(AssemblyError) as raised:
        assemble({Variable.TEMPERATURE: "0.3"})

    assert raised.value.problem is AssemblyProblem.SETTING_REFUSED


def test_building_with_changes_opens_makes_and_writes_nothing(
    machine: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(Variable.KEY.value, KEY)
    environment = dict(os.environ)
    before = sorted(tmp_path.rglob("*"))

    assemble({Variable.TEMPERATURE: "0.3", Variable.URL: "http://127.0.0.1:59999"})

    assert sorted(tmp_path.rglob("*")) == before
    assert not machine.exists()
    assert dict(os.environ) == environment
