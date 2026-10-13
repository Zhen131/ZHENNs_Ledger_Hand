"""Two models side by side on one set: the scores, what each sentence gave, and the cost.

Two runs are compared that differ only in the model: the same set and set
file, the same prompt version (the same content and reply table), the same
way of reading a passage and the same parameters. Every number is worked out
again from the two results files: the scores from the summary (``tables``),
the three more counts (``extra_counts``), and from the lines the calls, the
sentences with a reply cut off, the seconds, and what each sentence gave.

The comparison shows:

- the scores, one row per model, in the shape of the prompt comparison
  (``compare.row_of``), with the seconds per sentence (the seconds of the
  sentences added up, divided by the sentences), the first sentence's
  seconds and the longest sentence's, with the sentence it was;
- how many sentences gave each result (``extracted``, ``reply_unreadable``,
  ``model_failed``, ``passage_refused``), with the model failures sorted by
  kind and, among malformed replies, the empty replies apart. A reply cut off
  at the longest reply is counted only where the call's record says so: an
  empty reply is a failure, its call is not recorded, and it is not counted
  as cut off;
- each field, right of the pairs, for both models;
- the sentences where the two models differ in result, drafts, whole trades
  right or the fields not right; for the voice set, every sentence.

Two runs are refused, with what keeps them apart, when either did not finish
or ran only some sentences, when both are of the same model, or when they
differ in anything named in ``SAME_CONDITIONS`` or in a parameter. One
parameter may be let through by name (``--parameter``), when a model was run
with that one setting changed; the comparison then says which, and its two
values.

    .venv/bin/python -m evals.compare_models <first>.jsonl <second>.jsonl [--parameter <name>]

Names defined here: ``SAME_CONDITIONS``, ``check_comparable``,
``comparison_markdown`` and ``main``.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping, Sequence
from fractions import Fraction
from pathlib import Path
from typing import TextIO

from evals.compare import Row, row_of
from evals.gold import Split
from evals.methods import method_of
from evals.records import Results, read_results
from evals.scoring import ResultKind
from evals.tables import summarize
from ledger_hand.extraction.reply_table import Field
from ledger_hand.ports import ModelErrorKind

# What two runs must share, besides the parameters, to be compared.
SAME_CONDITIONS = (
    "set",
    "set_sha256",
    "prompt",
    "prompt_content_sha256",
    "reply_table_sha256",
    "method",
    "split_prompt_content_sha256",
    "split_table_sha256",
)
_EMPTY_REPLY = "has an empty reply"
_DASH = "-"


def _model(results: Results) -> str:
    return str(results.run.get("model"))


def _condition(results: Results, key: str) -> object:
    # A run line without a method was made before there was a choice: one list.
    if key == "method":
        return method_of(results.run).value
    return results.run.get(key)


def _parameters(results: Results) -> Mapping[str, object]:
    parameters = results.run.get("parameters") or {}
    assert isinstance(parameters, dict)
    return parameters


def _differing_parameters(first: Results, second: Results) -> list[str]:
    one, other = _parameters(first), _parameters(second)
    return sorted(name for name in {*one, *other} if one.get(name) != other.get(name))


def _check_run(results: Results) -> None:
    if results.end is None:
        raise ValueError(f"the run of {_model(results)} has no end line: it did not finish")
    if "only" in results.run:
        raise ValueError(f"the run of {_model(results)} ran only some sentences")


def check_comparable(first: Results, second: Results, parameter: str | None = None) -> None:
    """Raise ``ValueError``, saying what, when the two runs cannot be compared.

    ``parameter`` names the one parameter the two runs may differ in.
    """
    for results in (first, second):
        _check_run(results)
    if _model(first) == _model(second):
        raise ValueError(f"both runs are of the model {_model(first)}")
    for key in SAME_CONDITIONS:
        one, other = _condition(first, key), _condition(second, key)
        if one != other:
            raise ValueError(f"the two runs differ in {key}: {one} and {other}")
    differing = _differing_parameters(first, second)
    if parameter is not None and differing != [parameter]:
        raise ValueError(
            f"the parameter {parameter} was to be the only one that differs; "
            f"the parameters that differ are: {', '.join(differing) or 'none'}"
        )
    if parameter is None and differing:
        raise ValueError(f"the two runs differ in the parameters {', '.join(differing)}")
    ids = [sorted(str(line["id"]) for line in r.sentences) for r in (first, second)]
    if ids[0] != ids[1]:
        raise ValueError("the two runs hold different sentences")


def _ratio(part: int, whole: int) -> str:
    if whole == 0:
        return f"{part} / 0 (-)"
    return f"{part} / {whole} ({float(Fraction(100 * part, whole)):.1f}%)"


def _conditions_line(first: Results, second: Results, parameter: str | None) -> str:
    if parameter is None:
        return (
            "The two runs share the set, the prompt, the way of reading a passage and every "
            f"parameter; only the model differs: `{_model(first)}` and `{_model(second)}`."
        )
    one, other = _parameters(first).get(parameter), _parameters(second).get(parameter)
    return (
        "The two runs share the set, the prompt and the way of reading a passage; besides "
        f"the model, one parameter differs: {parameter}, {one} for `{_model(first)}` and "
        f"{other} for `{_model(second)}`."
    )


def _scores_table(runs: Sequence[tuple[Results, Row]]) -> list[str]:
    lines = [
        "| Model | Well-formed | Whole trades right | One trade | Several trades | Missed "
        "| Extra | Made up | No-trade sentences right |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for results, row in runs:
        lines.append(
            f"| `{_model(results)}` | {_ratio(row.well_formed, row.sentences)} "
            f"| {_ratio(row.whole_right, row.gold_trades)} | {_ratio(*row.one_trade)} "
            f"| {_ratio(*row.several_trades)} | {row.missed} | {row.extra} "
            f"| {_ratio(*row.made_up)} | {_ratio(*row.no_trade)} |"
        )
    return lines


def _longest(results: Results, seconds: object) -> str:
    found = next(
        (line["id"] for line in results.sentences if line.get("seconds") == seconds), _DASH
    )
    return f"{seconds} ({found})"


def _cost_table(runs: Sequence[tuple[Results, Row]]) -> list[str]:
    lines = [
        "| Model | Wrong values with no issue | A total put as the price | Half copies (any) "
        "| Half copies (not right) | A time in another language "
        "| Sentences with a reply cut off | Calls | Sentences | Seconds | Seconds per sentence "
        "| First sentence, seconds | Longest sentence, seconds | Results file |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for results, row in runs:
        timing = summarize(results)["timing"]
        assert isinstance(timing, dict)
        count = int(timing["sentences"])
        each = float(timing["sum_of_sentence_seconds"]) / count if count else 0.0
        lines.append(
            f"| `{_model(results)}` | {row.silent_wrong} | {row.total_as_price} "
            f"| {row.half_copies_any} | {row.half_copies_not_right} "
            f"| {row.time_in_another_language} | {row.cut_off_sentences} | {row.calls} "
            f"| {count} | {row.seconds} | {each:.2f} | {timing['first_sentence_seconds']} "
            f"| {_longest(results, timing['longest_sentence_seconds'])} "
            f"| `{row.results_file}` |"
        )
    return lines


def _result_counts(results: Results) -> dict[str, int]:
    counts = {"all sentences": len(results.sentences)}
    for kind in ResultKind:
        counts[kind.value] = 0
    for error in ModelErrorKind:
        counts[f"- {error.value}"] = 0
    counts["- malformed_reply, of them an empty reply"] = 0
    for line in results.sentences:
        counts[str(line["result"])] += 1
        failure = line.get("failure") or {}
        assert isinstance(failure, dict)
        if line["result"] != ResultKind.MODEL_FAILED.value:
            continue
        counts[f"- {failure.get('kind')}"] += 1
        if _EMPTY_REPLY in str(failure.get("message")):
            counts["- malformed_reply, of them an empty reply"] += 1
    return counts


def _results_table(first: Results, second: Results) -> list[str]:
    one, other = _result_counts(first), _result_counts(second)
    lines = [
        f"| Result | `{_model(first)}` | `{_model(second)}` |",
        "| --- | --- | --- |",
    ]
    order = ["all sentences", *(kind.value for kind in ResultKind)]
    failed = order.index(ResultKind.MODEL_FAILED.value) + 1
    order[failed:failed] = [
        *(f"- {error.value}" for error in ModelErrorKind),
        "- malformed_reply, of them an empty reply",
    ]
    lines += [f"| {name} | {one[name]} | {other[name]} |" for name in order]
    return lines


def _fields_table(first: Results, second: Results) -> list[str]:
    every = []
    for results in (first, second):
        groups = summarize(results)["groups"]
        assert isinstance(groups, dict)
        every.append(groups["all scored sentences"])
    lines = [
        f"| Field | `{_model(first)}`, right / pairs | `{_model(second)}`, right / pairs |",
        "| --- | --- | --- |",
    ]
    for field in Field:
        cells = [_ratio(int(g["field_right"][field.value]), int(g["pairs"])) for g in every]
        lines.append(f"| {field.value} | {cells[0]} | {cells[1]} |")
    return lines


def _per_sentence(results: Results) -> dict[str, tuple[str, str, str, str, str]]:
    """For each sentence: its group, result, drafts, whole trades right and fields not right."""
    summary = summarize(results)
    scored, apart = summary["sentences"], summary["not_to_record"]
    assert isinstance(scored, list) and isinstance(apart, list)
    rows: dict[str, tuple[str, str, str, str, str]] = {}
    for row in scored:
        wrong = ", ".join(row["wrong_fields"]) or _DASH
        shown = (str(row["result"]), str(row["drafts"]), str(row["whole_right"]), wrong)
        rows[str(row["id"])] = ("scored", *shown)
    for row in apart:
        shown = (str(row["result"]), str(row["drafts"]), _DASH, _DASH)
        rows[str(row["id"])] = ("not_to_record", *shown)
    return rows


def _sentences_table(first: Results, second: Results) -> list[str]:
    one, other = _per_sentence(first), _per_sentence(second)
    every = first.run.get("set") == Split.VOICE.value
    ids = [str(line["id"]) for line in first.sentences]
    shown = [name for name in ids if every or one[name] != other[name]]
    a, b = f"`{_model(first)}`", f"`{_model(second)}`"
    said = (
        "Every sentence"
        if every
        else (
            "The sentences where the two models differ in result, drafts, whole trades right or "
            "the fields not right"
        )
    )
    lines = [
        f"{said} ({len(shown)} of {len(ids)}):",
        "",
        f"| Sentence | Group | Result, {a} | Result, {b} | Drafts, {a} | Drafts, {b} "
        f"| Whole right, {a} | Whole right, {b} | Fields not right, {a} "
        f"| Fields not right, {b} |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for name in shown:
        group, *left = one[name]
        _, *right = other[name]
        cells = " | ".join(f"{x} | {y}" for x, y in zip(left, right, strict=True))
        lines.append(f"| {name} | {group} | {cells} |")
    return lines


def comparison_markdown(
    first: Results,
    second: Results,
    files: tuple[str, str],
    parameter: str | None = None,
) -> str:
    """The comparison of two runs of two models, as the lines of the results record.

    ``files`` names the two results files as the table shows them. Raises
    ``ValueError`` when the runs cannot be compared (``check_comparable``).
    """
    check_comparable(first, second, parameter)
    pairs = zip((first, second), files, strict=True)
    runs = [(results, row_of(results, name)) for results, name in pairs]
    parts = [
        _conditions_line(first, second, parameter),
        "",
        *_scores_table(runs),
        "",
        *_cost_table(runs),
        "",
        *_results_table(first, second),
        "",
        *_fields_table(first, second),
        "",
        *_sentences_table(first, second),
    ]
    return "\n".join(parts) + "\n"


def _relative(path: Path) -> str:
    parts = path.resolve().parts
    return "/".join(parts[parts.index("evals") :]) if "evals" in parts else path.name


def main(arguments: Sequence[str], *, out: TextIO = sys.stdout) -> int:
    """Print the comparison of two runs; 2 when one cannot be read or they cannot be compared."""
    parser = argparse.ArgumentParser(prog="python -m evals.compare_models", description=__doc__)
    parser.add_argument("first", type=Path)
    parser.add_argument("second", type=Path)
    parser.add_argument(
        "--parameter", default=None, help="the one parameter the two runs may differ in"
    )
    options = parser.parse_args(arguments)
    try:
        runs = [read_results(path) for path in (options.first, options.second)]
    except (OSError, ValueError) as error:
        print(f"cannot read: {error}", file=out)
        return 2
    files = (_relative(options.first), _relative(options.second))
    try:
        text = comparison_markdown(runs[0], runs[1], files, options.parameter)
    except ValueError as error:
        print(f"cannot compare: {error}", file=out)
        return 2
    print(text, file=out)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="backslashreplace")  # type: ignore[union-attr]
    sys.exit(main(sys.argv[1:]))
