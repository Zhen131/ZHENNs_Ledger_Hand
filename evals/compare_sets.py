"""Prompt versions side by side on each set, and the rule that picks a candidate over ``first``.

The runs compared are of one model, one way of reading a passage and one set
of parameters: on each set, a run of ``first`` and a run of each candidate
version. Every number is worked out again from the results files: the
scores from the summary (``tables``), the three more counts
(``extra_counts``), and from the lines the calls, the sentences with a reply
cut off, the seconds, and what each sentence gave.

The comparison of the runs of one set shows:

- the scores, one row per version, ``first`` first, in the shape of the
  prompt comparison (``compare.row_of``);
- the three more counts and the cost: the calls, the sentences, their
  seconds added up and per sentence (added up, divided by the sentences),
  the first sentence's seconds and the longest sentence's, with the
  sentence it was;
- each field, right of the pairs, for each version;
- sentence by sentence, for the voice set every sentence, and for the other
  sets every sentence not to record and the sentences where the versions
  differ in result, drafts, whole trades right or the fields not right: a
  sentence not to record shows its drafts and whether each passes the check
  of a draft, and a scored sentence a candidate gets fewer trades whole
  right in than ``first`` is marked.

Runs are refused, with what keeps them apart, when one did not finish or ran
only some sentences, when two are of the same version, when there is no run
of ``first``, when they hold different sentences, or when they differ in
anything named in ``SAME_CONDITIONS``: the set and its file, the model and
its fingerprint, the Ollama version, the way of reading a passage, the
parameters and the reply table. The version, the fingerprint of its content
and the commit may differ.

The rule that picks a candidate (``--choose``) was fixed before the first
run it judges. It looks at one run of ``first`` and one run of the
candidate on each of the debug set and the voice set, all of the same
experiment, and reads as follows (``RULE``, printed with the choice):

A candidate is picked when, and only when, all five of these hold, each
against the run of ``first`` made in the same experiment:

1. on the voice set, more whole trades right than ``first``;
2. on the debug set, no fewer whole trades right than ``first``;
3. on the debug set, no more wrong values with no issue about them than
   ``first`` (the list "Wrong values in drafts with no issue about them" of
   the summary, the made-up values with no issue included);
4. on the debug set, no more trades missed and extra, added up over all
   scored sentences, than ``first``;
5. on the voice set, no more wrong values with no issue about them than
   ``first``.

The writings set is shown beside the debug and the voice set, with the same
counts, and judged by none of the five. The seconds are shown only. A later
candidate is held to the same rule against ``first``, never against an
earlier candidate.

The final-set line, fixed with the rule and printed with its judgement by
``--final`` (``FINAL_LINE``), reads:

The final set is run once, with the candidate the rule picked, and only
then. Its run is compared with an earlier run of ``first`` on the final set,
of the same model with the same parameters, and passes when all three of
these hold:

1. no fewer whole trades right than ``first``;
2. no more trades missed and extra, added up over all scored sentences,
   than ``first``;
3. no more wrong values with no issue about them than ``first``.

    .venv/bin/python -m evals.compare_sets <run of first>.jsonl <run of a candidate>.jsonl ...
    .venv/bin/python -m evals.compare_sets --choose <run>.jsonl ...
    .venv/bin/python -m evals.compare_sets --final <earlier final run>.jsonl <final run>.jsonl

Names defined here: ``SAME_CONDITIONS``, ``RULE``, ``FINAL_LINE``,
``check_comparable``, ``sets_markdown``, ``Judged``, ``choose``,
``choice_markdown``, ``final_check``, ``final_markdown`` and ``main``.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import TextIO

from evals.compare import Row, row_of
from evals.gold import Split
from evals.methods import method_of
from evals.records import Results, read_results
from evals.tables import summarize
from ledger_hand.extraction.reply_table import Field

# What the runs must share to be compared.
SAME_CONDITIONS = (
    "set",
    "set_sha256",
    "model",
    "model_fingerprint",
    "server_version",
    "method",
    "split_prompt_content_sha256",
    "split_table_sha256",
    "parameters",
    "reply_table_sha256",
)
# The conditions that must be the same across the sets the rule looks at.
_SAME_ACROSS_SETS = tuple(name for name in SAME_CONDITIONS if name not in ("set", "set_sha256"))
BASELINE = "first"

RULE = """\
A candidate is picked when, and only when, all five of these hold, each
against the run of `first` made in the same experiment:

