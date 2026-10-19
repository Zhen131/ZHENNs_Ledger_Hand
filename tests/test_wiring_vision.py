"""Tests of the two parts the wiring module builds for a screenshot: the vision model and its check.

With the local plug, the parts hold the vision model, built from the same
settings as the model (the settings page's changes among them), so that its
name, the thinking setting and the address are the settings'; and a way to
ask the server whether it has that model. With the cloud plug, neither is
built and the parts are built all the same. Building sends nothing, and the
model plug is built once. The check is the real one, with only the transport
fake: it asks for the vision model, not the model that extracts. Every
value here is invented.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest
import tzlocal

from ledger_hand import wiring
from ledger_hand.flows.uploading import VisionModelPresence
from ledger_hand.llm.connect import connect_vision_model
from ledger_hand.llm.ollama_identity import ask_identity
from ledger_hand.ports import (
    Message,
    ModelError,
    ModelErrorKind,
    ModelPort,
    Picture,
    PictureKind,
    Role,
)
from ledger_hand.settings import (
    DATA_DIRECTORY_VARIABLE,
    ENV_PREFIX,
    ModelSettings,
    Plug,
    Thinking,
    Variable,
)
from ledger_hand.wiring import assemble
from tests.llm.fake_server import FakeServer, chat_reply, json_response

KEY = "sk-invented-wiring-vision-0123456789"
CLOUD_ADDRESS = "https://api.example.com/v1"
PICTURE = Picture(b"\x89PNG\r\n\x1a\n invented", PictureKind.PNG)
ASKED = [Message(Role.USER, "Read the invented card.")]
FINGERPRINT = "a" * 64


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


class VisionPlugs:
    """Stands in for ``connect_vision_model``: the real one, but with a fake server behind it."""

    def __init__(self, server: FakeServer) -> None:
        self.server = server
        self.settings: list[ModelSettings] = []

    def __call__(self, settings: ModelSettings) -> ModelPort:
        self.settings.append(settings)
        return connect_vision_model(settings, transport=self.server.transport, sleep=lambda _: None)


@pytest.fixture
def vision_plugs(monkeypatch: pytest.MonkeyPatch) -> VisionPlugs:
    plugs = VisionPlugs(FakeServer([json_response(200, chat_reply("Side: buy"))]))
    monkeypatch.setattr(wiring, "connect_vision_model", plugs)
    return plugs


@pytest.fixture
def model_plugs(monkeypatch: pytest.MonkeyPatch) -> list[ModelSettings]:
    """The settings each model plug is built from, in order."""
    built: list[ModelSettings] = []
    real = wiring.connect_model

    def connect(settings: ModelSettings) -> ModelPort:
        built.append(settings)
        return real(settings)

    monkeypatch.setattr(wiring, "connect_model", connect)
    return built


# --- the local plug -------------------------------------------------------------


def test_the_local_plug_gives_a_vision_model_and_a_check(machine: Path) -> None:
    parts = assemble()

    assert parts.settings.plug is Plug.LOCAL
    assert parts.vision_model is not None
    assert callable(parts.vision_model.chat_with_pictures)
    assert callable(parts.vision_check)


def test_the_vision_model_is_built_from_the_settings_the_model_is_built_from(
    machine: Path, vision_plugs: VisionPlugs, model_plugs: list[ModelSettings]
) -> None:
    parts = assemble()

    (settings,) = vision_plugs.settings
    assert settings == parts.settings
    assert (model_plugs[-1], len(model_plugs)) == (parts.settings, 1)


def test_the_vision_model_reads_with_the_vision_name_and_the_thinking_setting(
    machine: Path, monkeypatch: pytest.MonkeyPatch, vision_plugs: VisionPlugs
) -> None:
    monkeypatch.setenv(Variable.THINK.value, "off")

    parts = assemble()
    assert parts.vision_model is not None
    reply = parts.vision_model.chat_with_pictures(ASKED, [PICTURE])

    assert reply.text == "Side: buy"
    sent = vision_plugs.server.sent_json()
    assert isinstance(sent, dict)
    assert sent["model"] == ModelSettings().vision_model
    assert sent["model"] != parts.settings.model
    assert sent["think"] is False


def test_a_change_on_the_settings_page_reaches_the_vision_model(
    machine: Path, vision_plugs: VisionPlugs, model_plugs: list[ModelSettings]
) -> None:
    parts = assemble({Variable.VISION_NAME: "invented-vision:3b", Variable.THINK: "on"})
    assert parts.vision_model is not None
    parts.vision_model.chat_with_pictures(ASKED, [PICTURE])

    (settings,) = vision_plugs.settings
    assert (settings.vision_model, settings.think) == ("invented-vision:3b", Thinking.ON)
    sent = vision_plugs.server.sent_json()
    assert isinstance(sent, dict)
    assert (sent["model"], sent["think"]) == ("invented-vision:3b", True)
    assert len(model_plugs) == 1


def test_building_them_sends_nothing(machine: Path, vision_plugs: VisionPlugs) -> None:
    assemble()

    assert vision_plugs.server.requests == []


def test_building_them_sends_nothing_through_the_real_transport_either(machine: Path) -> None:
    # The guard in conftest.py would fail the test on any connection.
    parts = assemble()

    assert parts.vision_model is not None


# --- the cloud plug ---------------------------------------------------------------


def test_the_cloud_plug_gives_neither_and_the_parts_are_built(
    machine: Path, monkeypatch: pytest.MonkeyPatch, vision_plugs: VisionPlugs
) -> None:
    monkeypatch.setenv(Variable.KEY.value, KEY)

    parts = assemble({Variable.PLUG: "cloud", Variable.URL: CLOUD_ADDRESS})

    assert parts.settings.plug is Plug.CLOUD
    assert (parts.vision_model, parts.vision_check) == (None, None)
    assert vision_plugs.settings == []


def test_a_cloud_chosen_in_the_environment_gives_neither(
    machine: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(Variable.PLUG.value, "cloud")
    monkeypatch.setenv(Variable.URL.value, CLOUD_ADDRESS)
    monkeypatch.setenv(Variable.KEY.value, KEY)

    parts = assemble()

    assert (parts.vision_model, parts.vision_check) == (None, None)


# --- the check, as the wiring module makes it ---------------------------------------


def tags(*names: str) -> httpx.Response:
    models = [{"name": name, "model": name, "digest": FINGERPRINT} for name in names]
    return json_response(200, {"models": models})


def with_server(monkeypatch: pytest.MonkeyPatch, server: FakeServer) -> list[ModelSettings]:
    """Has the wiring module's check ask ``server``; gives the settings it asked with."""
    asked: list[ModelSettings] = []

    def asking(settings: ModelSettings) -> object:
        asked.append(settings)
        return ask_identity(settings, transport=server.transport)

    monkeypatch.setattr(wiring, "ask_identity", asking)
    return asked


