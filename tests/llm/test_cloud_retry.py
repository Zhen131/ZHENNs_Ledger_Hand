"""Tests of the cloud plug tried again: the wait a 429 asks for, and no retry of a refusal.

The plug is wrapped as the program wraps it, in ``RetryingModel``, and fed
by the fake transport. A 429 that says ``Retry-After: 2`` is waited for two
seconds, then the call is tried again; the same holds for a date two
seconds ahead. A wait over the limit is not sat through. 400, 401, 403 and
a 404 that is not a missing model are tried once; 500 and timeouts are
tried again with doubling waits. The waits are recorded, never slept
through, and the wall clock is fixed. Every value is invented.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime

import httpx
import pytest

from ledger_hand.llm.cloud import CloudModel
from ledger_hand.llm.retry import LONGEST_ASKED_WAIT_SECONDS, RetryingModel
from ledger_hand.ports import Message, ModelError, ModelErrorKind, Role
from tests.llm.fake_cloud import CLOUD_SETTINGS, completion, error_body
from tests.llm.fake_server import FakeServer, json_response

HELLO = [Message(Role.USER, "Greet the invented baker.")]
NOW = datetime(2026, 10, 21, 7, 28, 0, tzinfo=UTC).timestamp()
SETTINGS = dataclasses.replace(CLOUD_SETTINGS, retries=3, retry_wait_seconds=1.0)


class Waits:
    """Stands in for sleeping: records each wait instead."""

    def __init__(self) -> None:
        self.seconds: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.seconds.append(seconds)


def wrapped(server: FakeServer, waits: Waits) -> RetryingModel:
    plug = CloudModel(SETTINGS, transport=server.transport, wall_clock=lambda: NOW)
    return RetryingModel(
        plug, retries=SETTINGS.retries, first_wait_seconds=SETTINGS.retry_wait_seconds, sleep=waits
    )


def too_often(retry_after: str | None) -> httpx.Response:
    headers = {} if retry_after is None else {"Retry-After": retry_after}
    body = error_body("Rate limit reached for requests", kind="requests")
    return httpx.Response(429, headers=headers, content=json_response(429, body).content)


# --- V-4: the wait a 429 asks for --------------------------------------------------


@pytest.mark.parametrize("retry_after", ["2", "Wed, 21 Oct 2026 07:28:02 GMT"])
def test_a_429_asking_for_two_seconds_is_waited_two_seconds_then_answered(
    retry_after: str,
) -> None:
    server = FakeServer([too_often(retry_after), json_response(200, completion("at last"))])
    waits = Waits()

    reply = wrapped(server, waits).chat(HELLO)

    assert reply.text == "at last"
    assert waits.seconds == [2.0]
    assert len(server.requests) == 2


def test_a_429_without_a_wait_falls_back_to_the_doubling_wait() -> None:
    server = FakeServer([too_often(None), too_often(None), json_response(200, completion())])
    waits = Waits()

    wrapped(server, waits).chat(HELLO)

    assert waits.seconds == [1.0, 2.0]


@pytest.mark.parametrize(
    "retry_after",
    [str(int(LONGEST_ASKED_WAIT_SECONDS) + 1), "3600", "Wed, 21 Oct 2026 08:28:00 GMT"],
)
def test_a_429_asking_for_more_than_the_limit_is_handed_back_at_once_with_its_wait(
    retry_after: str,
) -> None:
    server = FakeServer([too_often(retry_after), json_response(200, completion("never"))])
    waits = Waits()

    with pytest.raises(ModelError) as caught:
        wrapped(server, waits).chat(HELLO)

    assert caught.value.kind is ModelErrorKind.RATE_LIMITED
    assert caught.value.retry_after_seconds is not None
    assert caught.value.retry_after_seconds > LONGEST_ASKED_WAIT_SECONDS
    assert waits.seconds == []
    assert len(server.requests) == 1


def test_when_the_tries_run_out_the_last_429_keeps_its_wait() -> None:
    server = FakeServer([too_often("2")] * 4)
    waits = Waits()

    with pytest.raises(ModelError) as caught:
        wrapped(server, waits).chat(HELLO)

    assert caught.value.retry_after_seconds == 2.0
    assert waits.seconds == [2.0, 2.0, 2.0]
    assert len(server.requests) == 4


# --- V-5: a refusal is tried once; 500 and timeouts again ------------------------------


@pytest.mark.parametrize(
    ("status", "said"),
    [
        (400, "Invalid schema for response_format 'reply'"),
        (401, "Incorrect API key provided"),
        (403, "You are not allowed to sample from this model"),
        (404, "Unknown request URL: POST /v1/chat/completions"),
    ],
)
def test_a_refusal_is_tried_once_without_a_wait(status: int, said: str) -> None:
    server = FakeServer([json_response(status, error_body(said)), json_response(200, completion())])
    waits = Waits()

    with pytest.raises(ModelError) as caught:
        wrapped(server, waits).chat(HELLO)

    assert caught.value.kind is ModelErrorKind.SERVER_ERROR
    assert caught.value.status == status
    assert len(server.requests) == 1
    assert waits.seconds == []


def test_a_missing_model_is_tried_once_without_a_wait() -> None:
    body = error_body("The model `x` does not exist", code="model_not_found")
    server = FakeServer([json_response(404, body), json_response(200, completion())])
    waits = Waits()

    with pytest.raises(ModelError) as caught:
        wrapped(server, waits).chat(HELLO)

    assert caught.value.kind is ModelErrorKind.MODEL_NOT_FOUND
    assert len(server.requests) == 1
    assert waits.seconds == []


@pytest.mark.parametrize(
    "failure",
    [
        json_response(500, error_body("The server had an error")),
        httpx.ReadTimeout("timed out"),
    ],
    ids=["500", "timeout"],
)
def test_a_500_and_a_timeout_are_tried_again_with_doubling_waits(
    failure: httpx.Response | Exception,
) -> None:
    server = FakeServer([failure, failure, failure, json_response(200, completion("at last"))])
    waits = Waits()

    reply = wrapped(server, waits).chat(HELLO)

    assert reply.text == "at last"
    assert waits.seconds == [1.0, 2.0, 4.0]
    assert len(server.requests) == 4
