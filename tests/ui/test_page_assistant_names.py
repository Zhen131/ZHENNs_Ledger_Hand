"""Tests of the Assistant page handing the two switches of matching names, and the file of answers.

The page runs headless with the demo ledger and a scripted model. An
answer to "which asset" is kept in the data folder's file of answers, for
the kind of ledger the page reaches; with answers not remembered, or no
data folder, no file is handed in; a refused switch stops the Assistant
page alone. Every sentence is invented; the data folder is temporary.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from ledger_hand.core.assets import BUILT_IN_ASSETS
from ledger_hand.flows.asset_names import NamesFile
from ledger_hand.flows.recording import tuning_from
from ledger_hand.flows.standing import LedgerKind
from ledger_hand.ledger.demo_book import demo_ledger
from ledger_hand.ledger.invented_book import INVENTED_NOW, INVENTED_ZONE
from ledger_hand.settings import (
    NAME_TABLE_VARIABLE,
    REMEMBER_NAMES_VARIABLE,
    DataPlaces,
    ModelSettings,
)
from ledger_hand.ui.assistant_turns import names_file
from ledger_hand.ui.session import BUILDER_KEY, PARTS_KEY
from ledger_hand.ui.settings_page import NAMES_KEY, NAMES_WORDS
from ledger_hand.wiring import Parts
from tests.fakes.routed_model import RoutedModel
from tests.flows.scripted_flow import copied, screened, table
from tests.flows.test_conversation_asset_pick import RECORD, row_of, said_as
from tests.ui.app_harness import APP_FILE
from tests.ui.assistant_harness import CountingBook, say_on_page, to_assistant
from tests.ui.page_harness import Builds, open_built, to_settings
from tests.ui.test_page_assistant_settings import ScriptedBuilds


def parts(data: Path | None, kind: LedgerKind, *, remember_names: bool = True) -> Parts:
    settings = ModelSettings()
    return Parts(
        model=RoutedModel(),
        tuning=tuning_from(settings),
        book=CountingBook(),  # type: ignore[arg-type]
        assets=BUILT_IN_ASSETS,
        clock=lambda: INVENTED_NOW,
        zone=INVENTED_ZONE,
        settings=settings,
        places=DataPlaces(data) if data is not None else None,
        ledger=demo_ledger(),
        ledger_kind=kind,
        remember_names=remember_names,
    )


def test_the_file_is_handed_in_for_the_kind_of_ledger_the_parts_reach(tmp_path: Path) -> None:
    place = DataPlaces(tmp_path).asset_names

    assert place == tmp_path / "asset-names.json"
    assert names_file(parts(tmp_path, LedgerKind.DEMO)) == NamesFile(place, LedgerKind.DEMO)
    assert names_file(parts(tmp_path, LedgerKind.PAGE)) == NamesFile(place, LedgerKind.PAGE)
    assert names_file(parts(tmp_path, LedgerKind.DEMO, remember_names=False)) is None
    assert names_file(parts(None, LedgerKind.DEMO)) is None


def test_an_answer_on_the_page_is_kept_in_the_data_folder(tmp_path: Path) -> None:
    words = said_as("小可")
    model = RoutedModel(
        tools=[RECORD],
        screen=[screened(("spot_trade", words.split("，")[0]))],
        extraction=[table(row_of("小可"))],
        answers=[copied("KO")],
    )
    kept = parts(tmp_path, LedgerKind.DEMO)
    page = AppTest.from_file(str(APP_FILE), default_timeout=30)
    page.session_state[PARTS_KEY] = Parts(**{**kept.__dict__, "model": model})
    page = to_assistant(page.run())

    page = say_on_page(page, words)
    page = say_on_page(page, "KO")

    assert not page.exception
    written = json.loads((tmp_path / "asset-names.json").read_text(encoding="utf-8"))
    assert written["demo"] == [{"name": "小可", "code": "KO", "day": "2026-11-24"}]
    assert written["page"] == []


@pytest.mark.parametrize("variable", [NAME_TABLE_VARIABLE, REMEMBER_NAMES_VARIABLE])
def test_a_refused_switch_stops_the_assistant_page_alone(
    bare_machine: Path, monkeypatch: pytest.MonkeyPatch, variable: str
) -> None:
    monkeypatch.setenv(variable, "yes")
    model = RoutedModel()
    page = AppTest.from_file(str(APP_FILE), default_timeout=30)
    page.session_state[BUILDER_KEY] = ScriptedBuilds(model)
    page = page.run()

    assert list(page.error) == []

    page = to_assistant(page)
    notice = str(page.container(key="assistant_notice").warning[0].value)
    assert notice.startswith("The assistant cannot start:")
    assert variable in notice
    assert page.chat_input(key="assistant_chat_input").proto.disabled
    assert model.tools.calls == []


def test_the_settings_page_shows_both_switches_and_the_file(
    bare_machine: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(NAME_TABLE_VARIABLE, "off")
    page = to_settings(open_built(Builds(RoutedModel())))

    names = page.container(key=NAMES_KEY)
    shown = str(names.text[0].value)
    assert f"{NAME_TABLE_VARIABLE}: off" in shown
    assert f"{REMEMBER_NAMES_VARIABLE}: on" in shown
    assert str(bare_machine / "asset-names.json") in shown
    assert str(names.caption[0].value) == NAMES_WORDS
    assert "deleting it forgets every answer" in NAMES_WORDS
