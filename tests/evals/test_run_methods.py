"""Tests of the runner's two ways of reading a passage, with the scripted model standing in.

Only sentences of the debug set are run, and only through the scripted
model: its script plays the split's reply first and then one extraction
reply per segment. The record of every reply read (``reads``) must match
each draft with the phrases the model wrote for it, the split's call
included in the record.
"""

from __future__ import annotations

import io
import json
import re
from pathlib import Path

import pytest

from evals import run as runner
from evals.extra_counts import extra_counts
from evals.methods import Method, method_of
from evals.records import produced_from_line, read_results
from evals.tables import summarize
from ledger_hand.extraction.prompts.split import SPLIT_PROMPT
from ledger_hand.extraction.reply_table import Field
from tests.evals.test_run import (
    D01,
    NOTHING,
    RunCutShortError,
    StopAfterOne,
    backend,
    lines_of,
    run,
)
from tests.extraction.scripted_runs import row, table

SHA256 = re.compile(r"[0-9a-f]{64}")
D21_SHARED = ("今天在 Bitget", "每笔手续费 0.1U")
D21_OWN = ("卖了 50 个 LINK，13.6 一个", "买了 2 个 AVAX，26.1 一个", "又买了 100 个 OP，1.73 一个")
D21_SPLIT = json.dumps(
    {"trades": [{"pieces": [D21_SHARED[0], own, D21_SHARED[1]]} for own in D21_OWN]},
    ensure_ascii=False,
)


def d21_row(**cells: str) -> dict[str, str]:
    return row(platform="Bitget", fee="0.1U", time="今天", **cells)


D21_TABLES = (
    # The first segment's quantity is copied as half of the gold phrase.
    table(d21_row(side="sell", coin="LINK", quantity="50", price="13.6")),
    table(d21_row(side="buy", coin="AVAX", quantity="2 个 AVAX", price="26.1")),
    table(d21_row(side="buy", coin="OP", quantity="100 个 OP", price="1.73")),
)
ONE_TRADE_SPLIT = json.dumps({"trades": [{"pieces": []}]})


def test_the_run_line_records_the_way_of_reading_and_the_split_prompt(tmp_path: Path) -> None:
    status, _, path = run(
        ["--only", "d01", "--method", "split_first"], backend(ONE_TRADE_SPLIT, D01), tmp_path
    )

    assert status == 0 and path is not None
    assert path.name.endswith("-debug-first-split_first.jsonl")
    head = lines_of(path)[0]
    assert head["method"] == "split_first"
    assert head["split_prompt"] == SPLIT_PROMPT.name == "split-1"
    assert [f["path"] for f in head["split_prompt_files"]] == [  # type: ignore[union-attr]
        "src/ledger_hand/extraction/prompts/split.py"
    ]
    assert SHA256.fullmatch(str(head["split_prompt_content_sha256"]))
    assert SHA256.fullmatch(str(head["split_table_sha256"]))
    assert (head["prompt"], head["model"]) == ("first", "scripted")


def test_a_run_in_one_call_records_its_way_and_nothing_of_a_split(tmp_path: Path) -> None:
    _, _, path = run(["--only", "d01"], backend(D01), tmp_path)

    assert path is not None and path.name.endswith("-debug-first.jsonl")
    head, line, _ = lines_of(path)
    assert head["method"] == "one_list"
    assert not any(key.startswith("split") for key in head)
    assert "split" not in line
    assert line["reads"] == [
        {
            "call": 0,
            "step": "extract",
            "segment": None,
            "rows": line["copied"],
            "drafts": [0],
        }
    ]


def test_three_segments_each_match_their_own_draft_and_the_split_call_is_kept(
    tmp_path: Path,
) -> None:
    _, _, path = run(
        ["--only", "d21", "--method", "split_first"], backend(D21_SPLIT, *D21_TABLES), tmp_path
    )

    assert path is not None
    line = lines_of(path)[1]
    drafts, copied = line["drafts"], line["copied"]
    assert isinstance(drafts, list) and isinstance(copied, list)
    assert [d["coin"] for d in drafts] == ["LINK", "AVAX", "OP"]
    assert [c["coin"] for c in copied] == ["LINK", "AVAX", "OP"]
    assert [c["quantity"] for c in copied] == ["50", "2 个 AVAX", "100 个 OP"]
    assert len(line["calls"]) == len(line["replies"]) == 4  # type: ignore[arg-type]
    reads = line["reads"]
    assert isinstance(reads, list)
    assert [(r["step"], r["segment"], r.get("drafts")) for r in reads] == [
        ("split", None, None),
        ("extract", 0, [0]),
        ("extract", 1, [1]),
        ("extract", 2, [2]),
    ]
    assert line["split"] == {
        "route": "SEGMENTS",
        "fell_back": False,
        "trades_listed": 3,
        "segments": [
            "今天在 Bitget，卖了 50 个 LINK，13.6 一个，每笔手续费 0.1U",
            "今天在 Bitget，买了 2 个 AVAX，26.1 一个，每笔手续费 0.1U",
            "今天在 Bitget，又买了 100 个 OP，1.73 一个。每笔手续费 0.1U",
        ],
    }
    assert line["scores"]["whole_right"] == 3  # type: ignore[index]


