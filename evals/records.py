"""The results file: one JSON object per line, written as a run goes and read back to re-score it.

A results file (``evals/results/*.jsonl``) starts with a ``run`` line that
records the conditions of the run (``run``), then one ``sentence`` line per
passage, each written the moment that passage is done, and ends with an
``end`` line when the run finished. A run cut short has no ``end`` line,
and its last line may be cut off half way; ``read_results`` leaves such a
line out.

A ``sentence`` line holds everything needed to score the passage again
without the model: the gold answer it was scored against, what extraction
gave (the drafts, the issues, the phrases the model wrote for each draft),
the model's raw replies and a record of each call, and how long it took. It
also holds the scores worked out when it was written, for reading; the
summary is always worked out afresh from the drafts and the gold answer.

This module turns drafts, issues and scores into JSON values and back. It
reads and writes no file except through ``read_results`` and
``append_line``.

Names defined here: ``draft_to_json``, ``draft_from_json``,
``issue_to_json``, ``issue_from_json``, ``score_to_json``,
``produced_from_line``, ``sentence_from_line``, ``read_results``,
``append_line``, ``Results`` and ``LineKind``.
"""

from __future__ import annotations

import enum
import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from evals.gold import (
    Feature,
    Group,
    Language,
    NotToRecord,
    Sentence,
    Split,
    trade_from_json,
)
from evals.scoring import Produced, ResultKind, SentenceScore
from ledger_hand.core.numbers import Caution, Doubt, write_number
from ledger_hand.core.timeparse import Refusal, TimeCaution
from ledger_hand.core.trade import OccurredTime, Side, TimePrecision, TradeDraft
from ledger_hand.extraction.issues import Cause, Issue, IssueKind
from ledger_hand.extraction.reply_table import Field


class LineKind(enum.Enum):
    """What one line of a results file is."""

    RUN = "run"
    SENTENCE = "sentence"
    END = "end"


_CAUSES: Mapping[str, type[enum.Enum]] = {
    "Doubt": Doubt,
    "Caution": Caution,
    "Refusal": Refusal,
    "TimeCaution": TimeCaution,
}
_NUMBERS = ("quantity", "price", "total", "fee")
_WORDS = ("coin", "quote", "fee_coin", "platform", "note", "raw_text")


def _time_to_json(time: OccurredTime | None) -> dict[str, str] | None:
    if time is None:
        return None
    return {
        "value": time.value.isoformat(),
        "precision": time.precision.value,
        "zone": time.time_zone,
    }


def _time_from_json(data: object) -> OccurredTime | None:
    if data is None:
        return None
    if not isinstance(data, dict):
        raise ValueError(f"not a time: {data!r}")
    precision = TimePrecision(data["precision"])
    text = str(data["value"])
    value: date | datetime = (
        date.fromisoformat(text) if precision is TimePrecision.DAY else datetime.fromisoformat(text)
    )
    return OccurredTime(value, precision, str(data["zone"]))


def draft_to_json(draft: TradeDraft) -> dict[str, object]:
    """A draft as a JSON object; numbers as the ledger writes them."""
    data: dict[str, object] = {"side": None if draft.side is None else draft.side.value}
    for name in _NUMBERS:
        number = getattr(draft, name)
        data[name] = None if number is None else write_number(number)
    for name in _WORDS:
        data[name] = getattr(draft, name)
    data["occurred"] = _time_to_json(draft.occurred)
    return data


def draft_from_json(data: Mapping[str, object]) -> TradeDraft:
    """The draft a JSON object written by ``draft_to_json`` holds."""
    side = data.get("side")
    values: dict[str, object] = {"side": None if side is None else Side(side)}
    for name in _NUMBERS:
        number = data.get(name)
        values[name] = None if number is None else Decimal(str(number))
    for name in _WORDS:
        values[name] = data.get(name)
    values["occurred"] = _time_from_json(data.get("occurred"))
    return TradeDraft(**values)  # type: ignore[arg-type]


def _cause_to_json(cause: Cause | None) -> str | None:
    return None if cause is None else f"{type(cause).__name__}.{cause.name}"


def _cause_from_json(text: object) -> Cause | None:
    if text is None:
        return None
    kind, _, name = str(text).partition(".")
    return _CAUSES[kind][name]  # type: ignore[return-value]


def issue_to_json(issue: Issue) -> dict[str, object]:
    """An issue as a JSON object; enumerations by name."""
    return {
        "kind": issue.kind.name,
        "draft": issue.draft,
        "field": None if issue.field is None else issue.field.value,
        "phrase": issue.phrase,
        "cause": _cause_to_json(issue.cause),
        "candidates": [_time_to_json(time) for time in issue.candidates],
        "numbers": list(issue.numbers),
        "same_as": issue.same_as,
    }


