"""Measure asking the ledger: each question of the ask set, from what is said to the end.

    .venv/bin/python -m evals.ask_run
    .venv/bin/python -m evals.ask_run --model qwen2.5:7b
    .venv/bin/python -m evals.ask_run --set evals/sets/asks_times.json

Run from the top of the repository. ``--set`` names another set of the same
shape (``evals/sets/asks_times.json``); the default is ``evals/sets/asks.json``.
Each group of the set is one chat with
the whole assistant (``flows.conversation.say``): the real model, the
system prompt a turn uses by default (``flows.assisting.DEFAULT_PROMPT``),
the fake ledger with its invented book, and the set's fixed moment and
zone. Each sentence is run until it stops, and the last lookup of its turn
is judged against the gold answers (``ask_set``). The model is the one the
settings name unless ``--model`` names another, with the settings'
parameters; the steps a turn may take are the settings' too. Only the
local plug is used, since the run asks Ollama for the model's fingerprint.

The results go into ``evals/tool_results/``. The first line records the
conditions: the set file and its fingerprint, the prompt and the
fingerprint of its words and its file, the fingerprint of the tools, the
commit and whether the work tree was clean, the model, its fingerprint, the
Ollama version, every parameter, the steps allowed, the moment and zone,
and when the run began. One line follows for each sentence, then an
``end`` line with the counts and the pass lines. The table is printed at the end.

A set may name two keys at its top. ``"book": "exam"`` holds the exam
book (``exam_book``) in place of the invented one, and leaves out the
pass line about Q1 to Q6, which such a set does not hold.
``"half": "hidden"`` prints the count of each verdict alone, never a
sentence, and adds the run to the hidden-run log (``hidden_runs``); the
results file still holds every sentence. A set naming neither runs,
writes and prints as before.

Exit status: 0 the run finished; 2 it could not start.

Names defined here: ``found_in``, ``run``, ``hidden_totals`` and ``main``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO

from evals.ask_set import (
    ASK_SET,
    FIRST_SIX,
    AskSentence,
    AskSet,
    Found,
    Verdict,
    judge_answer,
    load_ask_set,
    passes,
    totals,
)
from evals.ask_set import markdown as ask_markdown
from evals.exam_book import exam_ledger
from evals.hidden_runs import log_hidden_run
from evals.run import Backend, local_backend
from evals.tool_run import REPO_ROOT, TOOL_RESULTS_DIR, _git
from ledger_hand.assistant.outcome import Ending
from ledger_hand.assistant.tools import tool_specs
from ledger_hand.flows import assisting
from ledger_hand.flows.conversation import ASSISTANT_EXTRACT_PROMPT, AssistantChat, Said, say
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ports import ModelError
from ledger_hand.settings import SettingsError, load_assistant_steps


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _ledger(ask_set: AskSet) -> FakeLedger:
    """A fresh fake ledger: the exam book for a set that names it, else the invented book."""
    return exam_ledger() if ask_set.book == "exam" else FakeLedger()


def _named(ask_set: AskSet) -> dict[str, object]:
    """The book and half a set names, for the first line; nothing for a set that names neither."""
    if ask_set.book is None and ask_set.half is None:
        return {}
    return {"book": ask_set.book, "half": ask_set.half}


def found_in(said: Said) -> Found:
    """What one thing said came to: its last lookup, or the program's own words."""
    turn = said.turn
    if turn is None:
        return Found(program_words=said.reply)
    if not turn.lookups:
        words = turn.reply if turn.ending is Ending.ANSWERED_BY_PROGRAM else None
        return Found(program_words=words)
    lookup = turn.lookups[-1]
    conditions = lookup.conditions
    period = conditions.period if conditions is not None else None
    return Found(
        tool=lookup.tool.value,
        first_day=period.first_day if period is not None else None,
        last_day=period.last_day if period is not None else None,
        asset=conditions.asset if conditions is not None else None,
        side=conditions.side.value if conditions is not None and conditions.side else None,
    )


def _words_by(said: Said) -> str:
    turn = said.turn
    if turn is None or said.recorded is not None or turn.ending is not Ending.ANSWERED:
        return "the program"
    if turn.withheld is not None:
        return f"the program (withheld: {turn.withheld.reason})"
    return "the model"


def _conditions(
    backend: Backend, started: datetime, set_file: Path, steps: int
) -> dict[str, object]:
    prompt = assisting.DEFAULT_PROMPT
    ask_set = load_ask_set(set_file)
    tools = json.dumps(
        [[spec.name, spec.description, dict(spec.parameters)] for spec in tool_specs()],
        ensure_ascii=False,
    )
    results = TOOL_RESULTS_DIR.relative_to(REPO_ROOT).as_posix()
    return {
        "record": "run",
        "set_file": set_file.resolve().relative_to(REPO_ROOT).as_posix(),
        "set_sha256": _sha256(set_file.read_bytes()),
        "prompt": prompt.name,
        "prompt_words_sha256": _sha256(prompt.words.encode("utf-8")),
        "tools_sha256": _sha256(tools.encode("utf-8")),
        "commit": _git("rev-parse", "HEAD"),
        "worktree_clean": not _git("status", "--porcelain", "--", ".", f":(exclude){results}"),
        "model": backend.name,
        "model_fingerprint": backend.fingerprint,
        "server_version": backend.server_version,
        "base_url": backend.base_url,
        "parameters": dict(backend.parameters),
        "max_steps": steps,
        "now": ask_set.now.isoformat(),
        "zone": ask_set.zone,
        "started_at": started.isoformat(timespec="seconds"),
        **_named(ask_set),
    }


