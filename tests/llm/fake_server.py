"""A fake Ollama server for the plug's tests, built on httpx's mock transport.

``FakeServer`` answers each request with the next of its steps: an
``httpx.Response`` to return, or an exception to raise as the transport
would. It records every request it was sent. Its ``transport`` is handed to
the plug in place of the network, so no port is opened and nothing leaves
the process.

``mock_transport`` is httpx's mock transport with one change: a response
built from ready content (which httpx reads at once) is handed back as an
unread stream, the way the network hands responses back. The plug reads
bodies as they arrive, so it needs them unread.

The rest are pieces for building answers: the body of a normal chat reply,
response bodies that break off, trickle or never end, and a clock that
moves only when it is read.

Names defined here: ``SETTINGS``, ``chat_reply``, ``json_response``,
``mock_transport``, ``FakeServer``, ``Pieces``, ``Endless``, ``FakeClock``.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field

import httpx

from ledger_hand.settings import ModelSettings

# Default settings, but with no retries and no wait, so a test sees one try.
SETTINGS = ModelSettings(retries=0, retry_wait_seconds=0.0)

type Step = httpx.Response | Exception


def chat_reply(content: str = '{"fruit": "apple"}', **fields: object) -> dict[str, object]:
    """The body of a normal answer from Ollama's chat endpoint, with ``fields`` changed."""
    body: dict[str, object] = {
        "model": SETTINGS.model,
        "created_at": "2026-01-02T03:04:05.000000Z",
        "message": {"role": "assistant", "content": content},
        "done": True,
        "done_reason": "stop",
        "total_duration": 3888024583,
        "prompt_eval_count": 44,
        "eval_count": 14,
    }
    body.update(fields)
    return body


def json_response(status: int, data: object) -> httpx.Response:
    return httpx.Response(status, content=json.dumps(data).encode("utf-8"))


def mock_transport(answer: Callable[[httpx.Request], httpx.Response]) -> httpx.MockTransport:
    """httpx's mock transport, handing every response back unread, as the network does."""

    def handle(request: httpx.Request) -> httpx.Response:
        response = answer(request)
        if not response.is_stream_consumed:
            return response
        return httpx.Response(
            response.status_code,
            headers=response.headers,
            stream=httpx.ByteStream(response.content),
        )

    return httpx.MockTransport(handle)


@dataclass
class FakeServer:
    """Answers request number N with step number N, and records the requests."""

    steps: list[Step]
    requests: list[httpx.Request] = field(default_factory=list)

    @property
    def transport(self) -> httpx.MockTransport:
        return mock_transport(self._answer)

    def sent_json(self, number: int = 0) -> object:
        """The body of request ``number``, read back as JSON."""
        return json.loads(self.requests[number].content)

    def _answer(self, request: httpx.Request) -> httpx.Response:
        request.read()
        self.requests.append(request)
        if len(self.requests) > len(self.steps):
            raise AssertionError(f"the fake server got request {len(self.requests)} unexpectedly")
        step = self.steps[len(self.requests) - 1]
        if isinstance(step, Exception):
            raise step
        return step


class Pieces(httpx.SyncByteStream):
    """A body sent in pieces, which may end by raising an error mid-way."""

    def __init__(self, pieces: list[bytes], then: Exception | None = None) -> None:
        self._pieces = pieces
        self._then = then

    def __iter__(self) -> Iterator[bytes]:
        yield from self._pieces
        if self._then is not None:
            raise self._then


class Endless(httpx.SyncByteStream):
    """A body that never ends: the same piece, again and again. Counts what it sent."""

    def __init__(self, piece: bytes) -> None:
        self._piece = piece
        self.sent = 0

    def __iter__(self) -> Iterator[bytes]:
        while True:
            self.sent += 1
            yield self._piece


class FakeClock:
    """A clock that moves forward by ``step`` seconds each time it is read."""

    def __init__(self, step: float = 0.0, start: float = 1000.0) -> None:
        self.step = step
        self.now = start
        self.reads = 0

    def __call__(self) -> float:
        value = self.now
        self.now += self.step
        self.reads += 1
        return value