def issue_from_json(data: Mapping[str, object]) -> Issue:
    """The issue a JSON object written by ``issue_to_json`` holds."""
    field = data.get("field")
    candidates = data.get("candidates") or []
    numbers = data.get("numbers") or []
    assert isinstance(candidates, list) and isinstance(numbers, list)
    draft = data.get("draft")
    same_as = data.get("same_as")
    phrase = data.get("phrase")
    return Issue(
        kind=IssueKind[str(data["kind"])],
        draft=draft if isinstance(draft, int) else None,
        field=None if field is None else Field(field),
        phrase=phrase if isinstance(phrase, str) else None,
        cause=_cause_from_json(data.get("cause")),
        candidates=tuple(t for c in candidates if (t := _time_from_json(c)) is not None),
        numbers=tuple(str(number) for number in numbers),
        same_as=same_as if isinstance(same_as, int) else None,
    )


def copied_to_json(copied: Sequence[Mapping[Field, str]]) -> list[dict[str, str]]:
    """The model's phrases for each draft, by field name."""
    return [{field.value: text for field, text in row.items()} for row in copied]


def score_to_json(score: SentenceScore) -> dict[str, object]:
    """A sentence's scores as a JSON object, for reading the results file."""
    return {
        "result": score.kind.value,
        "gold_trades": score.gold_trades,
        "drafts": score.drafts,
        "whole_right": score.whole_right,
        "missed": score.missed,
        "extra": score.extra,
        "pairs": [
            {
                "gold": pair.gold_at,
                "draft": pair.draft_at,
                "whole": pair.whole,
                "cells": [
                    {
                        "field": cell.field.value,
                        "outcome": cell.outcome.name,
                        "gold": cell.gold,
                        "got": cell.got,
                        "copied": cell.copied,
                        "half_copy": cell.half_copy,
                        "reason": None if cell.reason is None else cell.reason.name,
                        "issues": [kind.name for kind in cell.issues],
                    }
                    for cell in pair.cells
                ],
            }
            for pair in score.pairs
        ],
    }


def sentence_from_line(line: Mapping[str, object], split: Split) -> Sentence:
    """The sentence, with the gold answer it was scored against, that a line records."""
    text = str(line["text"])
    zone = str(line["zone"])
    gold = line["gold"]
    features = line.get("features") or []
    assert isinstance(gold, list) and isinstance(features, list)
    kind = line.get("kind")
    return Sentence(
        id=str(line["id"]),
        text=text,
        now=datetime.fromisoformat(str(line["now"])),
        zone=zone,
        split=split,
        language=Language(line["language"]),
        group=Group(line["group"]),
        kind=None if kind is None else NotToRecord(kind),
        features=frozenset(Feature(name) for name in features),
        trades=tuple(trade_from_json(trade, text, zone) for trade in gold),
    )


def produced_from_line(line: Mapping[str, object]) -> Produced:
    """What extraction gave, as a line records it."""
    drafts = line.get("drafts") or []
    issues = line.get("issues") or []
    copied = line.get("copied") or []
    assert isinstance(drafts, list) and isinstance(issues, list) and isinstance(copied, list)
    return Produced(
        kind=ResultKind(line["result"]),
        drafts=tuple(draft_from_json(draft) for draft in drafts),
        issues=tuple(issue_from_json(issue) for issue in issues),
        copied=tuple({Field(name): str(text) for name, text in row.items()} for row in copied),
    )


@dataclass(frozen=True)
class Results:
    """A results file read back: the run line, the sentence lines, and the end line if any."""

    run: Mapping[str, object]
    sentences: tuple[Mapping[str, object], ...]
    end: Mapping[str, object] | None
    complete_bytes: int


def read_results(path: Path) -> Results:
    """The lines of the results file at ``path``; a last line cut off half way is left out."""
    raw = path.read_bytes()
    lines: list[dict[str, object]] = []
    complete = 0
    for chunk in raw.splitlines(keepends=True):
        if not chunk.endswith(b"\n"):
            break
        try:
            parsed = json.loads(chunk.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            break
        lines.append(parsed)
        complete += len(chunk)
    if not lines or lines[0].get("record") != LineKind.RUN.value:
        raise ValueError(f"{path.name} does not start with a run line")
    sentences = tuple(line for line in lines if line.get("record") == LineKind.SENTENCE.value)
    ends = [line for line in lines if line.get("record") == LineKind.END.value]
    return Results(lines[0], sentences, ends[-1] if ends else None, complete)


def append_line(path: Path, data: Mapping[str, object]) -> None:
    """Add one line to the file at ``path`` and make sure it reaches the disk."""
    text = json.dumps(data, ensure_ascii=False, sort_keys=False) + "\n"
    with path.open("a", encoding="utf-8") as stream:
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())
