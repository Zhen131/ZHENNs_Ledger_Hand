"""Prompt versions side by side: one row per run, and the version the fixed rule picks.

Every number of a row is worked out again from the run's results file: the
scores from its summary (``tables``), the three more counts
(``extra_counts``), and from its lines how many sentences had a reply cut
off at the longest reply, how many calls were made, and the seconds the
sentences took between them.

The rule that picks the best version was fixed before any version was
measured. It looks at runs of the debug set only, one per version:

1. the most whole trades right;
2. then the fewest wrong values with no issue about them: the fields that
   are wrong with no issue, and the made-up ones with no issue (the list
   "Wrong values in drafts with no issue about them" of the summary);
3. then the fewest trades missed and extra, added up;
4. then the first in this order: ``first``, ``price_total``, ``persona``,
   ``zero_shot``, ``stepwise``, and any later version in the order given.

So a new version is picked only when it does strictly better than
``first``. Runs that change a parameter are compared apart, not by the rule.

The writings set gets the same rows, and also, for each way of writing a
number, the whole trades right among the sentences that show it.

    .venv/bin/python -m evals.compare evals/results/<file>.jsonl ... [--choose]

Names defined here: ``Row``, ``row_of``, ``rows_markdown``, ``choose``,
``Choice``, ``choice_markdown``, ``writing_scores``, ``writing_markdown``,
``TECHNIQUES``, ``TIE_ORDER`` and ``main``.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import TextIO

from evals.extra_counts import extra_counts
from evals.gold import Group, Split
from evals.records import Results, read_results
from evals.tables import rescore, summarize
from evals.writings import Writing, writings_of

# Each version's technique, and the one thing it changes from ``first``.
TECHNIQUES: Mapping[str, tuple[str, str]] = {
    "first": ("few-shot", "the baseline: instructions and ten examples"),
    "zero_shot": ("zero-shot", "no example"),
    "persona": ("persona", "a role said before the instructions"),
    "stepwise": ("chain of thought", "a step-by-step analysis written before the table"),
    "price_total": ("content iteration", "one more rule: a total is never the price"),
}
TIE_ORDER: tuple[str, ...] = ("first", "price_total", "persona", "zero_shot", "stepwise")
_CUT_OFF = "length_limit"


@dataclass(frozen=True)
class Row:
    """One run, as the comparison shows it."""

    prompt: str
    set: str
    results_file: str
    sentences: int
    well_formed: int
    gold_trades: int
    whole_right: int
    one_trade: tuple[int, int]
    several_trades: tuple[int, int]
    missed: int
    extra: int
    made_up: tuple[int, int]
    no_trade: tuple[int, int]
    silent_wrong: int
    total_as_price: int
    half_copies_any: int
    half_copies_not_right: int
    time_in_another_language: int
    cut_off_sentences: int
    calls: int
    seconds: float


def _group(summary: Mapping[str, object], name: str) -> Mapping[str, int]:
    groups = summary["groups"]
    assert isinstance(groups, dict)
    group = groups[name]
    assert isinstance(group, dict)
    return group


def _calls(results: Results) -> tuple[int, int]:
    calls = cut = 0
    for line in results.sentences:
        made = line.get("calls") or []
        assert isinstance(made, list)
        calls += len(made)
        cut += any(call.get("finish") == _CUT_OFF for call in made)
    return calls, cut


def row_of(results: Results, results_file: str) -> Row:
    """The row of the run ``results`` records, read from ``results_file``."""
    summary = summarize(results)
    counts = extra_counts(results)
    everything = _group(summary, "all scored sentences")
    one = _group(summary, "one trade")
    several = _group(summary, "several trades")
    talk = _group(summary, "no trade (talk)")
    silent = summary["wrong_values_with_no_issue"]
    total_as_price = counts["total_as_price"]
    half_any = counts["half_copies_any"]
    moved = counts["time_in_another_language"]
    assert isinstance(silent, list) and isinstance(total_as_price, list)
    assert isinstance(half_any, list) and isinstance(moved, list)
    calls, cut = _calls(results)
    seconds = sum(float(str(line.get("seconds", 0))) for line in results.sentences)
    return Row(
        prompt=str(results.run.get("prompt")),
        set=str(results.run.get("set")),
        results_file=results_file,
        sentences=everything["sentences"],
        well_formed=everything["well_formed"],
        gold_trades=everything["gold_trades"],
        whole_right=everything["whole_right"],
        one_trade=(one["whole_right"], one["gold_trades"]),
        several_trades=(several["whole_right"], several["gold_trades"]),
        missed=everything["missed"],
        extra=everything["extra"],
        made_up=(everything["made_up_fields"], everything["gold_empty_fields"]),
        no_trade=(talk["no_trade_right"], talk["no_trade_sentences"]),
        silent_wrong=len(silent),
        total_as_price=len(total_as_price),
        half_copies_any=len(half_any),
        half_copies_not_right=int(str(counts["half_copies_not_right"])),
        time_in_another_language=len(moved),
        cut_off_sentences=cut,
        calls=calls,
        seconds=round(seconds, 1),
    )


def _ratio(part: int, whole: int) -> str:
    if whole == 0:
        return f"{part} / 0 (-)"
    return f"{part} / {whole} ({float(Fraction(100 * part, whole)):.1f}%)"


def _technique(prompt: str) -> tuple[str, str]:
    return TECHNIQUES.get(prompt, ("-", "-"))


def rows_markdown(rows: Sequence[Row]) -> str:
    """The rows as two Markdown tables: the scores, then the counts and the cost."""
    scores = [
        "| Version | Technique | Differs from `first` in | Well-formed | Whole trades right "
        "| One trade | Several trades | Missed | Extra | Made up | No-trade sentences right |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        technique, change = _technique(row.prompt)
        scores.append(
            f"| `{row.prompt}` | {technique} | {change} "
            f"| {_ratio(row.well_formed, row.sentences)} "
            f"| {_ratio(row.whole_right, row.gold_trades)} | {_ratio(*row.one_trade)} "
            f"| {_ratio(*row.several_trades)} | {row.missed} | {row.extra} "
            f"| {_ratio(*row.made_up)} | {_ratio(*row.no_trade)} |"
        )
    counts = [
        "| Version | Wrong values with no issue | A total put as the price "
        "| Half copies (any) | Half copies (not right) | A time in another language "
        "| Sentences with a reply cut off | Calls | Seconds | Results file |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        counts.append(
            f"| `{row.prompt}` | {row.silent_wrong} | {row.total_as_price} "
            f"| {row.half_copies_any} | {row.half_copies_not_right} "
            f"| {row.time_in_another_language} | {row.cut_off_sentences} | {row.calls} "
            f"| {row.seconds} | `{row.results_file}` |"
        )
    return "\n".join([*scores, "", *counts]) + "\n"


@dataclass(frozen=True)
class Choice:
    """The version the rule picks, the step it was settled at, and why."""

    prompt: str
    step: int
    steps: tuple[str, ...]


def _order(rows: Sequence[Row]) -> list[str]:
    known = [name for name in TIE_ORDER if any(row.prompt == name for row in rows)]
    later = [row.prompt for row in rows if row.prompt not in TIE_ORDER]
    return known + later


def choose(rows: Sequence[Row]) -> Choice:
    """The version the fixed rule picks among ``rows``, one run of the debug set per version."""
    if not rows:
        raise ValueError("no run to choose from")
    if any(row.set != Split.DEBUG.value for row in rows):
        raise ValueError("the rule looks at runs of the debug set only")
    names = [row.prompt for row in rows]
    if len(set(names)) != len(names):
        raise ValueError("one run per version")
    tests = (
        ("most whole trades right", lambda row: -row.whole_right),
        ("fewest wrong values with no issue", lambda row: row.silent_wrong),
        ("fewest trades missed and extra", lambda row: row.missed + row.extra),
    )
    left = list(rows)
    said: list[str] = []
    for step, (name, key) in enumerate(tests, start=1):
        best = min(key(row) for row in left)
        left = [row for row in left if key(row) == best]
        kept = ", ".join(f"`{row.prompt}`" for row in left)
        said.append(f"Step {step}, {name}: {kept}.")
        if len(left) == 1:
            return Choice(left[0].prompt, step, tuple(said))
    order = _order(rows)
    first = min(left, key=lambda row: order.index(row.prompt))
    said.append(f"Step 4, the fixed order: `{first.prompt}`.")
    return Choice(first.prompt, 4, tuple(said))


def choice_markdown(choice: Choice) -> str:
    """The choice as the lines of the results record."""
    lines = [f"Picked by the rule: `{choice.prompt}`, settled at step {choice.step}.", ""]
    lines += [f"- {said}" for said in choice.steps]
    return "\n".join(lines) + "\n"


def writing_scores(results: Results) -> dict[Writing, tuple[int, int]]:
    """For each way of writing a number: whole trades right, and gold trades, of its sentences."""
    scores = {writing: (0, 0) for writing in Writing}
    for sentence, _, score in rescore(results):
        if sentence.group is not Group.SCORED:
            continue
        for writing in writings_of(sentence):
            right, trades = scores[writing]
            scores[writing] = (right + score.whole_right, trades + score.gold_trades)
    return scores


def writing_markdown(runs: Sequence[tuple[str, Results]]) -> str:
    """Whole trades right for each way of writing, one column per run."""
    head = "| Way of writing | " + " | ".join(f"`{prompt}`" for prompt, _ in runs) + " |"
    lines = [head, "| --- |" + " --- |" * len(runs)]
    columns = [writing_scores(results) for _, results in runs]
    for writing in Writing:
        cells = " | ".join(_ratio(*column[writing]) for column in columns)
        lines.append(f"| {writing.value} | {cells} |")
    return "\n".join(lines) + "\n"


def _relative(path: Path) -> str:
    parts = path.resolve().parts
    return "/".join(parts[parts.index("evals") :]) if "evals" in parts else path.name


def main(arguments: Sequence[str], *, out: TextIO = sys.stdout) -> int:
    """Print the rows of the runs named; with ``--choose``, the version the rule picks."""
    parser = argparse.ArgumentParser(prog="python -m evals.compare", description=__doc__)
    parser.add_argument("results", type=Path, nargs="+")
    parser.add_argument("--choose", action="store_true", help="apply the rule to the runs")
    options = parser.parse_args(arguments)
    try:
        runs = [(path, read_results(path)) for path in options.results]
    except (OSError, ValueError) as error:
        print(f"cannot read: {error}", file=out)
        return 2
    rows = [row_of(results, _relative(path)) for path, results in runs]
    print(rows_markdown(rows), file=out)
    if options.choose:
        try:
            print(choice_markdown(choose(rows)), file=out)
        except ValueError as error:
            print(f"cannot choose: {error}", file=out)
            return 2
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="backslashreplace")  # type: ignore[union-attr]
    sys.exit(main(sys.argv[1:]))
