"""Tests of an experiment run on DeepSeek: the first line, a comparison, carrying a run on.

With the deepseek plug the runner asks Ollama nothing; the first line names
the plug, the service and how a table was asked for, the model asked, and
says the service gives no fingerprint. The parameters hold what DeepSeek is
sent besides (thinking turned off). A local run's first line has the same
names it always had. A local run and a DeepSeek run of one set can be
compared, every parameter that differs listed; a run whose way of asking
for a table has changed since it began is not carried on. The service is a
fake transport; nothing leaves the process. Every value is invented.
"""

from __future__ import annotations

import io
import json
import os
from collections.abc import Iterator, Sequence
from pathlib import Path

import httpx
import pytest

from evals import run as runner
from evals.compare_models import comparison_markdown
from evals.records import read_results
from ledger_hand.llm import cloud
from ledger_hand.llm.cloud import CloudModel, forget_dropped_formats
from ledger_hand.llm.ollama_identity import BackendIdentity
from ledger_hand.ports import Message, ModelError, ModelErrorKind, ModelReply
from ledger_hand.settings import ENV_PREFIX, ModelSettings, Plug, Variable
from tests.llm.fake_cloud import completion
from tests.llm.fake_server import mock_transport

KEY = "sk-invented-deepseek-0123456789abcdef"
# The names a local run's first line had before the cloud plugs were added
# (evals/run.py, run_conditions, one list), in their order.
LOCAL_FIRST_LINE = [
    "record",
    "set",
    "final_exam_switch",
    "set_file",
    "set_sha256",
    "prompt",
    "prompt_files",
    "prompt_content_sha256",
    "reply_table_sha256",
    "method",
    "commit",
    "worktree_clean",
    "model",
    "model_fingerprint",
    "server_version",
    "base_url",
    "parameters",
    "coin_table",
    "started_at",
]


@pytest.fixture(autouse=True)
def every_service_asks_its_own_way() -> Iterator[None]:
    forget_dropped_formats()
    yield
    forget_dropped_formats()


@pytest.fixture
def machine(monkeypatch: pytest.MonkeyPatch) -> list[httpx.Request]:
    """No model setting but the plug and the key; DeepSeek a fake answering a JSON object."""
    for name in list(os.environ):
        if name.startswith(ENV_PREFIX):
            monkeypatch.delenv(name)
    sent: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        body = completion('{"trades": []}', model="deepseek-v4-pro", system_fingerprint="fp_x1")
        return httpx.Response(200, content=json.dumps(body).encode("utf-8"))

    def connect(settings: ModelSettings) -> CloudModel:
        return CloudModel(settings, transport=mock_transport(answer))

    monkeypatch.setattr(runner, "connect_model", connect)
    monkeypatch.setattr(runner, "ask_identity", _never)
    monkeypatch.setattr(runner, "connect_local_model", _never)
    return sent


def _never(settings: ModelSettings) -> None:
    raise AssertionError("Ollama was asked")


def deepseek_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, arguments: Sequence[str] = ("--only", "d01")
) -> Path:
    monkeypatch.setenv(Variable.PLUG.value, "deepseek")
    monkeypatch.setenv(Variable.DEEPSEEK_KEY.value, KEY)
    out = io.StringIO()
    status = runner.main(list(arguments), out=out, results_dir=tmp_path)
    assert status == 0, out.getvalue()
    (path,) = tmp_path.glob("*.jsonl")
    return path


