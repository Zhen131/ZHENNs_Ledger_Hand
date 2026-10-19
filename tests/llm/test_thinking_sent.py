"""Tests of the thinking setting as the plugs send it.

The local plug sends Ollama's top-level ``think`` field as true for on and
false for off, with every call, with pictures or without, and leaves it out
for model, so that the body is then what it was before the setting was
there. The cloud plug never sends it, whatever the setting.
"""

from __future__ import annotations

import dataclasses

import pytest

from ledger_hand.llm.cloud import CloudModel
from ledger_hand.llm.ollama import OllamaModel
from ledger_hand.llm.ollama_request import THINK_VALUES, chat_body, picture_body
from ledger_hand.ports import Message, ModelParameters, Picture, PictureKind, Role
from ledger_hand.settings import Thinking
from tests.llm.fake_cloud import CLOUD_SETTINGS, completion
from tests.llm.fake_server import SETTINGS, FakeServer, chat_reply, json_response

ASKED = [Message(Role.USER, "Which fruit did the invented stall sell most?")]
PICTURE = Picture(b"\x89PNG\r\n\x1a\n invented", PictureKind.PNG)
SCHEMA = {"type": "object", "properties": {"fruit": {"type": "string"}}}
PARAMETERS = ModelParameters(
    temperature=0.0, top_p=1.0, max_reply_tokens=64, context_tokens=2048, timeout_seconds=5.0
)
SENT = {Thinking.ON: True, Thinking.OFF: False}


def local(thinking: Thinking, server: FakeServer) -> OllamaModel:
    return OllamaModel(dataclasses.replace(SETTINGS, think=thinking), transport=server.transport)


def sent(server: FakeServer, number: int = 0) -> dict[str, object]:
    body = server.sent_json(number)
    assert isinstance(body, dict)
    return body


def test_on_and_off_are_sent_as_true_and_false() -> None:
    assert THINK_VALUES == SENT
    assert Thinking.MODEL not in THINK_VALUES


@pytest.mark.parametrize("thinking", [Thinking.ON, Thinking.OFF])
def test_the_local_plug_sends_on_and_off_with_every_call(thinking: Thinking) -> None:
    server = FakeServer([json_response(200, chat_reply()) for _ in range(3)])
    model = local(thinking, server)

    model.chat(ASKED)
    model.chat(ASKED, reply_schema=SCHEMA, parameters=PARAMETERS)
    model.chat_with_pictures(ASKED, [PICTURE])

    for number in range(3):
        assert sent(server, number)["think"] is SENT[thinking]


def test_the_local_plug_sends_no_think_field_for_model() -> None:
    server = FakeServer([json_response(200, chat_reply()) for _ in range(3)])
    model = local(Thinking.MODEL, server)

    model.chat(ASKED)
    model.chat(ASKED, reply_schema=SCHEMA)
    model.chat_with_pictures(ASKED, [PICTURE])

    assert set(sent(server, 0)) == {"model", "messages", "stream", "options"}
    assert set(sent(server, 1)) == {"model", "messages", "stream", "options", "format"}
    assert set(sent(server, 2)) == {"model", "messages", "stream", "options"}


def test_for_model_the_body_is_the_bytes_it_is_without_the_setting() -> None:
    with_setting = chat_body("m", ASKED, SCHEMA, PARAMETERS, thinking=Thinking.MODEL)
    without = chat_body("m", ASKED, SCHEMA, PARAMETERS)

    assert with_setting == without
    assert list(with_setting) == ["model", "messages", "stream", "options", "format"]


@pytest.mark.parametrize("thinking", [Thinking.ON, Thinking.OFF])
def test_the_think_field_is_the_only_difference_it_makes(thinking: Thinking) -> None:
    for build in (
        lambda t: chat_body("m", ASKED, SCHEMA, PARAMETERS, thinking=t),
        lambda t: picture_body("m", ASKED, [PICTURE], PARAMETERS, thinking=t),
    ):
        thinking_body, plain = build(thinking), build(Thinking.MODEL)
        assert thinking_body.pop("think") is SENT[thinking]
        assert thinking_body == plain


@pytest.mark.parametrize("thinking", ["on", True, None])
def test_a_thinking_setting_that_is_not_one_is_refused(thinking: object) -> None:
    with pytest.raises(TypeError, match="thinking must be a Thinking"):
        chat_body("m", ASKED, None, PARAMETERS, thinking=thinking)  # type: ignore[arg-type]


@pytest.mark.parametrize("thinking", list(Thinking))
def test_the_cloud_plug_never_sends_a_think_field(thinking: Thinking) -> None:
    server = FakeServer([json_response(200, completion()) for _ in range(2)])
    settings = dataclasses.replace(CLOUD_SETTINGS, think=thinking)
    model = CloudModel(settings, transport=server.transport)

    model.chat(ASKED)
    model.chat(ASKED, reply_schema=SCHEMA, parameters=PARAMETERS)

    for number in range(2):
        body = sent(server, number)
        assert "think" not in body
        assert "thinking" not in body
        assert "think" not in server.requests[number].content.decode("utf-8")
