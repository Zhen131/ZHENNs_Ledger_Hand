"""Measure recording a share bought with dollars: each sentence of the share set, said once.

    .venv/bin/python -m evals.stock_run
    .venv/bin/python -m evals.stock_run --model qwen2.5:7b

Run from the top of the repository. Each sentence is said once, in a chat of
its own, to the whole assistant (``flows.conversation.say``): the real
model, the system prompt a turn uses by default, a fresh fake ledger with
its invented book (or the same book with USD a money no trade is priced in,
where the sentence says ``usdt_only``), and the set's fixed moment and zone.
The recording flow judges and extracts with the prompts it uses by
default. Nothing is answered: a question asked is what came of it. What came
of it is judged against the gold answer (``stock_set``), every field by the
ledger's code. The model is the one the settings name unless ``--model``
names another, with the settings' parameters and question tuning; the steps
a turn may take are the settings' too.

The results go into ``evals/tool_results/``: a first line with the
conditions, one line for each sentence, and an ``end`` line with the counts
and the pass lines. The table is printed at the end.

Exit status: 0 the run finished; 2 it could not start.

Names defined here: ``outcome_of``, ``run`` and ``main``.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import sys
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO

from evals.run import Backend, local_backend
from evals.stock_set import (
    STOCK_SET,
    Outcome,
    StockSentence,
    Verdict,
    judge,
    load_stock_set,
    markdown,
    passes,
)
from evals.tool_run import REPO_ROOT, TOOL_RESULTS_DIR, _git
from ledger_hand.core.followup import AskCell, AskWhichCell, ConfirmCoin
from ledger_hand.core.ledger_records import Pricing
from ledger_hand.extraction.prompts.first import FIRST_PROMPT
from ledger_hand.extraction.prompts.screen import SCREEN_PROMPT
from ledger_hand.flows import assisting
from ledger_hand.flows.conversation import AssistantChat, Said, say
from ledger_hand.flows.progress import Tuning
from ledger_hand.flows.recorded import Recorded, RecordEnding
from ledger_hand.flows.recording import tuning_from
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ledger.invented_book import INVENTED_ASSETS
from ledger_hand.ports import ModelError, ModelPort
from ledger_hand.settings import SettingsError, load_assistant_steps, load_model_settings

# The invented book with USD a money no trade is priced in: its assets and trades kept.
_USDT_ONLY = tuple(
    dataclasses.replace(asset, pricing=Pricing.CANNOT_PRICE) if asset.code == "USD" else asset
    for asset in INVENTED_ASSETS
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _ledger(book: str) -> FakeLedger:
    return FakeLedger(assets=_USDT_ONLY) if book == "usdt_only" else FakeLedger()


def _asked(recorded: Recorded) -> str | None:
    question = recorded.question
    if question is None:
        return None
    asked = question.asked
    if isinstance(asked, AskCell):
        return asked.cell.value
    if isinstance(asked, ConfirmCoin):
        return f"confirm {asked.cell.value}"
    if isinstance(asked, AskWhichCell):
        return "which of " + ", ".join(cell.value for cell in asked.cells)
    return None


def outcome_of(said: Said) -> Outcome:
    """What came of one sentence said once."""
    recorded = said.recorded
    if recorded is None:
        ending = said.turn.ending.value if said.turn is not None else "-"
        return Outcome(reasons=frozenset({f"not recorded ({ending})"}))
    sent = recorded.trades if recorded.ending is RecordEnding.SENT else ()
    if recorded.ending is RecordEnding.NOTHING_TO_SEND:
        reasons = frozenset(left.why.value for left in recorded.left_out)
    else:
        reasons = frozenset({recorded.ending.value})
    return Outcome(sent=sent, asked=_asked(recorded), reasons=reasons)


def _came(said: Said, outcome: Outcome) -> str:
    """What came of it, in a few words for the table."""
    if outcome.sent:
        return "sent: " + "; ".join(
            f"{one.side.value} {one.quantity} {one.asset} at {one.price} {one.quote}, "
            f"fee {one.fee} {one.fee_asset}, {one.occurred.strftime('%H:%M')}, {one.platform}"
            for one in outcome.sent
        )
    if outcome.asked is not None:
        return f"asked the {outcome.asked}"
    return ("nothing sent: " + ", ".join(sorted(outcome.reasons))).replace("|", "/")


def _line(
    sentence: StockSentence, said: Said, outcome: Outcome, verdict: Verdict, seconds: float
) -> dict[str, object]:
    calls = []
    if said.turn is not None:
        calls = [
            [{"name": one.call.name, "arguments": dict(one.call.arguments)} for one in step.calls]
            for step in said.turn.steps
        ]
    recorded = said.recorded
    return {
        "record": "sentence",
        "id": sentence.id,
        "book": sentence.book,
        "said": sentence.text,
        "route": said.route.name,
        "steps": calls,
        "ending": recorded.ending.value if recorded is not None else None,
        "reply": said.reply,
        "sent": [
            {
                "side": one.side.value,
                "asset": one.asset,
                "quantity": str(one.quantity),
                "price": str(one.price),
                "total": str(one.total),
                "quote": one.quote,
                "fee": str(one.fee),
                "fee_asset": one.fee_asset,
                "occurred": one.occurred.isoformat(),
                "platform": one.platform,
            }
            for one in outcome.sent
        ],
        "asked": outcome.asked,
        "reasons": sorted(outcome.reasons),
        "verdict": verdict.name,
        "seconds": round(seconds, 1),
    }


def _conditions(
    backend: Backend, started: datetime, set_file: Path, steps: int
) -> dict[str, object]:
    prompt = assisting.DEFAULT_PROMPT
    stock_set = load_stock_set(set_file)
    results = TOOL_RESULTS_DIR.relative_to(REPO_ROOT).as_posix()
    return {
        "record": "run",
        "set_file": set_file.resolve().relative_to(REPO_ROOT).as_posix(),
        "set_sha256": _sha256(set_file.read_bytes()),
        "prompt": prompt.name,
        "prompt_words_sha256": _sha256(prompt.words.encode("utf-8")),
        "screen_prompt": SCREEN_PROMPT.name,
        "extraction_prompt": FIRST_PROMPT.name,
        "commit": _git("rev-parse", "HEAD"),
        "worktree_clean": not _git("status", "--porcelain", "--", ".", f":(exclude){results}"),
        "model": backend.name,
        "model_fingerprint": backend.fingerprint,
        "server_version": backend.server_version,
        "base_url": backend.base_url,
        "parameters": dict(backend.parameters),
        "max_steps": steps,
        "now": stock_set.now.isoformat(),
        "zone": stock_set.zone,
        "started_at": started.isoformat(timespec="seconds"),
    }


def _said(
    sentence: StockSentence, model: ModelPort, steps: int, tuning: Tuning, set_file: Path
) -> Said:
    stock_set = load_stock_set(set_file)
    return say(
        AssistantChat(),
        sentence.text,
        model=model,
        ledger=_ledger(sentence.book),
        now=stock_set.now,
        zone=stock_set.zone,
        max_steps=steps,
        tuning=tuning,
    )


def run(
    backend: Backend, set_file: Path, path: Path, max_steps: int, tuning: Tuning
) -> list[tuple[StockSentence, Outcome, Verdict, str]]:
    """Run every sentence of the set, writing each sentence's line as it comes."""
    rows: list[tuple[StockSentence, Outcome, Verdict, str]] = []
    with path.open("a", encoding="utf-8") as out:
        for sentence in load_stock_set(set_file).sentences:
            began = time.monotonic()
            said = _said(sentence, backend.model, max_steps, tuning, set_file)
            outcome = outcome_of(said)
            verdict = judge(sentence.gold, outcome)
            rows.append((sentence, outcome, verdict, _came(said, outcome)))
            line = _line(sentence, said, outcome, verdict, time.monotonic() - began)
            out.write(json.dumps(line, ensure_ascii=False) + "\n")
            out.flush()
    return rows


