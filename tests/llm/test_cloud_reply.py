"""Tests of what the cloud plug reads back: the reply and its record, or the failure.

A normal answer gives the text, the model's name, the two token counts and
why the model stopped: ``stop`` is stopped, ``length`` is cut off at the
longest reply, anything else or nothing is not reported. An answer with
status 200 in any other shape is a malformed reply. Every value is invented.
"""

from __future__ import annotations

import json

import httpx
import pytest

from ledger_hand.llm.cloud import CloudModel
from ledger_hand.ports import FinishReason, Message, ModelError, ModelErrorKind, ModelReply, Role
from tests.llm.fake_cloud import CLOUD_SETTINGS, MODEL, completion
from tests.llm.fake_server import FakeClock, FakeServer, json_response

HELLO = [Message(Role.USER, "Greet the invented baker.")]


def answered(response: httpx.Response, clock: FakeClock | None = None) -> ModelReply:
    server = FakeServer([response])
    if clock is None:
        return CloudModel(CLOUD_SETTINGS, transport=server.transport).chat(HELLO)
    return CloudModel(CLOUD_SETTINGS, transport=server.transport, clock=clock).chat(HELLO)


def fails_as(response: httpx.Response) -> ModelError:
    with pytest.raises(ModelError) as caught:
        answered(response)
    return caught.value


# --- V-2: a normal answer -------------------------------------------------------------


@pytest.mark.parametrize(
    ("finish", "expected"),
    [
        ("stop", FinishReason.STOPPED),
        ("length", FinishReason.LENGTH_LIMIT),
        ("content_filter", FinishReason.NOT_REPORTED),
        (None, FinishReason.NOT_REPORTED),
    ],
)
def test_a_normal_answer_gives_the_text_the_model_the_tokens_and_why_it_stopped(
    finish: str | None, expected: FinishReason
) -> None:
    reply = answered(json_response(200, completion('{"trades": []}', finish=finish)))

    assert reply.text == '{"trades": []}'
    assert reply.record.model == MODEL
    assert reply.record.prompt_tokens == 812
    assert reply.record.reply_tokens == 9
    assert reply.record.finish is expected


def test_an_answer_without_a_finish_reason_at_all_says_not_reported() -> None:
    body = completion()
    choices = body["choices"]
    assert isinstance(choices, list)
    del choices[0]["finish_reason"]

    assert answered(json_response(200, body)).record.finish is FinishReason.NOT_REPORTED


def test_the_time_spent_is_measured_on_this_side() -> None:
    clock = FakeClock(step=0.5)

    reply = answered(json_response(200, completion()), clock)

    assert reply.record.elapsed_seconds == pytest.approx(0.5 * (clock.reads - 1))


def test_text_with_surrounding_blanks_is_kept_as_it_came() -> None:
    assert answered(json_response(200, completion("  padded \n"))).text == "  padded \n"


def test_only_the_first_choice_is_read() -> None:
    body = completion("first")
    choices = body["choices"]
    assert isinstance(choices, list)
    choices.append({"index": 1, "message": {"role": "assistant", "content": "second"}})

    assert answered(json_response(200, body)).text == "first"


@pytest.mark.parametrize(
    ("fields", "model", "prompt_tokens", "reply_tokens"),
    [
        ({"usage": None}, MODEL, None, None),
        ({"usage": []}, MODEL, None, None),
        ({"usage": {"prompt_tokens": -1, "completion_tokens": True}}, MODEL, None, None),
        ({"usage": {"prompt_tokens": 1.5, "completion_tokens": "9"}}, MODEL, None, None),
        ({"usage": {"prompt_tokens": 10**30}}, MODEL, 10**30, None),
        ({"model": 7}, CLOUD_SETTINGS.model, 812, 9),
        ({"model": ""}, CLOUD_SETTINGS.model, 812, 9),
        ({"model": "x" * 257}, CLOUD_SETTINGS.model, 812, 9),
        ({"model": "\x1b[31m"}, CLOUD_SETTINGS.model, 812, 9),
        ({"model": "invented-cloud-model-2026-10-01"}, "invented-cloud-model-2026-10-01", 812, 9),
    ],
)
def test_odd_record_fields_say_not_reported_rather_than_fail(
    fields: dict[str, object], model: str, prompt_tokens: int | None, reply_tokens: int | None
) -> None:
    reply = answered(json_response(200, completion(**fields)))

    assert reply.record.model == model
    assert reply.record.prompt_tokens == prompt_tokens
    assert reply.record.reply_tokens == reply_tokens


def test_a_record_without_usage_or_model_names_the_model_asked() -> None:
    body = {"choices": [{"message": {"content": "text"}}]}

    reply = answered(json_response(200, body))

    assert reply.record.model == CLOUD_SETTINGS.model
    assert reply.record.prompt_tokens is None
    assert reply.record.reply_tokens is None
    assert reply.record.finish is FinishReason.NOT_REPORTED


# --- status 200 in another shape --------------------------------------------------


MALFORMED = [
    pytest.param(b"<html>", "is not JSON", id="not json"),
    pytest.param(b"\xff\xfe", "is not UTF-8 text", id="not utf-8"),
    pytest.param(b"[]", "is not a JSON object", id="a list"),
    pytest.param(b'{"value": NaN}', "is not JSON", id="nan"),
    pytest.param(b"{}", "has no choices", id="no choices"),
    pytest.param(b'{"choices": []}', "has no choices", id="no choice in the list"),
    pytest.param(b'{"choices": {"0": {}}}', "has no choices", id="choices not a list"),
    pytest.param(b'{"choices": ["text"]}', "is not an object", id="a choice that is text"),
    pytest.param(b'{"choices": [{}]}', "has no message", id="no message"),
    pytest.param(b'{"choices": [{"message": "hi"}]}', "has no message", id="message not object"),
    pytest.param(b'{"choices": [{"message": {}}]}', "has no text", id="no content"),
    pytest.param(
        b'{"choices": [{"message": {"content": null, "refusal": "no"}}]}',
        "has no text",
        id="content null",
    ),
    pytest.param(b'{"choices": [{"message": {"content": ["a"]}}]}', "has no text", id="a list"),
    pytest.param(b'{"choices": [{"message": {"content": ""}}]}', "empty reply", id="empty"),
    pytest.param(b'{"choices": [{"message": {"content": " \\n"}}]}', "empty reply", id="blank"),
    pytest.param(
        b'{"choices": [{"message": {"content": "\\ud800"}}]}', "not valid Unicode", id="surrogate"
    ),
    pytest.param(
        json.dumps({"error": {"message": "invented"}}).encode(), "has no choices", id="an error"
    ),
]


@pytest.mark.parametrize(("body", "why"), MALFORMED)
def test_status_200_in_any_other_shape_is_a_malformed_reply(body: bytes, why: str) -> None:
    error = fails_as(httpx.Response(200, content=body))

    assert error.kind is ModelErrorKind.MALFORMED_REPLY
    assert why in error.message
    assert error.status == 200
