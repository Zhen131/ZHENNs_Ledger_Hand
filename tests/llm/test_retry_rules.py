"""Tests of the rules for trying again: no 4xx but 429, and the wait a server asks for.

A server error whose status is 400 to 499 says the request itself is wrong,
so it is tried once and raised without a wait. A rate-limited call whose
server said how long to wait waits exactly that long, not the doubling wait,
up to ``LONGEST_ASKED_WAIT_SECONDS``; a longer wait is not sat through, and
the error is raised at once with the wait it asked for. Timeouts and 5xx
errors are tried again with doubling waits as before. The waits are
recorded, never slept through. Every value is invented.
"""

from __future__ import annotations

import pytest

from ledger_hand.llm.retry import (
    LONGEST_ASKED_WAIT_SECONDS,
    RETRYABLE,
    RetryingModel,
    worth_retrying,
)
from ledger_hand.ports import Message, ModelError, ModelErrorKind, Role
from tests.fakes.scripted_model import ScriptedModel

HELLO = [Message(Role.USER, "Greet the invented baker.")]


class Waits:
    """Stands in for sleeping: records each wait instead."""

    def __init__(self) -> None:
        self.seconds: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.seconds.append(seconds)


def retrying(
    script: list[str | ModelError], waits: Waits, retries: int = 3, first: float = 1.0
) -> tuple[ScriptedModel, RetryingModel]:
    inner = ScriptedModel(script)
    return inner, RetryingModel(inner, retries=retries, first_wait_seconds=first, sleep=waits)


def server_error(status: int | None) -> ModelError:
    return ModelError(ModelErrorKind.SERVER_ERROR, f"status {status}", status=status)


def rate_limited(wait: float | None) -> ModelError:
    return ModelError(
        ModelErrorKind.RATE_LIMITED, "too often", status=429, retry_after_seconds=wait
    )


# --- 4xx is not tried again ---------------------------------------------------------


@pytest.mark.parametrize("status", [400, 401, 403, 404, 405, 413, 422, 499])
def test_a_server_error_with_a_4xx_status_is_tried_once_without_a_wait(status: int) -> None:
    error = server_error(status)
    waits = Waits()
    inner, model = retrying([error, "never reached"], waits)

    with pytest.raises(ModelError) as caught:
        model.chat(HELLO)

    assert caught.value is error
    assert len(inner.calls) == 1
    assert waits.seconds == []


@pytest.mark.parametrize("status", [500, 502, 503, 599, None, 301, 600])
def test_any_other_server_error_is_tried_again_with_doubling_waits(status: int | None) -> None:
    waits = Waits()
    inner, model = retrying([server_error(status)] * 3 + ["at last"], waits, first=0.5)

    assert model.chat(HELLO).text == "at last"
    assert len(inner.calls) == 4
    assert waits.seconds == [0.5, 1.0, 2.0]


def test_a_timeout_is_still_tried_again_with_doubling_waits() -> None:
    waits = Waits()
    timed_out = ModelError(ModelErrorKind.TIMED_OUT, "slow")
    inner, model = retrying([timed_out, timed_out, "at last"], waits, first=1.5)

    assert model.chat(HELLO).text == "at last"
    assert waits.seconds == [1.5, 3.0]


def test_a_rate_limit_is_its_own_kind_and_still_tried_again() -> None:
    assert worth_retrying(rate_limited(None))
    assert worth_retrying(ModelError(ModelErrorKind.RATE_LIMITED, "x", status=429))
    assert not worth_retrying(server_error(401))
    assert worth_retrying(server_error(503))
    assert set(RETRYABLE) == {
        ModelErrorKind.TIMED_OUT,
        ModelErrorKind.RATE_LIMITED,
        ModelErrorKind.SERVER_ERROR,
    }


# --- the wait a server asks for -----------------------------------------------------


def test_the_wait_a_server_asks_for_is_waited_instead_of_the_doubling_one() -> None:
    waits = Waits()
    inner, model = retrying([rate_limited(2.0), "the reply"], waits, first=1.0)

    assert model.chat(HELLO).text == "the reply"
    assert waits.seconds == [2.0]
    assert len(inner.calls) == 2


def test_each_wait_asked_for_is_waited_as_asked_and_not_doubled() -> None:
    waits = Waits()
    script = [rate_limited(5.0), rate_limited(5.0), rate_limited(0.0), "the reply"]
    _, model = retrying(script, waits, retries=3, first=1.0)

    assert model.chat(HELLO).text == "the reply"
    assert waits.seconds == [5.0, 5.0, 0.0]


def test_a_wait_asked_for_and_a_wait_not_asked_for_mix_in_one_call() -> None:
    waits = Waits()
    script = [rate_limited(None), rate_limited(7.0), server_error(503), "the reply"]
    _, model = retrying(script, waits, retries=3, first=1.0)

    assert model.chat(HELLO).text == "the reply"
    # The first and third waits double by the number of the retry; the second is as asked.
    assert waits.seconds == [1.0, 7.0, 4.0]


def test_a_wait_up_to_the_limit_is_sat_through() -> None:
    waits = Waits()
    _, model = retrying([rate_limited(LONGEST_ASKED_WAIT_SECONDS), "the reply"], waits)

    assert model.chat(HELLO).text == "the reply"
    assert waits.seconds == [LONGEST_ASKED_WAIT_SECONDS]


def test_a_wait_over_the_limit_is_not_sat_through_and_the_error_keeps_it() -> None:
    asked = LONGEST_ASKED_WAIT_SECONDS + 1
    error = rate_limited(asked)
    waits = Waits()
    inner, model = retrying([error, "never reached"], waits)

    with pytest.raises(ModelError) as caught:
        model.chat(HELLO)

    assert caught.value is error
    assert caught.value.kind is ModelErrorKind.RATE_LIMITED
    assert caught.value.retry_after_seconds == asked
    assert len(inner.calls) == 1
    assert waits.seconds == []


def test_every_wait_asked_for_counts_as_a_retry() -> None:
    last = rate_limited(2.0)
    waits = Waits()
    inner, model = retrying([rate_limited(2.0), rate_limited(2.0), last], waits, retries=2)

    with pytest.raises(ModelError) as caught:
        model.chat(HELLO)

    assert caught.value is last
    assert len(inner.calls) == 3
    assert waits.seconds == [2.0, 2.0]


def test_with_no_retries_a_wait_asked_for_is_not_waited() -> None:
    waits = Waits()
    error = rate_limited(2.0)
    _, model = retrying([error, "never reached"], waits, retries=0)

    with pytest.raises(ModelError) as caught:
        model.chat(HELLO)

    assert caught.value is error
    assert waits.seconds == []


def test_the_limit_is_a_minute() -> None:
    assert LONGEST_ASKED_WAIT_SECONDS == 60
