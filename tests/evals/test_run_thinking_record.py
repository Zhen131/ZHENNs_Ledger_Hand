"""The thinking setting in a run's conditions, and how earlier runs compare with it.

A run writes ``think`` among its parameters only when it is on or off, and
the two are written apart. When nothing is sent (model), the parameters are
written as every run made before the setting was there, so an earlier
run's first line, which has no ``think``, stands for "not sent": the three
places that compare the parameters of two runs (``compare_sets``, the model
comparison and carrying a run on with ``--resume``) find no difference
between such a run and an earlier one, and do find one for on or off.

The earlier run read here is a results file of the repository; it is only
read, and a copy is made in a test's own folder for ``--resume``.
"""

from __future__ import annotations

import argparse
import dataclasses
import io
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest

from evals import compare_models, compare_sets
from evals import run as runner
from evals.methods import method_of
from evals.records import Results, read_results
from ledger_hand.llm.ollama_identity import BackendIdentity
from ledger_hand.ports import ModelPort
from ledger_hand.settings import ENV_PREFIX, ModelSettings, Thinking
from tests.fakes.scripted_model import ScriptedModel

# A run made before the setting was there: the default parameters, no think field sent.
EARLIER = runner.RESULTS_DIR / "run-20261013T093206Z-debug-first.jsonl"


def earlier() -> Results:
    return read_results(EARLIER)


def written(thinking: Thinking) -> dict[str, object]:
    return runner._parameters(ModelSettings(think=thinking))


def with_parameters(results: Results, parameters: dict[str, object]) -> Results:
    return dataclasses.replace(results, run={**results.run, "parameters": parameters})


def test_the_earlier_run_sent_no_think_field_and_has_no_think_parameter() -> None:
    parameters = earlier().run["parameters"]

    assert isinstance(parameters, dict)
    assert "think" not in parameters


def test_nothing_sent_is_written_as_the_parameters_were_before() -> None:
    assert written(Thinking.MODEL) == earlier().run["parameters"]
    assert "think" not in written(Thinking.MODEL)
    assert list(written(Thinking.MODEL)) == list(earlier().run["parameters"])  # type: ignore[arg-type]


def test_on_and_off_are_written_and_written_apart() -> None:
    on, off = written(Thinking.ON), written(Thinking.OFF)

    assert on["think"] == "on"
    assert off["think"] == "off"
    assert on != off
    assert {name: value for name, value in off.items() if name != "think"} == written(
        Thinking.MODEL
    )


def test_compare_sets_finds_no_difference_for_nothing_sent_and_one_for_off() -> None:
    old = earlier()

    compare_sets._check_same([old, with_parameters(old, written(Thinking.MODEL))], ["parameters"])
    with pytest.raises(ValueError, match="the runs differ in parameters"):
        compare_sets._check_same([old, with_parameters(old, written(Thinking.OFF))], ["parameters"])


def test_the_model_comparison_finds_no_difference_for_nothing_sent_and_one_for_off() -> None:
    old = earlier()

    nothing = compare_models._differing_parameters(
        old, with_parameters(old, written(Thinking.MODEL))
    )
    off = compare_models._differing_parameters(old, with_parameters(old, written(Thinking.OFF)))

    assert nothing == []
    assert off == ["think"]


def resumed(tmp_path: Path, parameters: dict[str, object]) -> str:
    """What ``--resume`` says of a copy of the earlier run, given conditions with ``parameters``."""
    copy = tmp_path / EARLIER.name
    shutil.copyfile(EARLIER, copy)
    old = read_results(copy)
    conditions = {**old.run, "method": method_of(old.run).value, "parameters": parameters}
    options = argparse.Namespace(resume=copy, prompt=old.run["prompt"], method="one_list")
    out = io.StringIO()
    started = datetime(2026, 10, 19, tzinfo=UTC)

    assert runner._start_or_resume(options, conditions, started, tmp_path, out) is None
    assert copy.read_bytes() == EARLIER.read_bytes()
    return out.getvalue()


def test_resuming_finds_no_change_for_nothing_sent_and_a_change_for_off(tmp_path: Path) -> None:
    nothing = resumed(tmp_path, written(Thinking.MODEL))
    off = resumed(tmp_path, written(Thinking.OFF))

    assert nothing == f"{EARLIER.name} is already finished\n"
    assert off == f"cannot resume {EARLIER.name}: changed since it began: parameters\n"


@pytest.mark.parametrize(("text", "recorded"), [("on", "on"), ("off", "off"), ("model", None)])
def test_a_run_records_the_thinking_setting_it_was_given(
    text: str, recorded: str | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in list(os.environ):
        if name.startswith(ENV_PREFIX):
            monkeypatch.delenv(name)
    monkeypatch.setenv("LEDGER_HAND_MODEL_THINK", text)
    built: list[ModelSettings] = []

    def identity(settings: ModelSettings) -> BackendIdentity:
        return BackendIdentity("0.0.0", settings.model, "invented-fingerprint")

    def connect(settings: ModelSettings) -> ModelPort:
        built.append(settings)
        return ScriptedModel([])

    monkeypatch.setattr(runner, "ask_identity", identity)
    monkeypatch.setattr(runner, "connect_local_model", connect)

    backend = runner.local_backend("invented-vl:8b")

    assert backend.parameters.get("think") == recorded
    assert ("think" in backend.parameters) is (recorded is not None)
    (settings,) = built
    assert settings.think.value == text
