"""Three more counts of a run, worked out from its results file beside the summary, not in it.

The summary of a run (``tables``) is kept exactly as it is; these counts are
a table of their own, worked out the same way: every sentence scored again
from its line. Only the scored sentences count, and only fields of a draft
paired with a gold trade.

- **A total put as the price.** In a pair whose gold trade says a total, the
  model's phrase for the price is the gold phrase of the total (after the
  same tidying as the scoring's), or the draft's price is the gold total's
  value while the gold price is another value or empty. One per pair.
- **Half copies, counted the second way.** The model's phrase for a field
  is part of the gold phrase of that field but not all of it (both tidied),
  whether the field came out right or not. The first way, which the summary
  reports, counts only the fields that did not come out right; it is shown
  beside this one.
- **A time written in another language.** The issue about the time is that
  the model's phrase is not a piece of the passage, and of the model's
  phrase and the gold phrase, one holds a Chinese character and the other
  none: the model wrote an English time in Chinese, or the other way round.

Each count is listed case by case: the sentence, its passage, the draft,
the field, what the model copied, what the draft holds, and the gold phrase
and value.

    .venv/bin/python -m evals.extra_counts evals/results/<file>.jsonl

Names defined here: ``extra_counts``, ``extra_markdown``, ``main``,
``half_copy_any`` and ``has_chinese``.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Iterable, Mapping, Sequence
from decimal import Decimal
from pathlib import Path
from typing import TextIO

from evals.cells import CellOutcome, CellResult, shown, tidy_text
from evals.gold import GoldTrade, Group, Sentence
from evals.records import Results, read_results
from evals.scoring import PairScore, Produced
from evals.tables import rescore
from ledger_hand.extraction.issues import IssueKind
from ledger_hand.extraction.reply_table import Field

_CHINESE = re.compile(r"[㐀-䶿一-鿿豈-﫿]")

type Case = dict[str, object]


def has_chinese(text: str) -> bool:
    """Whether ``text`` holds a Chinese character."""
    return _CHINESE.search(text) is not None


def half_copy_any(copied: str | None, phrase: str | None) -> bool:
    """Whether ``copied`` is part of ``phrase`` but not all of it, both tidied."""
    if copied is None or phrase is None:
        return False
    part, whole = tidy_text(copied), tidy_text(phrase)
    return bool(part) and part != whole and part in whole


def _case(
    sentence: Sentence, pair: PairScore, cell: CellResult, gold: GoldTrade, field: Field
) -> Case:
    gold_cell = gold.cell(field)
    return {
        "id": sentence.id,
        "text": sentence.text,
        "draft": pair.draft_at + 1,
        "field": field.value,
        "copied": cell.copied,
        "got": cell.got,
        "gold_phrase": gold_cell.phrase,
        "gold": shown(gold_cell.value),
    }


def _cell(pair: PairScore, field: Field) -> CellResult:
    return next(cell for cell in pair.cells if cell.field is field)


def _total_as_price(
    sentence: Sentence, produced: Produced, pair: PairScore, gold: GoldTrade
) -> Case | None:
    total = gold.cell(Field.TOTAL)
    if total.phrase is None:
        return None
    price = _cell(pair, Field.PRICE)
    copied_total = price.copied is not None and tidy_text(price.copied) == tidy_text(total.phrase)
    drafted = produced.drafts[pair.draft_at].price
    gold_total = total.value
    took_total = (
        isinstance(gold_total, Decimal)
        and isinstance(drafted, Decimal)
        and drafted == gold_total
        and gold.value(Field.PRICE) != gold_total
    )
    if not (copied_total or took_total):
        return None
    case = _case(sentence, pair, price, gold, Field.TOTAL)
    case["field"] = Field.PRICE.value
    return case


def _translated_time(sentence: Sentence, pair: PairScore, gold: GoldTrade) -> Case | None:
    cell = _cell(pair, Field.TIME)
    phrase = gold.cell(Field.TIME).phrase
    if IssueKind.NOT_IN_PASSAGE not in cell.issues or cell.copied is None or phrase is None:
        return None
    if has_chinese(cell.copied) == has_chinese(phrase):
        return None
    return _case(sentence, pair, cell, gold, Field.TIME)


def _pairs(results: Results) -> Iterable[tuple[Sentence, Produced, PairScore, GoldTrade]]:
    for sentence, produced, score in rescore(results):
        if sentence.group is not Group.SCORED:
            continue
        for pair in score.pairs:
            yield sentence, produced, pair, sentence.trades[pair.gold_at]


def extra_counts(results: Results) -> dict[str, object]:
    """The three counts of ``results``, each with its cases, and the first way of half copies."""
    total_as_price: list[Case] = []
    half_any: list[Case] = []
    translated: list[Case] = []
    half_not_right = 0
    for sentence, produced, pair, gold in _pairs(results):
        found = _total_as_price(sentence, produced, pair, gold)
        if found is not None:
            total_as_price.append(found)
        for cell in pair.cells:
            half_not_right += cell.half_copy
            if half_copy_any(cell.copied, gold.cell(cell.field).phrase):
                case = _case(sentence, pair, cell, gold, cell.field)
                case["right"] = cell.outcome is CellOutcome.RIGHT
                half_any.append(case)
        moved = _translated_time(sentence, pair, gold)
        if moved is not None:
            translated.append(moved)
    return {
        "total_as_price": total_as_price,
        "half_copies_any": half_any,
        "half_copies_not_right": half_not_right,
        "time_in_another_language": translated,
    }


# --- writing the counts as tables ----------------------------------------------


def _text(value: object) -> str:
    if value is None:
        return "(empty)"
    return str(value).replace("|", "\\|")


def _listing(cases: Sequence[Mapping[str, object]], *, with_right: bool = False) -> list[str]:
    head = "| Sentence | Draft | Field | Model copied | Draft holds | Gold phrase | Gold |"
    rule = "| --- | --- | --- | --- | --- | --- | --- |"
    if with_right:
        head += " Field right |"
        rule += " --- |"
    lines = [head, rule]
    for case in cases:
        line = (
            f"| {_text(case['id'])}: {_text(case['text'])} | {case['draft']} | {case['field']} "
            f"| {_text(case['copied'])} | {_text(case['got'])} | {_text(case['gold_phrase'])} "
            f"| {_text(case['gold'])} |"
        )
        if with_right:
            line += f" {'yes' if case['right'] else 'no'} |"
        lines.append(line)
    return lines


def extra_markdown(counts: Mapping[str, object]) -> str:
    """The three counts as the Markdown tables of the results record."""
    total_as_price = counts["total_as_price"]
    half_any = counts["half_copies_any"]
    translated = counts["time_in_another_language"]
    assert isinstance(total_as_price, list) and isinstance(half_any, list)
    assert isinstance(translated, list)
    parts = [
        "#### Three more counts",
        "| Count | Cases |",
        "| --- | --- |",
        f"| A total put as the price | {len(total_as_price)} |",
        f"| Half copies, any field whose phrase is part of the gold phrase | {len(half_any)} |",
        f"| Half copies, only fields not right (as in the summary) "
        f"| {counts['half_copies_not_right']} |",
        f"| A time written in another language | {len(translated)} |",
        "",
        f"#### A total put as the price ({len(total_as_price)}; gold is the total)",
        *_listing(total_as_price),
        "",
        f"#### Half copies, counted the second way ({len(half_any)})",
        *_listing(half_any, with_right=True),
        "",
        f"#### A time written in another language ({len(translated)})",
        *_listing(translated),
    ]
    return "\n".join(parts) + "\n"


def main(arguments: Sequence[str], *, out: TextIO = sys.stdout) -> int:
    """Print the three counts of a results file; 2 when it cannot be read."""
    parser = argparse.ArgumentParser(prog="python -m evals.extra_counts", description=__doc__)
    parser.add_argument("results", type=Path)
    options = parser.parse_args(arguments)
    try:
        counts = extra_counts(read_results(options.results))
    except (OSError, ValueError) as error:
        print(f"cannot read {options.results}: {error}", file=out)
        return 2
    print(extra_markdown(counts), file=out)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="backslashreplace")  # type: ignore[union-attr]
    sys.exit(main(sys.argv[1:]))