def lines(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


# --- S16: the first line ------------------------------------------------------------


def test_a_deepseek_run_asks_no_ollama_and_its_first_line_says_where(
    machine: list[httpx.Request], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = deepseek_run(monkeypatch, tmp_path)

    first, sentence, *_ = lines(path)
    assert first["model"] == "deepseek-v4-pro"
    assert (first["model_fingerprint"], first["server_version"]) == (
        runner.NOT_GIVEN,
        runner.NOT_GIVEN,
    )
    assert first["base_url"] == "https://api.deepseek.com"
    assert (first["plug"], first["service"], first["reply_format"]) == (
        "deepseek",
        "deepseek",
        "json_object",
    )
    parameters = first["parameters"]
    assert isinstance(parameters, dict)
    assert parameters["thinking"] == {"type": "disabled"}
    assert "think" not in parameters
    calls = sentence["calls"]
    assert isinstance(calls, list) and calls
    assert calls[0]["model"] == "deepseek-v4-pro"
    assert calls[0]["system_fingerprint"] == "fp_x1"
    assert machine and all(r.url.host == "api.deepseek.com" for r in machine)
    assert KEY not in path.read_text(encoding="utf-8")


def test_a_model_named_with_deepseek_is_asked_as_named(
    machine: list[httpx.Request], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = deepseek_run(monkeypatch, tmp_path, ["--only", "d01", "--model", "qwen2.5:7b"])

    assert lines(path)[0]["model"] == "qwen2.5:7b"
    assert json.loads(machine[0].content)["model"] == "qwen2.5:7b"


def test_a_local_runs_first_line_has_the_names_it_always_had() -> None:
    backend = runner.Backend(
        model=object(),  # type: ignore[arg-type]
        name="qwen2.5:7b",
        fingerprint="a" * 64,
        server_version="0.0.0",
        base_url="http://127.0.0.1:11434",
        parameters={"temperature": 0.0},
    )

    first = runner.run_conditions(
        runner.Split.DEBUG, runner.DEBUG_SET, "first", backend, runner.datetime.now(runner.UTC)
    )

    assert list(first) == LOCAL_FIRST_LINE
    assert runner.cloud_conditions(backend) == {}


def test_a_failure_with_a_cloud_plug_is_written_by_its_kind_and_status_alone() -> None:
    error = ModelError(
        ModelErrorKind.SERVER_ERROR, "refused", status=401, snippet="Incorrect key ****cdef"
    )
    backend = runner.Backend(
        model=object(),  # type: ignore[arg-type]
        name="deepseek-v4-pro",
        fingerprint=runner.NOT_GIVEN,
        server_version=runner.NOT_GIVEN,
        base_url="https://api.deepseek.com",
        parameters={},
        plug=Plug.DEEPSEEK,
        service="deepseek",
    )

    assert runner.failure_text(error, backend) == "server_error (status 401)"


# --- S20: a way of asking dropped is written as it is ----------------------------------


def test_after_the_json_object_was_dropped_a_run_says_it_sends_none(
    machine: list[httpx.Request], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cloud._DROPPED.add(Plug.DEEPSEEK)

    path = deepseek_run(monkeypatch, tmp_path)

    assert lines(path)[0]["reply_format"] == "not_sent"
    assert "response_format" not in json.loads(machine[0].content)


def test_a_way_of_asking_dropped_during_a_run_is_said_in_its_end_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in list(os.environ):
        if name.startswith(ENV_PREFIX):
            monkeypatch.delenv(name)
    answers = iter(
        [
            httpx.Response(400, content=b'{"error": {"message": "Prompt must contain json"}}'),
        ]
    )

    def answer(request: httpx.Request) -> httpx.Response:
        for made in answers:
            return made
        body = completion('{"trades": []}')
        return httpx.Response(200, content=json.dumps(body).encode("utf-8"))

    monkeypatch.setattr(
        runner, "connect_model", lambda s: CloudModel(s, transport=mock_transport(answer))
    )
    path = deepseek_run(monkeypatch, tmp_path)

    first, *_, end = lines(path)
    assert first["reply_format"] == "json_object"
    assert end["reply_format_changed_to"] == "not_sent"


# --- S16b: compared with a local run; not resumed with another way of asking --------------


class Unreachable:
    """The local model, failing every call: a run still finishes, sentence by sentence."""

    def chat(self, messages: Sequence[Message], **_: object) -> ModelReply:
        raise ModelError(ModelErrorKind.UNREACHABLE, "invented: nothing answered")


def local_run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setattr(
        runner, "ask_identity", lambda s: BackendIdentity("0.0.0", s.model, "b" * 64)
    )
    monkeypatch.setattr(runner, "connect_local_model", lambda s: Unreachable())
    out = io.StringIO()
    folder = tmp_path / "local"
    assert runner.main(["--set", "voice"], out=out, results_dir=folder) == 0, out.getvalue()
    (path,) = folder.glob("*.jsonl")
    return path


def test_a_local_run_and_a_deepseek_run_are_compared_listing_the_parameters_apart(
    machine: list[httpx.Request], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    local = local_run(monkeypatch, tmp_path)
    monkeypatch.setattr(runner, "ask_identity", _never)
    deepseek = deepseek_run(monkeypatch, tmp_path / "deepseek", ["--set", "voice"])

    text = comparison_markdown(read_results(local), read_results(deepseek), ("a", "b"))

    assert "asked through different plugs: local and deepseek (deepseek)" in text
    assert "- thinking: not sent in the first run, {'type': 'disabled'} in the second" in text
    assert "`qwen2.5:7b`" in text and "`deepseek-v4-pro`" in text


def test_a_run_is_not_carried_on_when_the_way_of_asking_has_changed(
    machine: list[httpx.Request], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = deepseek_run(monkeypatch, tmp_path, ["--only", "d01", "d24"])
    kept = path.read_text(encoding="utf-8").splitlines()[:2]
    path.write_text("\n".join(kept) + "\n", encoding="utf-8", newline="\n")
    cloud._DROPPED.add(Plug.DEEPSEEK)
    out = io.StringIO()

    status = runner.main(
        ["--only", "d01", "d24", "--resume", str(path)], out=out, results_dir=tmp_path
    )

    assert status == 2
    assert "changed since it began" in out.getvalue()
    assert "reply_format" in out.getvalue()
