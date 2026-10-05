"""Shared test set-up: no test reaches the network unless it is marked ``live_model``.

For every test without the mark, connecting is replaced by a function that
fails the test on the spot: httpx's real transports, and below them every
socket connection, whatever library tries it. The test fails with a message
that says why, and no connection is attempted. The fake transports the tests
use instead (``httpx.MockTransport``) are not touched.

Tests marked ``live_model`` talk to a real model server on purpose. They are
left out of ordinary runs (see ``addopts`` in ``pyproject.toml``) and run only
by the live tier of ``scripts/check.sh``.

Names defined here: ``LIVE_MARK``, ``NetworkInTestError``.
"""

from __future__ import annotations

import socket
from typing import NoReturn

import httpx
import pytest

LIVE_MARK = "live_model"


class NetworkInTestError(BaseException):
    """A test without the live mark tried to connect.

    A ``BaseException`` rather than an ``Exception``, so that no handler in
    the code under test (the model plug sorts httpx's exceptions into kinds)
    can catch it and turn it into an ordinary failure.
    """


def _refuse(*_arguments: object, **_keywords: object) -> NoReturn:
    raise NetworkInTestError(
        f"this test tried to reach the network; only tests marked {LIVE_MARK!r} may, "
        "and the others use a fake transport"
    )


@pytest.fixture(autouse=True)
def _no_network_without_the_live_mark(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    if request.node.get_closest_marker(LIVE_MARK) is not None:
        return
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", _refuse)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", _refuse)
    monkeypatch.setattr(socket.socket, "connect", _refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", _refuse)
