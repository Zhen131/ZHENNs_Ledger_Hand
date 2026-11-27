"""Say the sentences about cash balances and money moved to the whole assistant, and judge them.

    .venv/bin/python -m evals.cash_balances_run
    .venv/bin/python -m evals.cash_balances_run --group manual

Run from the top of the repository. Each sentence of
``evals/sets/cash/cash-balances.json`` is said once, in a chat of its own,
to the whole assistant (``flows.conversation.say``): the real model the
settings name (or ``--model``), a fresh demo ledger with cash
(``ledger.demo_cash``) that takes cards, and the set's fixed moment and
zone. Nothing is answered: a question asked is what came of it.
``--group`` runs one group alone.

Each sentence is judged (``judge``):

- ``named``: laid out the ledger's table of balances, or not.
- ``manual``: read as the kinds the set names, or not (reported, no line);
  and never sent as a trade alone; beside a trade, the trade recorded or
  the reply saying it was not.
- ``must_pass``: read neither as money moved nor, by the reading after the
  question about cash, as a balance asked.
- every one: when the model wrote the reply, every figure in it is one a
  table of this turn or the user gave, and a figure said as cash is a
  cash balance of the money it names, never one of the holdings; none is
  said as money put in or taken out (``cash_figures.unfound``; second
  rework, 2026-11-26).

The results go into ``evals/tool_results/``: a first line with the
conditions, one line for each sentence with the way it went
(``cash_run.path_of``), the reply and the verdict. The totals and a table
are printed at the end.

Exit status: 0 the run finished; 2 it could not start.

Names defined here: ``CASH_BALANCES_SET``, ``Sentence``, ``load_set``,
``Verdict``, ``judge``, ``totals`` and ``main``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO

from evals.cash_figures import unfound
from evals.cash_run import path_of
from evals.run import Backend, cloud_conditions, local_backend
from evals.tool_run import REPO_ROOT, TOOL_RESULTS_DIR, _git
from ledger_hand.core.cash_words import held_names
from ledger_hand.core.ledger_table import names_of
from ledger_hand.core.money_asks import left_asked
from ledger_hand.flows import assisting
from ledger_hand.flows.cash_question import caught
from ledger_hand.flows.conversation import AssistantChat, Route, Said, WordsBy, say
from ledger_hand.flows.recorded import RecordEnding
from ledger_hand.flows.recording import tuning_from
from ledger_hand.ledger.demo_book import DEMO_ASSETS
from ledger_hand.ledger.demo_cash import demo_ledger_with_cash
from ledger_hand.ports import ModelError
from ledger_hand.settings import SettingsError, load_assistant_steps, load_model_settings

CASH_BALANCES_SET = Path(__file__).resolve().parent / "sets" / "cash" / "cash-balances.json"
_GROUPS = ("named", "manual", "must_pass")
# The names of the coins and shares, so that "BTC 余额" is not taken for cash.
_HELD = (*(name for name, _ in names_of(()).built_in), *held_names(DEMO_ASSETS))


@dataclass(frozen=True)
class Sentence:
    """One sentence of the set: its id, group and words; for ``manual``, what it tells."""

    id: str
    group: str
    text: str
    kinds: tuple[str, ...] = ()
    with_trade: bool = False


def load_set(path: Path = CASH_BALANCES_SET) -> tuple[datetime, str, tuple[Sentence, ...]]:
    """The set's moment, its zone and its sentences, group by group."""
    data = json.loads(path.read_text(encoding="utf-8"))
    sentences = tuple(
        Sentence(
            id=str(one["id"]),
            group=group,
            text=str(one["text"]),
            kinds=tuple(one.get("kinds", ())),
            with_trade=bool(one.get("with_trade", False)),
        )
        for group in _GROUPS
        for one in data[group]
    )
    return datetime.fromisoformat(data["now"]), str(data["zone"]), sentences


@dataclass(frozen=True)
class Verdict:
    """What came of one sentence: ``right`` as its group asks; ``trouble`` names what went
    wrong in a way the set allows none of (an empty text for none)."""

    right: bool
    trouble: str
    note: str


def _unheard_figure(said: Said, text: str) -> str | None:
    """Why a figure of the model's own words is made up (``cash_figures.unfound``), or ``None``.

    The tables are those the read tools handed back this turn, and the
    ledger's cash balances when the program read them.
    """
    turn = said.turn
    if said.words_by is not WordsBy.MODEL or turn is None:
        return None
    seen = said.cash_seen
    return unfound(
        said.reply,
        tables=turn.lookups,
        cash=seen.balances if seen is not None else None,
        user_said=(*turn.chat.user_said, text),
        held=_HELD,
    )


def judge(sentence: Sentence, said: Said) -> Verdict:
    """How ``said`` fares for ``sentence``, as its group asks."""
    figure = _unheard_figure(said, sentence.text)
    trouble = f"the model's words: {figure}" if figure else ""
    if sentence.group == "named":
        seen = said.cash_seen
        right = seen is not None and seen.shown
        return Verdict(right, trouble, "table laid out" if right else "no table")
    if sentence.group == "manual":
        manual = said.manual
        kinds = tuple(kind.name.lower() for kind in manual.kinds) if manual is not None else ()
        right = kinds == sentence.kinds and (manual is not None and manual.with_trade) == (
            sentence.with_trade
        )
        if not sentence.with_trade and said.sent is not None:
            trouble = trouble or "sent as a trade"
        if sentence.with_trade:
            recorded = (
                said.recorded is not None and said.recorded.ending is not RecordEnding.NO_TRADE
            )
            if not recorded and "was not recorded either" not in said.reply:
                trouble = trouble or "the trade beside it neither recorded nor said not to be"
        return Verdict(right, trouble, f"read as {', '.join(kinds) or 'nothing'}")
    misread = said.route is Route.MANUAL or said.manual is not None
    third = said.route is Route.CASH and caught(sentence.text, demo_ledger_with_cash()) is None
    if third and left_asked(sentence.text):
        misread = True
    return Verdict(not misread, trouble, "misread" if misread else "not read as either")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _cell(text: str) -> str:
    return " ".join(text.split()).replace("|", "/")