def main(arguments: Sequence[str] = (), *, out: TextIO = sys.stdout) -> int:
    """Run the measure; print the table."""
    parser = argparse.ArgumentParser(prog="evals.stock_run")
    parser.add_argument("--model", default=None)
    parser.add_argument("--set", default=str(STOCK_SET), help="the set of sentences to run")
    options = parser.parse_args(arguments)
    set_file = Path(options.set).resolve()
    try:
        backend = local_backend(options.model)
        steps = load_assistant_steps()
        tuning = tuning_from(load_model_settings())
    except (SettingsError, ModelError) as error:
        print(f"cannot start: {error}", file=out)
        return 2
    started = datetime.now(UTC)
    TOOL_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = started.strftime("%Y%m%dT%H%M%SZ")
    path = TOOL_RESULTS_DIR / f"run-{stamp}-{set_file.stem}-{assisting.DEFAULT_PROMPT.name}.jsonl"
    head = _conditions(backend, started, set_file, steps)
    path.write_text(json.dumps(head, ensure_ascii=False) + "\n", encoding="utf-8")
    rows = run(backend, set_file, path, steps, tuning)
    verdicts = {sentence.id: verdict for sentence, _, verdict, _ in rows}
    end = {
        "record": "end",
        "right": sum(verdict is Verdict.RIGHT for verdict in verdicts.values()),
        "of": len(rows),
        "silently_wrong": sum(verdict is Verdict.SILENTLY_WRONG for verdict in verdicts.values()),
        "passes": passes(verdicts),
    }
    with path.open("a", encoding="utf-8") as tail:
        tail.write(json.dumps(end, ensure_ascii=False) + "\n")
    print(f"results: {path.relative_to(REPO_ROOT).as_posix()}", file=out)
    print(markdown(rows, head), file=out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
