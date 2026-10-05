"""Tests of one HTTP exchange: how failed connections, statuses and bodies are sorted."""

from __future__ import annotations

import gzip

import httpx
import pytest

from ledger_hand.llm.exchange import (
    MAX_ANSWER_BYTES,
    Answer,
    Endpoint,
    exchange,
    failure_for_status,
    malformed,
)
from ledger_hand.ports import ModelError, ModelErrorKind
from ledger_hand.settings import Secret
from tests.llm.fake_server import Endless, FakeClock, FakeServer, Pieces

BASE = "http://127.0.0.1:11434"


def endpoint(server: FakeServer, clock: FakeClock | None = None) -> Endpoint:
    return Endpoint(
        base_url=BASE, api_key=None, transport=server.transport, clock=clock or FakeClock()
    )


def send(server: FakeServer, clock: FakeClock | None = None, timeout: float = 30) -> Answer:
    return exchange(
        endpoint(server, clock), "POST", "/api/chat", content=b"{}", timeout_seconds=timeout
    )


def fails_as(server: FakeServer, clock: FakeClock | None = None, timeout: float = 30) -> ModelError:
    with pytest.raises(ModelError) as caught:
        send(server, clock, timeout)
    return caught.value


# --- failed connections -----------------------------------------------------


@pytest.mark.parametrize(
    "error",
    [
        httpx.ConnectError("[Errno 61] Connection refused"),
        httpx.ConnectError("[Errno 8] nodename nor servname provided, or not known"),
        httpx.ConnectError(""),
        httpx.UnsupportedProtocol("Request URL has an unsupported protocol 'ftp://'."),
        httpx.InvalidURL("Invalid port"),
    ],
)
def test_a_connection_that_cannot_be_made_is_unreachable(error: Exception) -> None:
    found = fails_as(FakeServer([error]))

    assert found.kind is ModelErrorKind.UNREACHABLE
    assert BASE in found.message
    assert found.message.rstrip().endswith(str(error) or type(error).__name__)


@pytest.mark.parametrize(
    "error",
    [
        httpx.ConnectTimeout("timed out"),
        httpx.ReadTimeout("timed out"),
        httpx.WriteTimeout("timed out"),
        httpx.PoolTimeout("timed out"),
    ],
)
def test_any_wait_past_its_limit_is_timed_out(error: Exception) -> None:
    found = fails_as(FakeServer([error]), timeout=7.5)

    assert found.kind is ModelErrorKind.TIMED_OUT
    assert "within 7.5 seconds" in found.message


@pytest.mark.parametrize(
    "error",
    [
        httpx.RemoteProtocolError("Server disconnected without sending a response."),
        httpx.ReadError("[Errno 54] Connection reset by peer"),
        httpx.WriteError("[Errno 32] Broken pipe"),
        httpx.LocalProtocolError("Illegal header value"),
        httpx.ProxyError("proxy refused"),
        httpx.CloseError("close failed"),
        httpx.TooManyRedirects("Exceeded maximum allowed redirects."),
        httpx.DecodingError("broken before any body"),
    ],
)
def test_any_other_failure_of_the_exchange_is_a_server_error_with_its_raw_cause(
    error: Exception,
) -> None:
    found = fails_as(FakeServer([error]))

    assert found.kind is ModelErrorKind.SERVER_ERROR
    assert type(error).__name__ in found.message
    assert "no other kind fits" in found.message


def test_a_failure_that_is_not_from_httpx_is_not_hidden() -> None:
    # A mistake in the program is not a model failure and must not pass for one.
    with pytest.raises(KeyError):
        send(FakeServer([KeyError("a bug")]))


# --- bodies -----------------------------------------------------------------


def test_the_status_and_whole_body_come_back() -> None:
    answer = send(FakeServer([httpx.Response(201, content=b"abc")]))

    assert answer == Answer(201, b"abc")


def test_a_body_in_pieces_is_put_together() -> None:
    answer = send(FakeServer([httpx.Response(200, stream=Pieces([b"ab", b"", b"cd"]))]))

    assert answer.body == b"abcd"


def test_a_body_that_never_ends_is_stopped_at_the_cap() -> None:
    endless = Endless(b"x" * 65536)

    answer = send(FakeServer([httpx.Response(200, stream=endless)]))

    assert answer.body == b""
    assert answer.body_problem is not None
    assert str(MAX_ANSWER_BYTES) in answer.body_problem
    assert endless.sent == MAX_ANSWER_BYTES // 65536 + 1


def test_a_body_exactly_at_the_cap_is_taken() -> None:
    body = b"y" * MAX_ANSWER_BYTES

    assert send(FakeServer([httpx.Response(200, content=body)])).body == body