def _calls(said: Said) -> list[list[dict[str, object]]]:
    if said.turn is None:
        return []
    return [
        [{"name": call.call.name, "arguments": dict(call.call.arguments)} for call in step.calls]
        for step in said.turn.steps
    ]


def _line(sentence: AskSentence, said: Said, verdict: Verdict, seconds: float) -> dict[str, object]:
    found = found_in(said)
    turn = said.turn
    return {
        "record": "sentence",
        "id": sentence.id,
        "route": said.route.name,
        "ending": turn.ending.value if turn is not None else None,
        "steps": _calls(said),
        "found": {
            "tool": found.tool,
            "from": found.first_day.isoformat() if found.first_day else None,
            "to": found.last_day.isoformat() if found.last_day else None,
            "asset": found.asset,
            "side": found.side,
        },
        "not_narrowed": [
            line
            for lookup in (turn.lookups if turn is not None else ())
            for line in (lookup.conditions.not_narrowed if lookup.conditions else ())
        ],
        "reply": said.reply,
        "model_words": turn.steps[-1].text if turn is not None and turn.steps else None,
        "words_by": _words_by(said),
        "verdict": verdict.name,
        "seconds": round(seconds, 1),
    }


def run(
    backend: Backend, set_file: Path, path: Path, max_steps: int
) -> list[tuple[AskSentence, Found, Verdict, str]]:
    """Run every group of the set, one chat each, writing each sentence's line as it comes."""
    ask_set = load_ask_set(set_file)
    rows: list[tuple[AskSentence, Found, Verdict, str]] = []
    with path.open("a", encoding="utf-8") as out:
        for group in ask_set.groups:
            state = AssistantChat()
            for sentence in group.sentences:
                began = time.monotonic()
                said = say(
                    state,
                    sentence.text,
                    model=backend.model,
                    ledger=_ledger(ask_set),
                    now=ask_set.now,
                    zone=ask_set.zone,
                    max_steps=max_steps,
                )
                state = said.state
                verdict = judge_answer(sentence, found_in(said))
                rows.append((sentence, found_in(said), verdict, _words_by(said)))
                line = _line(sentence, said, verdict, time.monotonic() - began)
                out.write(json.dumps(line, ensure_ascii=False) + "\n")
                out.flush()
    return rows


def main(arguments: Sequence[str] = (), *, out: TextIO = sys.stdout) -> int:
    """Run the measure; print the table."""
    parser = argparse.ArgumentParser(prog="evals.ask_run")
    parser.add_argument("--model", default=None)
    parser.add_argument("--set", default=str(ASK_SET), help="the set of questions to run")
    options = parser.parse_args(arguments)
    set_file = Path(options.set).resolve()
    try:
        backend = local_backend(options.model)
        steps = load_assistant_steps()
    except (SettingsError, ModelError) as error:
        print(f"cannot start: {error}", file=out)
        return 2
    started = datetime.now(UTC)
    TOOL_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    prompt = assisting.DEFAULT_PROMPT.name
    stamp = started.strftime("%Y%m%dT%H%M%SZ")
    path = TOOL_RESULTS_DIR / f"run-{stamp}-{set_file.stem}-{prompt}.jsonl"
    head = _conditions(backend, started, set_file, steps)
    path.write_text(json.dumps(head, ensure_ascii=False) + "\n", encoding="utf-8")
    rows = run(backend, set_file, path, steps)
    _finish(rows, head, set_file, path, out)
    return 0


def _finish(
    rows: Sequence[tuple[AskSentence, Found, Verdict, str]],
    head: dict[str, object],
    set_file: Path,
    path: Path,
    out: TextIO,
) -> None:
    """The end line, then the table; for a hidden half, the totals alone and the log's line."""
    ask_set = load_ask_set(set_file)
    first = FIRST_SIX if ask_set.book is None else ()
    verdicts = {sentence.id: verdict for sentence, _, verdict, _ in rows}
    end = {
        "record": "end",
        "right": sum(verdict is Verdict.RIGHT for verdict in verdicts.values()),
        "of": len(rows),
        "passes": passes(verdicts, first),
    }
    with path.open("a", encoding="utf-8") as tail:
        tail.write(json.dumps(end, ensure_ascii=False) + "\n")
    print(f"results: {path.relative_to(REPO_ROOT).as_posix()}", file=out)
    if ask_set.half == "hidden":
        counts = totals(verdicts)
        log_hidden_run(
            set_file,
            path,
            {**counts, "of": len(rows)},
            extraction_prompt=ASSISTANT_EXTRACT_PROMPT.name,
            prompt=str(head["prompt"]),
        )
        print(hidden_totals(counts, head), file=out)
        return
    print(ask_markdown(rows, head, first), file=out)


def hidden_totals(counts: dict[str, int], head: dict[str, object]) -> str:
    """The counts of each verdict alone, for a hidden half: no sentence, no identifier."""
    names = " | ".join(counts)
    values = " | ".join(str(count) for count in counts.values())
    return (
        f"Model `{head['model']}`, prompt `{head['prompt']}`, the hidden half: totals only.\n\n"
        f"| {names} |\n|{' --- |' * len(counts)}\n| {values} |"
    )


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
