"""Tests of comparing two runs sentence by sentence, on results files written by hand."""

from __future__ import annotations

import io
from pathlib import Path

from evals import same_replies
from evals.gold import DEBUG_SET, Split, load_set, trade_to_json
from evals.records import append_line, draft_to_json, read_results
from tests.evals.builders import draft

SENTENCES = {s.id: s for s in load_set(DEBUG_SET, Split.DEBUG)}


def results(tmp_path: Path, name: str, lines: list[tuple[str, str, str | None]]) -> Path:
    """A results file; each line: sentence id, the raw reply, and the draft's side."""
    path = tmp_path / name
    append_line(path, {"record": "run", "set": "debug", "prompt": "first"})
    for sentence_id, reply, side in lines:
        sentence = SENTENCES[sentence_id]
        drafts = [] if side is None else [draft_to_json(draft(sentence.text, side=side))]
        append_line(
            path,
            {
                "record": "sentence",
                "id": sentence.id,
                "text": sentence.text,
                "now": sentence.now.isoformat(),
                "zone": sentence.zone,
                "language": sentence.language.value,
                "group": sentence.group.value,
                "kind": None,
                "features": [],
                "gold": [trade_to_json(trade) for trade in sentence.trades],
                "result": "extracted",
                "replies": [reply],
                "drafts": drafts,
                "copied": [{} for _ in drafts],
                "issues": [],
                "seconds": 1.0,
            },
        )
    append_line(path, {"record": "end", "finished_at": "x", "seconds_this_session": 1.0})
    return path


def test_same_replies_other_replies_and_other_drafts_are_told_apart(tmp_path: Path) -> None:
    earlier = results(
        tmp_path, "a.jsonl", [("d01", "r1", "buy"), ("d02", "r2", "sell"), ("d24", "r3", None)]
    )
    later = results(
        tmp_path, "b.jsonl", [("d01", "r1", "buy"), ("d02", "r2", "buy"), ("d24", "other", None)]
    )

    compared = same_replies.compare_runs(read_results(earlier), read_results(later))

    assert (compared["sentences"], compared["same_replies"], compared["different_replies"]) == (
        3,
        2,
        1,
    )
    assert compared["same_replies_other_drafts"] == 1
    rows = compared["differences"]
    assert isinstance(rows, list)
    assert [(row["id"], row["same_replies"], row["same_drafts_and_issues"]) for row in rows] == [
        ("d02", True, False),
        ("d24", False, True),
    ]


def test_the_table_and_the_script(tmp_path: Path) -> None:
    earlier = results(tmp_path, "a.jsonl", [("d24", "r", None)])
    later = results(tmp_path, "b.jsonl", [("d24", "r", None)])
    out = io.StringIO()

    assert same_replies.main([str(earlier), str(later)], out=out) == 0
    assert "| 1 | 1 | 0 | 0 |" in out.getvalue()
    assert same_replies.main([str(earlier), str(tmp_path / "none")], out=io.StringIO()) == 2
