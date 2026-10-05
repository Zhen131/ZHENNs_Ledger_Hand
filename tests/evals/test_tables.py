"""Tests of the summary worked out from a results file written by hand (no model, no runner)."""

from __future__ import annotations

from pathlib import Path

from evals.gold import DEBUG_SET, Split, load_set, trade_to_json
from evals.records import append_line, draft_to_json, issue_to_json, read_results
from evals.tables import markdown, summarize
from ledger_hand.extraction.issues import Issue, IssueKind
from ledger_hand.extraction.reply_table import Field
from tests.evals.builders import draft

D07 = next(s for s in load_set(DEBUG_SET, Split.DEBUG) if s.id == "d07")


def results_file(tmp_path: Path, copied: dict[str, str], issues: list[Issue]) -> Path:
    path = tmp_path / "run.jsonl"
    append_line(path, {"record": "run", "set": "debug", "prompt": "first"})
    made = draft(D07.text, side="buy", coin="ETH", time=D07.trades[0].value(Field.TIME))
    append_line(
        path,
        {
            "record": "sentence",
            "id": D07.id,
            "text": D07.text,
            "now": D07.now.isoformat(),
            "zone": D07.zone,
            "language": D07.language.value,
            "group": D07.group.value,
            "kind": None,
            "features": [],
            "gold": [trade_to_json(trade) for trade in D07.trades],
            "result": "extracted",
            "drafts": [draft_to_json(made)],
            "copied": [copied],
            "issues": [issue_to_json(issue) for issue in issues],
            "seconds": 1.5,
        },
    )
    append_line(path, {"record": "end", "finished_at": "x", "seconds_this_session": 1.6})
    return path


def test_a_field_left_empty_though_the_model_copied_the_gold_phrase_is_marked(
    tmp_path: Path,
) -> None:
    cut = Issue(kind=IssueKind.CUTS_A_NUMBER, draft=0, field=Field.QUANTITY, phrase="1.2 个")
    path = results_file(tmp_path, {"coin": "ETH", "quantity": "1.2 个", "time": "前天"}, [cut])

    summary = summarize(read_results(path))

    assert summary["left_empty_by_the_program"] == [
        {
            "id": "d07",
            "draft": 1,
            "field": "quantity",
            "copied": "1.2 个",
            "gold_phrase": "1.2 个",
            "reason": "CUTS_A_NUMBER",
            "copied_the_gold_phrase": True,
        }
    ]
    assert "the model's phrase was exactly the gold phrase in 1" in markdown(summary)


def test_a_field_left_empty_after_another_phrase_is_not_marked(tmp_path: Path) -> None:
    wrong = Issue(kind=IssueKind.NOT_IN_PASSAGE, draft=0, field=Field.QUANTITY, phrase="1.2 ETH")
    path = results_file(tmp_path, {"coin": "ETH", "quantity": "1.2 ETH", "time": "前天"}, [wrong])

    rows = summarize(read_results(path))["left_empty_by_the_program"]

    assert isinstance(rows, list)
    assert [(row["reason"], row["copied_the_gold_phrase"]) for row in rows] == [
        ("NOT_IN_PASSAGE", False)
    ]


def test_the_timing_comes_from_the_sentence_lines_and_the_end(tmp_path: Path) -> None:
    path = results_file(tmp_path, {}, [])

    timing = summarize(read_results(path))["timing"]

    assert timing == {
        "sentences": 1,
        "sum_of_sentence_seconds": 1.5,
        "first_sentence_seconds": 1.5,
        "longest_sentence_seconds": 1.5,
        "finished_at": "x",
        "seconds_of_the_last_session": 1.6,
    }
