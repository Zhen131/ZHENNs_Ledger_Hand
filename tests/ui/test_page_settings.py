"""Tests of the settings page: every setting with its value now, its default and why; changes.

One row for each model setting, as the settings module holds it; the key
shows only whether there is one, and appears nowhere on any page. A change
applied on the page builds the parts again, so the next call to the model
uses it, even half-way through a passage; a refused change names the
setting and its rule and changes nothing; what the page does not change
stays as the environment set it. Changes last for the browser tab only and
are written nowhere. When a setting in the environment is refused, the page
still opens and says so. Every value below is invented.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from ledger_hand.ports import ModelError, ModelErrorKind
from ledger_hand.settings import ABOUT, DEFAULT_QUESTION_TEMPERATURE, ModelSettings, Variable
from ledger_hand.ui.session import PARTS_KEY
from ledger_hand.ui.setting_text import shown
from ledger_hand.ui.settings_form import CHANGEABLE, NOTE_KEY, input_key
from ledger_hand.ui.settings_page import FOLDER_KEY
from tests.fakes.routed_model import RoutedModel
from tests.flows.scripted_flow import row, screened, table
from tests.ui.app_harness import INPUT_KEY, program_said, send
from tests.ui.page_harness import (
    Builds,
    apply,
    every_text,
    note,
    open_built,
    reset,
    set_setting,
    settings_rows,
    to_record,
    to_settings,
)

KEY = "sk-invented-page-key-0123456789"
ADDRESS = "http://127.0.0.1:59999"
SPOT = screened(("spot_trade", "Bought 0.02 BTC"))
COMPLETE = "Bought 0.02 BTC at 94,900 yesterday, fee 1 USDT"
COMPLETE_ROWS = table(
    row(side="buy", coin="BTC", quantity="0.02 BTC", price="94,900", fee="1 USDT", time="yesterday")
)
# Neither the fee nor the time: two questions, one after the other.
TWO_QUESTIONS = "Bought 0.5 ETH at 3,420"
TWO_QUESTIONS_ROWS = table(row(side="buy", coin="ETH", quantity="0.5 ETH", price="3,420"))


def settings_now(page: AppTest) -> ModelSettings:
    settings = page.session_state[PARTS_KEY].settings
    assert isinstance(settings, ModelSettings)
    return settings


def settings_note(page: AppTest) -> tuple[str, str]:
    found = note(page, NOTE_KEY)
    assert found is not None
    return found


# --- V-3: one row for each setting, with its value now, its default and why ---------


def test_every_setting_has_a_row_with_its_value_now_its_default_and_why(
    bare_machine: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(Variable.URL.value, ADDRESS)
    page = to_settings(open_built(Builds(RoutedModel())))

    assert not page.exception
    rows = settings_rows(page)
    assert [r["Setting"] for r in rows] == [variable.value for variable in Variable]
    for variable, shown_row in zip(Variable, rows, strict=True):
        assert shown_row["Now"] == shown(settings_now(page), variable)
        assert shown_row["Default"] == shown(ModelSettings(), variable)
        assert shown_row["What it sets"] == ABOUT[variable].sets
        assert shown_row["Why this default"] == ABOUT[variable].reason
    by_name = {r["Setting"]: r for r in rows}
    assert by_name[Variable.URL.value]["Now"] == ADDRESS
    assert by_name[Variable.URL.value]["Default"] == "http://127.0.0.1:11434"
    assert by_name[Variable.TEMPERATURE.value]["Default"] == "0"
    assert by_name[Variable.KEY.value]["Now"] == "not set"


def test_a_key_shows_only_as_set_and_is_nowhere_on_the_page(
    bare_machine: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(Variable.KEY.value, KEY)
    page = to_settings(open_built(Builds(RoutedModel())))

    by_name = {r["Setting"]: r for r in settings_rows(page)}
    assert by_name[Variable.KEY.value]["Now"] == "set"
    assert by_name[Variable.KEY.value]["Default"] == "not set"
    assert KEY not in every_text(page)
    assert sorted(t.key for t in page.text_input) == sorted(input_key(v) for v in CHANGEABLE)


def test_each_setting_but_the_key_can_be_typed_from_its_value_now(bare_machine: Path) -> None:
    page = to_settings(open_built(Builds(RoutedModel())))

    for variable in CHANGEABLE:
        assert page.text_input(key=input_key(variable)).value == shown(ModelSettings(), variable)


def test_the_page_says_the_changes_last_for_this_tab_and_shows_the_data_folder(
    bare_machine: Path,
) -> None:
    page = to_settings(open_built(Builds(RoutedModel())))

    words = " ".join(str(c.value) for c in page.caption)
    assert "last for this browser tab only" in words
    assert "Nothing is written to a file or to the environment" in words
    folder = page.container(key=FOLDER_KEY)
    assert str(bare_machine) in str(folder.text[0].value)
    assert not page.chat_input


# --- V-4: a change reaches the next call to the model ------------------------------


def test_a_new_temperature_is_the_one_the_next_call_uses(bare_machine: Path) -> None:
    builds = Builds(RoutedModel(screen=[SPOT], extraction=[COMPLETE_ROWS]))
    page = apply(set_setting(to_settings(open_built(builds)), Variable.TEMPERATURE, "0.3"))

    assert settings_note(page) == (
        "success",
        "Applied: LEDGER_HAND_MODEL_TEMPERATURE is now 0.3. The next call to the model uses "
        "them, in this browser tab only.",
    )
    page = send(to_record(page), COMPLETE)

    assert not page.exception
    first, latest = builds.models[0], builds.models[-1]
    assert first.used == []
    assert latest.settings.temperature == 0.3
    assert [used.temperature for used in latest.used] == [0.3, 0.3]


def test_half_way_through_a_passage_the_next_question_uses_the_new_settings(
    bare_machine: Path,
) -> None:
    routed = RoutedModel(screen=[SPOT], extraction=[TWO_QUESTIONS_ROWS])
    builds = Builds(routed)
    page = send(open_built(builds), TWO_QUESTIONS)
    assert program_said(page)[-1].startswith("[Trade 1 of 1: fee] ")
    asked = len(routed.question_parameters)

    page = apply(set_setting(to_settings(page), Variable.QUESTION_TEMPERATURE, "0.2"))
    page = send(to_record(page), "1 USDT")

    assert not page.exception
    assert program_said(page)[-1].startswith("[Trade 1 of 1: time] ")
    worded = routed.question_parameters
    assert worded[0] is not None and worded[0].temperature == DEFAULT_QUESTION_TEMPERATURE
    assert [p.temperature for p in worded[asked:] if p is not None] == [0.2]


# --- V-5: refused changes; what is not changed stays -------------------------------


@pytest.mark.parametrize(
    ("variable", "text", "rule"),
    [
        (Variable.TEMPERATURE, "-1", "'-1' is not a plain number"),
        (Variable.TEMPERATURE, "abc", "'abc' is not a plain number"),
        (
            Variable.URL,
            "http://someone:invented@127.0.0.1:11434",
            "an address may not hold a user name or password",
        ),
    ],
)
def test_a_refused_change_names_the_setting_and_its_rule_and_changes_nothing(
    bare_machine: Path, variable: Variable, text: str, rule: str
) -> None:
    builds = Builds(RoutedModel())
    page = to_settings(open_built(builds))

    page = apply(set_setting(page, variable, text))

    assert not page.exception
    tone, words = settings_note(page)
    assert tone == "error"
    assert words.startswith(f"Not applied: {variable.value}: ")
    assert rule in words
    assert words.endswith("The settings were not changed.")
    assert settings_now(page) == ModelSettings()
    assert len(builds.built) == 1
    assert {r["Setting"]: r["Now"] for r in settings_rows(page)}[variable.value] == shown(
        ModelSettings(), variable
    )


def test_changing_the_temperature_leaves_the_address_and_the_key_of_the_environment(
    bare_machine: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(Variable.KEY.value, KEY)
    monkeypatch.setenv(Variable.URL.value, ADDRESS)
    builds = Builds(RoutedModel())
    page = to_settings(open_built(builds))
    before = settings_now(page)

    page = apply(set_setting(page, Variable.TEMPERATURE, "0.4"))

    after = settings_now(page)
    assert after.temperature == 0.4
    assert after.base_url == ADDRESS
    assert after.api_key == before.api_key
    assert after.api_key is not None and after.api_key.reveal() == KEY
    assert builds.models[-1].settings == after
    assert KEY not in every_text(page)


def test_a_blank_value_takes_the_default(
    bare_machine: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(Variable.TEMPERATURE.value, "0.6")
    page = to_settings(open_built(Builds(RoutedModel())))
    assert settings_now(page).temperature == 0.6

    page = apply(set_setting(page, Variable.TEMPERATURE, ""))

    assert settings_now(page).temperature == 0.0
    assert page.text_input(key=input_key(Variable.TEMPERATURE)).value == "0"


def test_back_to_the_environment_and_the_defaults_drops_every_change(
    bare_machine: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(Variable.URL.value, ADDRESS)
    page = to_settings(open_built(Builds(RoutedModel())))
    page = apply(set_setting(page, Variable.URL, "http://127.0.0.1:11434"))
    page = apply(set_setting(page, Variable.RETRIES, "0"))
    assert (settings_now(page).base_url, settings_now(page).retries) == (
        "http://127.0.0.1:11434",
        0,
    )

    page = reset(page)

    assert (settings_now(page).base_url, settings_now(page).retries) == (ADDRESS, 2)
    assert page.text_input(key=input_key(Variable.URL)).value == ADDRESS
    tone, words = settings_note(page)
    assert tone == "success"
    assert words.startswith("Back to the environment and the defaults: ")


def test_applying_without_a_change_says_so(bare_machine: Path) -> None:
    page = apply(to_settings(open_built(Builds(RoutedModel()))))

    assert settings_note(page) == ("info", "Nothing was changed: every value is as it was.")


# --- this tab only; nothing written ------------------------------------------------


def test_a_change_lasts_for_this_tab_only_and_is_written_nowhere(
    bare_machine: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(Variable.KEY.value, KEY)
    environment = dict(os.environ)
    files = sorted(tmp_path.rglob("*"))

    changed = apply(
        set_setting(to_settings(open_built(Builds(RoutedModel()))), Variable.TOP_P, "0.5")
    )
    assert settings_now(changed).top_p == 0.5
    another_tab = to_settings(open_built(Builds(RoutedModel())))

    assert settings_now(another_tab).top_p == 1.0
    assert dict(os.environ) == environment
    assert sorted(tmp_path.rglob("*")) == files


# --- a refused environment: the page still opens ------------------------------------


def test_with_a_refused_setting_in_the_environment_the_settings_page_still_opens(
    bare_machine: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(Variable.TEMPERATURE.value, "warm")

    page = to_settings(open_built(Builds(RoutedModel())))

    assert not page.exception
    (error,) = page.error
    assert error.value.startswith("The program cannot start: a setting was refused: ")
    assert Variable.TEMPERATURE.value in error.value
    assert "start the program again" in error.value
    rows = settings_rows(page)
    assert [r["Setting"] for r in rows] == [variable.value for variable in Variable]
    assert list(rows[0]) == ["Setting", "Default", "What it sets", "Why this default"]
    assert len(page.text_input) == 0
    assert len(page.button) == 0


# --- the key, through every page and every failure ----------------------------------


def test_the_key_appears_on_no_page_whatever_happens(
    bare_machine: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(Variable.KEY.value, KEY)
    monkeypatch.setenv(Variable.URL.value, ADDRESS)
    # Errors whose own words hold the key, which no plug lets through: still never shown.
    errors = [ModelError(kind, f"invented {KEY}", snippet=KEY) for kind in ModelErrorKind]
    page = open_built(Builds(RoutedModel(screen=errors)))
    seen = [every_text(page)]
    for _ in errors:
        page = send(page, COMPLETE)
        seen.append(every_text(page))
    page = to_settings(page)
    seen.append(every_text(page))
    # Typed into the address by mistake: the refusal does not repeat it; only the input,
    # which shows what was typed, holds it, and it is left out of what is looked through.
    typed = f"http://x:{KEY}@127.0.0.1"
    page = apply(set_setting(page, Variable.URL, typed))
    assert KEY not in settings_note(page)[1]
    seen.append(every_text(page).replace(typed, ""))
    page = apply(set_setting(page, Variable.TOP_P, "0.9"))
    page = apply(set_setting(page, Variable.URL, ADDRESS))
    seen.append(every_text(page))
    seen.append(every_text(reset(page)))

    assert all(KEY not in text for text in seen)
    # What is looked through holds the chat, the table and the inputs.
    assert "No model answered at" in seen[1]
    assert ABOUT[Variable.KEY].reason in seen[len(errors) + 1]
    assert ADDRESS in seen[len(errors) + 1]
    unreachable = [line for line in program_said(to_record(page)) if "No model answered" in line]
    assert unreachable and ADDRESS in unreachable[0]
    assert page.chat_input(key=INPUT_KEY) is not None
