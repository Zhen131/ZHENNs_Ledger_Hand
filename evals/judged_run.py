"""Measure the extraction sets through the start of recording, judging step and all.

    .venv/bin/python -m evals.judged_run --screen screen-1
    .venv/bin/python -m evals.judged_run --screen screen-2 --final-exam

Run from the top of the repository. Every sentence of the debug set (or,
with ``--final-exam``, of the final set) goes through ``recording.start``
with the built-in asset table (the coins of the coin table and USDT), the
judging prompt version ``--screen`` names and the extraction version
``--extract`` names (``first`` unless said), at the sentence's own moment
and zone; nothing is asked or answered after that. The drafts the flow
holds then, and the issues extraction raised, are scored against the gold
answer exactly as ``evals.run`` scores extraction alone (``scoring``). A
passage the judging step stops, or finds no trade in, gives no draft.

It is here so that a new prompt version the assistant uses can be held to
the old sentences: on the same day, each version runs both sets, and the
fields wrong with nothing said about them (``silent_wrong``: a wrong value
with no issue, or a value made up with no issue, as ``tables`` counts
them) are compared. This runner changes nothing of ``evals.run`` and is
not one of its versions.

The results go into ``evals/tool_results/``, never ``evals/results/``: a
first line with the conditions, one line for each sentence, and an
``end`` line with the counts.

Exit status: 0 the run finished; 2 it could not start.

Names defined here: ``SCREENS``, ``EXTRACTS``, ``produced_of``,
``silent_wrong``, ``run`` and ``main``.
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

from evals.cells import CellOutcome
from evals.gold import DEBUG_SET, FINAL_SET, Sentence, Split, load_set
from evals.run import Backend, local_backend
from evals.scoring import Produced, ResultKind, SentenceScore, score_sentence
from evals.tool_run import REPO_ROOT, TOOL_RESULTS_DIR, _git
from ledger_hand.core.assets import BUILT_IN_ASSETS
from ledger_hand.extraction.prompting import PromptVersion
from ledger_hand.extraction.prompts.first import FIRST_PROMPT
from ledger_hand.extraction.prompts.first2 import FIRST_PROMPT_2
from ledger_hand.extraction.prompts.first3 import FIRST_PROMPT_3
from ledger_hand.extraction.prompts.screen import SCREEN_PROMPT
from ledger_hand.extraction.prompts.screen2 import SCREEN_PROMPT_2
from ledger_hand.flows.progress import Progress, Stage
from ledger_hand.flows.recording import start
from ledger_hand.ports import ModelError, ModelPort
from ledger_hand.settings import SettingsError

SCREENS: dict[str, PromptVersion] = {
    SCREEN_PROMPT.name: SCREEN_PROMPT,
    SCREEN_PROMPT_2.name: SCREEN_PROMPT_2,
}
EXTRACTS: dict[str, PromptVersion] = {
    FIRST_PROMPT.name: FIRST_PROMPT,
    FIRST_PROMPT_2.name: FIRST_PROMPT_2,
    FIRST_PROMPT_3.name: FIRST_PROMPT_3,
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def produced_of(progress: Progress) -> Produced:
    """What the start of recording gave, as the scorer takes it."""
    if progress.stage is Stage.FAILED:
        return Produced(ResultKind.MODEL_FAILED)
    if progress.stage is Stage.REFUSED:
        return Produced(ResultKind.PASSAGE_REFUSED)
    drafts = tuple(trade.draft for trade in progress.trades)
    return Produced(ResultKind.EXTRACTED, drafts, progress.issues)


def silent_wrong(score: SentenceScore) -> int:
    """The fields wrong with nothing said: a wrong value, or a made-up one, with no issue."""
    return sum(
        1
        for pair in score.pairs
        for cell in pair.cells
        if cell.outcome is CellOutcome.WRONG_SILENT
        or (cell.outcome is CellOutcome.MADE_UP and not cell.issues)
    )


def _one(
    sentence: Sentence, model: ModelPort, screen: PromptVersion, extract: PromptVersion
) -> Progress:
    return start(
        sentence.text,
        model,
        now=sentence.now,
        zone=sentence.zone,
        assets=BUILT_IN_ASSETS,
        screen_prompt=screen,
        extract_prompt=extract,
    )


def run(
    sentences: Sequence[Sentence],
    backend: Backend,
    path: Path,
    screen: PromptVersion,
    extract: PromptVersion,
) -> dict[str, object]:
    """Every sentence through the start of recording; each line added as it is done."""
    totals = {"sentences": 0, "gold_trades": 0, "whole_right": 0, "silent_wrong": 0}
    judged_no_trade = 0
    with path.open("a", encoding="utf-8") as out:
        for sentence in sentences:
            began = time.monotonic()
            progress = _one(sentence, backend.model, screen, extract)
            score = score_sentence(sentence, produced_of(progress))
            wrong = silent_wrong(score)
            totals["sentences"] += 1
            totals["gold_trades"] += score.gold_trades
            totals["whole_right"] += score.whole_right
            totals["silent_wrong"] += wrong
            if sentence.trades and progress.stage in (Stage.STOPPED, Stage.NO_TRADE):
                judged_no_trade += 1
            line = {
                "record": "sentence",
                "id": sentence.id,
                "stage": progress.stage.value,
                "drafts": len(progress.trades),
                "gold_trades": score.gold_trades,
                "whole_right": score.whole_right,
                "silent_wrong": wrong,
                "seconds": round(time.monotonic() - began, 1),
            }
            out.write(json.dumps(line, ensure_ascii=False) + "\n")
            out.flush()
    return {**totals, "gold_trades_judged_away": judged_no_trade}


def main(arguments: Sequence[str] = (), *, out: TextIO = sys.stdout) -> int:
    """Run one version on one set; print the counts."""
    parser = argparse.ArgumentParser(prog="evals.judged_run")
    parser.add_argument("--screen", choices=sorted(SCREENS), required=True)
    parser.add_argument("--extract", choices=sorted(EXTRACTS), default=FIRST_PROMPT.name)
    parser.add_argument("--final-exam", action="store_true", help="run the final set")
    parser.add_argument("--model", default=None)
    options = parser.parse_args(arguments)
    set_file, split = (FINAL_SET, Split.FINAL) if options.final_exam else (DEBUG_SET, Split.DEBUG)
    screen, extract = SCREENS[options.screen], EXTRACTS[options.extract]
    try:
        backend = local_backend(options.model)
    except (SettingsError, ModelError) as error:
        print(f"cannot start: {error}", file=out)
        return 2
    started = datetime.now(UTC)
    TOOL_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = started.strftime("%Y%m%dT%H%M%SZ")
    path = TOOL_RESULTS_DIR / f"judged-{stamp}-{split.value}-{screen.name}-{extract.name}.jsonl"
    results = TOOL_RESULTS_DIR.relative_to(REPO_ROOT).as_posix()
    head = {
        "record": "run",
        "set_file": set_file.relative_to(REPO_ROOT).as_posix(),
        "set_sha256": _sha256(set_file.read_bytes()),
        "screen_prompt": screen.name,
        "extraction_prompt": extract.name,
        "asset_table": "built-in: the coin table's coins, priced in USDT",
        "commit": _git("rev-parse", "HEAD"),
        "worktree_clean": not _git("status", "--porcelain", "--", ".", f":(exclude){results}"),
        "model": backend.name,
        "model_fingerprint": backend.fingerprint,
        "server_version": backend.server_version,
        "parameters": dict(backend.parameters),
        "started_at": started.isoformat(timespec="seconds"),
    }
    path.write_text(json.dumps(head, ensure_ascii=False) + "\n", encoding="utf-8")
    end = {"record": "end", **run(load_set(set_file, split), backend, path, screen, extract)}
    with path.open("a", encoding="utf-8") as tail:
        tail.write(json.dumps(end, ensure_ascii=False) + "\n")
    print(f"results: {path.relative_to(REPO_ROOT).as_posix()}", file=out)
    print(json.dumps(end, ensure_ascii=False), file=out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
