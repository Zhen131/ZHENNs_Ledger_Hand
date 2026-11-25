"""Measure changing and deleting: each sentence of the edit set, from what is said to the end.

    .venv/bin/python -m evals.edit_run
    .venv/bin/python -m evals.edit_run --model qwen2.5:7b

Run from the top of the repository. Each sentence is said in a chat of its
own to the whole assistant (``flows.conversation.say``): the real model,
the system prompt a turn uses by default (``flows.assisting.DEFAULT_PROMPT``),
a fresh fake ledger with its invented book, and the set's fixed moment and
zone. When the program asks which trade and the gold answer has a pick,
the ruler says the pick; when it asks which amount follows and the gold
answer has a choice, the ruler names that amount; it answers nothing else.
What came of it is judged against the gold answer (``edit_set``). The model
is the one the settings name unless ``--model`` names another, with the
settings' parameters; the steps a turn may take are the settings' too.

The results go into ``evals/tool_results/``: a first line with the
conditions (as ``ask_run`` writes them), one line for each sentence, and
an ``end`` line with the counts and the pass lines. The table is printed
at the end.

A set may name ``"book": "exam"`` and ``"half"`` at its top, as for
``ask_run``: the exam book is held and the gold answers' trades are its
own, the line about E1 to E3 is left out, and a hidden half prints its
totals alone and is logged. A set naming neither runs as before.

Exit status: 0 the run finished; 2 it could not start.

Names defined here: ``outcome_of``, ``run`` and ``main``.
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

from evals.ask_run import hidden_totals
from evals.edit_set import (
    EDIT_SET,
    FIRST_THREE,
    EditSentence,
    EditSet,
    Outcome,
    Verdict,
    judge_edit,
    load_edit_set,
    passes,
)
from evals.edit_set import markdown as edit_markdown
from evals.exam_book import EXAM_TRADES, exam_ledger
from evals.hidden_runs import log_hidden_run
from evals.run import Backend, local_backend
from evals.tool_run import REPO_ROOT, TOOL_RESULTS_DIR, _git
from ledger_hand.assistant.tools import tool_specs
from ledger_hand.core.ledger_records import TradeFacts
from ledger_hand.flows import assisting
from ledger_hand.flows.conversation import ASSISTANT_EXTRACT_PROMPT, AssistantChat, Said, say
from ledger_hand.flows.editing import EditEnding
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ledger.invented_book import INVENTED_TRADES
from ledger_hand.ports import ModelError, ModelPort
from ledger_hand.settings import SettingsError, load_assistant_steps


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _ledger(edit_set: EditSet) -> FakeLedger:
    """A fresh fake ledger: the exam book for a set that names it, else the invented book."""
    return exam_ledger() if edit_set.book == "exam" else FakeLedger()


def _book(edit_set: EditSet) -> dict[str, TradeFacts]:
    """The trades the gold answers of ``edit_set`` name, by identifier."""
    return dict(EXAM_TRADES if edit_set.book == "exam" else INVENTED_TRADES)


def _named(edit_set: EditSet) -> dict[str, object]:
    """The book and half a set names, for the first line; nothing for a set that names neither."""
    if edit_set.book is None and edit_set.half is None:
        return {}
    return {"book": edit_set.book, "half": edit_set.half}


def outcome_of(saids: Sequence[Said]) -> Outcome:
    """What came of a sentence and the ruler's answers after it."""
    endings = [said.edited.ending for said in saids if said.edited is not None]
    sent = next((said for said in saids if said.edit_sent is not None), None)
    return Outcome(
        asked_pick=EditEnding.PICKING in endings,
        asked_choose=EditEnding.CHOOSING in endings,
        sent_kind=sent.edit_sent.kind.value if sent and sent.edit_sent else None,
        sent_trade=sent.edit_sent.trade if sent and sent.edit_sent else None,
        after=sent.edited.after if sent and sent.edited else None,
        ending=endings[-1].value if endings else None,
    )


def _came(saids: Sequence[Said]) -> str:
    """What came of it, in a few words for the table."""
    parts = []
    for said in saids:
        if said.edited is None:
            turn = said.turn
            ending = turn.ending.value if turn is not None else "-"
            parts.append(f"no change taken on ({ending}): {said.reply[:80]!r}")
            continue
        sent = said.edit_sent
        if sent is not None:
            parts.append(f"sent: {sent.kind.value} of {sent.trade}")
        else:
            parts.append(said.edited.ending.value)
    return "; then ".join(parts).replace("|", "/")


