"""Tests of the local plug end to end, against a fake Ollama server.

A normal reply comes back with its record; the schema and every parameter
reach the field Ollama reads them from; each of the six kinds of failure is
recognised; one try per call.
"""

from __future__ import annotations

import dataclasses

import httpx
import pytest

from ledger_hand.llm.ollama import OllamaModel, parameters_from
from ledger_hand.llm.ollama_request import CHAT_PATH, OPTION_FIELDS
from ledger_hand.ports import (
    FinishReason,
    Message,
    ModelError,
    ModelErrorKind,
    ModelParameters,
    ModelPort,
    Role,
)
from ledger_hand.settings import DEFAULT_MODEL, ModelSettings, Secret
from tests.llm.fake_server import SETTINGS, FakeClock, FakeServer, Pieces, chat_reply, json_response

QUESTION = [
    Message(Role.SYSTEM, "You answer about an invented fruit stall."),
    Message(Role.USER, "The stall sold 3 apples and 2 pears. Which fruit sold more?"),
]
SCHEMA = {
    "type": "object",
    "properties": {"fruit": {"type": "string"}, "count": {"type": "integer"}},
    "required": ["fruit", "count"],
}
UNUSUAL = ModelParameters(
    temperature=0.7, top_p=0.8, max_reply_tokens=77, context_tokens=3333, timeout_seconds=9.5
)


def plug(server: FakeServer, clock: FakeClock | None = None) -> OllamaModel:
    if clock is None:
        return OllamaModel(SETTINGS, transport=server.transport)
    return OllamaModel(SETTINGS, transport=server.transport, clock=clock)


def fails_as(server: FakeServer) -> ModelError:
    with pytest.raises(ModelError) as caught:
        plug(server).chat(QUESTION)
    return caught.value


# --- a normal reply ---------------------------------------------------------


def test_a_normal_reply_comes_back_with_its_text_and_record() -> None:
    server = FakeServer([json_response(200, chat_reply('{"fruit": "apple", "count": 3}'))])
    clock = FakeClock(step=1.25)

    reply = plug(server, clock).chat(QUESTION)

    assert reply.text == '{"fruit": "apple", "count": 3}'
    assert reply.record.model == DEFAULT_MODEL
    assert reply.record.prompt_tokens == 44
    assert reply.record.reply_tokens == 14
    assert reply.record.finish is FinishReason.STOPPED
    assert reply.record.elapsed_seconds > 0


def test_the_time_spent_is_measured_from_sending_to_the_whole_answer() -> None:
    server = FakeServer([json_response(200, chat_reply())])
    clock = FakeClock(step=0.5)

    reply = plug(server, clock).chat(QUESTION)

    # The clock is read once at the start, and then by the exchange and at the end.
    assert reply.record.elapsed_seconds == pytest.approx(0.5 * (clock.reads - 1))


def test_a_reply_cut_off_at_the_length_limit_says_so() -> None:
    server = FakeServer([json_response(200, chat_reply('{"fruit": "app', done_reason="length"))])

    reply = plug(server).chat(QUESTION)

    assert reply.text == '{"fruit": "app'
    assert reply.record.finish is FinishReason.LENGTH_LIMIT


def test_the_plug_fits_the_model_port() -> None:
    server = FakeServer([json_response(200, chat_reply("hello"))])
    model: ModelPort = plug(server)

    assert model.chat([Message(Role.USER, "hi")]).text == "hello"


# --- what is sent -----------------------------------------------------------


def test_the_request_goes_to_the_chat_endpoint_as_json() -> None:
    server = FakeServer([json_response(200, chat_reply())])

    plug(server).chat(QUESTION)

    (request,) = server.requests
    assert request.method == "POST"
    assert str(request.url) == SETTINGS.base_url + CHAT_PATH
    assert request.headers["content-type"] == "application/json"
    assert "authorization" not in request.headers


