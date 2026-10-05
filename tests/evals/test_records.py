"""Tests of the results file: drafts and issues written as JSON and read back, lines cut off."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import pytest

from evals.records import (
    append_line,
    draft_from_json,
    draft_to_json,
    issue_from_json,
    issue_to_json,
    read_results,
)
from ledger_hand.core.numbers import Doubt
from ledger_hand.core.timeparse import Refusal, TimeCaution
from ledger_hand.extraction.issues import Issue, IssueKind
from ledger_hand.extraction.reply_table import Field
from tests.evals.builders import at_minute, draft, on_day


@pytest.mark.parametrize(
    "made",
    [
        draft(
            "原话",
            side="buy",
            coin="BTC",
            quantity="0.05",
            price="63480.10",
            total="3174.005",
            price_currency="U",
            fee="0",
            fee_currency="USDT",
            time=at_minute(datetime(2026, 10, 4, 20, 15)),
            platform="币安",
            opinion="不亏",
        ),
        draft(time=on_day(date(2026, 10, 4))),
        draft(),
    ],
)
def test_a_draft_reads_back_the_same(made: object) -> None:
    data = draft_to_json(made)  # type: ignore[arg-type]

    assert draft_from_json(json.loads(json.dumps(data))) == made


@pytest.mark.parametrize(
    "issue",
    [
        Issue(kind=IssueKind.NUMBER_UNSURE, draft=0, field=Field.PRICE, phrase="94 900",
              cause=Doubt.AMBIGUOUS_SEPARATOR),
        Issue(kind=IssueKind.TIME_REFUSED, draft=1, field=Field.TIME, cause=Refusal.AMBIGUOUS),
        Issue(kind=IssueKind.TIME_CAUTION, draft=0, field=Field.TIME,
              cause=TimeCaution.NO_HALF_OF_DAY),
        Issue(kind=IssueKind.TWO_TIMES, draft=0, field=Field.TIME,
              candidates=(on_day(date(2026, 10, 4)), on_day(date(2026, 10, 5)))),
        Issue(kind=IssueKind.NUMBERS_LEFT_OVER, numbers=("94", "两")),
        Issue(kind=IssueKind.SAME_AS_ANOTHER, draft=1, same_as=0),
    ],
)  # fmt: skip
def test_an_issue_reads_back_the_same(issue: Issue) -> None:
    data = issue_to_json(issue)

    assert issue_from_json(json.loads(json.dumps(data))) == issue


def test_a_last_line_cut_off_is_left_out(tmp_path: Path) -> None:
    path = tmp_path / "run.jsonl"
    append_line(path, {"record": "run", "set": "debug"})
    append_line(path, {"record": "sentence", "id": "d01"})
    complete = path.stat().st_size
    with path.open("ab") as stream:
        stream.write(b'{"record": "sentence", "id"')

    results = read_results(path)

    assert results.run["set"] == "debug"
    assert [line["id"] for line in results.sentences] == ["d01"]
    assert results.end is None
    assert results.complete_bytes == complete


def test_a_file_without_a_run_line_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "run.jsonl"
    append_line(path, {"record": "sentence", "id": "d01"})

    with pytest.raises(ValueError, match="run line"):
        read_results(path)
