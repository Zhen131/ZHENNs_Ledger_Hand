"""Tests of the question and change measures on a set that names the exam book and its half.

A set naming ``"book": "exam"`` is run against the exam book, and its
changes are judged against the exam book's trades; a hidden half prints
the count of each verdict alone, never a sentence or its identifier, and
adds a line to the hidden-run log. A stand-in model does the same thing
every turn; no real model is called.
"""

from __future__ import annotations

import io
import json
import shutil
from collections.abc import Sequence
from pathlib import Path

import pytest

import evals.ask_run as ask_run
import evals.edit_run as edit_run
import evals.hidden_runs as hidden_runs
from evals.ask_set import load_ask_set
from evals.edit_set import Outcome, Verdict, expected_trade, judge_edit, load_edit_set
from evals.exam_book import EXAM_TRADES
from evals.run import Backend
from ledger_hand.core.ledger_records import TradeFilter
from ledger_hand.ports import ChatItem, ModelParameters, ToolCall, ToolReply, ToolResult, ToolSpec
from tests.fakes.scripted_model import scripted_record

SPOKEN = Path(__file__).resolve().parents[2] / "evals" / "sets" / "spoken"


class _SameEveryTurn:
    """A stand-in model: one tool call, then, once its result is back, a few words."""

    def __init__(self, call: ToolCall) -> None:
        self._call = call

    def chat_with_tools(
        self,
        items: Sequence[ChatItem],
        tools: Sequence[ToolSpec],
        *,
        parameters: ModelParameters | None = None,
    ) -> ToolReply:
        if items and isinstance(items[-1], ToolResult):
            return ToolReply(text="Here it is.", calls=(), record=scripted_record())
        return ToolReply(text="", calls=(self._call,), record=scripted_record())


def _run(
    measure: str, set_name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[str, list[dict[str, object]], Path]:
    module = ask_run if measure == "ask" else edit_run
    call = (
        ToolCall(name="get_positions", arguments={})
        if measure == "ask"
        else ToolCall(name="propose_trade_delete", arguments={"asset": "SOL"})
    )
    root = tmp_path / "repo"
    (root / "evals" / "sets").mkdir(parents=True)
    set_file = root / "evals" / "sets" / set_name
    shutil.copyfile(SPOKEN / set_name, set_file)
    results = root / "evals" / "tool_results"
    log = tmp_path / "hidden-runs.log"
    backend = Backend(
        model=_SameEveryTurn(call),  # type: ignore[arg-type]
        name="stand-in",
        fingerprint="-",
        server_version="-",
        base_url="-",
        parameters={},
    )
    monkeypatch.setattr(module, "REPO_ROOT", root)
    monkeypatch.setattr(module, "TOOL_RESULTS_DIR", results)
    monkeypatch.setattr(module, "local_backend", lambda _name: backend)
    monkeypatch.setattr(module, "load_assistant_steps", lambda: 6)
    monkeypatch.setattr(hidden_runs, "REPO_ROOT", root)
    monkeypatch.setattr(hidden_runs, "HIDDEN_LOG", log)
    monkeypatch.setattr(
        module,
        "log_hidden_run",
        lambda *arguments, **options: hidden_runs.log_hidden_run(*arguments, log=log, **options),
    )
    out = io.StringIO()
    assert module.main(["--set", str(set_file)], out=out) == 0
    (written,) = results.glob("*.jsonl")
    lines = [json.loads(line) for line in written.read_text("utf-8").splitlines()]
    return out.getvalue(), lines, log


def _entries(set_name: str) -> list[dict[str, object]]:
    data = json.loads((SPOKEN / set_name).read_text("utf-8"))
    groups = data.get("groups")
    return [entry for group in groups for entry in group] if groups else data["sentences"]


@pytest.mark.parametrize(
    ("measure", "set_name"),
    [("ask", "spoken-asks-hidden.json"), ("edit", "spoken-edits-hidden.json")],
)
def test_a_hidden_half_prints_totals_alone_and_is_logged(
    measure: str, set_name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    printed, lines, log = _run(measure, set_name, tmp_path, monkeypatch)

    leaked = [
        str(entry["id"])
        for entry in _entries(set_name)
        if str(entry["id"]) in printed or str(entry["text"]) in printed
    ]
    assert leaked == []
    assert "totals only" in printed
    assert (lines[0]["book"], lines[0]["half"]) == ("exam", "hidden")
    assert len(lines) == len(_entries(set_name)) + 2
    (logged,) = [json.loads(line) for line in log.read_text("utf-8").splitlines()]
    assert logged["results"].endswith(".jsonl")
    assert logged["totals"]["of"] == len(_entries(set_name))


@pytest.mark.parametrize(
    ("measure", "set_name"),
    [("ask", "spoken-asks-practice.json"), ("edit", "spoken-edits-practice.json")],
)
def test_a_practice_half_prints_each_sentence_without_the_first_sentences_line(
    measure: str, set_name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    printed, _, log = _run(measure, set_name, tmp_path, monkeypatch)

    assert all(f"| {entry['id']} |" in printed for entry in _entries(set_name))
    assert "Q1 to Q6" not in printed and "E1 to E3" not in printed
    assert not log.exists()


def test_a_set_naming_the_exam_book_is_run_against_it() -> None:
    asks = load_ask_set(SPOKEN / "spoken-asks-practice.json")
    edits = load_edit_set(SPOKEN / "spoken-edits-practice.json")

    for ledger in (ask_run._ledger(asks), edit_run._ledger(edits)):
        listed = {trade.id for trade in ledger.list_trades(TradeFilter()).trades}
        assert {"t-21", "t-27"} <= listed
    assert edit_run._book(edits) == dict(EXAM_TRADES)


def test_a_change_is_judged_against_the_exam_book() -> None:
    book = dict(EXAM_TRADES)
    edits = {one.id: one for one in load_edit_set(SPOKEN / "spoken-edits-practice.json").sentences}
    deleted = Outcome(asked_pick=True, sent_kind="delete", sent_trade="t-24", ending="sent")
    changed = expected_trade(edits["E-07"].gold, book)

    assert judge_edit(edits["E-05"].gold, deleted, book) is Verdict.RIGHT
    assert changed is not None
    assert (str(changed.price), str(changed.total)) == ("64500", "64.5")
