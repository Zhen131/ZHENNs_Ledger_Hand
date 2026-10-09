"""Tests of where the page gets its parts: from the wiring module, unless they are already there.

With nothing put in the session first, the page builds its parts with the
wiring module, which opens nothing; when they cannot be built, the page says
why and shows nothing else. No passage is sent here: nothing reaches the
network.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import tzlocal
from streamlit.testing.v1 import AppTest

from ledger_hand.settings import BOOK_FILE_NAME, DATA_DIRECTORY_VARIABLE, ENV_PREFIX, Variable
from ledger_hand.storage.sqlite_store import SqliteStore
from ledger_hand.wiring import Parts
from tests.ui.app_harness import APP_FILE, INPUT_KEY, PARTS_KEY, SAVE_KEY


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


def bare_page() -> AppTest:
    return AppTest.from_file(str(APP_FILE), default_timeout=30).run()


def test_the_page_builds_its_parts_with_the_wiring_module_and_opens_nothing(
    machine: Path, tmp_path: Path
) -> None:
    page = bare_page()

    assert not page.exception
    assert not page.error
    parts = page.session_state[PARTS_KEY]
    assert isinstance(parts, Parts)
    assert parts.zone == "Europe/Budapest"
    assert isinstance(parts.book, SqliteStore)
    assert parts.book.path == machine / BOOK_FILE_NAME
    assert page.chat_input(key=INPUT_KEY) is not None
    assert page.button(key=SAVE_KEY).disabled
    assert not machine.exists()
    assert list(tmp_path.iterdir()) == []


def test_a_refused_setting_is_said_on_the_page_and_nothing_else_is_shown(
    machine: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(Variable.TEMPERATURE.value, "warm")

    page = bare_page()

    assert not page.exception
    (error,) = page.error
    assert error.value.startswith("The program cannot start: a setting was refused: ")
    assert Variable.TEMPERATURE.value in error.value
    assert len(page.chat_input) == 0
    assert len(page.button) == 0


def test_a_machine_zone_without_a_name_is_said_on_the_page(
    machine: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tzlocal, "get_localzone_name", lambda: "Not/AZone")

    page = bare_page()

    assert not page.exception
    (error,) = page.error
    assert "time zone" in error.value
    assert len(page.chat_input) == 0
