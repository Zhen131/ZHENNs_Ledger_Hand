"""Tests of the setting that chooses the plug: local by default, cloud only when asked.

Reading the settings checks only the plug variable's own value: ``local`` or
``cloud``, nothing else, refused by name at reading. Whether the address and
the key fit a cloud service is not checked here but where the plug is built,
so a cloud plug with the local address, or without a key, is read without
complaint. Setting an address or a key never switches to the cloud by
itself. Every value is invented.
"""

from __future__ import annotations

import pytest

from ledger_hand.settings import (
    ABOUT,
    DEFAULT_BASE_URL,
    DEFAULT_PLUG,
    ModelSettings,
    Plug,
    SettingsError,
    Variable,
    apply_changes,
    load_model_settings,
)

KEY = "sk-invented-plug-0123456789"


def test_the_plug_is_local_by_default() -> None:
    assert DEFAULT_PLUG is Plug.LOCAL
    assert load_model_settings({}).plug is Plug.LOCAL
    assert ModelSettings().plug is Plug.LOCAL


def test_the_plugs_are_local_and_cloud() -> None:
    assert [plug.value for plug in Plug] == ["local", "cloud"]
    assert Variable.PLUG.value == "LEDGER_HAND_MODEL_PLUG"


@pytest.mark.parametrize(("text", "plug"), [("local", Plug.LOCAL), ("cloud", Plug.CLOUD)])
def test_each_plug_is_read_by_its_name(text: str, plug: Plug) -> None:
    assert load_model_settings({Variable.PLUG.value: text}).plug is plug
    assert load_model_settings({Variable.PLUG.value: f"  {text} "}).plug is plug


@pytest.mark.parametrize(
    "text", ["Cloud", "LOCAL", "remote", "openai", "ollama", "cloud,local", "1"]
)
def test_a_plug_misspelt_is_refused_by_name_when_the_settings_are_read(text: str) -> None:
    with pytest.raises(SettingsError) as refused:
        load_model_settings({Variable.PLUG.value: text})

    message = str(refused.value)
    assert message.startswith(f"{Variable.PLUG.value}: ")
    assert "local or cloud" in message


@pytest.mark.parametrize(
    "environ",
    [
        {Variable.PLUG.value: "cloud"},
        {Variable.PLUG.value: "cloud", Variable.URL.value: "http://192.0.2.7:8080/v1"},
        {Variable.PLUG.value: "cloud", Variable.URL.value: "https://api.example.com/v1"},
    ],
    ids=["the local address", "http off this machine", "no key"],
)
def test_a_cloud_plug_that_does_not_fit_its_address_or_key_is_still_read(
    environ: dict[str, str],
) -> None:
    loaded = load_model_settings(environ)

    assert loaded.plug is Plug.CLOUD


def test_an_address_or_a_key_alone_never_switches_to_the_cloud() -> None:
    loaded = load_model_settings(
        {Variable.URL.value: "https://api.example.com/v1", Variable.KEY.value: KEY}
    )

    assert loaded.plug is Plug.LOCAL


def test_the_plug_can_be_changed_on_the_settings_page_as_the_environment_reads_it() -> None:
    changed = apply_changes(ModelSettings(), {Variable.PLUG: "cloud"})

    assert changed.plug is Plug.CLOUD
    assert changed.base_url == DEFAULT_BASE_URL
    assert apply_changes(changed, {Variable.PLUG: ""}).plug is Plug.LOCAL


def test_a_plug_built_in_code_must_be_a_plug() -> None:
    with pytest.raises(SettingsError) as refused:
        ModelSettings(plug="cloud")  # type: ignore[arg-type]

    assert str(refused.value).startswith(f"{Variable.PLUG.value}: ")


def test_the_plug_says_what_it_sets_and_why_its_default() -> None:
    about = ABOUT[Variable.PLUG]

    assert about.field == "plug"
    assert "cloud" in about.sets and "local" in about.sets
    assert "nothing that is typed leaves it" in about.reason
    assert "only this does" in about.reason