1. on the voice set, more whole trades right than `first`;
2. on the debug set, no fewer whole trades right than `first`;
3. on the debug set, no more wrong values with no issue about them than
   `first` (the list "Wrong values in drafts with no issue about them" of
   the summary, the made-up values with no issue included);
4. on the debug set, no more trades missed and extra, added up over all
   scored sentences, than `first`;
5. on the voice set, no more wrong values with no issue about them than
   `first`.

The writings set is shown beside the debug and the voice set, with the same
counts, and judged by none of the five. The seconds are shown only. A later
candidate is held to the same rule against `first`, never against an
earlier candidate.
"""

FINAL_LINE = """\
The final set is run once, with the candidate the rule picked, and only
then. Its run is compared with an earlier run of `first` on the final set,
of the same model with the same parameters, and passes when all three of
these hold:

1. no fewer whole trades right than `first`;
2. no more trades missed and extra, added up over all scored sentences,
   than `first`;
3. no more wrong values with no issue about them than `first`.
"""

_DASH = "-"
_APART = "not_to_record"


def _prompt(results: Results) -> str:
    return str(results.run.get("prompt"))


def _condition(results: Results, key: str) -> object:
    # A run line without a method was made before there was a choice: one list.
    if key == "method":
        return method_of(results.run).value
    return results.run.get(key)


def _check_run(results: Results) -> None:
    if results.end is None:
        raise ValueError(f"the run of `{_prompt(results)}` has no end line: it did not finish")
    if "only" in results.run:
        raise ValueError(f"the run of `{_prompt(results)}` ran only some sentences")


def _check_same(runs: Sequence[Results], keys: Sequence[str]) -> None:
    for key in keys:
        values = [_condition(results, key) for results in runs]
        if any(value != values[0] for value in values):
            shown = ", ".join(f"`{_prompt(r)}` {v}" for r, v in zip(runs, values, strict=True))
            raise ValueError(f"the runs differ in {key}: {shown}")


def check_comparable(runs: Sequence[Results]) -> None:
    """Raise ``ValueError``, saying what, when the runs of one set cannot be compared."""
    if len(runs) < 2:
        raise ValueError("two runs or more are compared")
    for results in runs:
        _check_run(results)
    names = [_prompt(results) for results in runs]
    if len(set(names)) != len(names):
        raise ValueError(f"two runs are of the same version: {', '.join(names)}")
    if BASELINE not in names:
        raise ValueError(f"no run is of `{BASELINE}`")
    _check_same(runs, SAME_CONDITIONS)
    ids = [sorted(str(line["id"]) for line in results.sentences) for results in runs]
    if any(each != ids[0] for each in ids):
        raise ValueError("the runs hold different sentences")


def _ordered(runs: Sequence[tuple[Results, str]]) -> list[tuple[Results, str]]:
    """The runs with ``first`` first, the others in the order given."""
    return sorted(runs, key=lambda pair: _prompt(pair[0]) != BASELINE)


def _ratio(part: int, whole: int) -> str:
    if whole == 0:
        return f"{part} / 0 (-)"
    return f"{part} / {whole} ({float(Fraction(100 * part, whole)):.1f}%)"


def _scores_table(rows: Sequence[Row]) -> list[str]:
    lines = [
        "| Version | Well-formed | Whole trades right | One trade | Several trades | Missed "
        "| Extra | Made up | No-trade sentences right |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| `{row.prompt}` | {_ratio(row.well_formed, row.sentences)} "
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
        "| Version | Wrong values with no issue | A total put as the price | Half copies (any) "
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
            f"| `{row.prompt}` | {row.silent_wrong} | {row.total_as_price} "
            f"| {row.half_copies_any} | {row.half_copies_not_right} "
            f"| {row.time_in_another_language} | {row.cut_off_sentences} | {row.calls} "
            f"| {count} | {row.seconds} | {each:.2f} | {timing['first_sentence_seconds']} "
            f"| {_longest(results, timing['longest_sentence_seconds'])} "
            f"| `{row.results_file}` |"
        )
    return lines


def _everything(results: Results) -> Mapping[str, object]:
    groups = summarize(results)["groups"]
    assert isinstance(groups, dict)
    group = groups["all scored sentences"]
    assert isinstance(group, dict)
    return group


def _fields_table(runs: Sequence[Results]) -> list[str]:
    every = [_everything(results) for results in runs]
    head = " | ".join(f"`{_prompt(results)}`, right / pairs" for results in runs)
    lines = [f"| Field | {head} |", "| --- |" + " --- |" * len(runs)]
    for field in Field:
        cells = []
        for group in every:
            right = group["field_right"]
            assert isinstance(right, dict)
            cells.append(_ratio(int(right[field.value]), int(str(group["pairs"]))))
        lines.append(f"| {field.value} | {' | '.join(cells)} |")
    return lines


@dataclass(frozen=True)
class _Said:
    """What one sentence gave in one run, as the sentence table shows it."""

    group: str
    result: str
    drafts: str
    whole_right: int | None
    wrong: str
    checks: str


def _checks(checks: object) -> str:
    assert isinstance(checks, list)
    passed = ["passes" if str(text).startswith("not stopped") else "stopped" for text in checks]
    return ", ".join(passed) or _DASH


def _per_sentence(results: Results) -> dict[str, _Said]:
    summary = summarize(results)
    scored, apart = summary["sentences"], summary["not_to_record"]
    assert isinstance(scored, list) and isinstance(apart, list)
    said: dict[str, _Said] = {}
    for row in scored:
        wrong = ", ".join(row["wrong_fields"]) or _DASH
        said[str(row["id"])] = _Said(
            "scored", str(row["result"]), str(row["drafts"]), int(row["whole_right"]), wrong, _DASH
        )
    for row in apart:
        said[str(row["id"])] = _Said(
            _APART,
            str(row["result"]),
            str(row["drafts"]),
            None,
            _DASH,
            _checks(row["checks"]),
        )
    return said


def _shown(said: _Said, field: str) -> str:
    value = getattr(said, field)
    return _DASH if value is None else str(value)


def _fewer(runs: Sequence[Results], every: Sequence[dict[str, _Said]], name: str) -> str:
    """The candidates that get fewer trades of a scored sentence whole right than ``first``."""
    base = every[0][name].whole_right
    if base is None:
        return _DASH
    fewer = []
    for results, said in zip(runs[1:], every[1:], strict=True):
        right = said[name].whole_right
        if right is not None and right < base:
            fewer.append(f"`{_prompt(results)}`")
    return ", ".join(fewer) or _DASH


_COLUMNS = (
    ("Result", "result"),
    ("Drafts", "drafts"),
    ("Whole right", "whole_right"),
    ("Fields not right", "wrong"),
    ("Checks of the drafts", "checks"),
)


def _sentences_table(runs: Sequence[Results]) -> list[str]:
    every = [_per_sentence(results) for results in runs]
    voice = runs[0].run.get("set") == Split.VOICE.value
    ids = [str(line["id"]) for line in runs[0].sentences]
    shown = [
        n
        for n in ids
        if voice or every[0][n].group == _APART or any(each[n] != every[0][n] for each in every[1:])
    ]
    said = (
        "Every sentence"
        if voice
        else (
            "The sentences where the versions differ in result, drafts, whole trades right or "
            "the fields not right, and every sentence not to record"
        )
    )
    names = [f"`{_prompt(results)}`" for results in runs]
    head = " | ".join(f"{title}, {name}" for title, _ in _COLUMNS for name in names)
    lines = [
        f"{said} ({len(shown)} of {len(ids)}):",
        "",
        f"| Sentence | Group | {head} | Fewer whole right than `{BASELINE}` |",
        "| --- | --- |" + " --- |" * (len(_COLUMNS) * len(runs) + 1),
    ]
    for name in shown:
        cells = [_shown(each[name], field) for _, field in _COLUMNS for each in every]
        group = every[0][name].group
        lines.append(f"| {name} | {group} | {' | '.join(cells)} | {_fewer(runs, every, name)} |")
    return lines


def _conditions_line(runs: Sequence[Results]) -> str:
    names = ", ".join(f"`{_prompt(results)}`" for results in runs)
    return (
        "The runs share the set, the model, the way of reading a passage and every parameter; "
        f"only the prompt version differs: {names}."
    )


def sets_markdown(runs: Sequence[tuple[Results, str]]) -> str:
    """The comparison of the runs of one set, as the lines of the results record.

    Each run comes with the name of its results file as the table shows it.
    Raises ``ValueError`` when the runs cannot be compared (``check_comparable``).
    """
    check_comparable([results for results, _ in runs])
    ordered = _ordered(runs)
    rows = [(results, row_of(results, name)) for results, name in ordered]
    alone = [results for results, _ in ordered]
    parts = [
        _conditions_line(alone),
        "",
        *_scores_table([row for _, row in rows]),
        "",
        *_cost_table(rows),
        "",
        *_fields_table(alone),
        "",
        *_sentences_table(alone),
    ]
    return "\n".join(parts) + "\n"


# --- the rule ------------------------------------------------------------------------------


type _Count = Callable[[Row], int]


def _whole(row: Row) -> int:
    return row.whole_right


def _silent(row: Row) -> int:
    return row.silent_wrong


def _missed_extra(row: Row) -> int:
    return row.missed + row.extra


def _more(candidate: int, first: int) -> bool:
    return candidate > first


def _no_fewer(candidate: int, first: int) -> bool:
    return candidate >= first


def _no_more(candidate: int, first: int) -> bool:
    return candidate <= first


# Each condition of the rule: what it says, the set, the count and the test of the two counts.
_CONDITIONS: tuple[tuple[str, Split, _Count, Callable[[int, int], bool]], ...] = (
    ("1. more whole trades right", Split.VOICE, _whole, _more),
    ("2. no fewer whole trades right", Split.DEBUG, _whole, _no_fewer),
    ("3. no more wrong values with no issue", Split.DEBUG, _silent, _no_more),
    ("4. no more trades missed and extra", Split.DEBUG, _missed_extra, _no_more),
    ("5. no more wrong values with no issue", Split.VOICE, _silent, _no_more),
)
_FINAL_CONDITIONS: tuple[tuple[str, _Count, Callable[[int, int], bool]], ...] = (
    ("1. no fewer whole trades right", _whole, _no_fewer),
    ("2. no more trades missed and extra", _missed_extra, _no_more),
    ("3. no more wrong values with no issue", _silent, _no_more),
)
_SHOWN_COUNTS: tuple[tuple[str, _Count], ...] = (
    ("Whole trades right", _whole),
    ("Wrong values with no issue", _silent),
    ("Trades missed and extra", _missed_extra),
)


@dataclass(frozen=True)
class Judged:
    """A candidate against ``first``: each condition with the two counts and whether it holds."""

    candidate: str
    conditions: tuple[tuple[str, str, int, int, bool], ...]
    beside: tuple[tuple[str, int, int], ...]

    @property
    def picked(self) -> bool:
        """Whether every condition holds."""
        return all(holds for *_, holds in self.conditions)


def _by_set(runs: Sequence[Results]) -> dict[Split, dict[str, Results]]:
    grouped: dict[Split, dict[str, Results]] = {}
    for results in runs:
        chosen = Split(str(results.run.get("set")))
        if _prompt(results) in grouped.setdefault(chosen, {}):
            raise ValueError(f"two runs of `{_prompt(results)}` on the {chosen.value} set")
        grouped[chosen][_prompt(results)] = results
    return grouped


def _candidate_of(grouped: Mapping[Split, Mapping[str, Results]]) -> str:
    names = {name for runs in grouped.values() for name in runs}
    others = sorted(names - {BASELINE})
    if BASELINE not in names or len(others) != 1:
        raise ValueError(f"the rule takes runs of `{BASELINE}` and of one candidate")
    return others[0]


def _check_choice(runs: Sequence[Results]) -> tuple[dict[Split, dict[str, Results]], str]:
    grouped = _by_set(runs)
    candidate = _candidate_of(grouped)
    for needed in (Split.DEBUG, Split.VOICE):
        if set(grouped.get(needed, {})) != {BASELINE, candidate}:
            raise ValueError(f"the rule needs a run of each version on the {needed.value} set")
    for chosen, pair in grouped.items():
        if set(pair) != {BASELINE, candidate}:
            raise ValueError(f"the {chosen.value} set needs a run of each version")
        check_comparable(list(pair.values()))
    _check_same(runs, _SAME_ACROSS_SETS)
    for name in (BASELINE, candidate):
        _check_same([pair[name] for pair in grouped.values()], ("prompt_content_sha256",))
    return grouped, candidate


def choose(runs: Sequence[Results]) -> Judged:
    """The rule applied to runs of ``first`` and of one candidate, on the debug and voice sets.

    A run of each on the writings set may be given too: its counts are shown,
    and judged by none of the conditions. Raises ``ValueError`` when the runs
    are not what the rule takes.
    """
    grouped, candidate = _check_choice(runs)
    rows = {
        chosen: {name: row_of(results, name) for name, results in pair.items()}
        for chosen, pair in grouped.items()
    }
    conditions = []
    for said, chosen, count, test in _CONDITIONS:
        first, other = count(rows[chosen][BASELINE]), count(rows[chosen][candidate])
        conditions.append((said, chosen.value, first, other, test(other, first)))
    beside = []
    if Split.WRITINGS in rows:
        pair = rows[Split.WRITINGS]
        beside = [
            (said, count(pair[BASELINE]), count(pair[candidate])) for said, count in _SHOWN_COUNTS
        ]
    return Judged(candidate, tuple(conditions), tuple(beside))


def _yes(holds: object) -> str:
    return "yes" if holds else "no"


def _verdict(failed: Sequence[str], every: str) -> str:
    if not failed:
        return every
    numbers = [said.split(".")[0] for said in failed]
    if len(numbers) == 1:
        return f"condition {numbers[0]} does not hold"
    return f"conditions {', '.join(numbers[:-1])} and {numbers[-1]} do not hold"


def choice_markdown(judged: Judged) -> str:
    """The rule, then the candidate's conditions and whether it is picked, as record lines."""
    name = f"`{judged.candidate}`"
    lines = [
        "The rule, fixed before the first run it judges:",
        "",
        *RULE.rstrip("\n").split("\n"),
        "",
        f"{name} against `{BASELINE}`:",
        "",
        f"| Condition | Set | `{BASELINE}` | {name} | Holds |",
        "| --- | --- | --- | --- | --- |",
    ]
    lines += [
        f"| {said} | {chosen} | {first} | {other} | {_yes(holds)} |"
        for said, chosen, first, other, holds in judged.conditions
    ]
    if judged.beside:
        lines += [
            "",
            "The same counts on the writings set, judged by none of the conditions:",
            "",
            f"| Count | `{BASELINE}` | {name} |",
            "| --- | --- | --- |",
            *(f"| {said} | {first} | {other} |" for said, first, other in judged.beside),
        ]
    failed = [said for said, *_, holds in judged.conditions if not holds]
    verdict = _verdict(failed, "all five conditions hold")
    picked = "Picked" if judged.picked else "Not picked"
    lines += ["", f"{picked}: {name}; {verdict}."]
    return "\n".join(lines) + "\n"