def test_the_schema_arrives_as_it_was_given_and_every_parameter_in_its_field() -> None:
    server = FakeServer([json_response(200, chat_reply())])

    plug(server).chat(QUESTION, reply_schema=SCHEMA, parameters=UNUSUAL)

    sent = server.sent_json()
    assert isinstance(sent, dict)
    assert sent["format"] == SCHEMA
    assert list(sent["format"]) == list(SCHEMA)
    assert sent["options"] == {"temperature": 0.7, "top_p": 0.8, "num_predict": 77, "num_ctx": 3333}
    assert sent["model"] == DEFAULT_MODEL
    assert sent["stream"] is False
    assert sent["messages"] == [
        {"role": "system", "content": QUESTION[0].content},
        {"role": "user", "content": QUESTION[1].content},
    ]
    assert set(sent) == {"model", "messages", "stream", "options", "format"}


def test_the_time_allowed_is_not_sent_but_used_on_this_side() -> None:
    server = FakeServer([json_response(200, chat_reply())])

    plug(server).chat(QUESTION, parameters=UNUSUAL)

    sent_text = server.requests[0].content.decode("utf-8")
    assert "9.5" not in sent_text
    assert "timeout" not in sent_text
    assert server.requests[0].extensions["timeout"] == {
        "connect": 9.5,
        "read": 9.5,
        "write": 9.5,
        "pool": 9.5,
    }


def test_every_parameter_is_either_sent_or_is_the_time_allowed() -> None:
    names = {parameter.name for parameter in dataclasses.fields(ModelParameters)}

    assert names == set(OPTION_FIELDS) | {"timeout_seconds"}
    assert "timeout_seconds" not in OPTION_FIELDS


def test_without_parameters_the_defaults_from_the_settings_are_sent() -> None:
    settings = ModelSettings(temperature=0.4, top_p=0.6, max_reply_tokens=12, context_tokens=34)
    server = FakeServer([json_response(200, chat_reply())])

    OllamaModel(settings, transport=server.transport).chat(QUESTION)

    sent = server.sent_json()
    assert isinstance(sent, dict)
    assert sent["options"] == {"temperature": 0.4, "top_p": 0.6, "num_predict": 12, "num_ctx": 34}
    assert "format" not in sent
    assert server.requests[0].extensions["timeout"]["read"] == settings.timeout_seconds


def test_the_defaults_are_the_parameters_the_settings_name() -> None:
    assert OllamaModel(SETTINGS).defaults == parameters_from(SETTINGS)


def test_a_key_in_the_settings_is_sent_as_a_bearer_token() -> None:
    settings = ModelSettings(api_key=Secret("invented-key-123"))
    server = FakeServer([json_response(200, chat_reply())])

    OllamaModel(settings, transport=server.transport).chat(QUESTION)

    assert server.requests[0].headers["authorization"] == "Bearer invented-key-123"


@pytest.mark.parametrize(
    ("messages", "error"),
    [
        ([], ValueError),
        ("hello", TypeError),
        ([{"role": "user", "content": "hi"}], TypeError),
        ([Message(Role.USER, "bad \ud800 text")], ValueError),
    ],
)
def test_a_call_that_cannot_be_sent_is_refused_before_sending(
    messages: object, error: type[Exception]
) -> None:
    server = FakeServer([])

    with pytest.raises(error):
        plug(server).chat(messages)  # type: ignore[arg-type]
    assert server.requests == []


@pytest.mark.parametrize("schema", [{"a": {1, 2}}, {"a": float("nan")}, ["not", "a", "mapping"]])
def test_a_schema_that_is_not_plain_json_is_refused_before_sending(schema: object) -> None:
    server = FakeServer([])

    with pytest.raises((TypeError, ValueError)):
        plug(server).chat(QUESTION, reply_schema=schema)  # type: ignore[arg-type]
    assert server.requests == []


# --- the six kinds of failure -----------------------------------------------

