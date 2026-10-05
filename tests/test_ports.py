"""Tests of the model port's shapes: messages, parameters, replies and errors."""

from __future__ import annotations

import pytest

from ledger_hand.ports import (
    FinishReason,
    Message,
    ModelError,
    ModelErrorKind,
    ModelParameters,
    Role,
)

VALID = {
    "temperature": 0.0,
    "top_p": 1.0,
    "max_reply_tokens": 1,
    "context_tokens": 1,
    "timeout_seconds": 0.5,
}


def parameters(**changes: object) -> ModelParameters:
    return ModelParameters(**{**VALID, **changes})  # type: ignore[arg-type]


def test_the_six_kinds_of_failure_are_exactly_these() -> None:
    assert {kind.value for kind in ModelErrorKind} == {
        "unreachable",
        "timed_out",
        "model_not_found",
        "rate_limited",
        "server_error",
        "malformed_reply",
    }


def test_roles_carry_the_names_model_servers_use() -> None:
    assert [role.value for role in Role] == ["system", "user", "assistant"]


def test_finish_reasons_are_exactly_these() -> None:
    assert {reason.value for reason in FinishReason} == {"stopped", "length_limit", "not_reported"}


@pytest.mark.parametrize(
    ("role", "content", "error"),
    [("user", "hi", TypeError), (Role.USER, None, TypeError), (Role.USER, b"hi", TypeError)],
)
def test_a_message_refuses_the_wrong_types(role: object, content: object, error: type) -> None:
    with pytest.raises(error):
        Message(role, content)  # type: ignore[arg-type]


def test_a_message_may_be_empty_text() -> None:
    assert Message(Role.USER, "").content == ""


@pytest.mark.parametrize(
    "changes",
    [
        {"temperature": 0},
        {"temperature": 1.7},
        {"top_p": 0.01},
        {"top_p": 1},
        {"max_reply_tokens": 32768, "context_tokens": 32768},
        {"timeout_seconds": 600},
    ],
)
def test_parameters_inside_the_ranges_are_taken(changes: dict[str, object]) -> None:
    built = parameters(**changes)
    for name, value in changes.items():
        assert getattr(built, name) == value


@pytest.mark.parametrize(
    ("changes", "error"),
    [
        ({"temperature": -0.1}, ValueError),
        ({"temperature": float("nan")}, ValueError),
        ({"temperature": float("inf")}, ValueError),
        ({"temperature": True}, TypeError),
        ({"temperature": "0"}, TypeError),
        ({"top_p": 0}, ValueError),
        ({"top_p": 1.01}, ValueError),
        ({"top_p": float("nan")}, ValueError),
        ({"max_reply_tokens": 0}, ValueError),
        ({"max_reply_tokens": 10.0}, TypeError),
        ({"max_reply_tokens": True}, TypeError),
        ({"context_tokens": -1}, ValueError),
        ({"context_tokens": None}, TypeError),
        ({"timeout_seconds": 0}, ValueError),
        ({"timeout_seconds": -1}, ValueError),
        ({"timeout_seconds": float("inf")}, ValueError),
        ({"timeout_seconds": False}, TypeError),
    ],
)
def test_parameters_outside_the_ranges_are_refused(
    changes: dict[str, object], error: type[Exception]
) -> None:
    with pytest.raises(error):
        parameters(**changes)


def test_an_error_names_its_kind_and_message() -> None:
    error = ModelError(ModelErrorKind.TIMED_OUT, "no reply within 5 seconds")

    assert error.kind is ModelErrorKind.TIMED_OUT
    assert str(error) == "timed_out: no reply within 5 seconds"
    assert error.status is None
    assert error.snippet is None


def test_an_error_shows_the_status_and_the_start_of_the_reply() -> None:
    error = ModelError(ModelErrorKind.SERVER_ERROR, "odd answer", status=418, snippet="teapot")

    assert str(error) == "server_error: odd answer (status 418); the reply began 'teapot'"
    assert repr(error) == "ModelError(SERVER_ERROR, 'odd answer', status=418)"


def test_an_error_can_be_caught_as_an_exception() -> None:
    with pytest.raises(ModelError) as caught:
        raise ModelError(ModelErrorKind.UNREACHABLE, "refused")
    assert caught.value.kind is ModelErrorKind.UNREACHABLE
