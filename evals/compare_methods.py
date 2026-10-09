"""The two ways of reading a passage side by side, and the way a fixed rule picks.

The two ways (``methods``): the whole passage in one call, one list back
(``one_list``), and the passage split into one segment per trade first, each
extracted on its own (``split_first``). Every number here is worked out
again from the runs' results files: the scores from the summary
(``tables``), the three more counts (``extra_counts``), and from the lines
the calls (those made to split counted apart), the sentences with a reply
cut off, the seconds, and how each passage was split.

The rule was fixed before either way was measured, the same way as the
rule that picked the prompt version, on runs of the debug set with the
same prompt, model and parameters, one run per way:

1. the most whole trades right;
2. then the fewest wrong values with no issue about them (the fields that
   are wrong with no issue, and the made-up ones with no issue);
3. then the fewest trades missed and extra, added up;
4. then ``one_list``.

So splitting first is picked only when it does strictly better.

    .venv/bin/python -m evals.compare_methods <one_list file> <split_first file> [--choose]

Names defined here: ``MethodRow``, ``method_row``, ``method_markdown``,
``MethodChoice``, ``choose_method``, ``method_choice_markdown``,
``split_markdown`` and ``main``.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import TextIO

from evals.compare import Row, row_of
from evals.gold import Group, Split
from evals.methods import Method, method_of
from evals.records import Results, read_results
from evals.tables import rescore, summarize

_NAMES = {Method.ONE_LIST: "one list", Method.SPLIT_FIRST: "split first"}
_DASH = "-"


@dataclass(frozen=True)
class MethodRow:
    """One run, as the comparison of the two ways shows it."""

    method: Method
    row: Row
    two_trades: tuple[int, int]
    three_or_more: tuple[int, int]
    split_calls: int


def _pair(summary: Mapping[str, object], name: str) -> tuple[int, int]:
    groups = summary["groups"]
    assert isinstance(groups, dict)
    group = groups[name]
    return int(group["whole_right"]), int(group["gold_trades"])


def _split_calls(results: Results) -> int:
    count = 0
    for line in results.sentences:
        reads = line.get("reads") or []
        assert isinstance(reads, list)
        count += sum(entry.get("step") == "split" for entry in reads)
    return count


def method_row(results: Results, results_file: str) -> MethodRow:
    """The row of the run ``results`` records, read from ``results_file``."""
    summary = summarize(results)
    return MethodRow(
        method=method_of(results.run),
        row=row_of(results, results_file),
        two_trades=_pair(summary, "  two trades"),
        three_or_more=_pair(summary, "  three or more trades"),
        split_calls=_split_calls(results),
    )


def _ratio(part: int, whole: int) -> str:
    if whole == 0:
        return f"{part} / 0 (-)"
    return f"{part} / {whole} ({float(Fraction(100 * part, whole)):.1f}%)"


def method_markdown(rows: Sequence[MethodRow]) -> str:
    """The rows as two Markdown tables: the scores by number of trades, then counts and cost."""
    scores = [
        "| Way | Well-formed | Whole trades right | One trade | Two trades | Three or more "
        "| No-trade sentences right | Missed | Extra | Made up |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for each in rows:
        row = each.row
        scores.append(
            f"| {_NAMES[each.method]} | {_ratio(row.well_formed, row.sentences)} "
            f"| {_ratio(row.whole_right, row.gold_trades)} | {_ratio(*row.one_trade)} "
            f"| {_ratio(*each.two_trades)} | {_ratio(*each.three_or_more)} "
            f"| {_ratio(*row.no_trade)} | {row.missed} | {row.extra} | {_ratio(*row.made_up)} |"
        )
    counts = [
        "| Way | Wrong values with no issue | A total put as the price | Half copies (any) "
        "| Half copies (not right) | A time in another language "
        "| Sentences with a reply cut off | Calls | Calls to split | Seconds | Results file |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for each in rows:
        row = each.row
        counts.append(
            f"| {_NAMES[each.method]} | {row.silent_wrong} | {row.total_as_price} "
            f"| {row.half_copies_any} | {row.half_copies_not_right} "
            f"| {row.time_in_another_language} | {row.cut_off_sentences} | {row.calls} "
            f"| {each.split_calls} | {row.seconds} | `{row.results_file}` |"
        )
    return "\n".join([*scores, "", *counts]) + "\n"


@dataclass(frozen=True)
class MethodChoice:
    """The way the rule picks, the step it was settled at, and why."""

    method: Method
    step: int
    steps: tuple[str, ...]


def choose_method(rows: Sequence[MethodRow]) -> MethodChoice:
    """The way the fixed rule picks: one run of the debug set per way, same prompt."""
    if sorted(each.method.value for each in rows) != sorted(m.value for m in Method):
        raise ValueError("one run per way, and both ways")
    if any(each.row.set != Split.DEBUG.value for each in rows):
        raise ValueError("the rule looks at runs of the debug set only")
    if len({each.row.prompt for each in rows}) != 1:
        raise ValueError("both runs must use the same prompt version")
    tests = (
        ("most whole trades right", lambda each: -each.row.whole_right),
        ("fewest wrong values with no issue", lambda each: each.row.silent_wrong),
        ("fewest trades missed and extra", lambda each: each.row.missed + each.row.extra),
    )
    left = list(rows)
    said: list[str] = []
    for step, (name, key) in enumerate(tests, start=1):
        best = min(key(each) for each in left)
        left = [each for each in left if key(each) == best]
        kept = ", ".join(_NAMES[each.method] for each in left)
        said.append(f"Step {step}, {name}: {kept}.")
        if len(left) == 1:
            return MethodChoice(left[0].method, step, tuple(said))
    said.append(f"Step 4, a tie: {_NAMES[Method.ONE_LIST]}.")
    return MethodChoice(Method.ONE_LIST, 4, tuple(said))


def method_choice_markdown(choice: MethodChoice) -> str:
    """The choice as the lines of the results record."""
    lines = [f"Picked by the rule: {_NAMES[choice.method]}, settled at step {choice.step}.", ""]
    lines += [f"- {said}" for said in choice.steps]
    return "\n".join(lines) + "\n"


def _whole_right(results: Results) -> dict[str, int]:
    return {
        sentence.id: score.whole_right
        for sentence, _, score in rescore(results)
        if sentence.group is Group.SCORED
    }


def split_markdown(one_list: Results, split_first: Results) -> str:
    """For each sentence of a run that split first: how it was split, and both ways' scores."""
    before, after = _whole_right(one_list), _whole_right(split_first)
    lines = [
        "| Sentence | Gold trades | Trades the split listed | Same number as gold "
        "| Segments extracted | Route | Whole right, one list | Whole right, split first |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for line in split_first.sentences:
        split = line.get("split") or {}
        assert isinstance(split, dict)
        gold = line.get("gold") or []
        assert isinstance(gold, list)
        listed = split.get("trades_listed")
        same = _DASH if listed is None else ("yes" if listed == len(gold) else "no")
        segments = split.get("segments") or []
        extracted = len(segments) if split.get("route") == "SEGMENTS" else 0
        sid = str(line["id"])
        lines.append(
            f"| {sid} | {len(gold)} | {_DASH if listed is None else listed} | {same} "
            f"| {extracted} | {split.get('route', _DASH)} | {before.get(sid, _DASH)} "
            f"| {after.get(sid, _DASH)} |"
        )
    return "\n".join(lines) + "\n"


def _relative(path: Path) -> str:
    parts = path.resolve().parts
    return "/".join(parts[parts.index("evals") :]) if "evals" in parts else path.name


def main(arguments: Sequence[str], *, out: TextIO = sys.stdout) -> int:
    """Print the rows of the two runs, how the second split; with ``--choose``, the rule's pick."""
    parser = argparse.ArgumentParser(prog="python -m evals.compare_methods", description=__doc__)
    parser.add_argument("one_list", type=Path)
    parser.add_argument("split_first", type=Path)
    parser.add_argument("--choose", action="store_true", help="apply the rule to the two runs")
    options = parser.parse_args(arguments)
    try:
        runs = [(path, read_results(path)) for path in (options.one_list, options.split_first)]
    except (OSError, ValueError) as error:
        print(f"cannot read: {error}", file=out)
        return 2
    rows = [method_row(results, _relative(path)) for path, results in runs]
    print(method_markdown(rows), file=out)
    print(split_markdown(runs[0][1], runs[1][1]), file=out)
    if options.choose:
        try:
            print(method_choice_markdown(choose_method(rows)), file=out)
        except ValueError as error:
            print(f"cannot choose: {error}", file=out)
            return 2
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="backslashreplace")  # type: ignore[union-attr]
    sys.exit(main(sys.argv[1:]))
