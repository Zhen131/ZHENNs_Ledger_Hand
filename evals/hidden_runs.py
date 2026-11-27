"""The log of every run of a hidden half: one line a run, only ever added to.

Each time a measure runs a set whose file says it is a hidden half, it
adds one line here (``log_hidden_run``): when, at which commit, the set
file, the extraction and system prompt versions, the results file, and the
totals alone. Nothing in the log is changed or taken out, so it shows how
many times the hidden half was looked at, and with what. A test sees that
every results file of a hidden half has its line, and every line its file.

Names defined here: ``HIDDEN_LOG``, ``log_hidden_run`` and ``logged_results``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

from evals.tool_run import REPO_ROOT, TOOL_RESULTS_DIR, _git

HIDDEN_LOG = TOOL_RESULTS_DIR / "hidden-runs.log"


def log_hidden_run(
    set_file: Path,
    results: Path,
    totals: Mapping[str, object],
    *,
    extraction_prompt: str | None,
    prompt: str,
    log: Path = HIDDEN_LOG,
) -> None:
    """Add the line of one run of a hidden half to ``log``."""
    line = {
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "commit": _git("rev-parse", "HEAD"),
        "set_file": set_file.resolve().relative_to(REPO_ROOT).as_posix(),
        "extraction_prompt": extraction_prompt,
        "prompt": prompt,
        "results": results.name,
        "totals": dict(totals),
    }
    with log.open("a", encoding="utf-8", newline="\n") as out:
        out.write(json.dumps(line, ensure_ascii=False) + "\n")


def logged_results(log: Path = HIDDEN_LOG) -> list[str]:
    """The results file named by each line of ``log``, in order; none when there is no log."""
    if not log.exists():
        return []
    return [
        str(json.loads(line)["results"])
        for line in log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
