"""The summary of a run: every sentence scored again from the results file, added up and tabled.

``summarize`` reads nothing but the ``Results`` it is handed: each sentence
line's gold answer and what extraction gave. It scores every sentence again
(``scoring``), so the summary never rests on numbers worked out earlier, and
gives back a JSON value with:

- the scores of the scored sentences, all together and by group: one trade,
  several trades (and within them two, three or more), no trade (talk), and
  by language;
- every field that came out wrong, sorted into its kind, with the reasons
  the program gave for the fields it left empty;
- the half copies: where the model copied part of what the person wrote;
- every field the program left empty with a reason, one by one, marked
  where the model's phrase was exactly the gold phrase (after tidying): the
  model copied what the gold answer says, and the program still left the
  field empty;
- every wrong value that reached a draft with no issue about it, one by
  one: a ``WRONG_SILENT`` field, or a ``MADE_UP`` one with no issue;
- the sentences of the ``not_to_record`` group, which are scored by none of
  the above: how many drafts each gave, and what the check of a draft says
  of each (the rules that stop it, or that none does);
- one row per sentence;
- the conditions of the run, as its first line records them, and how long
  it took.

``markdown`` writes that summary as the tables of the results record.

Names defined here: ``summarize``, ``markdown``, ``rescore`` and
``GROUP_ORDER``.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from fractions import Fraction

from evals.cells import CellOutcome, CellResult, EmptyReason, tidy_text
from evals.gold import Group, Language, Sentence, Split
from evals.records import Results, produced_from_line, sentence_from_line
from evals.scoring import Produced, Scores, SentenceScore, add_up, score_sentence
from ledger_hand.core.coins import BUILT_IN_TABLE
from ledger_hand.core.trade import TradeRecord
from ledger_hand.core.validation import check_draft
from ledger_hand.extraction.reply_table import Field

type Scored = tuple[Sentence, Produced, SentenceScore]

_LANGUAGE_NAMES = {
    Language.CHINESE: "Chinese",
    Language.ENGLISH: "English",
    Language.MIXED: "mixed",
}
GROUP_ORDER: tuple[str, ...] = (
    "all scored sentences",
    "one trade",
    "several trades",
    "  two trades",
    "  three or more trades",
    "no trade (talk)",
    "Chinese",
    "English",
    "mixed",
)
_GROUP_TEST: Mapping[str, Callable[[Sentence], bool]] = {
    "all scored sentences": lambda s: True,
    "one trade": lambda s: len(s.trades) == 1,
    "several trades": lambda s: len(s.trades) >= 2,
    "  two trades": lambda s: len(s.trades) == 2,
    "  three or more trades": lambda s: len(s.trades) >= 3,
    "no trade (talk)": lambda s: not s.trades,
    "Chinese": lambda s: s.language is Language.CHINESE,
    "English": lambda s: s.language is Language.ENGLISH,
    "mixed": lambda s: s.language is Language.MIXED,
}


def rescore(results: Results) -> list[Scored]:
    """Every sentence of ``results`` scored again from its line."""
    split = Split(str(results.run.get("set", Split.DEBUG.value)))
    scored: list[Scored] = []
    for line in results.sentences:
        sentence = sentence_from_line(line, split)
        produced = produced_from_line(line)
        scored.append((sentence, produced, score_sentence(sentence, produced)))
    return scored


def _scores_json(total: Scores) -> dict[str, object]:
    return {
        "sentences": total.sentences,
        "well_formed": total.well_formed,
        "gold_trades": total.gold_trades,
        "drafts": total.drafts,
        "pairs": total.pairs,
        "whole_right": total.whole_right,
        "missed": total.missed,
        "extra": total.extra,
        "gold_empty_fields": total.gold_empty_fields,
        "made_up_fields": total.made_up_fields,
        "no_trade_sentences": total.no_trade_sentences,
        "no_trade_right": total.no_trade_right,
        "field_right": {field.value: total.field_right[field] for field in Field},
        "outcomes": {kind.name: total.outcomes[kind] for kind in CellOutcome},
        "empty_reasons": {reason.name: total.empty_reasons[reason] for reason in EmptyReason},
        "half_copies": {kind.name: total.half_copies[kind] for kind in CellOutcome},
    }


def _cells(scored: Iterable[Scored]) -> Iterable[tuple[Sentence, int, CellResult]]:
    for sentence, _, score in scored:
        for pair in score.pairs:
            for cell in pair.cells:
                yield sentence, pair.draft_at, cell


def _left_empty(scored: Sequence[Scored]) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    for sentence, _, score in scored:
        for pair in score.pairs:
            gold = sentence.trades[pair.gold_at]
            for cell in pair.cells:
                if cell.outcome is not CellOutcome.LEFT_EMPTY_WITH_REASON:
                    continue
                phrase = gold.cell(cell.field).phrase
                exact = None not in (cell.copied, phrase) and tidy_text(
                    str(cell.copied)
                ) == tidy_text(str(phrase))
                found.append(
                    {
                        "id": sentence.id,
                        "draft": pair.draft_at + 1,
                        "field": cell.field.value,
                        "copied": cell.copied,
                        "gold_phrase": phrase,
                        "reason": None if cell.reason is None else cell.reason.name,
                        "copied_the_gold_phrase": exact,
                    }
                )
    return found


def _timing(results: Results) -> dict[str, object]:
    seconds = [float(str(line.get("seconds", 0))) for line in results.sentences]
    end = results.end or {}
    return {
        "sentences": len(seconds),
        "sum_of_sentence_seconds": round(sum(seconds), 3),
        "first_sentence_seconds": seconds[0] if seconds else None,
        "longest_sentence_seconds": max(seconds) if seconds else None,
        "finished_at": end.get("finished_at"),
        "seconds_of_the_last_session": end.get("seconds_this_session"),
    }


def _silent_wrong(scored: Sequence[Scored]) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    for sentence, draft_at, cell in _cells(scored):
        outcome = cell.outcome
        silent_made_up = outcome is CellOutcome.MADE_UP and not cell.issues
        if outcome is CellOutcome.WRONG_SILENT or silent_made_up:
            found.append(
                {
                    "id": sentence.id,
                    "text": sentence.text,
                    "draft": draft_at + 1,
                    "field": cell.field.value,
                    "copied": cell.copied,
                    "got": cell.got,
                    "gold": cell.gold,
                    "kind": outcome.name,
                }
            )
    return found


def _made_up_with_issue(scored: Sequence[Scored]) -> int:
    return sum(
        cell.outcome is CellOutcome.MADE_UP and bool(cell.issues) for _, _, cell in _cells(scored)
    )


def _half_copies(scored: Sequence[Scored]) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    for sentence, draft_at, cell in _cells(scored):
        if cell.half_copy:
            found.append(
                {
                    "id": sentence.id,
                    "draft": draft_at + 1,
                    "field": cell.field.value,
                    "copied": cell.copied,
                    "got": cell.got,
                    "gold": cell.gold,
                    "kind": cell.outcome.name,
                }
            )
    return found


def _not_to_record(scored: Sequence[Scored]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for sentence, produced, score in scored:
        checks: list[str] = []
        for draft in produced.drafts:
            result = check_draft(draft, BUILT_IN_TABLE, sentence.now)
            if isinstance(result, TradeRecord):
                checks.append("not stopped: it passes the check")
            else:
                names = [item.name for item in (*result.missing, *result.violations)]
                checks.append("stopped by " + ", ".join(names))
        rows.append(
            {
                "id": sentence.id,
                "kind": None if sentence.kind is None else sentence.kind.value,
                "text": sentence.text,
                "result": score.kind.value,
                "drafts": len(produced.drafts),
                "checks": checks,
            }
        )
    return rows


def _sentence_rows(scored: Sequence[Scored]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for sentence, _, score in scored:
        wrong = [
            f"{pair.gold_at + 1}.{cell.field.value}:{cell.outcome.name}"
            for pair in score.pairs
            for cell in pair.cells
            if cell.outcome is not CellOutcome.RIGHT
        ]
        rows.append(
            {
                "id": sentence.id,
                "language": sentence.language.value,
                "result": score.kind.value,
                "gold_trades": score.gold_trades,
                "drafts": score.drafts,
                "whole_right": score.whole_right,
                "missed": score.missed,
                "extra": score.extra,
                "wrong_fields": wrong,
            }
        )
    return rows


def summarize(results: Results) -> dict[str, object]:
    """The summary of ``results``, worked out afresh from its sentence lines."""
    everything = rescore(results)
    scored = [entry for entry in everything if entry[0].group is Group.SCORED]
    apart = [entry for entry in everything if entry[0].group is Group.NOT_TO_RECORD]
    groups = {
        name: _scores_json(add_up(score for s, _, score in scored if _GROUP_TEST[name](s)))
        for name in GROUP_ORDER
    }
    return {
        "run": dict(results.run),
        "timing": _timing(results),
        "finished": results.end is not None,
        "groups": groups,
        "made_up_with_an_issue": _made_up_with_issue(scored),
        "wrong_values_with_no_issue": _silent_wrong(scored),
        "half_copies": _half_copies(scored),
        "left_empty_by_the_program": _left_empty(scored),
        "not_to_record": _not_to_record(apart),
        "sentences": _sentence_rows(scored),
    }


# --- writing the summary as tables ----------------------------------------------


def _ratio(part: object, whole: object) -> str:
    top, bottom = int(str(part)), int(str(whole))
    if bottom == 0:
        return f"{top} / 0 (-)"
    percent = Fraction(100 * top, bottom)
    return f"{top} / {bottom} ({float(percent):.1f}%)"


def _group_table(groups: Mapping[str, Mapping[str, object]]) -> list[str]:
    lines = [
        "| Group | Sentences | Well-formed | Whole trades right | Missed | Extra "
        "| Made up | No-trade sentences right |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for name in GROUP_ORDER:
        g = groups[name]
        lines.append(
            f"| {name.strip() if not name.startswith(' ') else '- ' + name.strip()} "
            f"| {g['sentences']} | {_ratio(g['well_formed'], g['sentences'])} "
            f"| {_ratio(g['whole_right'], g['gold_trades'])} | {g['missed']} | {g['extra']} "
            f"| {_ratio(g['made_up_fields'], g['gold_empty_fields'])} "
            f"| {_ratio(g['no_trade_right'], g['no_trade_sentences'])} |"
        )
    return lines


def _field_table(group: Mapping[str, object]) -> list[str]:
    right = group["field_right"]
    assert isinstance(right, dict)
    lines = ["| Field | Right / pairs |", "| --- | --- |"]
    lines += [
        f"| {field.value} | {_ratio(right[field.value], group['pairs'])} |" for field in Field
    ]
    return lines


def _outcome_table(group: Mapping[str, object], made_up_with_issue: object) -> list[str]:
    outcomes = group["outcomes"]
    reasons = group["empty_reasons"]
    assert isinstance(outcomes, dict) and isinstance(reasons, dict)
    lines = ["| Kind | Fields |", "| --- | --- |"]
    for kind in CellOutcome:
        lines.append(f"| {kind.name}: {kind.value} | {outcomes[kind.name]} |")
        if kind is CellOutcome.LEFT_EMPTY_WITH_REASON:
            lines += [
                f"| - because {reason.value} | {reasons[reason.name]} |" for reason in EmptyReason
            ]
        if kind is CellOutcome.MADE_UP:
            lines.append(f"| - of them with an issue about the field | {made_up_with_issue} |")
    return lines


def _cell_text(value: object) -> str:
    if value is None:
        return "(empty)"
    return str(value).replace("|", "\\|")


def _with_text(row: Mapping[str, object]) -> str:
    return f"{row['id']}: {row['text']}"


def _id_only(row: Mapping[str, object]) -> str:
    return str(row["id"])


def _listing(
    rows: Sequence[Mapping[str, object]], label: Callable[[Mapping[str, object]], str]
) -> list[str]:
    head = "| Sentence | Draft | Field | Model copied | Draft holds | Gold | Kind |"
    lines = [head, "| --- | --- | --- | --- | --- | --- | --- |"]
    for row in rows:
        sentence = label(row)
        lines.append(
            f"| {_cell_text(sentence)} | {row['draft']} | {row['field']} "
            f"| {_cell_text(row['copied'])} | {_cell_text(row['got'])} "
            f"| {_cell_text(row['gold'])} | {row['kind']} |"
        )
    return lines


def _not_to_record_table(rows: Sequence[Mapping[str, object]]) -> list[str]:
    lines = [
        "| Sentence | Kind | Result | Drafts | What the check of a draft says |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        checks = row["checks"]
        assert isinstance(checks, list)
        said = "; ".join(f"draft {at + 1}: {text}" for at, text in enumerate(checks)) or "-"
        lines.append(
            f"| {row['id']}: {_cell_text(row['text'])} | {row['kind']} | {row['result']} "
            f"| {row['drafts']} | {said} |"
        )
    return lines


def _sentence_table(rows: Sequence[Mapping[str, object]]) -> list[str]:
    lines = [
        "| Sentence | Language | Result | Gold trades | Drafts | Whole right | Missed | Extra "
        "| Fields not right (gold trade.field:kind) |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        wrong = row["wrong_fields"]
        assert isinstance(wrong, list)
        lines.append(
            f"| {row['id']} | {row['language']} | {row['result']} | {row['gold_trades']} "
            f"| {row['drafts']} | {row['whole_right']} | {row['missed']} | {row['extra']} "
            f"| {', '.join(wrong) or '-'} |"
        )
    return lines


def _run_table(run: Mapping[str, object], timing: Mapping[str, object]) -> list[str]:
    lines = ["| Condition | Value |", "| --- | --- |"]
    for key, value in run.items():
        if key == "record":
            continue
        if key == "prompt_files" and isinstance(value, list):
            for entry in value:
                lines.append(f"| prompt file {entry['path']} | sha256 {entry['sha256']} |")
        elif key == "parameters" and isinstance(value, dict):
            lines += [f"| parameter {name} | {number} |" for name, number in value.items()]
        else:
            lines.append(f"| {key} | {_cell_text(value)} |")
    lines += [f"| {key} | {_cell_text(value)} |" for key, value in timing.items()]
    return lines


def _left_empty_table(rows: Sequence[Mapping[str, object]]) -> list[str]:
    lines = [
        "| Sentence | Draft | Field | Model copied | Gold phrase | Reason "
        "| Model copied exactly the gold phrase |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        exact = "yes" if row["copied_the_gold_phrase"] else "no"
        lines.append(
            f"| {row['id']} | {row['draft']} | {row['field']} | {_cell_text(row['copied'])} "
            f"| {_cell_text(row['gold_phrase'])} | {row['reason']} | {exact} |"
        )
    return lines


def markdown(summary: Mapping[str, object]) -> str:
    """The summary as the Markdown tables of the results record."""
    groups = summary["groups"]
    assert isinstance(groups, dict)
    everything = groups["all scored sentences"]
    silent = summary["wrong_values_with_no_issue"]
    halves = summary["half_copies"]
    apart = summary["not_to_record"]
    rows = summary["sentences"]
    assert isinstance(silent, list) and isinstance(halves, list)
    assert isinstance(apart, list) and isinstance(rows, list)
    run = summary["run"]
    timing = summary["timing"]
    blocked = summary["left_empty_by_the_program"]
    assert isinstance(run, dict) and isinstance(timing, dict) and isinstance(blocked, list)
    exact = sum(1 for row in blocked if row["copied_the_gold_phrase"])
    parts = [
        "#### Run",
        *_run_table(run, timing),
        "",
        "#### Scores by group",
        *_group_table(groups),
        "",
        "#### Each field, all scored sentences",
        *_field_table(everything),
        "",
        "#### Every field of every pair, by kind",
        *_outcome_table(everything, summary["made_up_with_an_issue"]),
        "",
        f"#### Wrong values in drafts with no issue about them ({len(silent)})",
        *_listing(silent, _with_text),
        "",
        f"#### Half copies: the model copied part of the gold phrase ({len(halves)})",
        *_listing(halves, _id_only),
        "",
        f"#### Fields the program left empty ({len(blocked)}; the model's phrase was exactly "
        f"the gold phrase in {exact})",
        *_left_empty_table(blocked),
        "",
        "#### Passages not to record (not in any score above)",
        *_not_to_record_table(apart),
        "",
        "#### Every scored sentence",
        *_sentence_table(rows),
    ]
    return "\n".join(parts) + "\n"
