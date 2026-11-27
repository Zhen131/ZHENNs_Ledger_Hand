"""Tests of what the deepseek plug sends, and how it reads what comes back.

With the deepseek plug, a call goes to DeepSeek's own address with its own
key, asks for a JSON object rather than the table, and turns thinking off;
the cloud plug, at an address you set, sends as it always did. A model named
is asked as named. Every value is invented and nothing leaves the process.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Iterator

import httpx
import pytest

from ledger_hand.llm.cloud import CloudModel, forget_dropped_formats, reply_format_now
from ledger_hand.llm.connect import check_plug, connect_model
from ledger_hand.ports import Message, ModelError, ModelErrorKind, Role
from ledger_hand.settings import (
    DEEPSEEK_ADDRESS,
    DEEPSEEK_MODEL,
    ModelSettings,
    Plug,
    ReplyFormat,
    Secret,
    SettingsError,
    Thinking,
    Variable,
)
from tests.llm.fake_cloud import CLOUD_SETTINGS, completion, error_body
from tests.llm.fake_deepseek import GENERAL_KEY, KEY, deepseek_settings, sent_body
from tests.llm.fake_server import FakeServer, json_response

HELLO = [Message(Role.SYSTEM, "Reply with a JSON object."), Message(Role.USER, "hello")]
TABLE = {"type": "object", "properties": {"fruit": {"type": "string"}}, "required": ["fruit"]}
# DeepSeek's words when the prompt lacks the word, as its documents describe them.
NO_JSON_WORD = "Prompt must contain the word 'json' in some form to use 'response_format'"


@pytest.fixture(autouse=True)
def every_service_asks_its_own_way() -> Iterator[None]:
    forget_dropped_formats()
    yield
    forget_dropped_formats()


def one_call(settings: ModelSettings, *answers: object) -> FakeServer:
    steps = [json_response(200, completion())] if not answers else list(answers)
    server = FakeServer(steps)  # type: ignore[arg-type]
    CloudModel(settings, transport=server.transport).chat(HELLO, reply_schema=TABLE)
    return server


# --- S2: where it goes and what it holds ---------------------------------------


def test_a_call_with_a_table_goes_to_deepseek_asking_for_a_json_object() -> None:
    (sent,) = one_call(deepseek_settings()).requests

    body = sent_body(sent)
    assert str(sent.url) == "https://api.deepseek.com/chat/completions"
    assert sent.headers["authorization"] == f"Bearer {KEY}"
    assert body["model"] == "deepseek-v4-pro"
    assert body["thinking"] == {"type": "disabled"}
    assert body["response_format"] == {"type": "json_object"}
    assert "json_schema" not in sent.content.decode("utf-8")
    assert list(body) == [
        "model",
        "messages",
        "temperature",
        "top_p",
        "max_tokens",
        "response_format",
        "thinking",
    ]


def test_a_call_without_a_table_sends_no_response_format_but_still_turns_thinking_off() -> None:
    server = FakeServer([json_response(200, completion("hi"))])

    CloudModel(deepseek_settings(), transport=server.transport).chat(HELLO)

    body = sent_body(server.requests[0])
    assert "response_format" not in body
    assert body["thinking"] == {"type": "disabled"}


def test_the_effective_settings_fill_in_the_address_and_the_model() -> None:
    settings = deepseek_settings()

    assert (settings.base_url, settings.model) == (DEEPSEEK_ADDRESS, DEEPSEEK_MODEL)


# --- S4: a model named is asked as named ---------------------------------------


@pytest.mark.parametrize("model", ["deepseek-flash", "qwen2.5:7b"])
def test_a_model_named_is_asked_as_named(model: str) -> None:
    named = deepseek_settings(model="deepseek-flash") if model == "deepseek-flash" else None
    settings = named or dataclasses.replace(deepseek_settings(), model=model)

    (sent,) = one_call(settings).requests

    assert sent_body(sent)["model"] == model


# --- S7: the cloud plug at an address you set, as before ------------------------


def test_the_cloud_plug_sends_as_before_with_the_general_key() -> None:
    settings = dataclasses.replace(
        CLOUD_SETTINGS, plug=Plug.CLOUD, deepseek_key=Secret("sk-invented-other-0123456789ab")
    )

    (sent,) = one_call(settings).requests

    body = sent_body(sent)
    assert body["response_format"]["type"] == "json_schema"  # type: ignore[index]
    assert body["response_format"]["json_schema"]["strict"] is True  # type: ignore[index]
    assert "thinking" not in body
    assert sent.headers["authorization"] == f"Bearer {CLOUD_SETTINGS.api_key.reveal()}"  # type: ignore[union-attr]


def test_the_general_key_is_never_sent_to_deepseek() -> None:
    settings = deepseek_settings(api_key=Secret(GENERAL_KEY))

    (sent,) = one_call(settings).requests

    assert GENERAL_KEY not in sent.headers["authorization"]
    assert GENERAL_KEY.encode() not in sent.content


# --- S17: blank lines before the answer ---------------------------------------------


def test_blank_lines_before_the_answer_are_read_past() -> None:
    body = b"\n\n\n\n" + json.dumps(completion()).encode("utf-8")
    server = FakeServer([httpx.Response(200, content=body)])

    reply = CloudModel(deepseek_settings(), transport=server.transport).chat(HELLO)

    assert reply.text == '{"fruit": "apple"}'


# --- S19: thinking ---------------------------------------------------------------


def test_thinking_on_is_refused_naming_the_variable() -> None:
    with pytest.raises(SettingsError) as caught:
        check_plug(deepseek_settings(think=Thinking.ON))
    with pytest.raises(SettingsError):
        connect_model(deepseek_settings(think=Thinking.ON))

    assert str(caught.value).startswith(f"{Variable.THINK.value}: ")


@pytest.mark.parametrize("think", [Thinking.MODEL, Thinking.OFF])
def test_thinking_model_or_off_still_turns_thinking_off(think: Thinking) -> None:
    (sent,) = one_call(deepseek_settings(think=think)).requests

    assert sent_body(sent)["thinking"] == {"type": "disabled"}
    assert "think" not in sent_body(sent)


# --- S20: a prompt without the word json --------------------------------------------


def test_a_refusal_for_want_of_the_word_json_drops_the_json_object_for_good() -> None:
    server = FakeServer(
        [
            json_response(400, error_body(NO_JSON_WORD, kind="invalid_request_error")),
            json_response(200, completion()),
            json_response(200, completion()),
            json_response(200, completion()),
        ]
    )
    model = CloudModel(deepseek_settings(), transport=server.transport)

    first = model.chat(HELLO, reply_schema=TABLE)
    for _ in range(2):
        model.chat(HELLO, reply_schema=TABLE)

    assert first.text == '{"fruit": "apple"}'
    bodies = [sent_body(request) for request in server.requests]
    assert bodies[0]["response_format"] == {"type": "json_object"}
    assert all("response_format" not in body for body in bodies[1:])
    assert all(body["thinking"] == {"type": "disabled"} for body in bodies)
    assert reply_format_now(Plug.DEEPSEEK) is ReplyFormat.NOT_SENT
    assert reply_format_now(Plug.CLOUD) is ReplyFormat.JSON_SCHEMA


@pytest.mark.parametrize(
    "answer",
    [
        json_response(400, error_body("invalid model parameters")),
        json_response(422, error_body("json is wrong here")),
    ],
    ids=["400 without the word", "not 400"],
)
def test_other_refusals_keep_the_json_object(answer: object) -> None:
    server = FakeServer([answer])  # type: ignore[list-item]

    with pytest.raises(ModelError):
        CloudModel(deepseek_settings(), transport=server.transport).chat(HELLO, reply_schema=TABLE)

    assert len(server.requests) == 1
    assert reply_format_now(Plug.DEEPSEEK) is ReplyFormat.JSON_OBJECT


def test_a_call_without_a_table_never_drops_the_json_object() -> None:
    server = FakeServer([json_response(400, error_body(NO_JSON_WORD))])

    with pytest.raises(ModelError):
        CloudModel(deepseek_settings(), transport=server.transport).chat(HELLO)

    assert reply_format_now(Plug.DEEPSEEK) is ReplyFormat.JSON_OBJECT


# --- a model DeepSeek does not have (measured 2026-11-27, with status 400) --------


@pytest.mark.parametrize("plug", [Plug.DEEPSEEK, Plug.CLOUD])
def test_a_model_name_it_does_not_take_is_a_missing_model(plug: Plug) -> None:
    said = (
        "The supported API model names are deepseek-flash, deepseek-v4-pro, "
        "but you passed invented-model-x."
    )
    server = FakeServer([json_response(400, error_body(said, kind="invalid_request_error"))])
    settings = dataclasses.replace(
        deepseek_settings() if plug is Plug.DEEPSEEK else CLOUD_SETTINGS,
        plug=plug,
        model="invented-model-x",
    )

    with pytest.raises(ModelError) as caught:
        CloudModel(settings, transport=server.transport).chat(HELLO)

    assert caught.value.kind is ModelErrorKind.MODEL_NOT_FOUND
    assert caught.value.status == 400
    assert caught.value.snippet is None


def test_a_400_that_names_another_model_is_not_a_missing_model() -> None:
    said = "The supported API model names are deepseek-flash, but you passed other-model."
    server = FakeServer([json_response(400, error_body(said))])

    with pytest.raises(ModelError) as caught:
        CloudModel(deepseek_settings(), transport=server.transport).chat(HELLO)

    assert caught.value.kind is ModelErrorKind.SERVER_ERROR


# --- what the service answered stays out of an error with a cloud plug -------------


@pytest.mark.parametrize("status", [400, 401, 402, 403, 404, 429, 500])
@pytest.mark.parametrize("plug", [Plug.DEEPSEEK, Plug.CLOUD])
def test_no_error_keeps_what_the_service_answered(plug: Plug, status: int) -> None:
    server = FakeServer([json_response(status, error_body("Invented refusal ****cdef"))])
    settings = dataclasses.replace(
        deepseek_settings() if plug is Plug.DEEPSEEK else CLOUD_SETTINGS, plug=plug
    )

    with pytest.raises(ModelError) as caught:
        CloudModel(settings, transport=server.transport).chat(HELLO)

    assert caught.value.status == status
    assert caught.value.snippet is None
    assert "Invented refusal" not in str(caught.value)
    assert "cdef" not in str(caught.value)