def checked(machine: Path, changes: dict[Variable, str] | None = None) -> Callable[[], object]:
    parts = assemble(changes)
    assert parts.vision_check is not None
    return parts.vision_check


def test_a_server_that_lists_the_vision_model_has_it(
    machine: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    server = FakeServer([json_response(200, {"version": "0.34.3"}), tags("qwen3-vl:8b")])
    asked = with_server(monkeypatch, server)

    assert checked(machine)() is VisionModelPresence.PRESENT
    (settings,) = asked
    assert settings.model == ModelSettings().vision_model
    assert [request.url.path for request in server.requests] == ["/api/version", "/api/tags"]


def test_a_server_that_lists_only_the_model_that_extracts_does_not_have_it(
    machine: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    server = FakeServer([json_response(200, {"version": "0.34.3"}), tags(ModelSettings().model)])
    with_server(monkeypatch, server)

    assert checked(machine)() is VisionModelPresence.MISSING


def test_the_vision_name_changed_on_the_page_is_the_one_asked_for(
    machine: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    server = FakeServer([json_response(200, {"version": "0.34.3"}), tags("invented-vision:3b")])
    asked = with_server(monkeypatch, server)

    assert checked(machine, {Variable.VISION_NAME: "invented-vision:3b"})() is (
        VisionModelPresence.PRESENT
    )
    assert asked[0].model == "invented-vision:3b"


def test_a_server_that_cannot_say_raises_its_error(
    machine: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    server = FakeServer([json_response(500, {"error": "invented trouble"})])
    with_server(monkeypatch, server)

    with pytest.raises(ModelError) as raised:
        checked(machine)()

    assert raised.value.kind is ModelErrorKind.SERVER_ERROR
    assert raised.value.status == 500


def test_asking_uses_the_real_ask_identity_by_default() -> None:
    assert wiring.ask_identity is ask_identity
