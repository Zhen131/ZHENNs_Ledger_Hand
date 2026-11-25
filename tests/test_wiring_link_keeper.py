"""Tests of the assistant link's keeper as the wiring builds it, and of the first ledger setting.

Without the ledger's folder, or with a port refused, there is no keeper
but a reason; with a folder there is one, not started, that builds a fresh
link with a fresh token at each start. A new tab reaches the demo ledger
first unless the setting says the ledger page; a value refused leaves the
demo ledger first and says why.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ledger_hand.ledger.link_keeper import LinkKeeper, LinkState
from ledger_hand.settings import (
    ASSISTANT_LEDGER_VARIABLE,
    LEDGER_DIRECTORY_VARIABLE,
    LEDGER_LINK_PORT_VARIABLE,
    AssistantLedger,
    SettingsError,
    load_assistant_ledger,
)
from ledger_hand.wiring import LinkNotSet, NoLink, _first_ledger, link_keeper


def test_without_the_ledgers_folder_there_is_no_keeper_and_it_says_which_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(LEDGER_DIRECTORY_VARIABLE, raising=False)

    found = link_keeper()

    assert found == NoLink(LinkNotSet.NO_FOLDER)
    assert LEDGER_DIRECTORY_VARIABLE in LinkNotSet.NO_FOLDER.value


def test_a_port_refused_is_said_with_the_settings_words(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(LEDGER_DIRECTORY_VARIABLE, str(tmp_path))
    monkeypatch.setenv(LEDGER_LINK_PORT_VARIABLE, "seventy")

    found = link_keeper()

    assert isinstance(found, NoLink)
    assert found.reason is LinkNotSet.SETTING_REFUSED
    assert LEDGER_LINK_PORT_VARIABLE in found.detail


def test_with_a_folder_there_is_a_keeper_not_started(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(LEDGER_DIRECTORY_VARIABLE, str(tmp_path))

    found = link_keeper()

    assert isinstance(found, LinkKeeper)
    assert found.state() is LinkState.NOT_STARTED


def test_a_start_in_a_folder_that_is_not_the_ledgers_fails_and_runs_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(LEDGER_DIRECTORY_VARIABLE, str(tmp_path))
    found = link_keeper()
    assert isinstance(found, LinkKeeper)

    failure = found.start()

    assert failure is not None
    assert found.state() is LinkState.NOT_STARTED


@pytest.mark.parametrize(
    ("value", "first"),
    [
        ("", AssistantLedger.DEMO),
        ("  ", AssistantLedger.DEMO),
        ("demo", AssistantLedger.DEMO),
        ("page", AssistantLedger.PAGE),
    ],
)
def test_the_first_ledger_is_the_demo_unless_the_page_is_named(
    value: str, first: AssistantLedger
) -> None:
    assert load_assistant_ledger({ASSISTANT_LEDGER_VARIABLE: value}) is first
    assert load_assistant_ledger({}) is AssistantLedger.DEMO


def test_a_first_ledger_refused_names_the_variable_and_the_two_values() -> None:
    with pytest.raises(SettingsError) as raised:
        load_assistant_ledger({ASSISTANT_LEDGER_VARIABLE: "real"})

    assert str(raised.value) == f"{ASSISTANT_LEDGER_VARIABLE}: demo or page, not 'real'"


def test_the_parts_start_with_the_demo_and_say_why_when_the_setting_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(ASSISTANT_LEDGER_VARIABLE, "real")

    first, refused = _first_ledger()

    assert first is AssistantLedger.DEMO
    assert refused is not None and "'real'" in refused
