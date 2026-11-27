"""Tests of the guard in ``conftest.py``: a test without the live mark cannot connect.

These tests carry no mark, so the guard is on while they run. Each tries to
connect in a different way and must be stopped before any connection is
made. The address is a port on this machine that nothing listens on, so even
a broken guard would send nothing anywhere; the tests that need to tell the
guard apart from a refused connection open their own listening port on this
machine instead. On Windows ``socket.socketpair()`` is built with a connect on
127.0.0.1, which the guard lets through only while that call runs and only on
its own thread; the socket-pair tests here hold it to that.
"""

from __future__ import annotations

import socket
import sys
import threading
import urllib.request
from collections.abc import Iterator

import httpx
import pytest

from ledger_hand.llm.local import connect_local_model
from ledger_hand.llm.ollama import OllamaModel
from ledger_hand.llm.ollama_identity import ask_identity
from ledger_hand.ports import Message, Role
from ledger_hand.settings import ModelSettings
from tests import conftest as guard
from tests.conftest import LIVE_MARK, NetworkInTestError

NOWHERE = "http://127.0.0.1:9"
HELLO = [Message(Role.USER, "hello")]


def test_httpx_cannot_connect() -> None:
    with pytest.raises(NetworkInTestError, match=LIVE_MARK):
        httpx.get(NOWHERE)


def test_the_plug_with_its_real_transport_cannot_connect() -> None:
    model = OllamaModel(ModelSettings(base_url=NOWHERE, retries=0))

    # The guard's error goes straight through the plug: it is not sorted into a
    # kind of model failure, so it cannot pass for "the server is not running".
    with pytest.raises(NetworkInTestError):
        model.chat(HELLO)


def test_the_assembled_local_model_cannot_connect() -> None:
    model = connect_local_model(ModelSettings(base_url=NOWHERE), sleep=lambda _: None)

    with pytest.raises(NetworkInTestError):
        model.chat(HELLO)


def test_asking_the_server_who_it_is_cannot_connect() -> None:
    with pytest.raises(NetworkInTestError):
        ask_identity(ModelSettings(base_url=NOWHERE))


def test_a_plain_socket_cannot_connect() -> None:
    with pytest.raises(NetworkInTestError):
        socket.create_connection(("127.0.0.1", 9), timeout=0.5)
    with socket.socket() as raw, pytest.raises(NetworkInTestError):
        raw.connect_ex(("127.0.0.1", 9))


@pytest.fixture
def listening_port() -> Iterator[int]:
    # A port on this machine that really listens, so a refused connect can
    # only be the guard: without it the connect would succeed.
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        yield listener.getsockname()[1]


def test_a_port_that_really_listens_on_this_machine_cannot_be_reached(listening_port: int) -> None:
    with pytest.raises(NetworkInTestError):
        socket.create_connection(("127.0.0.1", listening_port), timeout=0.5)
    with socket.socket() as raw, pytest.raises(NetworkInTestError):
        raw.connect(("127.0.0.1", listening_port))
    with socket.socket() as raw, pytest.raises(NetworkInTestError):
        raw.connect_ex(("127.0.0.1", listening_port))


def test_a_socket_pair_can_be_made_under_the_guard() -> None:
    # On Windows the pair is built with a connect on 127.0.0.1, which the
    # guard lets through while socket.socketpair() runs and at no other time.
    first, second = socket.socketpair()
    with first, second:
        first.sendall(b"ping")
        assert second.recv(4) == b"ping"


def test_after_a_socket_pair_the_guard_still_refuses(listening_port: int) -> None:
    first, second = socket.socketpair()
    first.close()
    second.close()

    with socket.socket() as raw, pytest.raises(NetworkInTestError):
        raw.connect(("127.0.0.1", listening_port))
    with socket.socket() as raw, pytest.raises(NetworkInTestError):
        raw.connect_ex(("127.0.0.1", listening_port))


def test_another_thread_gets_no_pass_while_a_socket_pair_is_being_made(
    listening_port: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The pass is kept per thread: while one thread is inside
    # socket.socketpair(), a connect from another thread is still refused.
    outcome: list[BaseException | None] = []

    def connect_from_elsewhere() -> None:
        with socket.socket() as raw:
            try:
                raw.connect(("127.0.0.1", listening_port))
            except BaseException as error:  # the guard's error is a BaseException
                outcome.append(error)
            else:
                outcome.append(None)

    def pair_that_lets_another_thread_connect(
        *_arguments: object, **_keywords: object
    ) -> tuple[socket.socket, socket.socket]:
        other = threading.Thread(target=connect_from_elsewhere)
        other.start()
        other.join()
        return socket.socket(), socket.socket()

    if sys.platform == "win32":
        # The pass exists only on Windows; there the real pair-making is
        # swapped for one that runs the other thread while the pass is on.
        monkeypatch.setattr(guard, "_real_socketpair", pair_that_lets_another_thread_connect)
        first, second = socket.socketpair()
        first.close()
        second.close()
    else:
        connect_from_elsewhere()

    assert len(outcome) == 1
    assert isinstance(outcome[0], NetworkInTestError)


def test_the_standard_library_cannot_connect() -> None:
    with pytest.raises(NetworkInTestError):
        urllib.request.urlopen(NOWHERE, timeout=0.5)


def test_the_fake_transport_still_works_under_the_guard() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=b"fine"))

    with httpx.Client(transport=transport) as client:
        assert client.get(NOWHERE).content == b"fine"


def test_the_guard_error_is_not_an_ordinary_exception() -> None:
    assert not issubclass(NetworkInTestError, Exception)
