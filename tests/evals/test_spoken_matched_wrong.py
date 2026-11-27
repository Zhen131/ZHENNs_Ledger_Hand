"""Tests of the spoken ruler's count of trades whose asset the program matched wrongly.

A trade whose asset the program matched by its table of company names, as
an asset that is not the gold one, counts once, marked or not; one
matched as the gold asset, or one the user named by its code, counts
nothing; the count is in the ``end`` line and printed after the counts.
A scripted model stands in; every sentence and figure is invented.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

import evals.spoken_run as spoken_run
from evals.spoken_run import matched_wrong, say_sentence
from tests.evals.test_spoken_run import (
    MSFT_ROW,
    WHEN,
    _msft,
    _said,
    model,
    one_set,
    ports,
)
from tests.flows.scripted_flow import row

APPLE_ROW = row(
    side="buy", coin="苹果", quantity="1股", price="400美元", total="400美元", time=WHEN
)


def test_a_name_matched_as_another_asset_than_the_gold_one_counts_once(tmp_path: Path) -> None:
    text = f"{WHEN}买入1股苹果，成交价400美元，总额400美元"
    spoken = one_set(tmp_path, text, [_msft(asset=_said("MSFT", "苹果"))])

    saids, _ = say_sentence(spoken.sentences[0], spoken, ports(model(text, [APPLE_ROW])))

    assert matched_wrong([said for _, said in saids], spoken.sentences[0]) == 1


def test_a_name_matched_as_the_gold_asset_or_a_code_said_counts_nothing(tmp_path: Path) -> None:
    text = f"{WHEN}买入1股苹果，成交价400美元，总额400美元"
    right = one_set(tmp_path, text, [_msft(asset=_said("AAPL", "苹果"))])
    coded = one_set(tmp_path, text, [_msft()])

    saids, _ = say_sentence(right.sentences[0], right, ports(model(text, [APPLE_ROW])))
    coded_saids, _ = say_sentence(coded.sentences[0], coded, ports(model(text, [MSFT_ROW])))

    assert matched_wrong([said for _, said in saids], right.sentences[0]) == 0
    assert matched_wrong([said for _, said in coded_saids], coded.sentences[0]) == 0


def test_the_count_is_in_the_end_line_and_printed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(spoken_run, "REPO_ROOT", tmp_path)
    text = f"{WHEN}买入1股苹果，成交价400美元，总额400美元"
    spoken = one_set(tmp_path, text, [_msft(asset=_said("MSFT", "苹果"))])
    results = tmp_path / "out.jsonl"
    results.write_text("", encoding="utf-8")
    rows = spoken_run.run(spoken, ports(model(text, [APPLE_ROW])), results, wait=lambda: None)
    out = io.StringIO()
    head = {"extraction_prompt": "first-3", "prompt": "assistant-5", "tier": "r70"}
    head["half"] = "practice"

    spoken_run.finish(rows, head, spoken, tmp_path / "spoken-r70-practice.json", results, out)

    end = json.loads(results.read_text("utf-8").splitlines()[-1])
    assert end["asset_matched_wrong"] == 1
    assert "asset matched by the program, not the gold one: 1" in out.getvalue()
