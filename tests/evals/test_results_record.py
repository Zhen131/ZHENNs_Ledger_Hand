"""Gate: every committed run is finished, its saved summary is the one its file gives, and the
results record shows that summary's tables as they are worked out now.

The summary is worked out again from each results file alone (the gold
answers and the drafts its lines hold), so a number in the record that the
file does not give is caught here. No model is called.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evals.records import read_results
from evals.run import RESULTS_DIR
from evals.summarize import summary_path
from evals.tables import markdown, summarize

RECORD = RESULTS_DIR.parent / "RESULTS.md"
RUNS = sorted(RESULTS_DIR.glob("*.jsonl")) if RESULTS_DIR.is_dir() else []


@pytest.mark.parametrize("path", RUNS, ids=lambda path: path.name)
def test_a_committed_run_is_finished(path: Path) -> None:
    assert read_results(path).end is not None


@pytest.mark.parametrize("path", RUNS, ids=lambda path: path.name)
def test_the_saved_summary_is_the_one_the_results_file_gives(path: Path) -> None:
    saved = json.loads(summary_path(path).read_text(encoding="utf-8"))

    assert saved == json.loads(json.dumps(summarize(read_results(path)), ensure_ascii=False))


@pytest.mark.parametrize("path", RUNS, ids=lambda path: path.name)
def test_the_results_record_shows_the_tables_the_results_file_gives(path: Path) -> None:
    tables = markdown(summarize(read_results(path)))

    assert path.name in RECORD.read_text(encoding="utf-8")
    assert tables in RECORD.read_text(encoding="utf-8")
