"""Tests of reading the wait a rate-limited server asks for, from its Retry-After header.

The header gives seconds or a date. The date is counted from a wall clock
handed in, so every result here is exact and nothing waits. The local plug
puts the wait it read into its rate-limited error. Every value is invented.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx
import pytest

from ledger_hand.llm.exchange import MAX_ANSWER_BYTES, Answer, Endpoint, failure_for_status
from ledger_hand.llm.ollama import OllamaModel
from ledger_hand.llm.retry_after import LONGEST_READ_SECONDS, seconds_to_wait
from ledger_hand.ports import Message, ModelError, ModelErrorKind, Role
from tests.llm.fake_server import SETTINGS, FakeServer

# 21 October 2026, 07:28:00 in GMT, in seconds since the epoch.
NOW = datetime(2026, 10, 21, 7, 28, 0, tzinfo=UTC).timestamp()
HELLO = [Message(Role.USER, "hello")]


@pytest.mark.parametrize(
    ("value", "seconds"),
    [
        ("2", 2.0),
        ("0", 0.0),
        (" 17 ", 17.0),
        ("120", 120.0),
        ("007", 7.0),
        ("1.5", 1.5),
        ("999999999", 999_999_999.0),
    ],
)
def test_a_number_of_seconds_is_read_as_it_stands(value: str, seconds: float) -> None:
    assert seconds_to_wait(value, NOW) == seconds


@pytest.mark.parametrize("value", ["1000000000", "9" * 400, "12345678901.5"])
def test_a_number_too_long_to_be_meant_is_the_longest_wait_read(value: str) -> None:
    assert seconds_to_wait(value, NOW) == LONGEST_READ_SECONDS


@pytest.mark.parametrize(
    "value",
    [
        "Wed, 21 Oct 2026 07:28:02 GMT",
        "Wednesday, 21-Oct-26 07:28:02 GMT",
        "Wed Oct 21 07:28:02 2026",
        "Wed, 21 Oct 2026 07:28:02 +0000",
    ],
)
def test_a_date_two_seconds_ahead_in_any_of_the_three_http_forms_is_two_seconds(
    value: str,
) -> None:
    assert seconds_to_wait(value, NOW) == 2.0


def test_a_date_already_past_is_no_wait() -> None:
    assert seconds_to_wait("Wed, 21 Oct 2026 07:27:00 GMT", NOW) == 0.0


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "   ",
        "soon",
        "-2",
        "+2",
        "2s",
        "1e3",
        "2, 3",
        "0x10",
        "Wed, 99 Oct 2026 07:28 GMT",
    ],
)
def test_anything_else_says_no_wait(value: str | None) -> None:
    assert seconds_to_wait(value, NOW) is None


# --- an answer with status 429 ------------------------------------------------------


def endpoint() -> Endpoint:
    return Endpoint(base_url="http://127.0.0.1:11434", api_key=None, wall_clock=lambda: NOW)


@pytest.mark.parametrize(
    ("header", "seconds"),
    [("2", 2.0), ("Wed, 21 Oct 2026 07:28:30 GMT", 30.0), (None, None), ("later", None)],
)
def test_a_429_carries_the_wait_its_header_asks_for(header: str | None, seconds: float) -> None:
    error = failure_for_status(Answer(429, b"slow down", retry_after=header), endpoint())

    assert error.kind is ModelErrorKind.RATE_LIMITED
    assert error.status == 429
    assert error.retry_after_seconds == seconds


@pytest.mark.parametrize("status", [500, 503, 404, 400])
def test_no_other_status_carries_a_wait_even_with_the_header(status: int) -> None:
    error = failure_for_status(Answer(status, b"busy", retry_after="2"), endpoint())

    assert error.retry_after_seconds is None


def rate_limited(header: dict[str, str]) -> httpx.Response:
    body = json.dumps({"error": "too many requests"}).encode()
    return httpx.Response(429, headers=header, content=body)


@pytest.mark.parametrize(
    ("header", "seconds"),
    [
        ({"Retry-After": "2"}, 2.0),
        ({"retry-after": "Wed, 21 Oct 2026 07:28:02 GMT"}, 2.0),
        ({}, None),
    ],
)
def test_the_local_plug_reads_the_header_of_a_429(
    header: dict[str, str], seconds: float | None
) -> None:
    server = FakeServer([rate_limited(header)])
    plug = OllamaModel(SETTINGS, transport=server.transport, wall_clock=lambda: NOW)

    with pytest.raises(ModelError) as caught:
        plug.chat(HELLO)

    assert caught.value.kind is ModelErrorKind.RATE_LIMITED
    assert caught.value.retry_after_seconds == seconds


def test_the_header_is_kept_when_the_body_of_a_429_is_too_long() -> None:
    server = FakeServer(
        [httpx.Response(429, headers={"Retry-After": "3"}, content=b"z" * (MAX_ANSWER_BYTES + 1))]
    )
    plug = OllamaModel(SETTINGS, transport=server.transport, wall_clock=lambda: NOW)

    with pytest.raises(ModelError) as caught:
        plug.chat(HELLO)

    assert caught.value.retry_after_seconds == 3.0


# --- the error itself ---------------------------------------------------------------


def test_an_error_says_how_long_the_server_asked_to_wait() -> None:
    error = ModelError(
        ModelErrorKind.RATE_LIMITED, "too often", status=429, retry_after_seconds=2.0
    )

    assert str(error) == (
        "rate_limited: too often (status 429); the server asked to wait 2 seconds"
    )
    assert repr(error) == (
        "ModelError(RATE_LIMITED, 'too often', status=429, retry_after_seconds=2.0)"
    )


def test_an_error_without_a_wait_is_written_as_before() -> None:
    error = ModelError(ModelErrorKind.RATE_LIMITED, "too often", status=429)

    assert error.retry_after_seconds is None
    assert str(error) == "rate_limited: too often (status 429)"
    assert repr(error) == "ModelError(RATE_LIMITED, 'too often', status=429)"


@pytest.mark.parametrize("wait", [-1.0, float("nan"), float("inf"), True, "2"])
def test_a_wait_that_is_not_a_finite_number_of_seconds_is_refused(wait: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        ModelError(ModelErrorKind.RATE_LIMITED, "x", retry_after_seconds=wait)  # type: ignore[arg-type]
