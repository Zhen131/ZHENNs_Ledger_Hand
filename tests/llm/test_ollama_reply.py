"""Tests of reading the answer to a chat request: the reply and its record, or the failure."""

from __future__ import annotations

import json

import pytest

from ledger_hand.llm.exchange import Answer, Endpoint
from ledger_hand.llm.ollama_reply import read_chat_answer
from ledger_hand.ports import FinishReason, ModelError, ModelErrorKind, ModelReply
from tests.llm.fake_server import chat_reply

ENDPOINT = Endpoint(base_url="http://127.0.0.1:11434", api_key=None)
ASKED = "qwen2.5:7b"


def read(status: int, body: bytes, problem: str | None = None) -> ModelReply:
    answer = Answer(status, body, problem)
    return read_chat_answer(answer, ENDPOINT, requested_model=ASKED, elapsed_seconds=2.5)


def read_json(data: object, status: int = 200) -> ModelReply:
    return read(status, json.dumps(data).encode("utf-8"))


def fails_as(status: int, body: bytes, problem: str | None = None) -> ModelError:
    with pytest.raises(ModelError) as caught:
        read(status, body, problem)
    return caught.value


def test_a_normal_answer_gives_the_text_and_every_part_of_the_record() -> None:
    reply = read_json(chat_reply("the text", model="qwen2.5:7b-instruct"))

    assert reply.text == "the text"
    assert reply.record.model == "qwen2.5:7b-instruct"
    assert reply.record.elapsed_seconds == 2.5
    assert reply.record.prompt_tokens == 44
    assert reply.record.reply_tokens == 14
    assert reply.record.finish is FinishReason.STOPPED


def test_text_with_surrounding_blanks_is_kept_as_it_came() -> None:
    assert read_json(chat_reply("  padded \n")).text == "  padded \n"


@pytest.mark.parametrize(
    ("fields", "model", "prompt_tokens", "reply_tokens", "finish"),
    [
        ({"done_reason": "length"}, ASKED, 44, 14, FinishReason.LENGTH_LIMIT),
        ({"done_reason": "unload"}, ASKED, 44, 14, FinishReason.NOT_REPORTED),
        ({"done_reason": None}, ASKED, 44, 14, FinishReason.NOT_REPORTED),
        ({"done_reason": ["stop"]}, ASKED, 44, 14, FinishReason.NOT_REPORTED),
        ({"done_reason": {"why": "stop"}}, ASKED, 44, 14, FinishReason.NOT_REPORTED),
        ({"prompt_eval_count": -1, "eval_count": True}, ASKED, None, None, FinishReason.STOPPED),
        ({"prompt_eval_count": 1.5, "eval_count": "14"}, ASKED, None, None, FinishReason.STOPPED),
        ({"prompt_eval_count": None, "eval_count": [1]}, ASKED, None, None, FinishReason.STOPPED),
        ({"prompt_eval_count": 10**30}, ASKED, 10**30, 14, FinishReason.STOPPED),
        ({"model": 7}, ASKED, 44, 14, FinishReason.STOPPED),
        ({"model": ""}, ASKED, 44, 14, FinishReason.STOPPED),
        ({"model": "evil\x1b[2J"}, ASKED, 44, 14, FinishReason.STOPPED),
        ({"model": "m" * 257}, ASKED, 44, 14, FinishReason.STOPPED),
    ],
)
def test_odd_record_fields_say_not_reported_instead_of_failing(
    fields: dict[str, object],
    model: str,
    prompt_tokens: int | None,
    reply_tokens: int | None,
    finish: FinishReason,
) -> None:
    body = chat_reply("text", model=ASKED)
    body.update(fields)

    reply = read_json(body)

    assert reply.text == "text"
    assert reply.record.model == model
    assert reply.record.prompt_tokens == prompt_tokens
    assert reply.record.reply_tokens == reply_tokens
    assert reply.record.finish is finish


def test_missing_record_fields_say_not_reported() -> None:
    reply = read_json({"message": {"content": "text"}, "done": True})

    assert reply.record.model == ASKED
    assert reply.record.prompt_tokens is None
    assert reply.record.reply_tokens is None
    assert reply.record.finish is FinishReason.NOT_REPORTED