def final_check(earlier: Results, later: Results) -> tuple[tuple[str, int, int, bool], ...]:
    """The three conditions of the final set: each with the two counts and whether it holds."""
    if _prompt(earlier) != BASELINE or _prompt(later) == BASELINE:
        raise ValueError(f"the earlier run is of `{BASELINE}`, the later one of a candidate")
    for results in (earlier, later):
        if results.run.get("set") != Split.FINAL.value:
            raise ValueError(f"the run of `{_prompt(results)}` is not of the final set")
    check_comparable([earlier, later])
    one, other = row_of(earlier, ""), row_of(later, "")
    return tuple(
        (said, count(one), count(other), test(count(other), count(one)))
        for said, count, test in _FINAL_CONDITIONS
    )


def final_markdown(earlier: tuple[Results, str], later: tuple[Results, str]) -> str:
    """The two final runs side by side, then the three conditions, as the lines of the record."""
    checked = final_check(earlier[0], later[0])
    name = f"`{_prompt(later[0])}`"
    lines = [
        sets_markdown([earlier, later]).rstrip("\n"),
        "",
        "The final-set line, fixed before the final set was run:",
        "",
        *FINAL_LINE.rstrip("\n").split("\n"),
        "",
        f"{name} against `{BASELINE}` in `{earlier[1]}`:",
        "",
        f"| Condition | `{BASELINE}` | {name} | Holds |",
        "| --- | --- | --- | --- |",
        *(
            f"| {said} | {first} | {other} | {_yes(holds)} |"
            for said, first, other, holds in checked
        ),
    ]
    failed = [said for said, *_, holds in checked if not holds]
    passed = "Passed" if not failed else "Not passed"
    lines += ["", f"{passed}: {name}; {_verdict(failed, 'all three conditions hold')}."]
    return "\n".join(lines) + "\n"


