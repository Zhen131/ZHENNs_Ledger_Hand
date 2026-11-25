"""Gate: the hidden-run log and the results files of the hidden halves name each other.

Every results file of a hidden half in ``evals/tool_results/`` has its line
in the log, and every line of the log names a results file that is there,
so a run of a hidden half cannot go unlogged, nor a line point at nothing.
Only file names are compared and printed; no model is called.
"""

from __future__ import annotations

import json

from evals.hidden_runs import HIDDEN_LOG, logged_results
from evals.tool_run import TOOL_RESULTS_DIR


def test_every_hidden_results_file_has_its_line_and_every_line_its_file() -> None:
    files = sorted(path.name for path in TOOL_RESULTS_DIR.glob("*hidden*.jsonl"))
    logged = logged_results()

    assert sorted(set(logged)) == files
    assert len(logged) == len(set(logged))


def test_every_line_of_the_log_is_whole() -> None:
    if not HIDDEN_LOG.exists():
        return
    for line in HIDDEN_LOG.read_text(encoding="utf-8").splitlines():
        entry = json.loads(line)
        assert set(entry) == {
            "at",
            "commit",
            "set_file",
            "extraction_prompt",
            "prompt",
            "results",
            "totals",
        }
