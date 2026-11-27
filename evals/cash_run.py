"""Say the sentences about cash, and those near them, to the whole assistant; compare two runs.

    .venv/bin/python -m evals.cash_run
    .venv/bin/python -m evals.cash_run --compare BEFORE.jsonl AFTER.jsonl

Run from the top of the repository. Each sentence of ``evals/sets/cash.json``
(``named`` and ``must_pass``) is said once, in a chat of its own, to the
whole assistant (``flows.conversation.say``): the real model the settings
name (or ``--model``), a fresh fake ledger with its invented book, and the
set's fixed moment and zone. Nothing is answered: a question asked is what
came of it.

For each sentence the way it went is written down (``path_of``): the
route, how the model's turn ended, the tools it asked for in each step,
how a recording or a change ended. The reply is kept beside it, and is
not part of the way. ``--compare`` reads two results files and says, for
every ``must_pass`` sentence, whether it went the same way in both.

The results go into ``evals/tool_results/``: a first line with the
conditions, one line for each sentence. The table is printed at the end.

Exit status: 0 the run finished, or every ``must_pass`` sentence went the
same way; 1 one did not; 2 it could not start.

Names defined here: ``CASH_SET``, ``CashSentence``, ``load_cash_set``, ``path_of``,
``compare`` and ``main``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO

from evals.run import local_backend
from evals.tool_run import REPO_ROOT, TOOL_RESULTS_DIR, _git
from ledger_hand.flows import assisting
from ledger_hand.flows.conversation import AssistantChat, Said, say
from ledger_hand.flows.recording import tuning_from
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ports import ModelError
from ledger_hand.settings import SettingsError, load_assistant_steps, load_model_settings

CASH_SET = Path(__file__).resolve().parent / "sets" / "cash.json"


@dataclass(frozen=True)
class CashSentence:
    """One sentence of the set: its id, its group (``named`` or ``must_pass``), its words."""

    id: str
    group: str
    text: str


def load_cash_set(path: Path = CASH_SET) -> tuple[datetime, str, tuple[CashSentence, ...]]:
    """The set's moment, its zone and its sentences, ``named`` first, those added last."""
    data = json.loads(path.read_text(encoding="utf-8"))
    sentences = tuple(
        CashSentence(id=str(one["id"]), group=group, text=str(one["text"]))
        for group in (
            "named",
            "must_pass",
            "named_added",
            "must_pass_added",
            "named_added_2",
            "must_pass_added_2",
        )
        for one in data.get(group, ())
    )
    return datetime.fromisoformat(data["now"]), str(data["zone"]), sentences


def path_of(said: Said) -> dict[str, Any]:
    """The way one thing said went: route, endings and the tools of each step, nothing else."""
    turn = said.turn
    return {
        "route": said.route.name,
        "turn": turn.ending.name if turn is not None else None,
        "tools": [[one.call.name for one in step.calls] for step in turn.steps]
        if turn is not None
        else [],
        "recorded": said.recorded.ending.name if said.recorded is not None else None,
        "edited": said.edited.ending.name if said.edited is not None else None,
    }


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _cell(text: str) -> str:
    return " ".join(text.split()).replace("|", "/")


def _run(arguments: argparse.Namespace, out: TextIO) -> int:
    try:
        backend = local_backend(arguments.model)
        steps = load_assistant_steps()
        tuning = tuning_from(load_model_settings())
    except (SettingsError, ModelError) as error:
        print(f"cannot start: {error}", file=out)
        return 2
    set_file = Path(arguments.set).resolve()
    now, zone, sentences = load_cash_set(set_file)
    started = datetime.now(UTC)
    TOOL_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = started.strftime("%Y%m%dT%H%M%SZ")
    path = TOOL_RESULTS_DIR / f"run-{stamp}-{set_file.stem}-{assisting.DEFAULT_PROMPT.name}.jsonl"
    results = TOOL_RESULTS_DIR.relative_to(REPO_ROOT).as_posix()
    head = {
        "record": "run",
        "set_file": set_file.relative_to(REPO_ROOT).as_posix(),
        "set_sha256": _sha256(set_file.read_bytes()),
        "prompt": assisting.DEFAULT_PROMPT.name,
        "commit": _git("rev-parse", "HEAD"),
        "worktree_clean": not _git("status", "--porcelain", "--", ".", f":(exclude){results}"),
        "model": backend.name,
        "model_fingerprint": backend.fingerprint,
        "server_version": backend.server_version,
        "parameters": dict(backend.parameters),
        "max_steps": steps,
        "now": now.isoformat(),
        "zone": zone,
        "started_at": started.isoformat(timespec="seconds"),
    }
    rows: list[str] = ["| Sentence | Group | Way | Reply |", "| --- | --- | --- | --- |"]
    with path.open("w", encoding="utf-8", newline="\n") as kept:
        kept.write(json.dumps(head, ensure_ascii=False) + "\n")
        for sentence in sentences:
            began = time.monotonic()
            said = say(
                AssistantChat(),
                sentence.text,
                model=backend.model,
                ledger=FakeLedger(),
                now=now,
                zone=zone,
                max_steps=steps,
                tuning=tuning,
            )
            line = {
                "record": "sentence",
                "id": sentence.id,
                "group": sentence.group,
                "said": sentence.text,
                "path": path_of(said),
                "reply": said.reply,
                "seconds": round(time.monotonic() - began, 1),
            }
            kept.write(json.dumps(line, ensure_ascii=False) + "\n")
            kept.flush()
            way = json.dumps(line["path"], ensure_ascii=False)
            rows.append(
                f"| {sentence.id} | {sentence.group} | {_cell(way)} | {_cell(said.reply)} |"
            )
    print(f"results: {path.relative_to(REPO_ROOT).as_posix()}", file=out)
    print("\n".join(rows), file=out)
    return 0


def _paths(path: Path) -> dict[str, Mapping[str, Any]]:
    lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    return {
        str(line["id"]): line["path"]
        for line in lines
        if line.get("record") == "sentence" and line.get("group") == "must_pass"
    }


def compare(before: Path, after: Path) -> list[str]:
    """Each ``must_pass`` sentence that did not go the same way in both runs, one line each."""
    first, second = _paths(before), _paths(after)
    found: list[str] = []
    for sentence in sorted(set(first) | set(second), key=lambda one: int(one[1:])):
        if first.get(sentence) != second.get(sentence):
            found.append(f"{sentence}: {first.get(sentence)} then {second.get(sentence)}")
    return found


def main(arguments: Sequence[str] = (), *, out: TextIO = sys.stdout) -> int:
    """Run the set, or compare two runs of it."""
    parser = argparse.ArgumentParser(prog="evals.cash_run")
    parser.add_argument("--model", default=None)
    parser.add_argument("--set", default=str(CASH_SET), help="the set of sentences to run")
    parser.add_argument("--compare", nargs=2, metavar=("BEFORE", "AFTER"), default=None)
    options = parser.parse_args(arguments)
    if options.compare is None:
        return _run(options, out)
    found = compare(Path(options.compare[0]), Path(options.compare[1]))
    for line in found:
        print(f"NOT THE SAME WAY: {line}", file=out)
    if not found:
        print("every must_pass sentence went the same way in both runs", file=out)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