def _relative(path: Path) -> str:
    parts = path.resolve().parts
    return "/".join(parts[parts.index("evals") :]) if "evals" in parts else path.name


def main(arguments: Sequence[str], *, out: TextIO = sys.stdout) -> int:
    """Print the comparison, the choice or the final line; 2 when the runs do not allow it."""
    parser = argparse.ArgumentParser(prog="python -m evals.compare_sets", description=__doc__)
    parser.add_argument("results", type=Path, nargs="+")
    way = parser.add_mutually_exclusive_group()
    way.add_argument("--choose", action="store_true", help="apply the rule to the runs")
    way.add_argument("--final", action="store_true", help="the final set against an earlier run")
    options = parser.parse_args(arguments)
    try:
        runs = [(read_results(path), _relative(path)) for path in options.results]
    except (OSError, ValueError) as error:
        print(f"cannot read: {error}", file=out)
        return 2
    try:
        if options.choose:
            text = choice_markdown(choose([results for results, _ in runs]))
        elif options.final:
            if len(runs) != 2:
                raise ValueError("the final line takes two runs: the earlier, then the later")
            text = final_markdown(runs[0], runs[1])
        else:
            text = sets_markdown(runs)
    except ValueError as error:
        print(f"cannot compare: {error}", file=out)
        return 2
    print(text, file=out)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="backslashreplace")  # type: ignore[union-attr]
    sys.exit(main(sys.argv[1:]))