SIX_KINDS = [
    pytest.param(
        httpx.ConnectError("[Errno 61] Connection refused"),
        ModelErrorKind.UNREACHABLE,
        id="connection refused",
    ),
    pytest.param(
        httpx.ConnectError("[Errno 8] nodename nor servname provided, or not known"),
        ModelErrorKind.UNREACHABLE,
        id="name does not resolve",
    ),
    pytest.param(httpx.ReadTimeout("timed out"), ModelErrorKind.TIMED_OUT, id="read timeout"),
    pytest.param(httpx.ConnectTimeout("timed out"), ModelErrorKind.TIMED_OUT, id="connect timeout"),
    pytest.param(
        json_response(404, {"error": 'model "qwen9:1b" not found, try pulling it first'}),
        ModelErrorKind.MODEL_NOT_FOUND,
        id="no such model",
    ),
    pytest.param(
        json_response(429, {"error": "too many requests"}),
        ModelErrorKind.RATE_LIMITED,
        id="too many requests",
    ),
    pytest.param(
        json_response(500, {"error": "llama runner process has terminated"}),
        ModelErrorKind.SERVER_ERROR,
        id="internal error",
    ),
    pytest.param(
        json_response(503, {"error": "server busy, please try again"}),
        ModelErrorKind.SERVER_ERROR,
        id="server busy",
    ),
    pytest.param(
        httpx.Response(200, content=b"<html>"), ModelErrorKind.MALFORMED_REPLY, id="not json"
    ),
    pytest.param(json_response(200, {}), ModelErrorKind.MALFORMED_REPLY, id="no message"),
    pytest.param(
        json_response(200, chat_reply("")), ModelErrorKind.MALFORMED_REPLY, id="empty reply"
    ),
]


@pytest.mark.parametrize(("step", "kind"), SIX_KINDS)
def test_each_failure_is_sorted_into_its_kind(
    step: httpx.Response | Exception, kind: ModelErrorKind
) -> None:
    server = FakeServer([step])

    assert fails_as(server).kind is kind
    assert len(server.requests) == 1


def test_every_kind_has_a_case() -> None:
    kinds = {case.values[1] for case in SIX_KINDS}

    assert kinds == set(ModelErrorKind)


def test_an_unreachable_server_is_named_in_the_message() -> None:
    error = fails_as(FakeServer([httpx.ConnectError("[Errno 61] Connection refused")]))

    assert str(error).startswith("unreachable: cannot reach the model server at ")
    assert SETTINGS.base_url in str(error)
    assert "Connection refused" in str(error)


def test_a_failure_nothing_recognises_is_a_server_error_with_the_raw_status() -> None:
    error = fails_as(FakeServer([httpx.Response(418, content=b"I'm a teapot")]))

    assert error.kind is ModelErrorKind.SERVER_ERROR
    assert error.status == 418
    assert error.snippet == "I'm a teapot"
    assert "does not expect" in error.message


def test_a_connection_that_breaks_off_mid_answer_is_a_server_error() -> None:
    broken = Pieces([b'{"message": {"con'], then=httpx.RemoteProtocolError("peer closed"))
    error = fails_as(FakeServer([httpx.Response(200, stream=broken)]))

    assert error.kind is ModelErrorKind.SERVER_ERROR
    assert "RemoteProtocolError" in error.message


def test_an_answer_still_trickling_in_after_the_time_allowed_is_abandoned() -> None:
    trickle = Pieces([b" "] * 1000)
    server = FakeServer([httpx.Response(200, stream=trickle)])
    clock = FakeClock(step=1.0)
    parameters = dataclasses.replace(UNUSUAL, timeout_seconds=5)

    with pytest.raises(ModelError) as caught:
        plug(server, clock).chat(QUESTION, parameters=parameters)

    assert caught.value.kind is ModelErrorKind.TIMED_OUT
    assert "within 5 seconds" in caught.value.message
    assert clock.reads < 20
