"""Tests of the deepseek plug's settings: one switch, its own key, a fixed address.

Only ``LEDGER_HAND_MODEL_PLUG`` switches to DeepSeek. Its address and model
are filled in where they were left at their defaults; another address is
refused where the plug is built, naming the address variable; its key is
read from ``DEEPSEEK_API_KEY`` alone, and neither key can be changed on the
settings page. Every value is invented.
"""

from __future__ import annotations

import pytest

from ledger_hand.llm.connect import check_plug
from ledger_hand.settings import (
    DEEPSEEK_ADDRESS,
    DEEPSEEK_MODEL,
    SERVICES,
    ModelSettings,
    Plug,
    ReplyFormat,
    Secret,
    SettingsError,
    Variable,
    apply_changes,
    effective_settings,
    every_key,
    key_in_use,
    key_variable,
    load_model_settings,
)

KEY = "sk-invented-deepseek-settings-0123456789"
GENERAL = "sk-invented-general-settings-0123456789"


def deepseek(**more: str) -> ModelSettings:
    return load_model_settings({Variable.PLUG.value: "deepseek", **more})


def test_the_service_row_holds_what_is_fixed() -> None:
    service = SERVICES[Plug.DEEPSEEK]

    assert (service.address, service.model) == ("https://api.deepseek.com", "deepseek-v4-pro")
    assert service.key is Variable.DEEPSEEK_KEY
    assert service.reply_format is ReplyFormat.JSON_OBJECT
    assert service.fields == {"thinking": {"type": "disabled"}}
    assert set(SERVICES) == {Plug.DEEPSEEK}


def test_only_the_plug_switches_to_deepseek() -> None:
    read = load_model_settings({Variable.DEEPSEEK_KEY.value: KEY})

    assert read.plug is Plug.LOCAL
    assert effective_settings(read) == read
    assert key_in_use(read) is None


def test_the_address_and_the_model_are_filled_in_once() -> None:
    read = deepseek(**{Variable.DEEPSEEK_KEY.value: KEY})

    settings = effective_settings(read)

    assert (settings.base_url, settings.model) == (DEEPSEEK_ADDRESS, DEEPSEEK_MODEL)
    assert effective_settings(settings) == settings
    check_plug(settings)


def test_a_model_named_is_kept() -> None:
    read = deepseek(**{Variable.DEEPSEEK_KEY.value: KEY, Variable.NAME.value: "deepseek-flash"})

    assert effective_settings(read).model == "deepseek-flash"


def test_each_plug_sends_its_own_key_and_both_are_hidden() -> None:
    read = deepseek(**{Variable.DEEPSEEK_KEY.value: KEY, Variable.KEY.value: GENERAL})

    assert key_in_use(read) == Secret(KEY)
    assert key_variable(read) is Variable.DEEPSEEK_KEY
    cloud = apply_changes(read, {Variable.PLUG: "cloud"})
    assert key_in_use(cloud) == Secret(GENERAL)
    assert key_variable(cloud) is Variable.KEY
    assert set(every_key(read)) == {Secret(KEY), Secret(GENERAL)}
    assert KEY not in repr(read) and GENERAL not in repr(read)


# --- S5: another address ---------------------------------------------------------


def test_another_address_is_refused_where_the_plug_is_built_naming_the_address() -> None:
    read = deepseek(
        **{Variable.DEEPSEEK_KEY.value: KEY, Variable.URL.value: "https://api.example.com/v1"}
    )
    settings = effective_settings(read)

    with pytest.raises(SettingsError) as caught:
        check_plug(settings)

    said = str(caught.value)
    assert said.startswith(f"{Variable.URL.value}: ")
    assert "https://api.deepseek.com" in said
    assert f"{Variable.PLUG.value} to cloud" in said


def test_deepseeks_own_address_written_out_is_taken() -> None:
    read = deepseek(**{Variable.DEEPSEEK_KEY.value: KEY, Variable.URL.value: DEEPSEEK_ADDRESS})

    check_plug(effective_settings(read))


# --- S6: no key ---------------------------------------------------------------------


def test_without_its_key_it_is_refused_naming_its_key_even_with_the_general_one() -> None:
    read = deepseek(**{Variable.KEY.value: GENERAL})

    with pytest.raises(SettingsError) as caught:
        check_plug(effective_settings(read))

    assert str(caught.value).startswith(f"{Variable.DEEPSEEK_KEY.value}: ")
    assert GENERAL not in str(caught.value)


# --- S21: neither key is changed on the page ------------------------------------------


@pytest.mark.parametrize("variable", [Variable.DEEPSEEK_KEY, Variable.KEY])
def test_neither_key_can_be_changed_on_the_page(variable: Variable) -> None:
    read = load_model_settings({})

    with pytest.raises(SettingsError) as caught:
        apply_changes(read, {Variable.PLUG: "deepseek", variable: KEY})

    assert str(caught.value).startswith(f"{variable.value}: the key is set in the environment")
    assert KEY not in str(caught.value)
    assert read == load_model_settings({})


def test_a_key_that_is_not_printable_is_refused_without_repeating_it() -> None:
    with pytest.raises(SettingsError) as caught:
        load_model_settings({Variable.DEEPSEEK_KEY.value: "sk invented with spaces"})

    assert str(caught.value).startswith(f"{Variable.DEEPSEEK_KEY.value}: ")
    assert "invented" not in str(caught.value)
