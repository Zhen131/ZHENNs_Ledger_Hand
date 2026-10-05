"""Work out the summary of a results file again, from its sentence lines alone.

    .venv/bin/python -m evals.summarize evals/results/<file>.jsonl
    .venv/bin/python -m evals.summarize evals/results/<file>.jsonl --check

Every sentence is scored again from the gold answer and the drafts its line
holds, so the numbers never rest on what was worked out during the run. The
summary is printed as the tables of the results record. With ``--check``,
nothing is printed but whether the summary saved beside the file
(``<name>.summary.json``) is the one worked out now.

Exit status: 0 printed, or the saved summary matches; 1 it does not match;
2 the file cannot be read.

Names defined here: ``main`` and ``summary_path``.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from evals.records import read_results
from evals.tables import markdown, summarize


def summary_path(results_path: Path) -> Path:
    """Where the summary of the results file at ``results_path`` is saved."""
    return results_path.with_name(results_path.name.removesuffix(".jsonl") + ".summary.json")


def main(arguments: Sequence[str], *, out: TextIO = sys.stdout) -> int:
    """Run the script."""
    parser = argparse.ArgumentParser(prog="python -m evals.summarize", description=__doc__)
    parser.add_argument("results", type=Path)
    parser.add_argument("--check", action="store_true", help="compare with the saved summary")
    options = parser.parse_args(arguments)
    try:
        summary = summarize(read_results(options.results))
    except (OSError, ValueError) as error:
        print(f"cannot read {options.results}: {error}", file=out)
        return 2
    if not options.check:
        print(markdown(summary), file=out)
        return 0
    saved = json.loads(summary_path(options.results).read_text(encoding="utf-8"))
    same = saved == json.loads(json.dumps(summary, ensure_ascii=False))
    print("the saved summary matches" if same else "the saved summary differs", file=out)
    return 0 if same else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="backslashreplace")  # type: ignore[union-attr]
    sys.exit(main(sys.argv[1:]))
