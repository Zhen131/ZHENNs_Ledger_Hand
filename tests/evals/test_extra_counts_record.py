"""Gate: the results record shows the three more counts of every run but the first two.

The two runs of the baseline came before these counts and their sections of
the record are never changed; every later run's section shows the tables of
the three counts exactly as its results file gives them. No model is called.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from evals.extra_counts import extra_counts, extra_markdown
from evals.records import read_results
from evals.run import RESULTS_DIR

RECORD = RESULTS_DIR.parent / "RESULTS.md"
# The baseline's two runs, recorded before the three counts were made.
BEFORE_THE_COUNTS = (
    "run-20261005T150041Z-debug-first.jsonl",
    "run-20261005T150537Z-debug-first.jsonl",
)
EVERY_RUN = sorted(RESULTS_DIR.glob("*.jsonl")) if RESULTS_DIR.is_dir() else []
LATER_RUNS = [path for path in EVERY_RUN if path.name not in BEFORE_THE_COUNTS]


def test_the_runs_before_the_counts_are_still_there() -> None:
    assert {path.name for path in EVERY_RUN} >= set(BEFORE_THE_COUNTS)


def sections_naming(path: Path) -> list[str]:
    """The sections of the record (under a heading of two or three marks) that name ``path``."""
    record = RECORD.read_text(encoding="utf-8")
    return [part for part in re.split(r"\n(?=#{2,3} )", record) if path.name in part]


@pytest.mark.parametrize("path", LATER_RUNS, ids=lambda path: path.name)
def test_the_record_shows_the_three_counts_the_results_file_gives(path: Path) -> None:
    tables = extra_markdown(extra_counts(read_results(path)))

    assert any(tables in section for section in sections_naming(path))


def test_a_section_is_found_by_the_file_it_names() -> None:
    baseline = sections_naming(RESULTS_DIR / BEFORE_THE_COUNTS[1])

    assert sections_naming(RESULTS_DIR / "run-not-made.jsonl") == []
    assert baseline
    assert all(part.startswith("## 2026-10-05: baseline") for part in baseline)
