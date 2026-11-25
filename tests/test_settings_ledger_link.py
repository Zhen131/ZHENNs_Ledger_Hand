"""Tests of the settings the ledger's assistant link is started with.

The ledger's folder, the two ports and the variables handed on to the link
are read here and nowhere else in the package. None of them is a model
setting, so setting them never makes the model settings refuse anything.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ledger_hand.settings import (
    DEFAULT_LEDGER_LINK_PORT,
    DEFAULT_LEDGER_PAGE_PORT,
    LEDGER_DIRECTORY_VARIABLE,
    LEDGER_LINK_PORT_VARIABLE,
    LEDGER_PAGE_PORT_VARIABLE,
    LedgerLinkSettings,
    SettingsError,
    load_ledger_link_settings,
    load_model_settings,
)


def test_nothing_set_names_no_folder_and_the_ledgers_own_ports() -> None:
    read = load_ledger_link_settings({})

    assert read == LedgerLinkSettings(directory=None)
    assert (read.link_port, read.page_port) == (DEFAULT_LEDGER_LINK_PORT, DEFAULT_LEDGER_PAGE_PORT)
    assert (DEFAULT_LEDGER_LINK_PORT, DEFAULT_LEDGER_PAGE_PORT) == (47651, 3000)


def test_the_folder_and_both_ports_are_read() -> None:
    read = load_ledger_link_settings(
        {
            LEDGER_DIRECTORY_VARIABLE: " ledger ",
            LEDGER_LINK_PORT_VARIABLE: "47668",
            LEDGER_PAGE_PORT_VARIABLE: "3068",
        }
    )

    assert read.directory == Path("ledger")
    assert (read.link_port, read.page_port) == (47668, 3068)


def test_a_leading_tilde_is_the_home_folder() -> None:
    read = load_ledger_link_settings({LEDGER_DIRECTORY_VARIABLE: "~/ledger"})

    assert read.directory == Path.home() / "ledger"


@pytest.mark.parametrize("blank", ["", "  "])
def test_blank_values_take_the_defaults(blank: str) -> None:
    read = load_ledger_link_settings(
        {
            LEDGER_DIRECTORY_VARIABLE: blank,
            LEDGER_LINK_PORT_VARIABLE: blank,
            LEDGER_PAGE_PORT_VARIABLE: blank,
        }
    )

    assert read == LedgerLinkSettings(directory=None)


@pytest.mark.parametrize("variable", [LEDGER_LINK_PORT_VARIABLE, LEDGER_PAGE_PORT_VARIABLE])
@pytest.mark.parametrize("value", ["0", "65536", "-1", "port", "1.5", "123456"])
def test_a_port_out_of_range_is_refused_naming_the_variable(variable: str, value: str) -> None:
    with pytest.raises(SettingsError) as raised:
        load_ledger_link_settings({variable: value})

    assert variable in str(raised.value)


def test_a_folder_with_a_nul_is_refused() -> None:
    with pytest.raises(SettingsError):
        load_ledger_link_settings({LEDGER_DIRECTORY_VARIABLE: "led\0ger"})


def test_only_path_and_home_are_handed_on_to_the_link() -> None:
    read = load_ledger_link_settings(
        {"PATH": "/usr/bin", "HOME": "home-folder", "LEDGER_HAND_MODEL_KEY": "k", "OTHER": "x"}
    )

    assert dict(read.environment) == {"PATH": "/usr/bin", "HOME": "home-folder"}


def test_these_variables_are_not_model_settings() -> None:
    load_model_settings(
        {
            LEDGER_DIRECTORY_VARIABLE: "ledger",
            LEDGER_LINK_PORT_VARIABLE: "47668",
            LEDGER_PAGE_PORT_VARIABLE: "3068",
        }
    )
