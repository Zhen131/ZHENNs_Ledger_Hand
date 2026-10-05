"""Tests of trying again: which failures, how often, and how long the waits are.

The waits are recorded, never slept through.
"""

from __future__ import annotations

import httpx
import pytest

from ledger_hand.llm.local import connect_local_model
from ledger_hand.llm.retry import RETRYABLE, RetryingModel
from ledger_hand.ports import Message, ModelError, ModelErrorKind, Role
from ledger_hand.settings import ModelSettings
from tests.fakes.scripted_model import ScriptedModel
from tests.llm.fake_server import FakeServer, chat_reply, json_response

HELLO = [Message(Role.USER, "Greet the invented baker.")]

# Written out by hand: the kinds worth trying again, and the kinds that are not.
WORTH_RETRYING = [
    ModelErrorKind.TIMED_OUT,
    ModelErrorKind.RATE_LIMITED,
    ModelErrorKind.SERVER_ERROR,
]
NOT_WORTH_RETRYING = [
    ModelErrorKind.UNREACHABLE,
    ModelErrorKind.MODEL_NOT_FOUND,
    ModelErrorKind.MALFORMED_REPLY,
]


class Waits:
    """Stands in for sleeping: records each wait instead."""

    def __init__(self) -> None:
        self.seconds: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.seconds.append(seconds)


def failure(kind: ModelErrorKind, number: int = 1) -> ModelError:
    return ModelError(kind, f"failure number {number}")


def retrying(
    inner: ScriptedModel, waits: Waits, retries: int = 3, first: float = 0.5
) -> RetryingModel:
    return RetryingModel(inner, retries=retries, first_wait_seconds=first, sleep=waits)


def test_the_two_lists_cover_every_kind_once() -> None:
    assert set(WORTH_RETRYING) == RETRYABLE
    assert set(WORTH_RETRYING) | set(NOT_WORTH_RETRYING) == set(ModelErrorKind)
    assert not set(WORTH_RETRYING) & set(NOT_WORTH_RETRYING)


@pytest.mark.parametrize("kind", WORTH_RETRYING)
def test_a_failure_worth_retrying_is_tried_again_until_it_succeeds(kind: ModelErrorKind) -> None:
    inner = ScriptedModel([failure(kind, 1), failure(kind, 2), "at last"])
    waits = Waits()

    reply = retrying(inner, waits).chat(HELLO)

    assert reply.text == "at last"
    assert len(inner.calls) == 3
    assert waits.seconds == [0.5, 1.0]


@pytest.mark.parametrize("kind", WORTH_RETRYING)
def test_when_the_tries_run_out_the_last_error_is_raised(kind: ModelErrorKind) -> None:
    errors = [failure(kind, number) for number in range(1, 5)]
    inner = ScriptedModel(errors)
    waits = Waits()

    with pytest.raises(ModelError) as caught:
        retrying(inner, waits, retries=3).chat(HELLO)

    assert caught.value is errors[-1]
    assert len(inner.calls) == 4
    assert inner.steps_left == 0


@pytest.mark.parametrize("kind", WORTH_RETRYING)
def test_each_wait_is_twice_the_one_before(kind: ModelErrorKind) -> None:
    inner = ScriptedModel([failure(kind, number) for number in range(1, 6)])
    waits = Waits()

    with pytest.raises(ModelError):
        retrying(inner, waits, retries=4, first=1.5).chat(HELLO)

    assert waits.seconds == [1.5, 3.0, 6.0, 12.0]
    assert all(
        later > earlier for earlier, later in zip(waits.seconds, waits.seconds[1:], strict=False)
    )


@pytest.mark.parametrize("kind", NOT_WORTH_RETRYING)
def test_a_failure_not_worth_retrying_is_raised_at_once(kind: ModelErrorKind) -> None:
    error = failure(kind)
    inner = ScriptedModel([error, "never reached"])
    waits = Waits()

    with pytest.raises(ModelError) as caught:
        retrying(inner, waits).chat(HELLO)

    assert caught.value is error
    assert len(inner.calls) == 1
    assert waits.seconds == []


def test_a_failure_not_worth_retrying_after_one_that_is_stops_the_tries() -> None:
    final = failure(ModelErrorKind.MODEL_NOT_FOUND, 2)
    inner = ScriptedModel([failure(ModelErrorKind.SERVER_ERROR, 1), final, "never reached"])
    waits = Waits()

    with pytest.raises(ModelError) as caught:
        retrying(inner, waits).chat(HELLO)

    assert caught.value is final
    assert waits.seconds == [0.5]


def test_with_no_retries_one_try_is_all() -> None:
    error = failure(ModelErrorKind.TIMED_OUT)
    inner = ScriptedModel([error, "never reached"])
    waits = Waits()

    with pytest.raises(ModelError) as caught:
        retrying(inner, waits, retries=0).chat(HELLO)

    assert caught.value is error
    assert waits.seconds == []


def test_the_call_is_passed_on_unchanged_each_try() -> None:
    inner = ScriptedModel([failure(ModelErrorKind.RATE_LIMITED), "ok"])
    schema = {"type": "object"}

    retrying(inner, Waits()).chat(HELLO, reply_schema=schema)

    assert inner.calls[0] == inner.calls[1]
    assert inner.calls[1].reply_schema == schema


def test_a_success_needs_no_wait() -> None:
    waits = Waits()

    assert retrying(ScriptedModel(["first time"]), waits).chat(HELLO).text == "first time"
    assert waits.seconds == []


@pytest.mark.parametrize(
    ("retries", "first"),
    [(-1, 1.0), (True, 1.0), (1.5, 1.0), (1, -0.1), (1, float("nan")), (1, float("inf")), (1, "1")],
)
def test_impossible_retry_settings_are_refused(retries: object, first: object) -> None:
    with pytest.raises(ValueError):
        RetryingModel(ScriptedModel([]), retries=retries, first_wait_seconds=first)  # type: ignore[arg-type]


# --- the assembled local model ----------------------------------------------


def test_the_local_model_retries_as_the_settings_say() -> None:
    settings = ModelSettings(retries=2, retry_wait_seconds=0.25)
    server = FakeServer(
        [
            json_response(503, {"error": "server busy, please try again"}),
            json_response(429, {"error": "slow down"}),
            json_response(200, chat_reply("finally")),
        ]
    )
    waits = Waits()

    model = connect_local_model(settings, transport=server.transport, sleep=waits)

    assert model.chat(HELLO).text == "finally"
    assert len(server.requests) == 3
    assert waits.seconds == [0.25, 0.5]


def test_the_local_model_does_not_retry_an_unreachable_server() -> None:
    settings = ModelSettings(retries=5, retry_wait_seconds=1.0)
    server = FakeServer([httpx.ConnectError("[Errno 61] Connection refused")])
    waits = Waits()

    with pytest.raises(ModelError) as caught:
        connect_local_model(settings, transport=server.transport, sleep=waits).chat(HELLO)

    assert caught.value.kind is ModelErrorKind.UNREACHABLE
    assert len(server.requests) == 1
    assert waits.seconds == []


def test_building_the_local_model_sends_nothing() -> None:
    server = FakeServer([])

    connect_local_model(ModelSettings(), transport=server.transport, sleep=Waits())

    assert server.requests == []
