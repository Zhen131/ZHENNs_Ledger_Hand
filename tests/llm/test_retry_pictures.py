"""Tests of a call with pictures tried again: the same rules as any other call.

A timeout or a server error is tried again after doubling waits; a request
refused with a status from 400 to 499 is not, nor is a malformed reply; a
rate limit that says how long to wait is waited that long; when the tries
run out, the last error is raised. What is asked is passed on unchanged.
"""

from __future__ import annotations

import pytest

from ledger_hand.llm.retry import RetryingModel
from ledger_hand.ports import (
    Message,
    ModelError,
    ModelErrorKind,
    ModelParameters,
    Picture,
    PictureKind,
    Role,
)
from tests.fakes.scripted_model import ScriptedModel, Step

PICTURE = Picture(b"\xff\xd8\xff\xe0 invented", PictureKind.JPEG)
ASKED = [Message(Role.SYSTEM, "Read the invented card."), Message(Role.USER, "Read it.")]
PARAMETERS = ModelParameters(
    temperature=0.0, top_p=1.0, max_reply_tokens=64, context_tokens=2048, timeout_seconds=5.0
)


class Waits:
    def __init__(self) -> None:
        self.seconds: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.seconds.append(seconds)


def tried(steps: list[Step], retries: int = 2) -> tuple[RetryingModel, ScriptedModel, Waits]:
    inner = ScriptedModel(steps)
    waits = Waits()
    return RetryingModel(inner, retries=retries, first_wait_seconds=1.0, sleep=waits), inner, waits


def test_a_timeout_then_a_server_error_are_tried_again_with_doubling_waits() -> None:
    model, inner, waits = tried(
        [
            ModelError(ModelErrorKind.TIMED_OUT, "slow"),
            ModelError(ModelErrorKind.SERVER_ERROR, "busy", status=503),
            "Card: invented",
        ]
    )

    reply = model.chat_with_pictures(ASKED, [PICTURE], parameters=PARAMETERS)

    assert reply.text == "Card: invented"
    assert waits.seconds == [1.0, 2.0]
    assert len(inner.calls) == 3
    for call in inner.calls:
        assert call.messages == tuple(ASKED)
        assert call.pictures == (PICTURE,)
        assert call.parameters is PARAMETERS
        assert call.reply_schema is None


@pytest.mark.parametrize(
    "error",
    [
        ModelError(ModelErrorKind.SERVER_ERROR, "no vision", status=400),
        ModelError(ModelErrorKind.MALFORMED_REPLY, "has an empty reply"),
        ModelError(ModelErrorKind.UNREACHABLE, "nothing there"),
        ModelError(ModelErrorKind.MODEL_NOT_FOUND, "no such model", status=404),
    ],
    ids=["refused", "malformed", "unreachable", "not found"],
)
def test_a_failure_waiting_cannot_mend_is_raised_at_once(error: ModelError) -> None:
    model, inner, waits = tried([error, "never asked for"])

    with pytest.raises(ModelError) as caught:
        model.chat_with_pictures(ASKED, [PICTURE])

    assert caught.value is error
    assert waits.seconds == []
    assert len(inner.calls) == 1


def test_a_rate_limit_that_says_how_long_is_waited_that_long() -> None:
    model, _, waits = tried(
        [ModelError(ModelErrorKind.RATE_LIMITED, "too often", retry_after_seconds=7.0), "ok"]
    )

    assert model.chat_with_pictures(ASKED, [PICTURE]).text == "ok"
    assert waits.seconds == [7.0]


def test_when_the_tries_run_out_the_last_error_is_raised() -> None:
    last = ModelError(ModelErrorKind.TIMED_OUT, "slow, third time")
    model, inner, waits = tried(
        [
            ModelError(ModelErrorKind.TIMED_OUT, "slow"),
            ModelError(ModelErrorKind.TIMED_OUT, "slow again"),
            last,
        ]
    )

    with pytest.raises(ModelError) as caught:
        model.chat_with_pictures(ASKED, [PICTURE])

    assert caught.value is last
    assert waits.seconds == [1.0, 2.0]
    assert len(inner.calls) == 3


def test_a_refusal_of_the_callers_mistake_is_not_tried_again() -> None:
    model, inner, waits = tried(["never asked for"])

    with pytest.raises(ValueError):
        model.chat_with_pictures([Message(Role.SYSTEM, "Read it.")], [PICTURE])

    assert waits.seconds == []
