"""Tests of choosing the plug: the one the settings name, wrapped in retries, checked first.

The local plug is the default and takes the settings as they are. A cloud
plug is built only when the plug setting says so, and only when the
settings fit it: an address of its own, and off this machine https and a
key. Settings that do not fit are read without complaint and refused here,
naming the variable to set, without repeating the key. The fake transport
shows which plug was built: the local one asks ``/api/chat``, the cloud one
``/chat/completions``. Every value is invented.
"""

from __future__ import annotations

import dataclasses

import httpx
import pytest

from ledger_hand.llm.connect import LOOPBACK_HOSTS, check_plug, connect_model
from ledger_hand.llm.retry import RetryingModel
from ledger_hand.ports import Message, ModelError, ModelErrorKind, Role
from ledger_hand.settings import (
    DEFAULT_BASE_URL,
    ModelSettings,
    Plug,
    Secret,
    SettingsError,
    Variable,
    load_model_settings,
)
from tests.llm.fake_cloud import completion, error_body
from tests.llm.fake_server import FakeServer, chat_reply, json_response

KEY = "sk-invented-connect-0123456789"
HELLO = [Message(Role.USER, "Greet the invented baker.")]
CLOUD = {
    Variable.PLUG.value: "cloud",
    Variable.URL.value: "https://api.example.com/v1",
    Variable.KEY.value: KEY,
}


class Waits:
    """Stands in for sleeping: records each wait instead."""

    def __init__(self) -> None:
        self.seconds: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.seconds.append(seconds)


# --- V-8: settings read, then checked where the plug is built ------------------------


def test_by_default_the_local_plug_is_built() -> None:
    server = FakeServer([json_response(200, chat_reply("hello"))])

    model = connect_model(load_model_settings({}), transport=server.transport, sleep=Waits())

    assert model.chat(HELLO).text == "hello"
    assert server.requests[0].url.path == "/api/chat"
    assert str(server.requests[0].url).startswith(DEFAULT_BASE_URL)


@pytest.mark.parametrize(
    ("environ", "variable", "rule"),
    [
        (
            {Variable.PLUG.value: "cloud"},
            Variable.URL,
            "the cloud plug needs the address of the service",
        ),
        (
            {Variable.PLUG.value: "cloud", Variable.URL.value: "http://192.0.2.7:8080/v1"},
            Variable.URL,
            "must start with https://",
        ),
        (
            {Variable.PLUG.value: "cloud", Variable.URL.value: "https://api.example.com/v1"},
            Variable.KEY,
            "the cloud plug needs a key",
        ),
    ],
    ids=["the local address", "http off this machine", "no key"],
)
def test_a_cloud_plug_that_does_not_fit_is_read_then_refused_where_it_is_built(
    environ: dict[str, str], variable: Variable, rule: str
) -> None:
    settings = load_model_settings(environ)
    server = FakeServer([])

    with pytest.raises(SettingsError) as refused:
        connect_model(settings, transport=server.transport, sleep=Waits())

    message = str(refused.value)
    assert message.startswith(f"{variable.value}: ")
    assert rule in message
    assert server.requests == []


def test_the_refusal_with_a_key_set_does_not_repeat_it() -> None:
    environ = {**CLOUD, Variable.URL.value: "http://192.0.2.7:8080/v1"}

    with pytest.raises(SettingsError) as refused:
        check_plug(load_model_settings(environ))

    assert KEY not in str(refused.value)
    assert "sk-invented" not in str(refused.value)


def test_a_plug_misspelt_is_refused_already_when_the_settings_are_read() -> None:
    with pytest.raises(SettingsError, match=Variable.PLUG.value):
        load_model_settings({**CLOUD, Variable.PLUG.value: "clowd"})


@pytest.mark.parametrize(
    "address",
    ["http://127.0.0.1:8080/v1", "http://localhost:1234/v1", "http://[::1]:8000/v1"],
)
def test_a_cloud_plug_on_this_machine_needs_neither_https_nor_a_key(address: str) -> None:
    settings = load_model_settings({Variable.PLUG.value: "cloud", Variable.URL.value: address})

    check_plug(settings)


def test_a_cloud_plug_with_https_and_a_key_fits() -> None:
    check_plug(load_model_settings(CLOUD))


def test_the_local_plug_takes_any_address_and_no_key() -> None:
    settings = load_model_settings({Variable.URL.value: "http://192.0.2.7:8080"})

    check_plug(settings)
    assert settings.plug is Plug.LOCAL


def test_the_names_of_this_machine_are_these_three() -> None:
    assert frozenset({"127.0.0.1", "localhost", "::1"}) == LOOPBACK_HOSTS


def test_settings_that_are_not_settings_are_a_mistake_of_the_caller() -> None:
    with pytest.raises(TypeError):
        check_plug({"plug": "cloud"})  # type: ignore[arg-type]


# --- V-9: the right plug, wrapped in retries ------------------------------------------


@pytest.mark.parametrize(
    ("environ", "path", "answer"),
    [
        ({}, "/api/chat", json_response(200, chat_reply("from the plug"))),
        (CLOUD, "/v1/chat/completions", json_response(200, completion("from the plug"))),
    ],
    ids=["local", "cloud"],
)
def test_the_plug_chosen_is_built_and_wrapped_in_retries(
    environ: dict[str, str], path: str, answer: httpx.Response
) -> None:
    settings = dataclasses.replace(load_model_settings(environ), retry_wait_seconds=0.5)
    busy = json_response(503, {"error": "busy"})
    server = FakeServer([busy, answer])
    waits = Waits()

    model = connect_model(settings, transport=server.transport, sleep=waits)

    assert isinstance(model, RetryingModel)
    assert model.chat(HELLO).text == "from the plug"
    assert [request.url.path for request in server.requests] == [path, path]
    assert waits.seconds == [0.5]


def test_the_cloud_plug_sends_the_key_as_a_bearer_token() -> None:
    server = FakeServer([json_response(200, completion())])

    connect_model(load_model_settings(CLOUD), transport=server.transport, sleep=Waits()).chat(HELLO)

    assert server.requests[0].headers["authorization"] == f"Bearer {KEY}"
    assert str(server.requests[0].url) == "https://api.example.com/v1/chat/completions"


def test_the_assembled_cloud_plug_waits_as_a_429_asks_and_does_not_retry_a_refused_key() -> None:
    settings = load_model_settings(CLOUD)
    limited = httpx.Response(
        429, headers={"Retry-After": "2"}, content=b'{"error": {"message": "slow down"}}'
    )
    refused = json_response(401, error_body("Incorrect API key provided"))
    server = FakeServer([limited, refused, json_response(200, completion("never"))])
    waits = Waits()

    with pytest.raises(ModelError) as caught:
        connect_model(settings, transport=server.transport, sleep=waits).chat(HELLO)

    assert caught.value.kind is ModelErrorKind.SERVER_ERROR
    assert caught.value.status == 401
    assert waits.seconds == [2.0]
    assert len(server.requests) == 2


@pytest.mark.parametrize("environ", [{}, CLOUD], ids=["local", "cloud"])
def test_building_either_plug_sends_nothing(environ: dict[str, str]) -> None:
    server = FakeServer([])

    connect_model(load_model_settings(environ), transport=server.transport, sleep=Waits())

    assert server.requests == []


def test_settings_built_in_code_are_checked_the_same_way() -> None:
    settings = ModelSettings(plug=Plug.CLOUD, base_url="https://api.example.com/v1")

    with pytest.raises(SettingsError, match=Variable.KEY.value):
        connect_model(settings)
    connect_model(dataclasses.replace(settings, api_key=Secret(KEY)))