def test_a_compressed_body_is_kept_as_it_came_and_never_expanded() -> None:
    bomb = gzip.compress(b"0" * (MAX_ANSWER_BYTES * 4))
    compressed = httpx.Response(200, stream=Pieces([bomb]), headers={"Content-Encoding": "gzip"})

    answer = send(FakeServer([compressed]))

    assert answer.body == bomb
    assert len(answer.body) < MAX_ANSWER_BYTES
    assert answer.body_problem is None


def test_the_request_asks_for_no_compression() -> None:
    server = FakeServer([httpx.Response(200, content=b"{}")])

    send(server)

    assert server.requests[0].headers["accept-encoding"] == "identity"


def test_a_body_still_arriving_after_the_deadline_is_abandoned() -> None:
    clock = FakeClock(step=1.0)

    found = fails_as(FakeServer([httpx.Response(200, stream=Pieces([b"."] * 100))]), clock, 3)

    assert found.kind is ModelErrorKind.TIMED_OUT


def test_a_whole_answer_that_comes_in_after_the_deadline_is_abandoned() -> None:
    clock = FakeClock(step=10.0)

    found = fails_as(FakeServer([httpx.Response(200, content=b"{}")]), clock, 5)

    assert found.kind is ModelErrorKind.TIMED_OUT


def test_a_body_that_breaks_off_is_a_server_error() -> None:
    stream = Pieces([b'{"mess'], then=httpx.RemoteProtocolError("peer closed connection"))

    found = fails_as(FakeServer([httpx.Response(200, stream=stream)]))

    assert found.kind is ModelErrorKind.SERVER_ERROR
    assert "RemoteProtocolError" in found.message


# --- what is sent -----------------------------------------------------------


def test_the_request_asks_for_json_and_carries_no_key_without_one() -> None:
    server = FakeServer([httpx.Response(200, content=b"{}")])

    send(server)

    headers = server.requests[0].headers
    assert headers["accept"] == "application/json"
    assert headers["content-type"] == "application/json"
    assert "authorization" not in headers


def test_a_key_travels_only_in_the_authorization_header() -> None:
    server = FakeServer([httpx.Response(200, content=b"{}")])
    keyed = Endpoint(base_url=BASE, api_key=Secret("invented-789"), transport=server.transport)

    exchange(keyed, "GET", "/api/version", content=None, timeout_seconds=5)

    request = server.requests[0]
    assert request.headers["authorization"] == "Bearer invented-789"
    assert "invented-789" not in str(request.url)


def test_redirects_are_not_followed() -> None:
    server = FakeServer([httpx.Response(307, headers={"Location": "http://elsewhere.example/"})])

    assert send(server).status == 307
    assert len(server.requests) == 1


def test_proxy_settings_in_the_environment_are_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HTTP_PROXY", "http://proxy.invalid:3128")
    monkeypatch.setenv("ALL_PROXY", "http://proxy.invalid:3128")
    server = FakeServer([httpx.Response(200, content=b"{}")])

    assert send(server).status == 200
    assert server.requests[0].url.host == "127.0.0.1"


# --- statuses ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "kind"),
    [
        (429, ModelErrorKind.RATE_LIMITED),
        (500, ModelErrorKind.SERVER_ERROR),
        (502, ModelErrorKind.SERVER_ERROR),
        (503, ModelErrorKind.SERVER_ERROR),
        (599, ModelErrorKind.SERVER_ERROR),
    ],
)
def test_statuses_that_are_recognised(status: int, kind: ModelErrorKind) -> None:
    error = failure_for_status(Answer(status, b'{"error": "x"}'), endpoint(FakeServer([])))

    assert error.kind is kind
    assert error.status == status
    assert "does not expect" not in error.message


@pytest.mark.parametrize(
    "status", [100, 201, 204, 301, 400, 401, 403, 404, 405, 418, 422, 499, 600]
)
def test_any_other_status_is_a_server_error_with_the_raw_status(status: int) -> None:
    error = failure_for_status(Answer(status, b"odd"), endpoint(FakeServer([])))

    assert error.kind is ModelErrorKind.SERVER_ERROR
    assert error.status == status
    assert error.snippet == "odd"
    assert "does not expect" in error.message


def test_a_malformed_answer_carries_its_status_and_start() -> None:
    error = malformed("is not JSON", Answer(200, b"<html>"), endpoint(FakeServer([])))

    assert error.kind is ModelErrorKind.MALFORMED_REPLY
    assert error.message == "the model server's answer is not JSON"
    assert error.status == 200
    assert error.snippet == "<html>"
