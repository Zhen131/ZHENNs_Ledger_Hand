"""Tests of the side-by-side comparison and of the fixed rule that picks a version.

The rule is tried on rows made by hand, one step at a time; a row is also
worked out from a results file written by hand. No model is called.
"""

from __future__ import annotations

import dataclasses
import io
from pathlib import Path

import pytest

from evals import compare
from evals.compare import Row, choose
from evals.gold import DEBUG_SET, Split, load_set, trade_to_json
from evals.records import append_line, draft_to_json, read_results
from evals.writings import Writing
from tests.evals.builders import draft

BASE = Row(
    prompt="first",
    set="debug",
    results_file="evals/results/x.jsonl",
    sentences=26,
    well_formed=26,
    gold_trades=34,
    whole_right=29,
    one_trade=(13, 15),
    several_trades=(16, 19),
    missed=0,
    extra=0,
    made_up=(2, 140),
    no_trade=(3, 3),
    silent_wrong=2,
    total_as_price=2,
    half_copies_any=0,
    half_copies_not_right=0,
    time_in_another_language=2,
    cut_off_sentences=0,
    calls=30,
    seconds=123.7,
)


def row(prompt: str, **changes: object) -> Row:
    return dataclasses.replace(BASE, prompt=prompt, **changes)  # type: ignore[arg-type]


def test_step_one_the_most_whole_trades_right() -> None:
    picked = choose([row("first"), row("persona", whole_right=30), row("stepwise")])

    assert (picked.prompt, picked.step) == ("persona", 1)


def test_step_two_the_fewest_wrong_values_with_no_issue() -> None:
    rows = [row("first", silent_wrong=2), row("price_total", silent_wrong=0), row("zero_shot")]

    picked = choose(rows)

    assert (picked.prompt, picked.step) == ("price_total", 2)
    assert picked.steps[0] == (
        "Step 1, most whole trades right: `first`, `price_total`, `zero_shot`."
    )


def test_step_three_the_fewest_missed_and_extra() -> None:
    rows = [row("first", missed=1), row("persona", extra=0, missed=0), row("zero_shot", extra=2)]

    picked = choose(rows)

    assert (picked.prompt, picked.step) == ("persona", 3)


def test_step_four_keeps_first_unless_a_version_does_strictly_better() -> None:
    rows = [row(name) for name in ("stepwise", "zero_shot", "persona", "price_total", "first")]

    assert (choose(rows).prompt, choose(rows).step) == ("first", 4)
    assert choose(rows[:4]).prompt == "price_total"
    assert choose(rows[:3]).prompt == "persona"
    assert choose(rows[:2]).prompt == "zero_shot"


def test_a_later_version_comes_last_in_the_fixed_order() -> None:
    assert choose([row("later"), row("stepwise")]).prompt == "stepwise"
    assert choose([row("later"), row("later_still")]).prompt == "later"


def test_the_rule_takes_one_debug_run_per_version() -> None:
    with pytest.raises(ValueError, match="debug set"):
        choose([row("first"), row("persona", set="writings")])
    with pytest.raises(ValueError, match="one run per version"):
        choose([row("first"), row("first")])
    with pytest.raises(ValueError, match="no run"):
        choose([])


def test_the_choice_is_written_with_every_step() -> None:
    text = compare.choice_markdown(choose([row("first"), row("persona", whole_right=30)]))

    assert text.startswith("Picked by the rule: `persona`, settled at step 1.")
    assert "- Step 1, most whole trades right: `persona`." in text


def test_the_tables_show_every_column_of_a_row() -> None:
    text = compare.rows_markdown([row("stepwise", cut_off_sentences=3, calls=34)])

    assert (
        "| `stepwise` | chain of thought | a step-by-step analysis written before the table "
        "| 26 / 26 (100.0%) | 29 / 34 (85.3%) | 13 / 15 (86.7%) | 16 / 19 (84.2%) | 0 | 0 "
        "| 2 / 140 (1.4%) | 3 / 3 (100.0%) |"
    ) in text
    assert "| `stepwise` | 2 | 2 | 0 | 0 | 2 | 3 | 34 | 123.7 | `evals/results/x.jsonl` |" in text


D07 = next(s for s in load_set(DEBUG_SET, Split.DEBUG) if s.id == "d07")


def results_with_calls(tmp_path: Path, finishes: list[str]) -> Path:
    path = tmp_path / "run.jsonl"
    append_line(path, {"record": "run", "set": "debug", "prompt": "stepwise"})
    made = draft(D07.text, side="buy")
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
            "calls": [{"finish": finish} for finish in finishes],
            "drafts": [draft_to_json(made)],
            "copied": [{}],
            "issues": [],
            "seconds": 2.25,
        },
    )
    append_line(path, {"record": "end", "finished_at": "x", "seconds_this_session": 2.3})
    return path


def test_a_row_counts_calls_and_the_sentences_with_a_reply_cut_off(tmp_path: Path) -> None:
    path = results_with_calls(tmp_path, ["length_limit", "stopped"])

    made = compare.row_of(read_results(path), "evals/results/run.jsonl")

    assert (made.prompt, made.set, made.calls, made.cut_off_sentences) == (
        "stepwise",
        "debug",
        2,
        1,
    )
    assert (made.whole_right, made.gold_trades, made.missed, made.seconds) == (0, 1, 0, 2.2)


def test_the_script_prints_the_rows_and_the_choice(tmp_path: Path) -> None:
    path = results_with_calls(tmp_path, ["stopped"])
    out = io.StringIO()

    assert compare.main([str(path), "--choose"], out=out) == 0
    assert "Picked by the rule: `stepwise`, settled at step 1." in out.getvalue()
    assert compare.main([str(tmp_path / "none.jsonl")], out=io.StringIO()) == 2


def test_each_way_of_writing_has_a_line_per_run(tmp_path: Path) -> None:
    results = read_results(results_with_calls(tmp_path, ["stopped"]))

    text = compare.writing_markdown([("first", results), ("stepwise", results)])

    assert text.splitlines()[0] == "| Way of writing | `first` | `stepwise` |"
    assert len(text.splitlines()) == 2 + len(Writing)
    assert compare.writing_scores(results) == {writing: (0, 0) for writing in Writing}
