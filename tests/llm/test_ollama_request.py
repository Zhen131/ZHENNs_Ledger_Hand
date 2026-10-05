"""Tests of the body sent to Ollama's chat endpoint."""

from __future__ import annotations

import json

import pytest

from ledger_hand.llm.ollama_request import CHAT_PATH, OPTION_FIELDS, chat_body, encode
from ledger_hand.ports import Message, ModelParameters, Role

PARAMETERS = ModelParameters(
    temperature=0.3, top_p=0.95, max_reply_tokens=256, context_tokens=4096, timeout_seconds=60
)
MESSAGES = [Message(Role.USER, "两万三 at 9:40, an invented line")]


def test_the_endpoint_is_ollamas_own_chat() -> None:
    assert CHAT_PATH == "/api/chat"


def test_each_parameter_goes_into_the_option_ollama_reads() -> None:
    # Written out by hand from Ollama's documentation of the chat endpoint.
    assert OPTION_FIELDS == {
        "temperature": "temperature",
        "top_p": "top_p",
        "max_reply_tokens": "num_predict",
        "context_tokens": "num_ctx",
    }


def test_the_body_holds_the_model_messages_options_and_no_streaming() -> None:
    body = chat_body("qwen2.5:7b", MESSAGES, None, PARAMETERS)

    assert body == {
        "model": "qwen2.5:7b",
        "messages": [{"role": "user", "content": MESSAGES[0].content}],
        "stream": False,
        "options": {"temperature": 0.3, "top_p": 0.95, "num_predict": 256, "num_ctx": 4096},
    }


def test_a_schema_goes_into_format_as_the_same_object() -> None:
    schema = {"type": "object", "properties": {"b": {}, "a": {}}}

    body = chat_body("m", MESSAGES, schema, PARAMETERS)

    assert body["format"] is schema


def test_the_encoded_body_is_utf8_json_and_keeps_text_as_written() -> None:
    raw = encode(chat_body("m", MESSAGES, None, PARAMETERS))

    assert json.loads(raw.decode("utf-8"))["messages"][0]["content"] == MESSAGES[0].content
    assert "两万三".encode() in raw


@pytest.mark.parametrize(
    "body",
    [
        {"format": {1, 2}},
        {"x": float("nan")},
        {"x": float("inf")},
        {"x": object()},
        {"x": "\ud800"},
    ],
)
def test_a_body_that_cannot_be_written_as_json_is_refused(body: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="cannot be written as JSON"):
        encode(body)


def test_a_deeply_nested_schema_is_refused_not_crashed() -> None:
    nested: dict[str, object] = {}
    for _ in range(100_000):
        nested = {"a": nested}

    with pytest.raises(ValueError):
        encode({"format": nested})


@pytest.mark.parametrize(
    ("messages", "schema", "parameters", "error"),
    [
        ([], None, PARAMETERS, ValueError),
        ((), None, PARAMETERS, ValueError),
        ("text", None, PARAMETERS, TypeError),
        (b"bytes", None, PARAMETERS, TypeError),
        (None, None, PARAMETERS, TypeError),
        ([Message(Role.USER, "a"), "b"], None, PARAMETERS, TypeError),
        (MESSAGES, ["not", "a", "mapping"], PARAMETERS, TypeError),
        (MESSAGES, "json", PARAMETERS, TypeError),
        (MESSAGES, None, {"temperature": 0}, TypeError),
    ],
)
def test_a_call_in_the_wrong_shape_is_refused(
    messages: object, schema: object, parameters: object, error: type[Exception]
) -> None:
    with pytest.raises(error):
        chat_body("m", messages, schema, parameters)  # type: ignore[arg-type]
