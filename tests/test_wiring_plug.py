"""Tests of building the parts with the plug the settings choose, and refusing what does not fit.

The environment may choose the cloud plug; the settings page may switch to
it. When the address and the key do not fit a cloud service, the plug is not
built: a refused setting when the environment's settings do not fit, a
refused change when the page's changes make them not fit, and the parts
stay as they were. When they fit, the parts hold the cloud plug, wrapped in
retries, and building sends nothing. Every value is invented.
"""

from __future__ import annotations

import os
from pathlib import Path

import httpx
import pytest
import tzlocal

from ledger_hand.llm.retry import RetryingModel
from ledger_hand.ports import Message, Role
from ledger_hand.settings import DATA_DIRECTORY_VARIABLE, ENV_PREFIX, Plug, Variable
from ledger_hand.wiring import AssemblyError, AssemblyProblem, assemble
from tests.conftest import NetworkInTestError

KEY = "sk-invented-wiring-plug-0123456789"
ADDRESS = "https://api.example.com/v1"


@pytest.fixture
def machine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A machine in Europe/Budapest, with no model setting and the data in a temp folder."""
    for name in list(os.environ):
        if name.startswith(ENV_PREFIX):
            monkeypatch.delenv(name)
    data = tmp_path / "data"
    monkeypatch.setenv(DATA_DIRECTORY_VARIABLE, str(data))
    monkeypatch.setattr(tzlocal, "get_localzone_name", lambda: "Europe/Budapest")
    monkeypatch.chdir(tmp_path)
    return data


@pytest.mark.parametrize(
    ("environ", "variable"),
    [
        ({Variable.PLUG.value: "cloud"}, Variable.URL),
        (
            {Variable.PLUG.value: "cloud", Variable.URL.value: "http://192.0.2.7:8080/v1"},
            Variable.URL,
        ),
        ({Variable.PLUG.value: "cloud", Variable.URL.value: ADDRESS}, Variable.KEY),
    ],
    ids=["the local address", "http off this machine", "no key"],
)
def test_an_environment_whose_settings_do_not_fit_the_cloud_is_a_refused_setting(
    machine: Path, monkeypatch: pytest.MonkeyPatch, environ: dict[str, str], variable: Variable
) -> None:
    for name, value in environ.items():
        monkeypatch.setenv(name, value)

    with pytest.raises(AssemblyError) as raised:
        assemble()

    assert raised.value.problem is AssemblyProblem.SETTING_REFUSED
    assert variable.value in str(raised.value)


@pytest.mark.parametrize(
    ("changes", "variable"),
    [
        ({Variable.PLUG: "cloud"}, Variable.URL),
        ({Variable.PLUG: "cloud", Variable.URL: "http://192.0.2.7:8080/v1"}, Variable.URL),
        ({Variable.PLUG: "cloud", Variable.URL: ADDRESS}, Variable.KEY),
    ],
    ids=["the local address", "http off this machine", "no key"],
)
def test_a_switch_to_the_cloud_on_the_page_that_does_not_fit_is_a_refused_change(
    machine: Path, changes: dict[Variable, str], variable: Variable
) -> None:
    with pytest.raises(AssemblyError) as raised:
        assemble(changes)

    assert raised.value.problem is AssemblyProblem.CHANGE_REFUSED
    assert raised.value.detail.startswith(f"{variable.value}: ")


def test_a_switch_to_the_cloud_with_the_environments_key_fits(
    machine: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(Variable.KEY.value, KEY)

    parts = assemble({Variable.PLUG: "cloud", Variable.URL: ADDRESS})

    assert parts.settings.plug is Plug.CLOUD
    assert isinstance(parts.model, RetryingModel)
    assert KEY not in repr(parts.settings)


def test_a_cloud_chosen_in_the_environment_is_built_and_cannot_reach_the_network_in_a_test(
    machine: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(Variable.PLUG.value, "cloud")
    monkeypatch.setenv(Variable.URL.value, ADDRESS)
    monkeypatch.setenv(Variable.KEY.value, KEY)
    monkeypatch.setenv(Variable.RETRIES.value, "0")

    parts = assemble()

    assert parts.settings.plug is Plug.CLOUD
    # The guard in conftest.py stops the real transport before any connection.
    with pytest.raises(NetworkInTestError):
        parts.model.chat([Message(Role.USER, "hello")])


def test_the_real_transport_is_stopped_before_anything_is_sent(
    machine: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent: list[httpx.Request] = []
    real = httpx.HTTPTransport.handle_request

    def record(self: httpx.HTTPTransport, request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return real(self, request)

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", record)
    monkeypatch.setenv(Variable.PLUG.value, "cloud")
    monkeypatch.setenv(Variable.URL.value, ADDRESS)
    monkeypatch.setenv(Variable.KEY.value, KEY)
    monkeypatch.setenv(Variable.RETRIES.value, "0")

    with pytest.raises(NetworkInTestError):
        assemble().model.chat([Message(Role.USER, "hello")])

    assert [str(request.url) for request in sent] == [f"{ADDRESS}/chat/completions"]
