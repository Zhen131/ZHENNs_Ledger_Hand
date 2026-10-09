"""Gate: the comparison of the two ways of reading a passage in the record is what its files give.

The record shows, for the two runs of the debug set (one list, split
first), the two tables of the comparison, the way the fixed rule picks, how
each passage was split, the first piece missed where a split fell back, and
the one-list run against the first experiment's run of the same prompt.
Each is worked out again here from the results files alone and must stand
in the record exactly. The final set is run only when the rule picks split
first; when it picks one list, the one final-set run is still the first
experiment's. A second model is not measured, and the record says so. No
model is called.
"""

from __future__ import annotations

from evals.compare import row_of, rows_markdown
from evals.compare_methods import (
    MethodRow,
    choose_method,
    method_choice_markdown,
    method_markdown,
    method_row,
    missed_pieces_markdown,
    split_markdown,
)
from evals.methods import Method, method_of
from evals.records import read_results
from evals.run import RESULTS_DIR
from evals.same_replies import compare_markdown, compare_runs

RECORD = RESULTS_DIR.parent / "RESULTS.md"
ONE_LIST = "run-20261009T055241Z-debug-first.jsonl"
SPLIT_FIRST = "run-20261009T055442Z-debug-first-split_first.jsonl"
# The first experiment's run of the debug set and of the final set, with ``first``.
EARLIER = "run-20261009T023225Z-debug-first.jsonl"
EARLIER_FINAL = "run-20261009T030436Z-final-first.jsonl"


def record() -> str:
    return RECORD.read_text(encoding="utf-8")


def rows() -> list[MethodRow]:
    return [
        method_row(read_results(RESULTS_DIR / name), f"evals/results/{name}")
        for name in (ONE_LIST, SPLIT_FIRST)
    ]


def test_the_two_runs_read_each_way_once_with_the_same_prompt_model_and_commit() -> None:
    heads = [read_results(RESULTS_DIR / name).run for name in (ONE_LIST, SPLIT_FIRST)]

    assert [method_of(head) for head in heads] == [Method.ONE_LIST, Method.SPLIT_FIRST]
    shared = (
        "set",
        "set_sha256",
        "prompt",
        "prompt_content_sha256",
        "reply_table_sha256",
        "commit",
        "worktree_clean",
        "model",
        "model_fingerprint",
        "server_version",
        "parameters",
    )
    for key in shared:
        assert heads[0][key] == heads[1][key], key
    assert heads[0]["worktree_clean"] is True
    assert (heads[0]["set"], heads[0]["prompt"]) == ("debug", "first")


def test_the_comparison_and_the_pick() -> None:
    compared = rows()

    assert method_markdown(compared) in record()
    assert method_choice_markdown(choose_method(compared)) in record()


def test_how_each_passage_was_split_and_the_pieces_missed() -> None:
    one = read_results(RESULTS_DIR / ONE_LIST)
    split = read_results(RESULTS_DIR / SPLIT_FIRST)

    assert split_markdown(one, split) in record()
    assert missed_pieces_markdown(split) in record()


def test_the_one_list_run_against_the_first_experiments_run() -> None:
    compared = compare_runs(
        read_results(RESULTS_DIR / EARLIER), read_results(RESULTS_DIR / ONE_LIST)
    )

    assert compare_markdown(compared) in record()


def test_the_final_set_was_run_only_if_the_rule_picked_split_first() -> None:
    picked = choose_method(rows()).method
    finals = sorted(
        path.name
        for path in RESULTS_DIR.glob("*.jsonl")
        if read_results(path).run.get("set") == "final"
    )

    if picked is Method.ONE_LIST:
        assert finals == [EARLIER_FINAL]
        final = row_of(read_results(RESULTS_DIR / EARLIER_FINAL), f"evals/results/{EARLIER_FINAL}")
        assert rows_markdown([final]) in record()
        assert "### The final set\n\nNot run in this experiment." in record()
    else:
        later = [name for name in finals if name != EARLIER_FINAL]
        assert len(later) == 1
        assert method_of(read_results(RESULTS_DIR / later[0]).run) is Method.SPLIT_FIRST


def test_the_record_says_the_second_model_was_not_obtained() -> None:
    assert "### A second model\n\nNot obtained: this machine has one model" in record()
