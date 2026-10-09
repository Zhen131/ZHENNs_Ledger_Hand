"""Gate: the comparison of the first prompt experiment in the record is what its results files give.

The record shows, for the five versions on the debug set, the two tables of
the comparison and the version the fixed rule picks; the same tables for
the writings set, with whole trades right for each way of writing and the
set's coverage; the two parameter comparisons beside the runs they change
one parameter of; and the first prompt's run against the baseline, sentence
by sentence. Each is worked out again here from the results files alone and
must stand in the record exactly. No model is called.
"""

from __future__ import annotations

from pathlib import Path

from evals.compare import Row, choice_markdown, choose, row_of, rows_markdown, writing_markdown
from evals.gold import Split, load_set
from evals.records import read_results
from evals.run import RESULTS_DIR
from evals.same_replies import compare_markdown, compare_runs
from evals.writings import WRITINGS_SET, coverage_markdown

RECORD = RESULTS_DIR.parent / "RESULTS.md"
# The five runs the rule compares, one per version, in the order of the table.
MAIN = (
    "run-20261009T023225Z-debug-first.jsonl",
    "run-20261009T023459Z-debug-zero_shot.jsonl",
    "run-20261009T023708Z-debug-persona.jsonl",
    "run-20261009T023913Z-debug-stepwise.jsonl",
    "run-20261009T024223Z-debug-price_total.jsonl",
)
WRITINGS = (
    "run-20261009T024502Z-writings-first.jsonl",
    "run-20261009T024611Z-writings-zero_shot.jsonl",
    "run-20261009T024737Z-writings-persona.jsonl",
    "run-20261009T024858Z-writings-stepwise.jsonl",
    "run-20261009T025103Z-writings-price_total.jsonl",
)
# Each parameter comparison, after the main run it changes one parameter of.
PARAMETERS = (
    ("run-20261009T023225Z-debug-first.jsonl", "run-20261009T025243Z-debug-first.jsonl"),
    ("run-20261009T023913Z-debug-stepwise.jsonl", "run-20261009T025506Z-debug-stepwise.jsonl"),
)
BASELINE = "run-20261005T150537Z-debug-first.jsonl"


def rows(names: tuple[str, ...]) -> list[Row]:
    return [row_of(read_results(RESULTS_DIR / name), f"evals/results/{name}") for name in names]


def record() -> str:
    return RECORD.read_text(encoding="utf-8")


def test_the_five_versions_on_the_debug_set_and_the_pick() -> None:
    main = rows(MAIN)

    assert [row.prompt for row in main] == [
        "first",
        "zero_shot",
        "persona",
        "stepwise",
        "price_total",
    ]
    assert {row.set for row in main} == {Split.DEBUG.value}
    assert rows_markdown(main) in record()
    assert choice_markdown(choose(main)) in record()


def test_the_runs_compared_share_every_condition_but_the_prompt() -> None:
    heads = [read_results(RESULTS_DIR / name).run for name in MAIN + WRITINGS]
    shared = ("model", "model_fingerprint", "server_version", "parameters", "worktree_clean")

    for key in shared:
        assert len({repr(head[key]) for head in heads}) == 1, key
    assert all(head["worktree_clean"] is True for head in heads)


def test_the_writings_set() -> None:
    runs = [(name.split("-")[-1].removesuffix(".jsonl"), name) for name in WRITINGS]
    results = [(prompt, read_results(RESULTS_DIR / name)) for prompt, name in runs]

    assert rows_markdown(rows(WRITINGS)) in record()
    assert writing_markdown(results) in record()
    assert coverage_markdown(load_set(WRITINGS_SET, Split.WRITINGS)) in record()


def test_each_parameter_comparison_beside_the_run_it_changes() -> None:
    for pair in PARAMETERS:
        before, after = rows(pair)
        assert before.prompt == after.prompt
        assert rows_markdown([before, after]) in record()


def test_the_first_prompt_against_the_baseline() -> None:
    compared = compare_runs(
        read_results(RESULTS_DIR / BASELINE), read_results(RESULTS_DIR / MAIN[0])
    )

    assert compare_markdown(compared) in record()


def test_every_run_named_here_is_in_the_results_directory() -> None:
    named = {*MAIN, *WRITINGS, BASELINE, *(name for pair in PARAMETERS for name in pair)}

    assert all(Path(RESULTS_DIR / name).is_file() for name in named)
