"""Measure the assistant's first step: each sentence of the tool set, one ask, no tool run.

    .venv/bin/python -m evals.tool_run
    .venv/bin/python -m evals.tool_run --prompt assistant-4 --model qwen2.5:7b

Run from the top of the repository. For each sentence the model is handed
the assistant's system prompt (at the set's fixed moment and zone), the
sentence and the eight tools, once; whatever it asks for is recorded and
scored (``tool_set``), and no tool is run. The model is the one the
settings name unless ``--model`` names another, with the settings'
parameters (temperature 0 by default). Only the local plug is used, since
the run asks Ollama for the model's fingerprint.

The results go into ``evals/tool_results/``, never ``evals/results/``: the
files there are all read as extraction runs. The first line records the
conditions: the set file and its fingerprint, the prompt version, its file
and the fingerprint of its words, the fingerprint of the tools handed over,
the commit and whether the work tree was clean, the model, its fingerprint,
the Ollama version, every parameter, the moment and zone the sentences were
read at, and when the run began; with a cloud plug, the plug, the service and
how a table is asked for (``run.cloud_conditions``), and a model's failure is
written by its kind and status only (``run.failure_text``). One line follows for each sentence, then
an ``end`` line with the count. The table is printed at the end.

Exit status: 0 the run finished; 2 it could not start (a setting, settings
that do not fit the plug they choose, or a local model server that could not
say who it is).

Names defined here: ``PROMPTS``, ``TOOL_RESULTS_DIR``, ``main``.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import subprocess
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import TextIO

from evals.run import Backend, cloud_conditions, failure_text, local_backend
from evals.tool_set import TOOL_SET, FirstStep, load_tool_set, markdown, score_first_step
from ledger_hand.assistant.prompting import AssistantPrompt, system_message
from ledger_hand.assistant.prompts import (
    assistant_fifth,
    assistant_first,
    assistant_fourth,
    assistant_second,
    assistant_third,
)
from ledger_hand.assistant.tools import tool_specs
from ledger_hand.ports import Message, ModelError, Role, ToolCall
from ledger_hand.settings import SettingsError

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL_RESULTS_DIR = REPO_ROOT / "evals" / "tool_results"

PROMPTS: dict[str, tuple[AssistantPrompt, ModuleType]] = {
    assistant_first.ASSISTANT_FIRST.name: (assistant_first.ASSISTANT_FIRST, assistant_first),
    assistant_second.ASSISTANT_SECOND.name: (assistant_second.ASSISTANT_SECOND, assistant_second),
    assistant_third.ASSISTANT_THIRD.name: (assistant_third.ASSISTANT_THIRD, assistant_third),
    assistant_fourth.ASSISTANT_FOURTH.name: (assistant_fourth.ASSISTANT_FOURTH, assistant_fourth),
    assistant_fifth.ASSISTANT_FIFTH.name: (assistant_fifth.ASSISTANT_FIFTH, assistant_fifth),
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git(*arguments: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(REPO_ROOT), *arguments],
        capture_output=True,
        stdin=subprocess.DEVNULL,
        timeout=30,
        check=False,
    )
    return done.stdout.decode("utf-8", "replace").strip() if done.returncode == 0 else ""


def conditions(
    prompt_name: str, backend: Backend, started: datetime, set_file: Path
) -> dict[str, object]:
    """The first line of a results file: everything the run's numbers depend on."""
    prompt, module = PROMPTS[prompt_name]
    prompt_file = Path(str(module.__file__))
    tools = json.dumps(
        [[spec.name, spec.description, dict(spec.parameters)] for spec in tool_specs()],
        ensure_ascii=False,
    )
    tool_set = load_tool_set(set_file)
    results = TOOL_RESULTS_DIR.relative_to(REPO_ROOT).as_posix()
    return {
        "record": "run",
        "set_file": set_file.resolve().relative_to(REPO_ROOT).as_posix(),
        "set_sha256": _sha256(set_file.read_bytes()),
        "prompt": prompt_name,
        "prompt_file": prompt_file.resolve().relative_to(REPO_ROOT).as_posix(),
        "prompt_file_sha256": _sha256(prompt_file.read_bytes()),
        "prompt_words_sha256": _sha256(prompt.words.encode("utf-8")),
        "tools_sha256": _sha256(tools.encode("utf-8")),
        "commit": _git("rev-parse", "HEAD"),
        "worktree_clean": not _git("status", "--porcelain", "--", ".", f":(exclude){results}"),
        "model": backend.name,
        "model_fingerprint": backend.fingerprint,
        "server_version": backend.server_version,
        "base_url": backend.base_url,
        "parameters": dict(backend.parameters),
        **cloud_conditions(backend),
        "now": tool_set.now.isoformat(),
        "zone": tool_set.zone,
        "started_at": started.isoformat(timespec="seconds"),
    }


