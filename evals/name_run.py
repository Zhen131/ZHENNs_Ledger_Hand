"""Measure picking an asset from the ledger's list, on the names set, one half at a time.

    .venv/bin/python -m evals.name_run --direct
    .venv/bin/python -m evals.name_run
    .venv/bin/python -m evals.name_run --direct --half locked --prompt asset-pick-2

Run from the top of the repository. Two ways to measure:

- direct (``--direct``): each sentence's words for the asset, written as a
  draft's cell holds them (``spoken_key``), go first through the same test
  the assistant makes of whether to hand them over (``should_pick``), with
  the demo book's asset table. Those handed over are picked with the prompt
  version named (``pick_asset``); the rest are not sent to the model, and
  are judged by what the table does with them: found as an asset, or not
  (marked "not asked");
- whole (the default): each sentence is said once, in a chat of its own, to
  the whole assistant (``flows.conversation.say``) with the real model, a
  new fake ledger holding the demo book, and the set's fixed moment and
  zone, the asset picked with the prompt version named. Every asset picked,
  named as a trade's asset or sent counts toward the verdict
  (``name_set.judge``), and how it ended is written beside it.

A sentence whose model call fails is said again once, three minutes later;
failing twice, it is "not measured". More than one in ten not measured in
a group voids the run, and the end line says so.

``--half`` picks the half: ``practice`` (the default) prints every
sentence; ``locked`` prints only the counts of each group, and writes each
sentence to the results file alone.

The results go into ``evals/tool_results/``: a first line with the
conditions, one line for each sentence, and an ``end`` line with the counts
of each group. Exit status: 0 the run finished; 2 it could not start.

Names defined here: ``PROMPTS``, ``RETRY_WAIT_SECONDS``, ``direct_assets``,
``whole_assets`` and ``main``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import TextIO

from evals.name_set import (
    NAMES_SET,
    NOT_MEASURED_SHARE,
    RIGHT_SHARE,
    Group,
    Half,
    NameSentence,
    Verdict,
    counts,
    judge,
    load_name_set,
)
from evals.run import Backend, cloud_conditions, local_backend
from evals.tool_run import REPO_ROOT, TOOL_RESULTS_DIR, _git
from ledger_hand.core.assets import AssetTable
from ledger_hand.core.coins import spoken_key
from ledger_hand.core.ledger_table import table_of
from ledger_hand.extraction.asset_picking import PickMiss, pick_asset, should_pick
from ledger_hand.extraction.prompts.asset_pick import ASSET_PICK_PROMPT, AssetPickPrompt
from ledger_hand.extraction.prompts.asset_pick2 import ASSET_PICK_PROMPT_2
from ledger_hand.extraction.prompts.asset_pick3 import ASSET_PICK_PROMPT_3
from ledger_hand.flows import conversation
from ledger_hand.flows.conversation import AssistantChat, Said, say
from ledger_hand.flows.progress import Tuning
from ledger_hand.flows.recorded import RecordEnding
from ledger_hand.flows.recording import tuning_from
from ledger_hand.ledger.demo_book import DEMO_ASSETS, demo_ledger
from ledger_hand.ports import ModelParameters, ModelPort
from ledger_hand.settings import SettingsError, load_assistant_steps, load_model_settings

# The prompt versions that may be measured, by name.
PROMPTS: dict[str, AssetPickPrompt] = {
    prompt.name: prompt for prompt in (ASSET_PICK_PROMPT, ASSET_PICK_PROMPT_2, ASSET_PICK_PROMPT_3)
}

# Another session may hold the model; three minutes lets it finish. Set on
# 2026-11-25; not measured.
RETRY_WAIT_SECONDS = 180

_DEMO_TABLE = table_of(DEMO_ASSETS)


def _table() -> AssetTable:
    if _DEMO_TABLE is None:
        raise ValueError("the demo book prices trades in no money")
    return _DEMO_TABLE


def _pick_parameters(tuning: Tuning) -> ModelParameters | None:
    base = tuning.question_parameters
    if base is None:
        return None
    return ModelParameters(
        temperature=0.0,
        top_p=base.top_p,
        max_reply_tokens=100,
        context_tokens=base.context_tokens,
        timeout_seconds=base.timeout_seconds,
    )


def direct_assets(
    sentence: NameSentence, model: ModelPort, prompt: AssetPickPrompt, tuning: Tuning
) -> tuple[set[str], dict[str, object], bool]:
    """The assets the direct measure finds, what to write of it, and whether the model failed."""
    table = _table()
    word = spoken_key(sentence.words)
    if not should_pick(word, table):
        coin = table.find(word)
        found = {coin.symbol} if coin is not None else set()
        return found, {"asked": False, "found": sorted(found)}, False
    picked = pick_asset(word, table, model, prompt=prompt, parameters=_pick_parameters(tuning))
    line: dict[str, object] = {
        "asked": True,
        "word": picked.word,
        "said": picked.said,
        "code": picked.answered,
        "picked": picked.code,
        "miss": picked.miss.name.lower() if picked.miss is not None else None,
    }
    found = {picked.code} if picked.code is not None else set()
    return found, line, picked.miss is PickMiss.MODEL_FAILED


def whole_assets(
    sentence: NameSentence, model: ModelPort, steps: int, tuning: Tuning
) -> tuple[set[str], dict[str, object], bool]:
    """The assets the whole assistant picked, named or sent, what to write, and a failure."""
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
    )
    found, line = _came(said)
    return found, line, _failed(said)


def _came(said: Said) -> tuple[set[str], dict[str, object]]:
    recorded = said.recorded
    if recorded is None:
        ending = said.turn.ending.value if said.turn is not None else "-"
        return set(), {"ending": f"not recorded ({ending})", "reply": said.reply}
    table = recorded.progress.setting.assets
    picked = {found.code for found in recorded.progress.picks if found.code is not None}
    named = set()
    for trade in recorded.progress.trades:
        coin = table.find(trade.draft.coin) if trade.draft.coin is not None else None
        if coin is not None:
            named.add(coin.symbol)
    sent = {trade.asset for trade in recorded.trades} if recorded.sent is not None else set()
    question = recorded.question
    asked = question.label if question is not None else None
    line: dict[str, object] = {
        "ending": recorded.ending.value,
        "asked": asked,
        "left_out": [left.why.value for left in recorded.left_out],
        "picks": [
            {
                "word": found.word,
                "said": found.said,
                "code": found.answered,
                "picked": found.code,
                "miss": found.miss.name.lower() if found.miss is not None else None,
            }
            for found in recorded.progress.picks
        ],
        "named": sorted(named),
        "sent": sorted(sent),
        "reply": said.reply,
    }
    return picked | named | sent, line


def _failed(said: Said) -> bool:
    """Whether the model failed anywhere in what was said."""
    if said.turn is not None and said.turn.failure is not None:
        return True
    recorded = said.recorded
    if recorded is None:
        return False
    if recorded.ending is RecordEnding.MODEL_FAILED:
        return True
    return any(found.miss is PickMiss.MODEL_FAILED for found in recorded.progress.picks)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _conditions(
    backend: Backend, started: datetime, prompt: AssetPickPrompt, way: str, half: Half, steps: int
) -> dict[str, object]:
    names = load_name_set()
    results = TOOL_RESULTS_DIR.relative_to(REPO_ROOT).as_posix()
    return {
        "record": "run",
        "set_file": NAMES_SET.relative_to(REPO_ROOT).as_posix(),
        "set_sha256": _sha256(NAMES_SET.read_bytes()),
        "way": way,
        "half": half.value,
        "pick_prompt": prompt.name,
        "pick_prompt_sha256": _sha256(
            (prompt.instructions + json.dumps([str(one) for one in prompt.examples])).encode()
        ),
        "screen_prompt": conversation.ASSISTANT_SCREEN_PROMPT.name,
        "extraction_prompt": conversation.ASSISTANT_EXTRACT_PROMPT.name,
        "commit": _git("rev-parse", "HEAD"),
        "worktree_clean": not _git("status", "--porcelain", "--", ".", f":(exclude){results}"),
        "model": backend.name,
        "model_fingerprint": backend.fingerprint,
        "server_version": backend.server_version,
        "parameters": dict(backend.parameters),
        **cloud_conditions(backend),
        "max_steps": steps,
        "now": names.now.isoformat(),
        "zone": names.zone,
        "started_at": started.isoformat(timespec="seconds"),
    }


type _Measure = Callable[[NameSentence], tuple[set[str], dict[str, object], bool]]


def _measured(sentence: NameSentence, measure: _Measure, wait: float) -> dict[str, object]:
    """One sentence measured, said again once after ``wait`` seconds when the model failed."""
    found, line, failed = measure(sentence)
    tries = 1
    if failed:
        time.sleep(wait)
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


def _end(lines: list[dict[str, object]], way: str) -> dict[str, object]:
    end: dict[str, object] = {"record": "end"}
    void = False
    for group in Group:
        mine = [line for line in lines if line["group"] == group.value]
        verdicts = [Verdict[str(line["verdict"]).upper()] for line in mine]
        tally = counts(verdicts)
        tally["not_asked"] = sum(1 for line in mine if line.get("asked") is False)
        tally["of"] = len(mine)
        if group is Group.ON_LIST and way == "direct":
            asked = [line for line in mine if line.get("asked") is True]
            measured = [line for line in asked if line["verdict"] != "not_measured"]
            right = sum(1 for line in measured if line["verdict"] == "right")
            tally["asked_right"] = right
            tally["asked_measured"] = len(measured)
            tally["asked_right_share_met"] = bool(measured) and (
                Decimal(right) / Decimal(len(measured)) >= RIGHT_SHARE
            )
        void = void or (Decimal(tally["not_measured"]) > NOT_MEASURED_SHARE * len(mine))
        end[group.value] = tally
    end["wrong"] = sum(1 for line in lines if line["verdict"] == "wrong")
    end["void"] = void
    return end


def _table_text(lines: list[dict[str, object]], way: str) -> str:
    rows = [
        "| Sentence | Group | Words | Gold | Found | What came of it | Verdict |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for line in lines:
        rows.append(
            f"| {line['id']} | {line['group']} | {line['words']} | {line['gold'] or '-'} | "
            f"{', '.join(line['found']) or '-'} | {_what(line, way)} | {line['verdict']} |"  # type: ignore[arg-type]
        )
    return "\n".join(rows)


def _what(line: dict[str, object], way: str) -> str:
    if way == "direct":
        if line.get("asked") is False:
            return "not asked"
        return f"said {line.get('said')!r}, code {line.get('code')!r}, miss {line.get('miss')}"
    picks = "; ".join(
        f"{pick['word']}->{pick['picked'] or pick['miss']}"
        for pick in line.get("picks", [])  # type: ignore[attr-defined]
    )
    asked = line.get("asked") or ""
    sent = ", ".join(line.get("sent", [])) or "-"  # type: ignore[arg-type]
    return f"{line['ending']}; picks: {picks or '-'}; asked: {asked}; sent: {sent}".replace(
        "|", "/"
    )


def _measure_for(
    *, direct: bool, backend: Backend, prompt: AssetPickPrompt, steps: int, tuning: Tuning
) -> _Measure:
    if direct:
        return lambda sentence: direct_assets(sentence, backend.model, prompt, tuning)
    return lambda sentence: whole_assets(sentence, backend.model, steps, tuning)


def _run(
    head: dict[str, object], measure: _Measure, half: Half
) -> tuple[Path, list[dict[str, object]], dict[str, object]]:
    """Measure every sentence of ``half``, writing each line as it comes; the file, lines, end."""
    TOOL_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.fromisoformat(str(head["started_at"])).strftime("%Y%m%dT%H%M%SZ")
    name = f"run-{stamp}-stock_names-{head['pick_prompt']}-{head['way']}-{half.value}.jsonl"
    path = TOOL_RESULTS_DIR / name
    path.write_text(json.dumps(head, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    lines: list[dict[str, object]] = []
    with path.open("a", encoding="utf-8", newline="\n") as file:
        for sentence in load_name_set().sentences:
            if sentence.half is not half:
                continue
            line = _measured(sentence, measure, RETRY_WAIT_SECONDS)
            lines.append(line)
            file.write(json.dumps(line, ensure_ascii=False) + "\n")
            file.flush()
        end = _end(lines, str(head["way"]))
        file.write(json.dumps(end, ensure_ascii=False) + "\n")
    return path, lines, end


def _report(
    out: TextIO, lines: list[dict[str, object]], end: dict[str, object], head: dict[str, object]
) -> None:
    way, half = str(head["way"]), Half(head["half"])
    print(
        f"way: {way}; half: {half.value}; prompt: {head['pick_prompt']}; model: {head['model']}",
        file=out,
    )
    for group in Group:
        print(f"{group.value}: {json.dumps(end[group.value])}", file=out)
    print(f"wrong in all: {end['wrong']}; void: {end['void']}", file=out)
    if half is Half.PRACTICE:
        print(_table_text(lines, way), file=out)


def main(arguments: Sequence[str] = (), *, out: TextIO = sys.stdout) -> int:
    """Run the measure on one half; print what that half may show."""
    parser = argparse.ArgumentParser(prog="evals.name_run")
    parser.add_argument("--direct", action="store_true")
    parser.add_argument("--half", choices=[half.value for half in Half], default="practice")
    parser.add_argument("--prompt", choices=sorted(PROMPTS), default=ASSET_PICK_PROMPT.name)
    parser.add_argument("--model", default=None)
    options = parser.parse_args(arguments)
    half = Half(options.half)
    prompt = PROMPTS[options.prompt]
    way = "direct" if options.direct else "whole"
    try:
        backend = local_backend(options.model)
        steps = load_assistant_steps()
        tuning = tuning_from(load_model_settings())
    except (SettingsError, ValueError) as error:
        print(f"cannot start: {error}", file=out)
        return 2
    # The step measured is off on the assistant; the whole measure turns it on.
    conversation.ASSISTANT_PICK_PROMPT = prompt
    conversation.ASSISTANT_PICKS_ASSETS = True
    measure = _measure_for(
        direct=options.direct, backend=backend, prompt=prompt, steps=steps, tuning=tuning
    )
    started = datetime.now(UTC)
    head = _conditions(backend, started, prompt, way, half, steps)
    path, lines, end = _run(head, measure, half)
    print(f"results: {path.relative_to(REPO_ROOT).as_posix()}", file=out)
    _report(out, lines, end, head)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
