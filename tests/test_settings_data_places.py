"""Tests of where the data is kept: one variable, its default, and that reading it makes nothing.

The variable is not a model setting: it does not start with the model
settings' prefix, it is not in ``Variable``, and setting it, or the other
``LEDGER_HAND_`` variables the scripts read, never makes the model settings
refuse anything.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ledger_hand.settings import (
    BOOK_FILE_NAME,
    DATA_DIRECTORY_VARIABLE,
    ENV_PREFIX,
    EXPORTS_DIRECTORY_NAME,
    DataPlaces,
    SettingsError,
    Variable,
    load_data_places,
    load_model_settings,
)


def test_the_default_is_data_in_the_working_directory(tmp_path: Path) -> None:
    places = load_data_places({}, working_directory=tmp_path)

    assert places == DataPlaces(tmp_path / "data")
    assert places.book == tmp_path / "data" / BOOK_FILE_NAME
    assert places.exports == tmp_path / "data" / EXPORTS_DIRECTORY_NAME


@pytest.mark.parametrize("blank", ["", "  ", "\t\n"])
def test_a_blank_variable_takes_the_default(tmp_path: Path, blank: str) -> None:
    places = load_data_places({DATA_DIRECTORY_VARIABLE: blank}, working_directory=tmp_path)

    assert places.directory == tmp_path / "data"


def test_an_absolute_folder_is_taken_as_it_is(tmp_path: Path) -> None:
    named = tmp_path / "elsewhere" / "kept"

    places = load_data_places({DATA_DIRECTORY_VARIABLE: f" {named} "}, working_directory=Path("x"))

    assert places.directory == named


def test_a_relative_folder_is_taken_from_the_working_directory(tmp_path: Path) -> None:
    places = load_data_places({DATA_DIRECTORY_VARIABLE: "my/book"}, working_directory=tmp_path)

    assert places.directory == tmp_path / "my" / "book"


def test_a_leading_tilde_is_the_home_folder(tmp_path: Path) -> None:
    places = load_data_places({DATA_DIRECTORY_VARIABLE: "~/kept"}, working_directory=tmp_path)

    assert places.directory == Path.home() / "kept"


def test_the_process_environment_and_working_directory_are_read_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(DATA_DIRECTORY_VARIABLE, raising=False)
    assert load_data_places().directory == tmp_path / "data"

    monkeypatch.setenv(DATA_DIRECTORY_VARIABLE, "other")
    assert load_data_places().directory == tmp_path / "other"


def test_a_nul_character_is_refused(tmp_path: Path) -> None:
    with pytest.raises(SettingsError, match=DATA_DIRECTORY_VARIABLE):
        load_data_places({DATA_DIRECTORY_VARIABLE: "da\0ta"}, working_directory=tmp_path)


def test_reading_where_the_data_is_kept_makes_nothing(tmp_path: Path) -> None:
    load_data_places({DATA_DIRECTORY_VARIABLE: "deep/folder"}, working_directory=tmp_path)
    load_data_places({}, working_directory=tmp_path)

    assert list(tmp_path.iterdir()) == []


def test_the_variable_is_not_a_model_setting() -> None:
    assert not DATA_DIRECTORY_VARIABLE.startswith(ENV_PREFIX)
    assert DATA_DIRECTORY_VARIABLE not in {variable.value for variable in Variable}


def test_the_scripts_own_variables_never_make_the_model_settings_refuse(tmp_path: Path) -> None:
    environ = {
        DATA_DIRECTORY_VARIABLE: str(tmp_path),
        "LEDGER_HAND_LEDGER_DIR": str(tmp_path),
        "LEDGER_HAND_PYTHON": "python",
    }

    assert load_model_settings(environ) == load_model_settings({})
