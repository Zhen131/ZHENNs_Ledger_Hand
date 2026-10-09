"""Tests of the comparison of the two ways of reading a passage, and of the rule that picks one.

The rule is tried on rows made by hand, one step at a time; the tables are
worked out from two small runs made with the scripted model. No model is
called.
"""

from __future__ import annotations

import dataclasses
import io
import json
from pathlib import Path

import pytest

from evals import compare_methods
from evals.compare_methods import MethodRow, choose_method, method_row
from evals.methods import Method
from evals.records import read_results
from tests.evals.test_compare import BASE
from tests.evals.test_run import D01, backend, run
from tests.evals.test_run_methods import D21_SPLIT, D21_TABLES


def each(method: Method, **changes: object) -> MethodRow:
    return MethodRow(
        method=method,
        row=dataclasses.replace(BASE, **changes),  # type: ignore[arg-type]
        two_trades=(6, 6),
        three_or_more=(9, 9),
        split_calls=0 if method is Method.ONE_LIST else 30,
    )


def test_step_one_the_most_whole_trades_right() -> None:
    picked = choose_method(
        [each(Method.ONE_LIST), each(Method.SPLIT_FIRST, whole_right=BASE.whole_right + 1)]
    )

    assert (picked.method, picked.step) == (Method.SPLIT_FIRST, 1)


def test_step_two_the_fewest_wrong_values_with_no_issue() -> None:
    picked = choose_method(
        [each(Method.SPLIT_FIRST, silent_wrong=0), each(Method.ONE_LIST, silent_wrong=1)]
    )

    assert (picked.method, picked.step) == (Method.SPLIT_FIRST, 2)
    assert picked.steps[0] == "Step 1, most whole trades right: split first, one list."


def test_step_three_the_fewest_missed_and_extra() -> None:
    picked = choose_method(
        [each(Method.ONE_LIST, missed=1), each(Method.SPLIT_FIRST, missed=0, extra=0)]
    )

    assert (picked.method, picked.step) == (Method.SPLIT_FIRST, 3)


def test_a_tie_keeps_one_list_so_splitting_must_do_strictly_better() -> None:
    picked = choose_method([each(Method.SPLIT_FIRST), each(Method.ONE_LIST)])

    assert (picked.method, picked.step) == (Method.ONE_LIST, 4)
    assert picked.steps[-1] == "Step 4, a tie: one list."


def test_better_in_one_list_settles_at_the_first_step_it_differs() -> None:
    picked = choose_method(
        [each(Method.ONE_LIST), each(Method.SPLIT_FIRST, whole_right=1, silent_wrong=0)]
    )

    assert (picked.method, picked.step) == (Method.ONE_LIST, 1)


@pytest.mark.parametrize(
    "rows",
    [
        [each(Method.ONE_LIST)],
        [each(Method.ONE_LIST), each(Method.ONE_LIST)],
        [each(Method.ONE_LIST), each(Method.SPLIT_FIRST, set="writings")],
        [each(Method.ONE_LIST), each(Method.SPLIT_FIRST, prompt="persona")],
    ],
)
def test_the_rule_wants_one_debug_run_per_way_with_the_same_prompt(rows: list[MethodRow]) -> None:
    with pytest.raises(ValueError):
        choose_method(rows)


def two_runs(tmp_path: Path) -> tuple[Path, Path]:
    one = tmp_path / "one"
    split = tmp_path / "split"
    one_steps = (D01, json.dumps({"trades": []}))
    run(["--only", "d01", "d21"], backend(*one_steps), one)
    split_steps = (json.dumps({"trades": [{"pieces": []}]}), D01, D21_SPLIT, *D21_TABLES)
    run(["--only", "d01", "d21", "--method", "split_first"], backend(*split_steps), split)
    return next(one.glob("*.jsonl")), next(split.glob("*.jsonl"))


def test_the_rows_count_whole_trades_by_number_of_trades_and_the_calls_to_split(
    tmp_path: Path,
) -> None:
    one, split = two_runs(tmp_path)

    rows = [method_row(read_results(path), path.name) for path in (one, split)]

    assert [r.method for r in rows] == [Method.ONE_LIST, Method.SPLIT_FIRST]
    assert [r.row.whole_right for r in rows] == [1, 4]
    assert [r.three_or_more for r in rows] == [(0, 3), (3, 3)]
    assert [r.two_trades for r in rows] == [(0, 0), (0, 0)]
    assert [r.split_calls for r in rows] == [0, 2]
    assert [r.row.calls for r in rows] == [2, 6]
    text = compare_methods.method_markdown(rows)
    assert "| one list | 2 / 2 (100.0%) | 1 / 4 (25.0%) |" in text
    assert "| split first | 2 / 2 (100.0%) | 4 / 4 (100.0%) |" in text


def test_the_split_table_shows_each_sentence_and_both_scores(tmp_path: Path) -> None:
    one, split = two_runs(tmp_path)

    table = compare_methods.split_markdown(read_results(one), read_results(split))

    assert "| d01 | 1 | 1 | yes | 0 | WHOLE | 1 | 1 |" in table
    assert "| d21 | 3 | 3 | yes | 3 | SEGMENTS | 0 | 3 |" in table


def test_the_command_prints_the_tables_and_the_pick(tmp_path: Path) -> None:
    one, split = two_runs(tmp_path)
    out = io.StringIO()

    status = compare_methods.main([str(one), str(split), "--choose"], out=out)

    assert status == 0
    assert "Picked by the rule: split first, settled at step 1." in out.getvalue()


def test_the_command_says_when_it_cannot_read(tmp_path: Path) -> None:
    out = io.StringIO()

    assert compare_methods.main([str(tmp_path / "a"), str(tmp_path / "b")], out=out) == 2
    assert "cannot read" in out.getvalue()


def test_a_split_that_fell_back_over_a_piece_shows_the_first_piece_missed(tmp_path: Path) -> None:
    glued = json.dumps(
        {"trades": [{"pieces": ["今天在 Bitget"]}, {"pieces": ["Bitget 卖了 50 个 LINK"]}]},
        ensure_ascii=False,
    )
    steps = (glued, *D21_TABLES[:1], json.dumps({"trades": []}), *D21_TABLES[:1])
    run(["--only", "d16", "d21", "--method", "split_first"], backend(*steps), tmp_path)
    (path,) = tmp_path.glob("*.jsonl")

    table = compare_methods.missed_pieces_markdown(read_results(path))

    assert "| 今天在 Bitget | the phrase is not a piece of the passage |" in table
    assert table.count("\n| d") == 1


def test_a_piece_that_cuts_a_number_is_shown_with_its_reason(tmp_path: Path) -> None:
    cut = json.dumps({"trades": [{"pieces": ["13"]}, {"pieces": ["26.1"]}]})
    run(["--only", "d21", "--method", "split_first"], backend(cut, *D21_TABLES[:1]), tmp_path)
    (path,) = tmp_path.glob("*.jsonl")

    table = compare_methods.missed_pieces_markdown(read_results(path))

    assert "| 13 | the phrase is in the passage only as part of a longer number |" in table