def test_the_counts_take_each_drafts_own_phrases_from_the_record(tmp_path: Path) -> None:
    _, _, path = run(
        ["--only", "d21", "--method", "split_first"], backend(D21_SPLIT, *D21_TABLES), tmp_path
    )
    assert path is not None
    results = read_results(path)
    line = results.sentences[0]

    produced = produced_from_line(line)
    counts = extra_counts(results)

    assert [cells[Field.COIN] for cells in produced.copied] == ["LINK", "AVAX", "OP"]
    half = counts["half_copies_any"]
    assert isinstance(half, list) and len(half) == 1
    assert (half[0]["draft"], half[0]["field"], half[0]["copied"]) == (1, "quantity", "50")
    # Read from the last reply alone, the first draft would carry the third segment's phrases.
    last_only = json.loads(line["replies"][-1])["trades"][0]  # type: ignore[index]
    assert last_only["coin"] == "OP"


def test_a_passage_the_split_cannot_cut_is_read_whole_and_says_why(tmp_path: Path) -> None:
    glued = json.dumps({"trades": [{"pieces": ["Bitget 卖了 50 个 LINK"]}, {"pieces": ["x"]}]})

    _, _, path = run(["--only", "d01", "--method", "split_first"], backend(glued, D01), tmp_path)

    assert path is not None
    line = lines_of(path)[1]
    assert line["split"] == {
        "route": "PIECE_NOT_IN_PASSAGE",
        "fell_back": True,
        "trades_listed": 2,
        "segments": [],
    }
    assert line["scores"]["whole_right"] == 1  # type: ignore[index]
    assert [r["step"] for r in line["reads"]] == ["split", "extract"]  # type: ignore[union-attr]


def test_the_summary_of_a_run_that_splits_first_is_saved_and_checks(tmp_path: Path) -> None:
    _, _, path = run(
        ["--only", "d21", "d24", "--method", "split_first"],
        backend(D21_SPLIT, *D21_TABLES, '{"trades": []}', NOTHING),
        tmp_path,
    )
    assert path is not None

    saved = json.loads(Path(str(path).replace(".jsonl", ".summary.json")).read_text("utf-8"))

    assert saved == json.loads(json.dumps(summarize(read_results(path)), ensure_ascii=False))
    assert saved["groups"]["all scored sentences"]["whole_right"] == 3


@pytest.mark.parametrize(
    ("first", "then"), [("one_list", "split_first"), ("split_first", "one_list")]
)
def test_a_run_is_not_carried_on_in_the_other_way(first: str, then: str, tmp_path: Path) -> None:
    cut = runner.Backend(**{**backend().__dict__, "model": StopAfterOne()})
    with pytest.raises(RunCutShortError):
        run(["--only", "d24", "d25", "--method", first], cut, tmp_path)
    (path,) = tmp_path.glob("*.jsonl")

    status, shown, _ = run(
        ["--only", "d24", "d25", "--method", then, "--resume", str(path)],
        backend(NOTHING),
        tmp_path,
    )

    assert status == 2
    assert "method" in shown


def test_a_run_line_without_a_method_is_carried_on_only_in_one_call(tmp_path: Path) -> None:
    cut = runner.Backend(**{**backend().__dict__, "model": StopAfterOne()})
    with pytest.raises(RunCutShortError):
        run(["--only", "d01", "d24"], cut, tmp_path)
    (path,) = tmp_path.glob("*.jsonl")
    lines = path.read_text(encoding="utf-8").splitlines()
    head = json.loads(lines[0])
    del head["method"]
    path.write_text("\n".join([json.dumps(head, ensure_ascii=False), *lines[1:]]) + "\n", "utf-8")

    assert method_of(head) is Method.ONE_LIST
    refused, _, _ = run(
        ["--only", "d01", "d24", "--method", "split_first", "--resume", str(path)],
        backend(NOTHING),
        tmp_path,
    )
    carried, _, _ = run(["--only", "d01", "d24", "--resume", str(path)], backend(NOTHING), tmp_path)

    assert (refused, carried) == (2, 0)


def test_the_method_is_named_on_the_command_line() -> None:
    out = io.StringIO()

    with pytest.raises(SystemExit):
        runner.main(["--method", "other"], out=out, backend=lambda _: backend())
