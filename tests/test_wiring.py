"""Tests of the wiring module: the parts built from the settings and the machine.

Building sends nothing and opens nothing; the machine's zone is read with
tzlocal, replaced here by a stand-in; a refused setting or a zone without a
name the program takes is an ``AssemblyError`` that says which.
"""

from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

import pytest
import tzlocal

from ledger_hand import wiring
from ledger_hand.core.coins import BUILT_IN_TABLE
from ledger_hand.flows.recording import tuning_from
from ledger_hand.settings import (
    BOOK_FILE_NAME,
    DATA_DIRECTORY_VARIABLE,
    ENV_PREFIX,
    ModelSettings,
    SettingsError,
    Variable,
)
from ledger_hand.storage.sqlite_store import SqliteStore
from ledger_hand.wiring import AssemblyError, AssemblyProblem, Parts, assemble


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


def test_the_parts_are_built_from_the_settings_and_the_machine(machine: Path) -> None:
    parts = assemble()

    assert isinstance(parts, Parts)
    assert parts.zone == "Europe/Budapest"
    assert parts.coins is BUILT_IN_TABLE
    assert parts.tuning == tuning_from(ModelSettings())
    assert isinstance(parts.book, SqliteStore)
    assert parts.book.path == machine / BOOK_FILE_NAME
    assert callable(parts.model.chat)


def test_building_the_parts_opens_nothing_and_makes_nothing(machine: Path, tmp_path: Path) -> None:
    before = sorted(tmp_path.rglob("*"))

    assemble()

    assert not machine.exists()
    assert sorted(tmp_path.rglob("*")) == before


def test_the_settings_reach_the_tuning(machine: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(Variable.QUESTION_TEMPERATURE.value, "0.3")

    parts = assemble()

    assert parts.tuning.question_parameters is not None
    assert parts.tuning.question_parameters.temperature == 0.3


def test_the_clock_gives_the_current_moment_with_an_offset() -> None:
    first = wiring.read_clock()
    second = wiring.read_clock()

    assert first.utcoffset() == timedelta(0)
    assert first <= second


def test_a_refused_model_setting_is_an_assembly_error(
    machine: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(Variable.TEMPERATURE.value, "warm")

    with pytest.raises(AssemblyError) as raised:
        assemble()

    assert raised.value.problem is AssemblyProblem.SETTING_REFUSED
    assert Variable.TEMPERATURE.value in str(raised.value)


def test_a_refused_data_setting_is_an_assembly_error(
    machine: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # An environment variable cannot carry the NUL the data setting refuses,
    # so the refusal is played by a stand-in for reading the setting.
    def refused() -> None:
        raise SettingsError(f"{DATA_DIRECTORY_VARIABLE}: refused")

    monkeypatch.setattr(wiring, "load_data_places", refused)

    with pytest.raises(AssemblyError) as raised:
        assemble()

    assert raised.value.problem is AssemblyProblem.SETTING_REFUSED
    assert DATA_DIRECTORY_VARIABLE in str(raised.value)


@pytest.mark.parametrize("name", ["Not/AZone", "localtime", ""])
def test_a_machine_zone_the_program_does_not_take_is_an_assembly_error(
    machine: Path, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    monkeypatch.setattr(tzlocal, "get_localzone_name", lambda: name)

    with pytest.raises(AssemblyError) as raised:
        assemble()

    assert raised.value.problem is AssemblyProblem.NO_ZONE_NAME


@pytest.mark.parametrize("error", [LookupError("none"), OSError("unreadable"), ValueError("odd")])
def test_a_machine_zone_that_cannot_be_read_is_an_assembly_error(
    machine: Path, monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    def unreadable() -> str:
        raise error

    monkeypatch.setattr(tzlocal, "get_localzone_name", unreadable)

    with pytest.raises(AssemblyError) as raised:
        assemble()

    assert raised.value.problem is AssemblyProblem.NO_ZONE_NAME
