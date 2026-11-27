"""Tests of the assistant's set of sentences and of the measure of the first step.

The set holds the nineteen sentences, each with first steps taken as right
that are tools on the list or no tool at all, read at one fixed moment. A
first step is right when every tool it asks for is accepted, or when it asks
for none and that is accepted; arguments do not count toward it. The words a
copy should hold, and what the program's judging says, are noted beside.
The runner writes into its own folder and asks the model once a sentence.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from evals import tool_run
from evals.run import Backend
from evals.tool_set import NO_TOOL, load_tool_set, markdown, score_first_step
from ledger_hand.ports import ToolCall, ToolReply
from tests.fakes.scripted_model import ScriptedModel, scripted_record

SET = load_tool_set()
BY_ID = {sentence.id: sentence for sentence in SET.sentences}


def test_the_set_holds_nineteen_sentences_read_at_the_invented_moment() -> None:
    assert len(SET.sentences) == 19
    assert SET.now.isoformat() == "2026-11-24T23:55:00+01:00"
    assert SET.zone == "Europe/Budapest"
    assert BY_ID["O2"].accept == {NO_TOOL}
    assert BY_ID["R6"].accept == {NO_TOOL, "propose_trade_add"}
    assert BY_ID["Q4"].copied == ("10月6号",)


def test_a_step_with_every_call_accepted_is_right_whatever_its_arguments() -> None:
    calls = [ToolCall(name="list_trades", arguments={"period": "2026-10-06"})]

    step = score_first_step(BY_ID["Q4"], calls, "")

    assert step.right
    assert step.words_missing == ("10月6号",)
    assert step.refused and "not_copied" in step.refused[0]


def test_two_calls_are_right_only_when_both_are_accepted() -> None:
    both = [
        ToolCall(name="get_period_summary", arguments={}),
        ToolCall(name="list_trades", arguments={}),
    ]
    one_wrong = [
        ToolCall(name="list_trades", arguments={}),
        ToolCall(name="get_positions", arguments={}),
    ]

    assert score_first_step(BY_ID["Q1"], both, "").right
    assert not score_first_step(BY_ID["Q1"], one_wrong, "").right


def test_no_call_is_right_only_where_no_tool_is_accepted() -> None:
    assert score_first_step(BY_ID["O3"], [], "I cannot place orders.").right
    assert not score_first_step(BY_ID["Q3"], [], "You hold BTC.").right


def test_the_table_counts_the_right_first_steps() -> None:
    steps = [score_first_step(BY_ID["O1"], [], "Hi."), score_first_step(BY_ID["Q3"], [], "No.")]

    table = markdown(steps, {"model": "scripted", "prompt": "assistant-1"})

    assert "first step right on 1 of 2 sentences" in table
    assert "| O1 | no_tool | no_tool | yes |" in table


def test_the_runner_asks_once_a_sentence_and_writes_into_its_own_folder(tmp_path: Path) -> None:
    replies = [
        ToolReply(
            text="", calls=(ToolCall(name="get_positions", arguments={}),), record=scripted_record()
        )
    ] * len(SET.sentences)
    model = ScriptedModel(replies)
    backend = Backend(
        model=model,
        name="scripted",
        fingerprint="f",
        server_version="v",
        base_url="b",
        parameters={},
    )
    path = tmp_path / "run.jsonl"

    steps = tool_run.run("assistant-1", backend, tool_run.TOOL_SET, path)

    assert len(model.calls) == 19
    assert [step.right for step in steps].count(True) == 1
    lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert [line["id"] for line in lines] == [sentence.id for sentence in SET.sentences]
    assert tool_run.TOOL_RESULTS_DIR.name == "tool_results"
    assert "2026-11-24 (Tuesday) 23:55" in model.calls[0].items[0].content  # type: ignore[union-attr]


def test_the_runner_refuses_a_cloud_plug_without_its_address_before_anything_is_sent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LEDGER_HAND_MODEL_PLUG", "cloud")
    out = io.StringIO()

    assert tool_run.main([], out=out) == 2
    assert "LEDGER_HAND_MODEL_URL" in out.getvalue()