def _one(
    sentence: EditSentence,
    model: ModelPort,
    steps: int,
    now: datetime,
    zone: str,
    ledger: FakeLedger | None = None,
) -> list[tuple[str, Said]]:
    """One sentence, in a chat of its own, with the ruler's answers when the gold has them.

    Each answer is said once at most: a question asked again is not answered again.
    ``ledger`` is the fake ledger to hold; the invented book's when none is given.
    """
    ledger = ledger if ledger is not None else FakeLedger()
    gold = sentence.gold
    pending = {EditEnding.PICKING: gold.pick, EditEnding.CHOOSING: gold.choose}
    state = AssistantChat()
    words: str | None = sentence.text
    saids: list[tuple[str, Said]] = []
    while words is not None:
        said = say(state, words, model=model, ledger=ledger, now=now, zone=zone, max_steps=steps)
        saids.append((words, said))
        state = said.state
        waiting = said.edited is not None and state.editing is not None
        words = pending.pop(said.edited.ending, None) if waiting and said.edited else None
    return saids


def _calls(said: Said) -> list[list[dict[str, object]]]:
    if said.turn is None:
        return []
    return [
        [{"name": call.call.name, "arguments": dict(call.call.arguments)} for call in step.calls]
        for step in said.turn.steps
    ]


def _line(
    sentence: EditSentence, said: Sequence[tuple[str, Said]], verdict: Verdict, seconds: float
) -> dict[str, object]:
    saids = [one for _, one in said]
    outcome = outcome_of(saids)
    return {
        "record": "sentence",
        "id": sentence.id,
        "said": [words for words, _ in said],
        "routes": [said.route.name for said in saids],
        "endings": [said.edited.ending.value if said.edited else None for said in saids],
        "steps": [_calls(said) for said in saids],
        "replies": [said.reply for said in saids],
        "sent": {"kind": outcome.sent_kind, "trade": outcome.sent_trade},
        "verdict": verdict.name,
        "seconds": round(seconds, 1),
    }


def _conditions(
    backend: Backend, started: datetime, set_file: Path, steps: int
) -> dict[str, object]:
    prompt = assisting.DEFAULT_PROMPT
    edit_set = load_edit_set(set_file)
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
        "now": edit_set.now.isoformat(),
        "zone": edit_set.zone,
        "started_at": started.isoformat(timespec="seconds"),
        **_named(edit_set),
    }


def run(
    backend: Backend, set_file: Path, path: Path, max_steps: int
) -> list[tuple[EditSentence, Outcome, Verdict, str]]:
    """Run every sentence of the set, writing each sentence's line as it comes."""
    edit_set = load_edit_set(set_file)
    rows: list[tuple[EditSentence, Outcome, Verdict, str]] = []
    with path.open("a", encoding="utf-8") as out:
        for sentence in edit_set.sentences:
            began = time.monotonic()
            said = _one(
                sentence, backend.model, max_steps, edit_set.now, edit_set.zone, _ledger(edit_set)
            )
            saids = [one for _, one in said]
            outcome = outcome_of(saids)
            verdict = judge_edit(sentence.gold, outcome, _book(edit_set))
            rows.append((sentence, outcome, verdict, _came(saids)))
            line = _line(sentence, said, verdict, time.monotonic() - began)
            out.write(json.dumps(line, ensure_ascii=False) + "\n")
            out.flush()
    return rows


def main(arguments: Sequence[str] = (), *, out: TextIO = sys.stdout) -> int:
    """Run the measure; print the table."""
    parser = argparse.ArgumentParser(prog="evals.edit_run")
    parser.add_argument("--model", default=None)
    parser.add_argument("--set", default=str(EDIT_SET), help="the set of sentences to run")
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
    rows: Sequence[tuple[EditSentence, Outcome, Verdict, str]],
    head: dict[str, object],
    set_file: Path,
    path: Path,
    out: TextIO,
) -> None:
    """The end line, then the table; for a hidden half, the totals alone and the log's line."""
    edit_set = load_edit_set(set_file)
    first = FIRST_THREE if edit_set.book is None else ()
    verdicts = {sentence.id: verdict for sentence, _, verdict, _ in rows}
    end = {
        "record": "end",
        "right": sum(verdict is Verdict.RIGHT for verdict in verdicts.values()),
        "of": len(rows),
        "silently_wrong": sum(verdict is Verdict.SILENTLY_WRONG for verdict in verdicts.values()),
        "passes": passes(verdicts, first),
    }
    with path.open("a", encoding="utf-8") as tail:
        tail.write(json.dumps(end, ensure_ascii=False) + "\n")
    print(f"results: {path.relative_to(REPO_ROOT).as_posix()}", file=out)
    if edit_set.half == "hidden":
        counts = {
            verdict.name: sum(one is verdict for one in verdicts.values()) for verdict in Verdict
        }
        log_hidden_run(
            set_file,
            path,
            {**counts, "of": len(rows)},
            extraction_prompt=ASSISTANT_EXTRACT_PROMPT.name,
            prompt=str(head["prompt"]),
        )
        print(hidden_totals(counts, head), file=out)
        return
    print(edit_markdown(rows, head, first), file=out)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
