"""Two runs sentence by sentence: did the model write the same replies, and did the program
make the same drafts of them?

Two runs of one prompt version can differ in two places: the model's raw
replies, and what the program made of the same replies when its code has
changed between the runs. This keeps the two apart. For every sentence the
two runs share, it tells whether the raw replies are the same, and whether
the drafts and the issues are; and it lists every sentence where either
differs, with the whole trades right in each run.

    .venv/bin/python -m evals.same_replies evals/results/<earlier>.jsonl evals/results/<later>.jsonl

Names defined here: ``compare_runs``, ``compare_markdown`` and ``main``.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TextIO

from evals.records import Results, read_results
from evals.tables import rescore


def _whole_right(results: Results) -> dict[str, int]:
    return {sentence.id: score.whole_right for sentence, _, score in rescore(results)}


def compare_runs(earlier: Results, later: Results) -> dict[str, object]:
    """The sentences of two runs compared: same replies or not, same drafts or not."""
    before = {str(line["id"]): line for line in earlier.sentences}
    after = {str(line["id"]): line for line in later.sentences}
    shared = [name for name in before if name in after]
    right_before, right_after = _whole_right(earlier), _whole_right(later)
    rows: list[dict[str, object]] = []
    same_replies = 0
    for name in shared:
        replies = before[name].get("replies") == after[name].get("replies")
        made = (before[name].get("drafts"), before[name].get("issues")) == (
            after[name].get("drafts"),
            after[name].get("issues"),
        )
        same_replies += replies
        if not (replies and made):
            rows.append(
                {
                    "id": name,
                    "same_replies": replies,
                    "same_drafts_and_issues": made,
                    "whole_right_earlier": right_before.get(name),
                    "whole_right_later": right_after.get(name),
                    "replies_earlier": before[name].get("replies"),
                    "replies_later": after[name].get("replies"),
                }
            )
    return {
        "sentences": len(shared),
        "same_replies": same_replies,
        "different_replies": len(shared) - same_replies,
        "same_replies_other_drafts": sum(
            1 for row in rows if row["same_replies"] and not row["same_drafts_and_issues"]
        ),
        "differences": rows,
    }


def _yes(flag: object) -> str:
    return "yes" if flag else "no"


def compare_markdown(compared: Mapping[str, object]) -> str:
    """The comparison as the lines of the results record."""
    rows = compared["differences"]
    assert isinstance(rows, list)
    lines = [
        "| Sentences in both runs | Same raw replies | Other raw replies "
        "| Same raw replies, other drafts or issues |",
        "| --- | --- | --- | --- |",
        f"| {compared['sentences']} | {compared['same_replies']} "
        f"| {compared['different_replies']} | {compared['same_replies_other_drafts']} |",
        "",
        "| Sentence | Same raw replies | Same drafts and issues "
        "| Whole trades right, earlier | Whole trades right, later |",
        "| --- | --- | --- | --- | --- |",
    ]
    lines += [
        f"| {row['id']} | {_yes(row['same_replies'])} | {_yes(row['same_drafts_and_issues'])} "
        f"| {row['whole_right_earlier']} | {row['whole_right_later']} |"
        for row in rows
    ]
    return "\n".join(lines) + "\n"


def main(arguments: Sequence[str], *, out: TextIO = sys.stdout) -> int:
    """Print the comparison of two results files; 2 when one cannot be read."""
    parser = argparse.ArgumentParser(prog="python -m evals.same_replies", description=__doc__)
    parser.add_argument("earlier", type=Path)
    parser.add_argument("later", type=Path)
    options = parser.parse_args(arguments)
    try:
        compared = compare_runs(read_results(options.earlier), read_results(options.later))
    except (OSError, ValueError) as error:
        print(f"cannot read: {error}", file=out)
        return 2
    print(compare_markdown(compared), file=out)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="backslashreplace")  # type: ignore[union-attr]
    sys.exit(main(sys.argv[1:]))
