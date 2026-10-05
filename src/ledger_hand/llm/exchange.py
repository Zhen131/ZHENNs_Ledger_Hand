"""One HTTP exchange with a model server, and what its failures mean.

``exchange`` sends one request and reads the whole answer, under a deadline
and a cap on its size, and returns an ``Answer``: the status and the body.
When the connection itself fails it raises ``ModelError`` instead, sorted by
what is recognised:

- the connection could not be made (refused, or the name does not resolve),
  or the address is one httpx cannot use: ``UNREACHABLE``;
- a wait passed the time allowed, or the whole answer was not in by the
  deadline: ``TIMED_OUT``;
- any other failure httpx reports (the connection broke off in the middle of
  the answer, the server spoke broken HTTP, too many redirects...): it fits
  no kind, so it is ``SERVER_ERROR``, with the raw error in the message.

The time allowed is counted from sending. Connecting, sending and each wait
for the next piece of the answer are each cut off at the time allowed, and
an answer still arriving once that time has passed is abandoned at its next
piece, however steadily its pieces keep coming.

A body longer than ``MAX_ANSWER_BYTES`` does not raise here: the answer
says so, and what that means depends on the status. Bodies are never
expanded: the request asks for no compression, and a body compressed anyway
is kept as the bytes that came, which are then not JSON. So a small
compressed body cannot swell into a huge one in memory before the cap sees
it. ``failure_for_status`` sorts an answer whose status
is not the success the caller expected: 429 is ``RATE_LIMITED``, 500 to 599
is ``SERVER_ERROR``, and any other status is ``SERVER_ERROR`` with the raw
status and the start of the body. ``malformed`` builds the error for an
answer that came back in the wrong shape.

httpx is used with ``trust_env=False``: no proxy, certificate or password
setting is picked up from the environment, so a request for the model on
this machine never leaves it through a proxy.

Names defined here: ``MAX_ANSWER_BYTES``, ``Endpoint``, ``Answer``,
``exchange``, ``failure_for_status``, ``malformed``.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field

import httpx

from ledger_hand.llm.error_text import detail, snippet
from ledger_hand.ports import ModelError, ModelErrorKind
from ledger_hand.settings import Secret

# Far above any real answer: a reply of 32768 tokens is about 0.2 MB of JSON.
# The cap stops a server that never stops sending from filling the memory.
MAX_ANSWER_BYTES = 4 * 1024 * 1024


@dataclass(frozen=True, kw_only=True)
class Endpoint:
    """Where to send, with which key; and, for tests, the transport and the clock."""

    base_url: str
    api_key: Secret | None
    transport: httpx.BaseTransport | None = None
    clock: Callable[[], float] = field(default=time.monotonic)


@dataclass(frozen=True)
class Answer:
    """What came back: the status, and the body or why it could not be read."""

    status: int
    body: bytes
    body_problem: str | None = None


def exchange(
    endpoint: Endpoint,
    method: str,
    path: str,
    *,
    content: bytes | None,
    timeout_seconds: float,
) -> Answer:
    """Send one request to ``endpoint.base_url + path`` and read the whole answer."""
    deadline = endpoint.clock() + timeout_seconds
    try:
        with _client(endpoint, timeout_seconds) as client:
            request = client.build_request(
                method, endpoint.base_url + path, content=content, headers=_headers(endpoint)
            )
            response = client.send(request, stream=True)
            try:
                return _read(response, endpoint, deadline, timeout_seconds)
            finally:
                response.close()
    except httpx.TimeoutException:
        raise _timed_out(endpoint, timeout_seconds) from None
    except httpx.ConnectError as error:
        message = f"cannot reach the model server at {endpoint.base_url}: {_said(error, endpoint)}"
        raise ModelError(ModelErrorKind.UNREACHABLE, message) from None
    except (httpx.UnsupportedProtocol, httpx.InvalidURL) as error:
        message = f"cannot use the address {endpoint.base_url}: {_said(error, endpoint)}"
        raise ModelError(ModelErrorKind.UNREACHABLE, message) from None
    except httpx.HTTPError as error:
        message = (
            f"the exchange with the model server at {endpoint.base_url} failed in a way "
            f"no other kind fits: {type(error).__name__}: {_said(error, endpoint)}"
        )
        raise ModelError(ModelErrorKind.SERVER_ERROR, message) from None


def failure_for_status(answer: Answer, endpoint: Endpoint) -> ModelError:
    """The error for an answer whose status is not the success the caller expected."""
    shown = snippet(answer.body, endpoint.api_key)
    if answer.status == 429:
        message = "the model server refused the call because it was called too often"
        return ModelError(ModelErrorKind.RATE_LIMITED, message, status=429, snippet=shown)
    if 500 <= answer.status <= 599:
        message = "the model server reported an internal error"
        return ModelError(ModelErrorKind.SERVER_ERROR, message, status=answer.status, snippet=shown)
    message = "the model server answered with a status this program does not expect"
    return ModelError(ModelErrorKind.SERVER_ERROR, message, status=answer.status, snippet=shown)


def malformed(why: str, answer: Answer, endpoint: Endpoint) -> ModelError:
    """The error for an answer that came back, but not in the agreed shape."""
    return ModelError(
        ModelErrorKind.MALFORMED_REPLY,
        f"the model server's answer {why}",
        status=answer.status,
        snippet=snippet(answer.body, endpoint.api_key),
    )


def _client(endpoint: Endpoint, timeout_seconds: float) -> httpx.Client:
    return httpx.Client(
        transport=endpoint.transport,
        timeout=httpx.Timeout(timeout_seconds),
        trust_env=False,
        follow_redirects=False,
    )


def _headers(endpoint: Endpoint) -> dict[str, str]:
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "identity",
        "Content-Type": "application/json",
    }
    if endpoint.api_key is not None:
        headers["Authorization"] = f"Bearer {endpoint.api_key.reveal()}"
    return headers


def _read(
    response: httpx.Response, endpoint: Endpoint, deadline: float, timeout_seconds: float
) -> Answer:
    status = response.status_code
    pieces: list[bytes] = []
    size = 0
    for piece in response.iter_raw():
        size += len(piece)
        if size > MAX_ANSWER_BYTES:
            return Answer(status, b"", f"is longer than {MAX_ANSWER_BYTES} bytes")
        pieces.append(piece)
        if endpoint.clock() > deadline:
            raise _timed_out(endpoint, timeout_seconds)
    if endpoint.clock() > deadline:
        raise _timed_out(endpoint, timeout_seconds)
    return Answer(status, b"".join(pieces))


def _timed_out(endpoint: Endpoint, timeout_seconds: float) -> ModelError:
    message = (
        f"no complete answer from the model server at {endpoint.base_url} "
        f"within {timeout_seconds:g} seconds"
    )
    return ModelError(ModelErrorKind.TIMED_OUT, message)


def _said(error: Exception, endpoint: Endpoint) -> str:
    """What an exception says, made safe to show; its type when it says nothing."""
    return detail(str(error) or type(error).__name__, endpoint.api_key)