@pytest.mark.parametrize(
    "error_text",
    [
        'model "qwen9:1b" not found, try pulling it first',
        "model 'qwen9:1b' not found",
        "Model Not Found",
    ],
)
def test_a_404_saying_not_found_is_model_not_found(error_text: str) -> None:
    error = fails_as(404, json.dumps({"error": error_text}).encode())

    assert error.kind is ModelErrorKind.MODEL_NOT_FOUND
    assert error.status == 404
    assert ASKED in error.message


@pytest.mark.parametrize(
    "body",
    [
        b"404 page not found",
        b"",
        b'{"error": "no route"}',
        b'{"error": ["not found"]}',
        b'{"message": "not found"}',
        b'["not found"]',
        b"\xff not found",
    ],
)
def test_any_other_404_is_a_server_error_with_the_raw_status(body: bytes) -> None:
    error = fails_as(404, body)

    assert error.kind is ModelErrorKind.SERVER_ERROR
    assert error.status == 404


def test_a_404_whose_body_could_not_be_read_is_a_server_error() -> None:
    assert fails_as(404, b"", "is longer than 4194304 bytes").kind is ModelErrorKind.SERVER_ERROR


def test_a_500_whose_body_could_not_be_read_is_still_a_server_error() -> None:
    assert fails_as(500, b"", "cannot be decoded").kind is ModelErrorKind.SERVER_ERROR


def test_a_429_is_rate_limited_whatever_its_body() -> None:
    assert fails_as(429, b"\x00\xff").kind is ModelErrorKind.RATE_LIMITED


@pytest.mark.parametrize(
    ("body", "why"),
    [
        (b"", "not JSON"),
        (b"   ", "not JSON"),
        (b"not json", "not JSON"),
        (b'{"message": {"content": "hi"}', "not JSON"),
        (b'{"message": {"content": "hi"}, "done": true, "eval_count": NaN}', "not JSON"),
        (b'{"message": {"content": "hi"}, "done": true, "x": Infinity}', "not JSON"),
        (b"\xef\xbb\xbf{}", "not JSON"),
        (b"\xff\xfe{\x00}\x00", "not UTF-8"),
        (b"\xc3\x28", "not UTF-8"),
        (b"null", "not a JSON object"),
        (b"[]", "not a JSON object"),
        (b'"text"', "not a JSON object"),
        (b"42", "not a JSON object"),
        (b"{}", "has no message"),
        (b'{"message": "hi", "done": true}', "has no message"),
        (b'{"message": ["hi"], "done": true}', "has no message"),
        (b'{"message": {}, "done": true}', "has no text"),
        (b'{"message": {"content": null}, "done": true}', "has no text"),
        (b'{"message": {"content": 7}, "done": true}', "has no text"),
        (b'{"message": {"content": ["a"]}, "done": true}', "has no text"),
        (b'{"message": {"content": ""}, "done": true}', "empty reply"),
        (b'{"message": {"content": " \\n\\t "}, "done": true}', "empty reply"),
        (b'{"message": {"content": "a\\ud800b"}, "done": true}', "not valid Unicode"),
        (b'{"message": {"content": "hi"}}', "not marked as complete"),
        (b'{"message": {"content": "hi"}, "done": false}', "not marked as complete"),
        (b'{"message": {"content": "hi"}, "done": "true"}', "not marked as complete"),
        (b'{"message": {"content": "hi"}, "done": 1}', "not marked as complete"),
        (b'{"error": "something failed"}', "has no message"),
    ],
)
def test_a_200_in_any_other_shape_is_malformed(body: bytes, why: str) -> None:
    error = fails_as(200, body)

    assert error.kind is ModelErrorKind.MALFORMED_REPLY
    assert why in error.message
    assert error.status == 200


def test_a_200_whose_body_could_not_be_read_is_malformed_and_says_why() -> None:
    error = fails_as(200, b"", "is longer than 4194304 bytes")

    assert error.kind is ModelErrorKind.MALFORMED_REPLY
    assert "longer than" in error.message


@pytest.mark.parametrize(
    "body",
    [
        b"[" * 200_000,
        b'{"a":' * 200_000,
        b'{"n": ' + b"9" * 5000 + b"}",
    ],
)
def test_extreme_json_is_malformed_not_a_crash(body: bytes) -> None:
    assert fails_as(200, body).kind is ModelErrorKind.MALFORMED_REPLY