def _extra(said: Said) -> dict[str, Any]:
    seen = said.cash_seen
    return {
        "manual": [kind.name.lower() for kind in said.manual.kinds] if said.manual else None,
        "cash_tool": seen.tool if seen is not None else None,
        "table": seen.shown if seen is not None else False,
        "sent": said.sent.trades if said.sent is not None else 0,
    }


def _head(
    set_file: Path,
    chosen: str | None,
    backend: Backend,
    steps: int,
    now: datetime,
    zone: str,
    started: datetime,
) -> dict[str, Any]:
    """The first line of a results file: everything the run's numbers depend on."""
    results = TOOL_RESULTS_DIR.relative_to(REPO_ROOT).as_posix()
    return {
        "record": "run",
        "set_file": set_file.relative_to(REPO_ROOT).as_posix(),
        "set_sha256": _sha256(set_file.read_bytes()),
        "group": chosen,
        "prompt": assisting.DEFAULT_PROMPT.name,
        "commit": _git("rev-parse", "HEAD"),
        "worktree_clean": not _git("status", "--porcelain", "--", ".", f":(exclude){results}"),
        "model": backend.name,
        "model_fingerprint": backend.fingerprint,
        "server_version": backend.server_version,
        "parameters": dict(backend.parameters),
        **cloud_conditions(backend),
        "max_steps": steps,
        "now": now.isoformat(),
        "zone": zone,
        "started_at": started.isoformat(timespec="seconds"),
    }


def _said_and_judged(sentence: Sentence, ports: dict[str, Any]) -> dict[str, Any]:
    """One sentence said in a chat of its own, and its line of the results file."""
    began = time.monotonic()
    said = say(
        AssistantChat(),
        sentence.text,
        ledger=demo_ledger_with_cash().taking_cards(),
        **ports,
    )
    verdict = judge(sentence, said)
    return {
        "record": "sentence",
        "id": sentence.id,
        "group": sentence.group,
        "said": sentence.text,
        "path": path_of(said),
        **_extra(said),
        "reply": said.reply,
        "right": verdict.right,
        "trouble": verdict.trouble,
        "note": verdict.note,
        "seconds": round(time.monotonic() - began, 1),
    }


def _run(options: argparse.Namespace, out: TextIO) -> int:
    try:
        backend = local_backend(options.model)
        steps = load_assistant_steps()
        tuning = tuning_from(load_model_settings())
    except (SettingsError, ModelError) as error:
        print(f"cannot start: {error}", file=out)
        return 2
    set_file = Path(options.set).resolve()
    now, zone, sentences = load_set(set_file)
    started = datetime.now(UTC)
    TOOL_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = started.strftime("%Y%m%dT%H%M%SZ")
    name = f"run-{stamp}-{set_file.stem}-{options.group or 'all'}-{assisting.DEFAULT_PROMPT.name}"
    path = TOOL_RESULTS_DIR / f"{name}.jsonl"
    head = _head(set_file, options.group, backend, steps, now, zone, started)
    ports = {"model": backend.model, "now": now, "zone": zone, "max_steps": steps, "tuning": tuning}
    lines = []
    with path.open("w", encoding="utf-8", newline="\n") as kept:
        kept.write(json.dumps(head, ensure_ascii=False) + "\n")
        for sentence in sentences:
            if options.group not in (None, sentence.group):
                continue
            line = _said_and_judged(sentence, ports)
            kept.write(json.dumps(line, ensure_ascii=False) + "\n")
            kept.flush()
            lines.append(line)
    print(f"results: {path.relative_to(REPO_ROOT).as_posix()}", file=out)
    print(totals(lines), file=out)
    print("\n".join(_table(lines)), file=out)
    return 0


def totals(lines: Sequence[dict[str, Any]]) -> str:
    """How many of each group went right, and how many sentences had trouble."""
    counted = []
    for group, words in zip(
        _GROUPS,
        ("named laid out a table", "manual read as the set says", "must_pass read as neither"),
        strict=True,
    ):
        mine = [line for line in lines if line["group"] == group]
        counted.append(f"{words}: {sum(line['right'] for line in mine)} of {len(mine)}")
    troubles = sum(bool(line["trouble"]) for line in lines)
    return "; ".join(counted) + f"; trouble: {troubles}"


def _table(lines: Sequence[dict[str, Any]]) -> list[str]:
    rows = [
        "| Sentence | Group | Verdict | Trouble | Way | Reply |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for line in lines:
        way = _cell(json.dumps(line["path"], ensure_ascii=False))
        rows.append(
            f"| {line['id']} | {line['group']} | {line['note']} | {line['trouble'] or '-'} "
            f"| {way} | {_cell(line['reply'])} |"
        )
    return rows


def main(arguments: Sequence[str] = (), *, out: TextIO = sys.stdout) -> int:
    """Run the set, or one group of it."""
    parser = argparse.ArgumentParser(prog="evals.cash_balances_run")
    parser.add_argument("--model", default=None)
    parser.add_argument("--set", default=str(CASH_BALANCES_SET), help="the set to run")
    parser.add_argument("--group", choices=_GROUPS, default=None)
    return _run(parser.parse_args(arguments), out)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
