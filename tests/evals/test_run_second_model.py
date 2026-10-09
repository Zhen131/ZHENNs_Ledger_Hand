"""A second model is one name away: the runner asks for it by name and records which it was.

No second model is downloaded for this; a run names the model with
``--model``. Here the real way of building the backend (``local_backend``)
is used, with the two places that would reach the model server replaced: the
question of who the model is, which answers for the model named with a
fingerprint of its own, and the plug, which is the scripted model. The run
line must record the name given and that fingerprint, in both ways of
reading a passage, and the plug must be built for that name. No network is
used.
"""

from __future__ import annotations

import io
import json
import os
from pathlib import Path

import pytest

from evals import run as runner
from ledger_hand.llm.ollama_identity import BackendIdentity
from ledger_hand.ports import ModelPort
from ledger_hand.settings import ENV_PREFIX, ModelSettings
from tests.evals.test_run import D01, NOTHING
from tests.fakes.scripted_model import ScriptedModel

OTHER = "another-model:8b"
FINGERPRINTS = {"qwen2.5:7b": "a" * 64, OTHER: "b" * 64}
ONE_TRADE_SPLIT = json.dumps({"trades": [{"pieces": []}]})
NO_TRADE_SPLIT = json.dumps({"trades": []})


class Machine:
    """Stands for the model server: who each model is, and a scripted plug per run."""

    def __init__(self, *steps: str) -> None:
        self.steps = steps
        self.asked: list[str] = []
        self.built: list[str] = []

    def ask_identity(self, settings: ModelSettings) -> BackendIdentity:
        self.asked.append(settings.model)
        return BackendIdentity("0.0.0", settings.model, FINGERPRINTS[settings.model])

    def connect_local_model(self, settings: ModelSettings) -> ModelPort:
        self.built.append(settings.model)
        return ScriptedModel(self.steps)


@pytest.fixture
def no_model_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in list(os.environ):
        if name.startswith(ENV_PREFIX):
            monkeypatch.delenv(name)


def run_with(
    machine: Machine, arguments: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> dict[str, object]:
    monkeypatch.setattr(runner, "ask_identity", machine.ask_identity)
    monkeypatch.setattr(runner, "connect_local_model", machine.connect_local_model)
    out = io.StringIO()
    status = runner.main(arguments, out=out, results_dir=tmp_path)
    assert status == 0, out.getvalue()
    (path,) = tmp_path.glob("*.jsonl")
    return dict(json.loads(path.read_text(encoding="utf-8").splitlines()[0]))


@pytest.mark.usefixtures("no_model_settings")
@pytest.mark.parametrize(
    ("method", "steps"),
    [
        ("one_list", (D01, NOTHING)),
        ("split_first", (ONE_TRADE_SPLIT, D01, NO_TRADE_SPLIT, NOTHING)),
    ],
)
def test_a_model_named_on_the_command_line_is_the_one_asked_and_recorded(
    method: str, steps: tuple[str, ...], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    machine = Machine(*steps)
    arguments = ["--model", OTHER, "--method", method, "--only", "d01", "d24"]

    head = run_with(machine, arguments, tmp_path, monkeypatch)

    assert (head["model"], head["model_fingerprint"]) == (OTHER, FINGERPRINTS[OTHER])
    assert machine.asked == machine.built == [OTHER]
    assert head["method"] == method


@pytest.mark.usefixtures("no_model_settings")
def test_without_a_name_the_settings_model_is_asked_and_recorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    machine = Machine(D01, NOTHING)

    head = run_with(machine, ["--only", "d01", "d24"], tmp_path, monkeypatch)

    assert (head["model"], head["model_fingerprint"]) == ("qwen2.5:7b", FINGERPRINTS["qwen2.5:7b"])


@pytest.mark.usefixtures("no_model_settings")
def test_a_run_is_not_carried_on_with_another_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_with(Machine(D01, NOTHING), ["--only", "d01", "d24"], tmp_path, monkeypatch)
    (path,) = tmp_path.glob("*.jsonl")
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(lines[:2]) + "\n", encoding="utf-8")
    out = io.StringIO()

    status = runner.main(
        ["--model", OTHER, "--only", "d01", "d24", "--resume", str(path)],
        out=out,
        results_dir=tmp_path,
    )

    assert status == 2
    assert "model" in out.getvalue() and "model_fingerprint" in out.getvalue()
