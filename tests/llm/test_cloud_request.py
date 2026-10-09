"""Tests of what the cloud plug sends: where, with which key, and the body.

Each call goes to ``<address>/chat/completions`` with the key as a bearer
token; the body holds the model, the messages, the three sampling
parameters an OpenAI-style endpoint takes and, with a reply schema, a strict
``response_format``. How much the model reads at once, and how long this
side waits, are never sent. Every value is invented; the fake transport
keeps everything in the process.
"""

from __future__ import annotations

import dataclasses
import json

import pytest

from ledger_hand.llm.cloud import CloudModel
from ledger_hand.llm.cloud_request import CHAT_PATH, PARAMETER_FIELDS, SCHEMA_NAME, chat_body
from ledger_hand.ports import Message, ModelParameters, Role
from tests.llm.fake_cloud import ADDRESS, CLOUD_SETTINGS, KEY, MODEL, completion
from tests.llm.fake_server import FakeServer, json_response

QUESTION = [
    Message(Role.SYSTEM, "You answer about an invented fruit stall."),
    Message(Role.USER, "两万三 apples were sold at the invented stall. Which fruit?"),
]
SCHEMA = {
    "type": "object",
    "properties": {"fruit": {"type": "string"}},
    "required": ["fruit"],
    "additionalProperties": False,
}
UNUSUAL = ModelParameters(
    temperature=0.7, top_p=0.8, max_reply_tokens=77, context_tokens=3333, timeout_seconds=9.5
)


def sent(reply_schema: object = SCHEMA, parameters: ModelParameters | None = None) -> FakeServer:
    server = FakeServer([json_response(200, completion())])
    CloudModel(CLOUD_SETTINGS, transport=server.transport).chat(
        QUESTION,
        reply_schema=reply_schema,  # type: ignore[arg-type]
        parameters=parameters,
    )
    return server


def test_the_endpoint_is_the_openai_style_chat() -> None:
    assert CHAT_PATH == "/chat/completions"


def test_each_parameter_goes_into_the_field_such_an_endpoint_reads() -> None:
    # Written out by hand from the chat endpoint's documentation.
    assert PARAMETER_FIELDS == {
        "temperature": "temperature",
        "top_p": "top_p",
        "max_reply_tokens": "max_tokens",
    }


def test_the_call_goes_to_the_address_and_path_with_the_key_as_a_bearer_token() -> None:
    server = sent()

    (request,) = server.requests
    assert request.method == "POST"
    assert str(request.url) == f"{ADDRESS}/chat/completions"
    assert request.headers["authorization"] == f"Bearer {KEY}"
    assert request.headers["content-type"] == "application/json"
    assert KEY not in str(request.url)
    assert KEY.encode() not in request.content


def test_the_body_holds_every_field_and_the_strict_schema_and_nothing_else() -> None:
    body = sent(parameters=UNUSUAL).sent_json()

    assert body == {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": QUESTION[0].content},
            {"role": "user", "content": QUESTION[1].content},
        ],
        "temperature": 0.7,
        "top_p": 0.8,
        "max_tokens": 77,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": SCHEMA_NAME, "schema": SCHEMA, "strict": True},
        },
    }


def test_how_much_the_model_reads_at_once_and_the_time_allowed_are_never_sent() -> None:
    raw = sent(parameters=UNUSUAL).requests[0].content.decode("utf-8")

    for never in ("num_ctx", "context", "3333", "timeout", "9.5", "options", "stream"):
        assert never not in raw


def test_without_parameters_the_settings_defaults_are_sent() -> None:
    settings = dataclasses.replace(CLOUD_SETTINGS, temperature=0.2, top_p=0.9, max_reply_tokens=55)
    server = FakeServer([json_response(200, completion())])

    CloudModel(settings, transport=server.transport).chat(QUESTION)

    body = server.sent_json()
    assert isinstance(body, dict)
    assert (body["temperature"], body["top_p"], body["max_tokens"]) == (0.2, 0.9, 55)


def test_without_a_schema_no_response_format_is_sent() -> None:
    body = sent(reply_schema=None).sent_json()

    assert isinstance(body, dict)
    assert "response_format" not in body


def test_text_is_sent_as_written() -> None:
    raw = sent().requests[0].content

    assert "两万三".encode() in raw
    assert json.loads(raw)["messages"][1]["content"] == QUESTION[1].content


def test_the_schema_object_is_put_in_as_it_is() -> None:
    body = chat_body(MODEL, QUESTION, SCHEMA, UNUSUAL)

    response_format = body["response_format"]
    assert isinstance(response_format, dict)
    assert response_format["json_schema"]["schema"] is SCHEMA


@pytest.mark.parametrize(
    ("messages", "schema"),
    [
        ([], None),
        ("hello", None),
        (["hello"], None),
        (QUESTION, ["not", "a", "mapping"]),
        (QUESTION, {"a": {1, 2}}),
        (QUESTION, {"a": float("nan")}),
    ],
)
def test_a_call_in_the_wrong_shape_is_refused_before_sending(
    messages: object, schema: object
) -> None:
    server = FakeServer([])

    with pytest.raises((TypeError, ValueError)):
        CloudModel(CLOUD_SETTINGS, transport=server.transport).chat(
            messages,  # type: ignore[arg-type]
            reply_schema=schema,  # type: ignore[arg-type]
        )
    assert server.requests == []


def test_building_the_plug_sends_nothing() -> None:
    server = FakeServer([])

    CloudModel(CLOUD_SETTINGS, transport=server.transport)

    assert server.requests == []


def test_the_plug_itself_does_not_show_the_key() -> None:
    plug = CloudModel(CLOUD_SETTINGS)

    assert KEY not in repr(plug)
    assert KEY not in repr(vars(plug))


def test_settings_that_are_not_settings_are_refused() -> None:
    with pytest.raises(TypeError):
        CloudModel({"base_url": ADDRESS})  # type: ignore[arg-type]
