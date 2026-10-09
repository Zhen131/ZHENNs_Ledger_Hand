"""Tests of the cloud plug's failures: every case falls into one of the six kinds.

``CASES`` is the table: each way a call can fail, as the fake transport plays
it, and the kind it must end in. A 404 is a missing model only when its body
says so (the code ``model_not_found``, or a message that names a model and
says it is not found or does not exist); any other 404, and 400, 401 and
403, are server errors that keep their status, for the interface to say by
status. No case may end in an exception of another type. Every value is
invented; nothing leaves the process.
"""

from __future__ import annotations

import httpx
import pytest

from ledger_hand.llm.cloud import CloudModel
from ledger_hand.ports import Message, ModelError, ModelErrorKind, Role
from tests.llm.fake_cloud import CLOUD_SETTINGS, MODEL, completion, error_body
from tests.llm.fake_server import FakeServer, json_response

HELLO = [Message(Role.USER, "Greet the invented baker.")]

U = ModelErrorKind.UNREACHABLE
T = ModelErrorKind.TIMED_OUT
N = ModelErrorKind.MODEL_NOT_FOUND
R = ModelErrorKind.RATE_LIMITED
S = ModelErrorKind.SERVER_ERROR
M = ModelErrorKind.MALFORMED_REPLY

CASES = [
    ("connection refused", httpx.ConnectError("[Errno 61] Connection refused"), U, None),
    (
        "name does not resolve",
        httpx.ConnectError("[Errno 8] nodename nor servname provided, or not known"),
        U,
        None,
    ),
    ("connect timeout", httpx.ConnectTimeout("timed out"), T, None),
    ("read timeout", httpx.ReadTimeout("timed out"), T, None),
    (
        "429",
        json_response(429, error_body("Rate limit reached for requests", kind="requests")),
        R,
        429,
    ),
    ("500", json_response(500, error_body("The server had an error", kind="server_error")), S, 500),
    ("503", json_response(503, error_body("The engine is currently overloaded")), S, 503),
    (
        "404, code model_not_found",
        json_response(404, error_body("The model `x` does not exist", code="model_not_found")),
        N,
        404,
    ),
    (
        "404, a message: the model does not exist",
        json_response(
            404, error_body("The model `invented-x` does not exist or you have no access")
        ),
        N,
        404,
    ),
    (
        "404, a message: model not found",
        json_response(404, error_body('model "invented-x" not found, try pulling it first')),
        N,
        404,
    ),
    ("404, error is Not Found as text", json_response(404, {"error": "Not Found"}), S, 404),
    ("404, an error object saying Not Found", json_response(404, error_body("Not Found")), S, 404),
    (
        "404, an unknown address",
        json_response(404, error_body("Unknown request URL: POST /v1/chat/completion")),
        S,
        404,
    ),
    ("404, a page", httpx.Response(404, content=b"<html>404 page not found</html>"), S, 404),
    (
        "404, code of another kind",
        json_response(404, error_body("No such route", code="not_found")),
        S,
        404,
    ),
    (
        "400",
        json_response(400, error_body("Invalid schema for response_format 'reply'")),
        S,
        400,
    ),
    (
        "401",
        json_response(401, error_body("Incorrect API key provided", kind="invalid_request_error")),
        S,
        401,
    ),
    (
        "403",
        json_response(403, error_body("You are not allowed to sample from this model")),
        S,
        403,
    ),
    ("200, not JSON", httpx.Response(200, content=b"<html>hello</html>"), M, 200),
    ("200, no choices", json_response(200, {"id": "x", "model": MODEL}), M, 200),
    ("200, empty content", json_response(200, completion("")), M, 200),
]


@pytest.mark.parametrize(
    ("step", "kind", "status"),
    [pytest.param(step, kind, status, id=name) for name, step, kind, status in CASES],
)
def test_each_case_falls_into_its_kind_with_one_try(
    step: httpx.Response | Exception, kind: ModelErrorKind, status: int | None
) -> None:
    server = FakeServer([step])

    with pytest.raises(ModelError) as caught:
        CloudModel(CLOUD_SETTINGS, transport=server.transport).chat(HELLO)

    assert caught.value.kind is kind
    assert caught.value.status == status
    assert len(server.requests) == 1


def test_every_kind_has_a_case() -> None:
    assert {kind for _, _, kind, _ in CASES} == set(ModelErrorKind)


def test_a_missing_model_names_the_model_and_the_address() -> None:
    server = FakeServer([json_response(404, error_body("x", code="model_not_found"))])

    with pytest.raises(ModelError) as caught:
        CloudModel(CLOUD_SETTINGS, transport=server.transport).chat(HELLO)

    assert MODEL in caught.value.message
    assert CLOUD_SETTINGS.base_url in caught.value.message


@pytest.mark.parametrize("status", [400, 401, 403])
def test_a_refusal_keeps_its_status_and_the_start_of_what_the_server_said(status: int) -> None:
    server = FakeServer([json_response(status, error_body("Invented refusal"))])

    with pytest.raises(ModelError) as caught:
        CloudModel(CLOUD_SETTINGS, transport=server.transport).chat(HELLO)

    assert caught.value.kind is ModelErrorKind.SERVER_ERROR
    assert caught.value.status == status
    assert caught.value.snippet is not None
    assert "Invented refusal" in caught.value.snippet
