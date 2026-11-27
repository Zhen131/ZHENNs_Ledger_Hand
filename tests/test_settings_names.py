"""The two switches of matching names of assets: read like the other switches.

Not set or blank, the table is off and the answers on; ``on`` and
``off`` are taken, written so; anything else is refused, naming the variable. Neither is a model
setting. The README's row for each names the variable and the default
this module holds, and the file of answers is in the data folder.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ledger_hand.settings import (
    ASSET_NAMES_FILE_NAME,
    DEFAULT_NAME_TABLE,
    DEFAULT_REMEMBER_NAMES,
    ENV_PREFIX,
    NAME_TABLE_VARIABLE,
    REMEMBER_NAMES_VARIABLE,
    DataPlaces,
    SettingsError,
    Switch,
    Variable,
    load_model_settings,
    load_name_table,
    load_remember_names,
)

README = Path(__file__).resolve().parents[1] / "README.md"
SWITCHES = [(NAME_TABLE_VARIABLE, load_name_table), (REMEMBER_NAMES_VARIABLE, load_remember_names)]


@pytest.mark.parametrize(
    ("variable", "load", "default"),
    [
        (NAME_TABLE_VARIABLE, load_name_table, False),
        (REMEMBER_NAMES_VARIABLE, load_remember_names, True),
    ],
)
def test_not_set_or_blank_is_the_default_the_table_off_the_answers_on(
    variable: str,
    load,  # type: ignore[no-untyped-def]
    default: bool,  # noqa: FBT001
) -> None:
    assert DEFAULT_NAME_TABLE is Switch.OFF
    assert DEFAULT_REMEMBER_NAMES is Switch.ON
    assert load({}) is default
    assert load({variable: ""}) is default
    assert load({variable: "  "}) is default


@pytest.mark.parametrize(("variable", "load"), SWITCHES)
def test_on_and_off_are_taken(variable: str, load) -> None:  # type: ignore[no-untyped-def]
    assert load({variable: "on"}) is True
    assert load({variable: " off "}) is False


@pytest.mark.parametrize(("variable", "load"), SWITCHES)
@pytest.mark.parametrize("value", ["ON", "Off", "yes", "1", "true", "开"])
def test_anything_else_is_refused_naming_the_variable(
    variable: str,
    load,  # type: ignore[no-untyped-def]
    value: str,
) -> None:
    with pytest.raises(SettingsError) as caught:
        load({variable: value})

    assert variable in str(caught.value)


@pytest.mark.parametrize("variable", [NAME_TABLE_VARIABLE, REMEMBER_NAMES_VARIABLE])
def test_neither_is_a_model_setting(variable: str) -> None:
    assert not variable.startswith(ENV_PREFIX)
    assert variable not in {one.value for one in Variable}
    assert load_model_settings({variable: "off"}) == load_model_settings({})


@pytest.mark.parametrize(
    ("variable", "default"),
    [(NAME_TABLE_VARIABLE, DEFAULT_NAME_TABLE), (REMEMBER_NAMES_VARIABLE, DEFAULT_REMEMBER_NAMES)],
)
def test_the_readme_row_names_the_variable_and_the_default_held_here(
    variable: str, default: Switch
) -> None:
    start = f"| `{variable}` |"
    (line,) = [
        line for line in README.read_text(encoding="utf-8").splitlines() if line.startswith(start)
    ]
    name, written, _sets, _why = (cell.strip() for cell in line.strip().strip("|").split(" | "))

    assert name == f"`{variable}`"
    assert written.strip("`") == default.value


def test_the_file_of_answers_is_in_the_data_folder(tmp_path: Path) -> None:
    assert DataPlaces(tmp_path).asset_names == tmp_path / ASSET_NAMES_FILE_NAME
    assert ASSET_NAMES_FILE_NAME == "asset-names.json"
