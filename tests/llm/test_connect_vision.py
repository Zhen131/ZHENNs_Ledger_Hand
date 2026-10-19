"""Tests of the plug that reads a screenshot, as the settings build it.

It is the local plug with the vision model in place of the model that
extracts; the address, the thinking setting, the time allowed and the
retries are the settings'. Settings that choose the cloud plug are refused
before anything is built or sent, naming the plug setting. Every name and
address here is invented.
"""

from __future__ import annotations

import dataclasses

import pytest

from ledger_hand.llm.connect import connect_vision_model
from ledger_hand.llm.retry import RetryingModel
from ledger_hand.ports import (
    Message,
    ModelError,
    ModelErrorKind,
    Picture,
    PictureKind,
    Role,
)
from ledger_hand.settings import Plug, SettingsError, Thinking
from tests.llm.fake_cloud import CLOUD_SETTINGS
from tests.llm.fake_server import SETTINGS, FakeServer, chat_reply, json_response

PICTURE = Picture(b"\xff\xd8\xff\xe0 invented", PictureKind.JPEG)
ASKED = [Message(Role.USER, "Read the invented card.")]
VISION = dataclasses.replace(
    SETTINGS,
    model="invented-text:7b",
    vision_model="invented-vl:8b",
    base_url="http://127.0.0.1:12345",
    think=Thinking.OFF,
    timeout_seconds=33.0,
    retries=1,
    retry_wait_seconds=0.5,
)


class Waits:
    def __init__(self) -> None:
        self.seconds: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.seconds.append(seconds)


def test_the_vision_model_is_asked_at_the_settings_address_with_their_thinking() -> None:
    server = FakeServer([json_response(200, chat_reply("Card: invented", model="invented-vl:8b"))])

    model = connect_vision_model(VISION, transport=server.transport)
    reply = model.chat_with_pictures(ASKED, [PICTURE])

    assert isinstance(model, RetryingModel)
    (request,) = server.requests
    assert str(request.url) == "http://127.0.0.1:12345/api/chat"
    body = server.sent_json()
    assert isinstance(body, dict)
    assert body["model"] == "invented-vl:8b"
    assert body["think"] is False
    assert request.extensions["timeout"]["read"] == 33.0
    assert reply.record.model == "invented-vl:8b"


def test_the_retries_are_the_settings() -> None:
    busy = json_response(503, {"error": "busy"})
    server = FakeServer([busy, json_response(200, chat_reply("Card: invented"))])
    waits = Waits()

    reply = connect_vision_model(
        VISION, transport=server.transport, sleep=waits
    ).chat_with_pictures(ASKED, [PICTURE])

    assert reply.text == "Card: invented"
    assert waits.seconds == [0.5]


def test_with_no_retries_in_the_settings_a_busy_server_is_said_at_once() -> None:
    server = FakeServer([json_response(503, {"error": "busy"})])
    waits = Waits()
    settings = dataclasses.replace(VISION, retries=0)

    with pytest.raises(ModelError) as caught:
        connect_vision_model(settings, transport=server.transport, sleep=waits).chat_with_pictures(
            ASKED, [PICTURE]
        )

    assert caught.value.kind is ModelErrorKind.SERVER_ERROR
    assert waits.seconds == []


def test_settings_that_choose_the_cloud_plug_are_refused_naming_the_plug_setting() -> None:
    server = FakeServer([])
    cloud = dataclasses.replace(CLOUD_SETTINGS, plug=Plug.CLOUD)

    with pytest.raises(SettingsError) as caught:
        connect_vision_model(cloud, transport=server.transport)

    said = str(caught.value)
    assert said.startswith("LEDGER_HAND_MODEL_PLUG is cloud")
    assert "local plug only" in said
    assert server.requests == []


def test_the_settings_must_be_settings() -> None:
    with pytest.raises(TypeError):
        connect_vision_model({"plug": "local"})  # type: ignore[arg-type]
