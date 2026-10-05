"""Tests of the guard in ``conftest.py``: a test without the live mark cannot connect.

These tests carry no mark, so the guard is on while they run. Each tries to
connect in a different way and must be stopped before any connection is
made. The address is a port on this machine that nothing listens on, so even
a broken guard would send nothing anywhere.
"""

from __future__ import annotations

import socket
import urllib.request

import httpx
import pytest

from ledger_hand.llm.local import connect_local_model
from ledger_hand.llm.ollama import OllamaModel
from ledger_hand.llm.ollama_identity import ask_identity
from ledger_hand.ports import Message, Role
from ledger_hand.settings import ModelSettings
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


def test_the_standard_library_cannot_connect() -> None:
    with pytest.raises(NetworkInTestError):
        urllib.request.urlopen(NOWHERE, timeout=0.5)


def test_the_fake_transport_still_works_under_the_guard() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=b"fine"))

    with httpx.Client(transport=transport) as client:
        assert client.get(NOWHERE).content == b"fine"


def test_the_guard_error_is_not_an_ordinary_exception() -> None:
    assert not issubclass(NetworkInTestError, Exception)
