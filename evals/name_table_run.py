"""Measure the program's own matching of names of assets, on the names set, one half at a time.

    .venv/bin/python -m evals.name_table_run --direct
    .venv/bin/python -m evals.name_table_run --model qwen2.5:7b
    .venv/bin/python -m evals.name_table_run --direct --half locked

Run from the top of the repository. The program matches a name the
ledger's table does not find by the user's earlier answers and by its own
table of common company names (``core.stock_names``), with no call to the
model. Two ways to measure it:

- direct (``--direct``): each sentence's words for the asset, written as a
  draft's cell holds them (``spoken_key``), are looked up as the assistant
  looks them up, with the demo book's asset table: first by the table
  itself, then by the same function the recording flow calls
  (``stock_names.find_name``), the table on and no answers remembered. No
  model is asked;
- whole (the default): each sentence is said once, in a chat of its own, to
  the whole assistant (``flows.conversation.say``) with the real model, a
  new fake ledger holding the demo book, and the set's fixed moment and
  zone; the table on, no file of answers handed in, and the model never
  handed a name to pick (``conversation.ASSISTANT_PICKS_ASSETS`` stays off).

Every asset the program matched, found as a trade's asset or sent counts
toward the verdict (``name_set.judge``): a name the table gives codes the
ledger lacks, told to be added first, is right for a sentence whose asset
the book does not hold. A sentence whose model call fails is said again
once, three minutes later; failing twice, it is "not measured". More than
one in ten not measured in a group voids the run, and the end line says so.

``--half`` picks the half. ``practice`` (the default) prints every
sentence, with the codes the table gives each name whether or not the
ledger has them, and writes each to the results file. ``locked`` prints
only the counts of each group, and writes only the conditions and the
counts to the results file, never a sentence; its file's name holds
"hidden", and the run gets its line in the hidden-run log
(``hidden_runs.log_hidden_run``).

The results go into ``evals/tool_results/``. Exit status: 0 the run
finished; 2 it could not start.

Names defined here: ``RETRY_WAIT_SECONDS``, ``direct_assets``,
``whole_assets``, ``results_name``, ``run`` and ``main``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO

from evals.hidden_runs import log_hidden_run
from evals.name_set import (
    NAMES_SET,
    NOT_MEASURED_SHARE,
    Group,
    Half,
    NameSentence,
    Verdict,
    counts,
    judge,
    load_name_set,
)
from evals.run import Backend, local_backend
from evals.tool_run import REPO_ROOT, TOOL_RESULTS_DIR, _git
from ledger_hand.core.assets import AssetTable
from ledger_hand.core.coins import spoken_key
from ledger_hand.core.ledger_table import table_of
from ledger_hand.core.stock_names import (
    COMPANY_NAMES,
    NameMatched,
    bare_name,
    codes_named,
    find_name,
)
from ledger_hand.flows import assisting, conversation
from ledger_hand.flows.conversation import AssistantChat, Said, say
from ledger_hand.flows.progress import Tuning
from ledger_hand.flows.recorded import RecordEnding
from ledger_hand.flows.recording import tuning_from
from ledger_hand.ledger.demo_book import DEMO_ASSETS, demo_ledger
from ledger_hand.ports import ModelPort
from ledger_hand.settings import SettingsError, load_assistant_steps, load_model_settings

# Another session may hold the model; three minutes lets it finish, as for the
# measure of picking. Not measured.
RETRY_WAIT_SECONDS = 180

_DEMO_TABLE = table_of(DEMO_ASSETS)

type _Measure = Callable[[NameSentence], tuple[set[str], dict[str, object], bool]]


def _table() -> AssetTable:
    if _DEMO_TABLE is None:
        raise ValueError("the demo book prices trades in no money")
    return _DEMO_TABLE


def direct_assets(sentence: NameSentence) -> tuple[set[str], dict[str, object], bool]:
    """The assets the direct measure finds, what to write of it, and no failure ever."""
    table = _table()
    word = spoken_key(sentence.words)
    name = bare_name(word)
    line: dict[str, object] = {
        "bare": name,
        "table_gives": list(codes_named(name)) if name is not None else [],
    }
    coin = table.find(word)
    if coin is not None:
        return (
            {coin.symbol},
            {**line, "came": f"found in the ledger's table as {coin.symbol}"},
            False,
        )
    outcome = find_name(word, table, (), table=True)
    if outcome is None:
        return set(), {**line, "came": "not matched"}, False
    found = outcome.found
    if isinstance(found, NameMatched):
        return {found.code}, {**line, "came": f"matched {found.code}"}, False
    kind = type(found).__name__
    return set(), {**line, "came": f"{kind}: {', '.join(found.codes)}"}, False


def whole_assets(
    sentence: NameSentence, model: ModelPort, steps: int, tuning: Tuning
) -> tuple[set[str], dict[str, object], bool]:
    """The assets the whole assistant matched, named or sent, what to write, and a failure."""
    names = load_name_set()
    said = say(
        AssistantChat(),
        sentence.text,
        model=model,
        ledger=demo_ledger(),
        now=names.now,
        zone=names.zone,
        max_steps=steps,
        tuning=tuning,
        name_table=True,
    )
    found, line = _came(said)
    return found, line, _failed(said)


def _came(said: Said) -> tuple[set[str], dict[str, object]]:
    recorded = said.recorded
    if recorded is None:
        ending = said.turn.ending.value if said.turn is not None else "-"
        return set(), {"ending": f"not recorded ({ending})", "reply": said.reply}
    progress = recorded.progress
    table = progress.setting.assets
    matched = {
        outcome.found.code for outcome in progress.names if isinstance(outcome.found, NameMatched)
    }
    named = set()
    for trade in progress.trades:
        coin = table.find(trade.draft.coin) if trade.draft.coin is not None else None
        if coin is not None:
            named.add(coin.symbol)
    sent = {trade.asset for trade in recorded.trades} if recorded.sent is not None else set()
    question = recorded.question
    line: dict[str, object] = {
        "ending": recorded.ending.value,
        "asked": question.label if question is not None else None,
        "left_out": [left.why.value for left in recorded.left_out],
        "names": [
            {"word": outcome.word, "bare": outcome.name, "found": _found_text(outcome.found)}
            for outcome in progress.names
        ],
        "words_in_cells": [trade.draft.picked or trade.draft.coin for trade in progress.trades],
        "named": sorted(named),
        "sent": sorted(sent),
        "reply": said.reply,
    }
    return matched | named | sent, line


def _found_text(found: object) -> str:
    if isinstance(found, NameMatched):
        return f"matched {found.code} ({found.source.by.name.lower()})"
    codes = getattr(found, "codes", ())
    return f"{type(found).__name__}: {', '.join(codes)}"


def _failed(said: Said) -> bool:
    """Whether the model failed anywhere in what was said."""
    if said.turn is not None and said.turn.failure is not None:
        return True
    recorded = said.recorded
    return recorded is not None and recorded.ending is RecordEnding.MODEL_FAILED


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _conditions(
    backend: Backend | None, started: datetime, way: str, half: Half, steps: int | None
) -> dict[str, object]:
    names = load_name_set()
    results = TOOL_RESULTS_DIR.relative_to(REPO_ROOT).as_posix()
    return {
        "record": "run",
        "set_file": NAMES_SET.relative_to(REPO_ROOT).as_posix(),
        "set_sha256": _sha256(NAMES_SET.read_bytes()),
        "way": way,
        "half": half.value,
        "table_rows": len(COMPANY_NAMES),
        "table_sha256": _sha256(json.dumps(COMPANY_NAMES, ensure_ascii=False).encode("utf-8")),
        "picks_assets": conversation.ASSISTANT_PICKS_ASSETS,
        "screen_prompt": conversation.ASSISTANT_SCREEN_PROMPT.name,
        "extraction_prompt": conversation.ASSISTANT_EXTRACT_PROMPT.name,
        "prompt": assisting.DEFAULT_PROMPT.name,
        "commit": _git("rev-parse", "HEAD"),
        "worktree_clean": not _git("status", "--porcelain", "--", ".", f":(exclude){results}"),
        "model": backend.name if backend is not None else None,
        "model_fingerprint": backend.fingerprint if backend is not None else None,
        "server_version": backend.server_version if backend is not None else None,
        "parameters": dict(backend.parameters) if backend is not None else None,
        "max_steps": steps,
        "now": names.now.isoformat(),
        "zone": names.zone,
        "started_at": started.isoformat(timespec="seconds"),
    }


def _measured(sentence: NameSentence, measure: _Measure, wait: Callable[[], None]) -> dict:
    """One sentence measured, said again once after ``wait`` when the model failed."""
    found, line, failed = measure(sentence)
    tries = 1
    if failed:
        wait()
        found, line, failed = measure(sentence)
        tries = 2
    verdict = Verdict.NOT_MEASURED if failed else judge(sentence, found)
    return {
        "record": "sentence",
        "id": sentence.id,
        "group": sentence.group.value,
        "kind": sentence.kind,
        "half": sentence.half.value,
        "said": sentence.text,
        "words": sentence.words,
        "gold": sentence.gold,
        "found": sorted(found),
        "tries": tries,
        "verdict": verdict.name.lower(),
        **line,
    }


def _end(lines: Sequence[dict]) -> dict[str, object]:
    end: dict[str, object] = {"record": "end"}
    void = False
    for group in Group:
        mine = [line for line in lines if line["group"] == group.value]
        tally: dict[str, object] = dict(
            counts(Verdict[str(line["verdict"]).upper()] for line in mine)
        )
        tally["of"] = len(mine)
        void = void or len([1 for line in mine if line["verdict"] == "not_measured"]) > (
            NOT_MEASURED_SHARE * len(mine)
        )
        end[group.value] = tally
    end["wrong"] = sum(1 for line in lines if line["verdict"] == "wrong")
    end["void"] = void
    return end


def results_name(head: dict[str, object], half: Half) -> str:
    """The results file's name; the locked half's holds "hidden", as the hidden-run log wants."""
    stamp = datetime.fromisoformat(str(head["started_at"])).strftime("%Y%m%dT%H%M%SZ")
    part = "hidden" if half is Half.LOCKED else half.value
    return f"run-{stamp}-stock_names-table-{head['way']}-{part}.jsonl"


def run(
    head: dict[str, object],
    measure: _Measure,
    half: Half,
    *,
    folder: Path = TOOL_RESULTS_DIR,
    wait: Callable[[], None] = lambda: time.sleep(RETRY_WAIT_SECONDS),
) -> tuple[Path, list[dict], dict[str, object]]:
    """Measure every sentence of ``half``; the results file, the lines, and the end line.

    For the locked half, the file holds the conditions and the end line
    alone: no sentence is ever written.
    """
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / results_name(head, half)
    lines: list[dict] = []
    for sentence in load_name_set().sentences:
        if sentence.half is half:
            lines.append(_measured(sentence, measure, wait))
    end = _end(lines)
    written = [head, end] if half is Half.LOCKED else [head, *lines, end]
    path.write_text(
        "".join(json.dumps(one, ensure_ascii=False) + "\n" for one in written),
        encoding="utf-8",
        newline="\n",
    )
    return path, lines, end


def _table_text(lines: Sequence[dict], way: str) -> str:
    rows = [
        "| Sentence | Group | Words | Gold | Table gives | Found | What came of it | Verdict |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for line in lines:
        gives = ", ".join(line.get("table_gives", [])) or "-"
        if way == "whole":
            what = (
                f"{line['ending']}; names: "
                + (
                    "; ".join(f"{one['word']}->{one['found']}" for one in line.get("names", []))
                    or "-"
                )
                + f"; asked: {line.get('asked') or ''}"
                + f"; sent: {', '.join(line.get('sent', [])) or '-'}"
            )
        else:
            what = str(line.get("came"))
        rows.append(
            f"| {line['id']} | {line['group']} | {line['words']} | {line['gold'] or '-'} | "
            f"{gives} | {', '.join(line['found']) or '-'} | {what.replace('|', '/')} | "
            f"{line['verdict']} |"
        )
    return "\n".join(rows)


def _report(out: TextIO, lines: Sequence[dict], end: dict[str, object], head: dict) -> None:
    way, half = str(head["way"]), Half(head["half"])
    print(f"way: {way}; half: {half.value}; model: {head['model']}", file=out)
    for group in Group:
        print(f"{group.value}: {json.dumps(end[group.value])}", file=out)
    print(f"wrong in all: {end['wrong']}; void: {end['void']}", file=out)
    if half is Half.PRACTICE:
        print(_table_text(lines, way), file=out)


def main(arguments: Sequence[str] = (), *, out: TextIO = sys.stdout) -> int:
    """Run the measure on one half; print what that half may show."""
    parser = argparse.ArgumentParser(prog="evals.name_table_run")
    parser.add_argument("--direct", action="store_true")
    parser.add_argument("--half", choices=[half.value for half in Half], default="practice")
    parser.add_argument("--model", default=None)
    options = parser.parse_args(arguments)
    half = Half(options.half)
    way = "direct" if options.direct else "whole"
    backend: Backend | None = None
    steps: int | None = None
    measure: _Measure = direct_assets
    if not options.direct:
        try:
            backend = local_backend(options.model)
            steps = load_assistant_steps()
            tuning = tuning_from(load_model_settings())
        except (SettingsError, ValueError) as error:
            print(f"cannot start: {error}", file=out)
            return 2
        model, many = backend.model, steps
        measure = lambda sentence: whole_assets(sentence, model, many, tuning)  # noqa: E731
    head = _conditions(backend, datetime.now(UTC), way, half, steps)
    path, lines, end = run(head, measure, half)
    if half is Half.LOCKED:
        log_hidden_run(
            NAMES_SET,
            path,
            {key: value for key, value in end.items() if key != "record"},
            extraction_prompt=str(head["extraction_prompt"]),
            prompt=str(head["prompt"]),
        )
    print(f"results: {path.relative_to(REPO_ROOT).as_posix()}", file=out)
    _report(out, lines, end, head)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
