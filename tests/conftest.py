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
import sys
import threading
from typing import Any, NoReturn

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
    if sys.platform == "win32":
        _let_socketpair_connect_on_windows(monkeypatch)


# Windows has no ready-made pair of connected sockets, so the standard library
# builds ``socket.socketpair()`` from a listener on 127.0.0.1 and one
# ``connect`` to it; every new event loop makes such a pair. On Windows only,
# that one ``connect`` is let through: only while ``socket.socketpair()`` runs,
# and only on the thread that called it. Any other connect, to 127.0.0.1 or
# anywhere, is still refused. macOS and Linux build the pair without
# connecting, so the guard there is exactly the four lines above.
_inside_socketpair = threading.local()
_real_connect = socket.socket.connect
_real_socketpair = socket.socketpair


def _socketpair_marked(*arguments: Any, **keywords: Any) -> tuple[socket.socket, socket.socket]:
    _inside_socketpair.active = True
    try:
        return _real_socketpair(*arguments, **keywords)
    finally:
        _inside_socketpair.active = False


def _connect_only_inside_socketpair(self: socket.socket, *arguments: Any) -> None:
    if getattr(_inside_socketpair, "active", False):
        _real_connect(self, *arguments)
        return
    _refuse()


def _let_socketpair_connect_on_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(socket, "socketpair", _socketpair_marked)
    monkeypatch.setattr(socket.socket, "connect", _connect_only_inside_socketpair)
