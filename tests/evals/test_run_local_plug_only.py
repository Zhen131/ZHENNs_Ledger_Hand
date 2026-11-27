"""The experiment runner takes the plug the settings choose; Ollama is asked only for the local one.

The runner asks Ollama itself who the model is, to record its fingerprint;
a cloud service has no such question. So with settings that choose the
cloud plug, Ollama is never asked and no local plug is made: the cloud plug
is built through ``connect_model``, and the first line says the service
gives no fingerprint. Settings that do not fit the plug they choose are
refused where the backend is built, and the run stops as any run that
cannot start does: exit status 2, nothing written. The real way of building
the backend (``local_backend``) is used, with the places that would reach a
server replaced by recorders. The address is a port on this machine that
nothing listens on, and the key is invented, so nothing is sent anywhere.
"""

from __future__ import annotations

import io
import json
import os
from pathlib import Path

import pytest

from evals import run as runner
from ledger_hand.ports import Message, ModelError, ModelErrorKind, ModelParameters
from ledger_hand.settings import ENV_PREFIX, ModelSettings
from tests.evals.test_run import D01
from tests.evals.test_run_second_model import Machine

NOWHERE = "http://127.0.0.1:59999"
# Another address of a local server: the plug, not the address, decides.
ELSEWHERE = "http://127.0.0.1:59998"


class Recorder:
    """Stands for the two calls that reach a server; records each call and answers nothing."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def ask_identity(self, settings: ModelSettings) -> None:
        self.calls.append(("ask_identity", settings.model))

    def connect_local_model(self, settings: ModelSettings) -> None:
        self.calls.append(("connect_local_model", settings.model))


class Unreachable:
    """Stands for the cloud plug: every call fails as if the service could not be reached."""

    def __init__(self, settings: ModelSettings) -> None:
        self.settings = settings

    def chat(
        self,
        messages: list[Message],
        *,
        reply_schema: object = None,
        parameters: ModelParameters | None = None,
    ) -> None:
        raise ModelError(ModelErrorKind.UNREACHABLE, "invented: nothing answered")


@pytest.fixture
def cloud_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in list(os.environ):
        if name.startswith(ENV_PREFIX):
            monkeypatch.delenv(name)
    monkeypatch.setenv(f"{ENV_PREFIX}PLUG", "cloud")
    monkeypatch.setenv(f"{ENV_PREFIX}URL", NOWHERE)
    monkeypatch.setenv(f"{ENV_PREFIX}KEY", "invented-key-for-a-test")
    monkeypatch.setenv(f"{ENV_PREFIX}NAME", "some-cloud-model")


@pytest.mark.usefixtures("cloud_settings")
@pytest.mark.parametrize(
    ("arguments", "model"),
    [
        (["--only", "d01"], "some-cloud-model"),
        (["--only", "d01", "--model", "another-model:8b"], "another-model:8b"),
        (["--only", "d01", "--method", "split_first"], "some-cloud-model"),
    ],
)
def test_cloud_settings_ask_no_ollama_and_say_so_in_the_first_line(
    arguments: list[str], model: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorder = Recorder()
    monkeypatch.setattr(runner, "ask_identity", recorder.ask_identity)
    monkeypatch.setattr(runner, "connect_local_model", recorder.connect_local_model)
    monkeypatch.setattr(runner, "connect_model", Unreachable)
    out = io.StringIO()

    status = runner.main(arguments, out=out, results_dir=tmp_path)

    assert status == 0, out.getvalue()
    assert recorder.calls == []
    (path,) = [p for p in tmp_path.iterdir() if p.suffix == ".jsonl"]
    first, sentence = [json.loads(line) for line in path.read_text("utf-8").splitlines()][:2]
    assert first["model"] == model
    assert first["model_fingerprint"] == runner.NOT_GIVEN
    assert first["server_version"] == runner.NOT_GIVEN
    assert (first["plug"], first["service"], first["reply_format"]) == (
        "cloud",
        "cloud",
        "json_schema",
    )
    assert sentence["failure"] == {"kind": "unreachable", "message": "unreachable"}
    assert "invented-key-for-a-test" not in path.read_text("utf-8")


def test_a_cloud_plug_without_its_key_is_refused_naming_the_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in list(os.environ):
        if name.startswith(ENV_PREFIX):
            monkeypatch.delenv(name)
    monkeypatch.setenv(f"{ENV_PREFIX}PLUG", "deepseek")
    monkeypatch.setenv(f"{ENV_PREFIX}KEY", "invented-key-for-a-test")
    recorder = Recorder()
    monkeypatch.setattr(runner, "ask_identity", recorder.ask_identity)
    monkeypatch.setattr(runner, "connect_local_model", recorder.connect_local_model)
    out = io.StringIO()

    status = runner.main(["--only", "d01"], out=out, results_dir=tmp_path)

    assert status == 2
    assert out.getvalue().startswith("cannot start: DEEPSEEK_API_KEY")
    assert "invented-key-for-a-test" not in out.getvalue()
    assert recorder.calls == []
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("plug", ["local", None])
def test_the_local_plug_runs_whatever_its_address(
    plug: str | None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in list(os.environ):
        if name.startswith(ENV_PREFIX):
            monkeypatch.delenv(name)
    if plug is not None:
        monkeypatch.setenv(f"{ENV_PREFIX}PLUG", plug)
    monkeypatch.setenv(f"{ENV_PREFIX}URL", ELSEWHERE)
    machine = Machine(D01)
    monkeypatch.setattr(runner, "ask_identity", machine.ask_identity)
    monkeypatch.setattr(runner, "connect_local_model", machine.connect_local_model)
    out = io.StringIO()

    status = runner.main(["--only", "d01"], out=out, results_dir=tmp_path)

    assert status == 0, out.getvalue()
    assert machine.asked == ["qwen2.5:7b"]
    assert machine.built == ["qwen2.5:7b"]
