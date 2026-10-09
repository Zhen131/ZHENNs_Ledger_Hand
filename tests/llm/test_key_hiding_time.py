"""Hiding the key takes time in step with the length of the answer, whatever the answer holds.

A server that answers with a long run of backslashes, or with a long run of
escapes, must not make hiding the key take long: the cap on an answer's
size and the time allowed for a call would mean nothing if handing back the
error took minutes. Each case is first timed on a short answer, with a bound
that a time growing with the square of the length would already break, so
that a slow way of hiding fails here in about a second instead of running
for hours; then on an answer of 1 MiB, with the bound of one second. Every
key is invented.
"""

from __future__ import annotations

import dataclasses
import time
from collections.abc import Callable

import httpx
import pytest

from ledger_hand.llm.cloud import CloudModel
from ledger_hand.llm.error_text import HIDDEN, hide, snippet
from ledger_hand.llm.ollama import OllamaModel
from ledger_hand.ports import Message, ModelError, ModelPort, Role
from ledger_hand.settings import ModelSettings, Secret
from tests.llm.fake_cloud import CLOUD_SETTINGS
from tests.llm.fake_server import mock_transport

# A key holding every character a way of writing escapes, a backslash among them.
KEY = "sk-invented-\"time\\key%41&<b>/'end"
SHORT = 16 * 1024
LONG = 1024 * 1024
# With the time growing with the square of the length, 16 KiB of backslashes
# took over a second; growing in step with it, it takes well under a hundredth.
SHORT_BOUND_SECONDS = 0.5
LONG_BOUND_SECONDS = 1.0
HELLO = [Message(Role.USER, "hello")]

SHAPES = {
    "backslashes": "\\",
    "backslash and a letter": "\\a",
    "percent escapes": "%41",
    "numbered entities": "&#65;",
    "unicode escapes": "\\u0041",
    "every escape and backslashes": "\\\\u0041%41&amp;\\",
}


def body(shape: str, size: int) -> str:
    unit = SHAPES[shape]
    return unit * (size // len(unit))


def timed(work: Callable[[], object]) -> float:
    started = time.perf_counter()
    work()
    return time.perf_counter() - started


@pytest.mark.parametrize("shape", list(SHAPES))
def test_hiding_the_key_in_a_long_text_of_escapes_takes_time_in_step_with_its_length(
    shape: str,
) -> None:
    secret = Secret(KEY)

    assert timed(lambda: hide(body(shape, SHORT), secret)) < SHORT_BOUND_SECONDS
    assert timed(lambda: snippet(body(shape, LONG).encode(), secret)) < LONG_BOUND_SECONDS


def test_the_key_written_back_at_the_end_of_a_long_text_of_escapes_is_hidden_in_time() -> None:
    secret = Secret(KEY)
    written = KEY.replace("\\", "\\\\").replace('"', '\\"')
    text = body("backslash and a letter", LONG) + " " + written

    started = time.perf_counter()
    hidden = hide(text, secret)
    took = time.perf_counter() - started

    assert hidden.endswith(" " + HIDDEN)
    assert took < LONG_BOUND_SECONDS


def local(transport: httpx.BaseTransport) -> ModelPort:
    settings = ModelSettings(api_key=Secret(KEY), retries=0, retry_wait_seconds=0.0)
    return OllamaModel(settings, transport=transport)


def cloud(transport: httpx.BaseTransport) -> ModelPort:
    return CloudModel(dataclasses.replace(CLOUD_SETTINGS, api_key=Secret(KEY)), transport=transport)


PLUGS = {"local": local, "cloud": cloud}


def failing_in(plug: str, status: int, content: str) -> float:
    transport = mock_transport(lambda _: httpx.Response(status, content=content.encode()))
    model = PLUGS[plug](transport)
    started = time.perf_counter()
    with pytest.raises(ModelError):
        model.chat(HELLO)
    return time.perf_counter() - started


@pytest.mark.parametrize("status", [400, 200])
@pytest.mark.parametrize("plug", list(PLUGS))
def test_an_answer_of_backslashes_is_handed_back_as_fast_as_a_plain_one(
    plug: str, status: int
) -> None:
    assert failing_in(plug, status, body("backslashes", SHORT)) < SHORT_BOUND_SECONDS

    plain = failing_in(plug, status, "x" * LONG)
    backslashes = failing_in(plug, status, body("backslashes", LONG))

    assert plain < LONG_BOUND_SECONDS
    assert backslashes < LONG_BOUND_SECONDS