def _calls_json(calls: Sequence[ToolCall]) -> list[dict[str, object]]:
    return [{"name": call.name, "arguments": dict(call.arguments)} for call in calls]


def _line(step: FirstStep, seconds: float | None, failure: str | None) -> dict[str, object]:
    return {
        "record": "sentence",
        "id": step.sentence.id,
        "calls": _calls_json(step.calls),
        "text": step.text,
        "right": step.right,
        "words_found": list(step.words_found),
        "words_missing": list(step.words_missing),
        "refused": list(step.refused),
        "seconds": seconds,
        "failure": failure,
    }


def run(prompt_name: str, backend: Backend, set_file: Path, path: Path) -> list[FirstStep]:
    """Ask the first step of every sentence, writing each line as it comes."""
    prompt, _ = PROMPTS[prompt_name]
    tool_set = load_tool_set(set_file)
    system = system_message(prompt, tool_set.now, tool_set.zone)
    tools = tool_specs()
    steps: list[FirstStep] = []
    with path.open("a", encoding="utf-8", newline="\n") as out:
        for sentence in tool_set.sentences:
            seconds, failure = None, None
            try:
                reply = backend.model.chat_with_tools(
                    [system, Message(Role.USER, sentence.text)], tools
                )
                step = score_first_step(sentence, reply.calls, reply.text)
                seconds = reply.record.elapsed_seconds
            except ModelError as error:
                step = dataclasses.replace(score_first_step(sentence, (), ""), right=False)
                failure = failure_text(error, backend)
            steps.append(step)
            out.write(json.dumps(_line(step, seconds, failure), ensure_ascii=False) + "\n")
            out.flush()
    return steps


def main(arguments: Sequence[str] = (), *, out: TextIO = sys.stdout) -> int:
    """Run the measure; print the table."""
    parser = argparse.ArgumentParser(prog="evals.tool_run")
    parser.add_argument("--prompt", choices=sorted(PROMPTS), default=sorted(PROMPTS)[-1])
    parser.add_argument("--model", default=None)
    options = parser.parse_args(arguments)
    try:
        backend = local_backend(options.model)
    except (SettingsError, ModelError) as error:
        print(f"cannot start: {error}", file=out)
        return 2
    started = datetime.now(UTC)
    TOOL_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = started.strftime("%Y%m%dT%H%M%SZ")
    path = TOOL_RESULTS_DIR / f"run-{stamp}-tools-{options.prompt}.jsonl"
    head = conditions(options.prompt, backend, started, TOOL_SET)
    path.write_text(json.dumps(head, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    steps = run(options.prompt, backend, TOOL_SET, path)
    right = sum(step.right for step in steps)
    with path.open("a", encoding="utf-8", newline="\n") as end:
        end.write(json.dumps({"record": "end", "right": right, "of": len(steps)}) + "\n")
    print(f"results: {path.relative_to(REPO_ROOT).as_posix()}", file=out)
    print(markdown(steps, head), file=out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
