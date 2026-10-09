"""Tests of the page with a cloud plug: what it says when a key or a call is turned away.

A key the server does not take (401) and a call turned away for being too
often, with the wait the server asked for, are each said in their own plain
sentence in the chat. The settings page says which plug talks to the model
and whether there is a key, never the key itself. Switching to the cloud on
the settings page without an address of its own or a key is refused as any
refused change is, and nothing changes. Every value is invented; the model
is scripted and nothing reaches the network.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from ledger_hand.ports import ModelError, ModelErrorKind
from ledger_hand.settings import ModelSettings, Plug, Secret, Variable
from ledger_hand.ui.session import PARTS_KEY
from ledger_hand.ui.settings_form import NOTE_KEY
from ledger_hand.ui.settings_page import PLUG_KEY
from tests.fakes.memory_store import MemoryStore
from tests.fakes.routed_model import RoutedModel
from tests.ui.app_harness import program_said, send
from tests.ui.page_harness import (
    Builds,
    apply,
    every_text,
    note,
    open_built,
    open_with,
    set_setting,
    settings_rows,
    to_settings,
)

KEY = "sk-invented-page-cloud-0123456789"
ADDRESS = "https://api.example.com/v1"
SETTINGS = ModelSettings(
    plug=Plug.CLOUD, base_url=ADDRESS, model="invented-cloud-model", api_key=Secret(KEY)
)
PASSAGE = "Bought 0.02 BTC at 94,900 yesterday, fee 1 USDT"


def page_failing_with(error: ModelError, tmp_path: Path) -> AppTest:
    page = open_with(
        RoutedModel(screen=[error]), MemoryStore(), tmp_path / "data", settings=SETTINGS
    )
    return send(page, PASSAGE)


def plug_line(page: AppTest) -> str:
    (line,) = page.container(key=PLUG_KEY).text
    return str(line.value)


# --- V-10: the sentences in the chat -------------------------------------------------


def test_a_key_refused_with_401_is_said_in_its_own_sentence(tmp_path: Path) -> None:
    error = ModelError(
        ModelErrorKind.SERVER_ERROR,
        "the model server answered with a status this program does not expect",
        status=401,
        snippet='{"error": {"message": "Incorrect API key provided"}}',
    )

    page = page_failing_with(error, tmp_path)

    assert not page.exception
    (said,) = program_said(page)
    assert said.startswith("The model gave no usable reply while judging the passage, ")
    assert f"The model server at {ADDRESS} did not take the key (status 401)." in said
    assert f"Check {Variable.KEY.value} in the environment" in said
    assert KEY not in every_text(page)


def test_a_call_turned_away_with_a_wait_says_the_seconds(tmp_path: Path) -> None:
    error = ModelError(
        ModelErrorKind.RATE_LIMITED, "too often", status=429, retry_after_seconds=2.0
    )

    page = page_failing_with(error, tmp_path)

    assert not page.exception
    (said,) = program_said(page)
    assert "called too often, and asked to wait 2 seconds. Wait that long, then try again." in said


# --- V-10: the settings page -------------------------------------------------------


@pytest.fixture
def cloud_machine(bare_machine: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv(Variable.PLUG.value, "cloud")
    monkeypatch.setenv(Variable.URL.value, ADDRESS)
    monkeypatch.setenv(Variable.KEY.value, KEY)
    return bare_machine


def test_the_settings_page_says_the_cloud_plug_and_that_there_is_a_key(
    cloud_machine: Path,
) -> None:
    page = to_settings(open_built(Builds(RoutedModel())))

    assert not page.exception
    line = plug_line(page)
    assert line.startswith(f"Model plug now: cloud, the OpenAI-style chat endpoint at {ADDRESS}")
    assert "what is typed is sent there" in line
    assert line.endswith("Key: set.")
    rows = {row["Setting"]: row for row in settings_rows(page)}
    assert rows[Variable.PLUG.value]["Now"] == "cloud"
    assert rows[Variable.PLUG.value]["Default"] == "local"
    assert rows[Variable.KEY.value]["Now"] == "set"
    assert KEY not in every_text(page)


def test_the_settings_page_says_the_local_plug_and_no_key_by_default(bare_machine: Path) -> None:
    page = to_settings(open_built(Builds(RoutedModel())))

    assert plug_line(page) == (
        "Model plug now: local, Ollama's own chat endpoint at http://127.0.0.1:11434. Key: not set."
    )


@pytest.mark.parametrize(
    ("changes", "variable", "rule"),
    [
        ({Variable.PLUG: "cloud"}, Variable.URL, "the cloud plug needs the address of the service"),
        (
            {Variable.PLUG: "cloud", Variable.URL: "http://192.0.2.7:8080/v1"},
            Variable.URL,
            "must start with https://",
        ),
        (
            {Variable.PLUG: "cloud", Variable.URL: ADDRESS},
            Variable.KEY,
            "the cloud plug needs a key",
        ),
    ],
    ids=["the local address", "http off this machine", "no key"],
)
def test_switching_to_the_cloud_without_what_it_needs_is_refused_and_changes_nothing(
    bare_machine: Path, changes: dict[Variable, str], variable: Variable, rule: str
) -> None:
    builds = Builds(RoutedModel())
    page = to_settings(open_built(builds))
    for changed, text in changes.items():
        page = set_setting(page, changed, text)

    page = apply(page)

    assert not page.exception
    found = note(page, NOTE_KEY)
    assert found is not None
    tone, words = found
    assert tone == "error"
    assert words.startswith(f"Not applied: {variable.value}: ")
    assert rule in words
    assert words.endswith("The settings were not changed.")
    assert page.session_state[PARTS_KEY].settings == ModelSettings()
    assert len(builds.built) == 1
    assert plug_line(page).startswith("Model plug now: local")
