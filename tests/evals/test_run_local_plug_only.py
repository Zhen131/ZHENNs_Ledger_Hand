"""The experiment runner uses the local plug only; cloud settings are refused up front.

The runner asks Ollama itself who the model is, to record its fingerprint;
a cloud service has no such question. So settings that choose the cloud
plug are refused where the backend is built, before the model is asked who
it is and before a plug is made, and the run stops as any run that cannot
start does: exit status 2, nothing written. The real way of building the
backend (``local_backend``) is used, with the two places that would reach a
server replaced by recorders. The address is a port on this machine that
nothing listens on, and the key is invented, so even a broken refusal would
send nothing anywhere.
"""

from __future__ import annotations

import io
import os
from pathlib import Path

import pytest

from evals import run as runner
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
    "arguments",
    [[], ["--only", "d01"], ["--model", "another-model:8b"], ["--method", "split_first"]],
)
def test_cloud_settings_are_refused_before_anything_is_asked(
    arguments: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorder = Recorder()
    monkeypatch.setattr(runner, "ask_identity", recorder.ask_identity)
    monkeypatch.setattr(runner, "connect_local_model", recorder.connect_local_model)
    out = io.StringIO()

    status = runner.main(arguments, out=out, results_dir=tmp_path)

    said = out.getvalue()
    assert status == 2
    assert said.startswith("cannot start: ")
    assert "LEDGER_HAND_MODEL_PLUG" in said
    assert "cloud" in said and "local" in said
    assert "invented-key-for-a-test" not in said
    assert recorder.calls == []
    assert list(tmp_path.iterdir()) == []


@pytest.mark.usefixtures("cloud_settings")
def test_the_refusal_names_the_reason(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = Recorder()
    monkeypatch.setattr(runner, "ask_identity", recorder.ask_identity)
    monkeypatch.setattr(runner, "connect_local_model", recorder.connect_local_model)
    out = io.StringIO()

    runner.main(["--only", "d01"], out=out, results_dir=tmp_path)

    assert "fingerprint" in out.getvalue()
    assert out.getvalue().count("\n") == 1


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
