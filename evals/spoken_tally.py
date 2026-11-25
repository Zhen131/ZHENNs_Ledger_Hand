"""The counts of one run of a set said the owner's way, and the tables they are printed in.

``tally`` adds up the results ``spoken_judge.judge`` gave each sentence of
a run into one table row: how many gold trades came out each way, the
columns kept apart beside them, the sentences not enabled, and how often
the model's first tool was the one to record. It is the row the results
file's last line holds and the table prints.

The columns, all counting trades unless they say sentences:

- ``clean`` (①) and ``clean_after_code`` (①a, saved with no cell changed
  once the ruler answered the asset's code), ``empty_left`` (①b),
  ``marked`` (②), ``silent`` (③, with every trade sent beyond the gold
  ones, a sentence not enabled among them), ``asked_ok``, ``asked_not_ok``
  and ``not_its_turn`` (④), ``not_sent`` (⑤), ``not_measured``;
- for ②, ③, ④ and ⑤, how many of them had the asset's code answered;
- ``silent_with_passage_reminder``: ③ trades of a reply that held a
  reminder about the whole passage; ``picked_saved``: kept out of ③ by
  the picked-asset line alone; ``guess_missing``: a money that should be
  marked a guess and is not; ``draft_unmarked``: asked about, or waiting
  their turn, with a draft cell wrong and unmarked;
- ``clean_share``: ① and ①a over the enabled gold trades with no none
  and no suspect cell, those not measured left out (the denominator is
  given);
- ``first_tool_right`` of ``first_tool_judged`` enabled sentences.

``markdown_totals`` prints the row alone (all a hidden half ever shows);
``markdown_sentences`` one row a sentence, for a practice half.

Names defined here: ``SentenceRow``, ``tally``, ``markdown_totals`` and
``markdown_sentences``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from evals.spoken_judge import (
    DisabledEnding,
    Ending,
    Observed,
    TradeResult,
    disabled_ending,
    first_tool_right,
)
from evals.spoken_set import SpokenSentence


@dataclass(frozen=True)
class SentenceRow:
    """One sentence of a run: what came of it, its results, and the first tool the model called."""

    sentence: SpokenSentence
    observed: Observed
    results: tuple[TradeResult, ...]
    first_tool: str | None
    came: str


_ENDING_COLUMNS = {
    Ending.EMPTY_LEFT: "empty_left",
    Ending.MARKED: "marked",
    Ending.SILENT: "silent",
    Ending.ASKED_OK: "asked_ok",
    Ending.ASKED_NOT_OK: "asked_not_ok",
    Ending.NOT_ITS_TURN: "not_its_turn",
    Ending.NOT_SENT: "not_sent",
    Ending.NOT_MEASURED: "not_measured",
}
_ANSWERED_COLUMNS = {
    Ending.MARKED: "marked_answered",
    Ending.SILENT: "silent_answered",
    Ending.ASKED_OK: "asked_answered",
    Ending.ASKED_NOT_OK: "asked_answered",
    Ending.NOT_ITS_TURN: "asked_answered",
    Ending.NOT_SENT: "not_sent_answered",
}
_DISABLED_COLUMNS = {
    DisabledEnding.TOLD: "disabled_told",
    DisabledEnding.ASKED: "disabled_asked",
    DisabledEnding.SENT: "disabled_sent",
    DisabledEnding.OTHER: "disabled_other",
}


def _empty() -> dict[str, int]:
    names = (
        "sentences_enabled",
        "sentences_disabled",
        "sentences_not_measured",
        "gold_trades",
        "not_measured",
        "clean",
        "clean_after_code",
        "empty_left",
        "marked",
        "silent",
        "silent_with_passage_reminder",
        "picked_saved",
        "guess_missing",
        "asked_ok",
        "asked_not_ok",
        "not_its_turn",
        "draft_unmarked",
        "not_sent",
        "marked_answered",
        "silent_answered",
        "asked_answered",
        "not_sent_answered",
        "clean_share_of",
        "first_tool_right",
        "first_tool_judged",
        "disabled_told",
        "disabled_asked",
        "disabled_sent",
        "disabled_other",
    )
    return dict.fromkeys(names, 0)


def _add_result(counts: dict[str, int], result: TradeResult, row: SentenceRow) -> None:
    if result.ending is Ending.CLEAN:
        counts["clean_after_code" if result.answered else "clean"] += 1
    else:
        counts[_ENDING_COLUMNS[result.ending]] += 1
        if result.answered and result.ending in _ANSWERED_COLUMNS:
            counts[_ANSWERED_COLUMNS[result.ending]] += 1
    if result.ending is Ending.SILENT and row.observed.passage_reminders:
        counts["silent_with_passage_reminder"] += 1
    counts["picked_saved"] += result.picked_saved
    counts["guess_missing"] += bool(result.guess_missing)
    counts["draft_unmarked"] += bool(result.draft_unmarked)


def tally(rows: Sequence[SentenceRow]) -> dict[str, object]:
    """The counts of a run, as the results file's last line holds them."""
    counts = _empty()
    for row in rows:
        sentence = row.sentence
        measured = not row.observed.model_unreachable
        counts["sentences_not_measured"] += not measured
        if sentence.enabled:
            counts["sentences_enabled"] += 1
            counts["gold_trades"] += len(sentence.gold.trades)
            counts["clean_share_of"] += sum(
                trade.clean
                for trade, result in zip(sentence.gold.trades, row.results, strict=False)
                if result.ending is not Ending.NOT_MEASURED
            )
            if measured:
                counts["first_tool_judged"] += 1
                counts["first_tool_right"] += first_tool_right(row.first_tool)
        else:
            counts["sentences_disabled"] += 1
            ending = disabled_ending(sentence, row.observed)
            if ending is not None:
                counts[_DISABLED_COLUMNS[ending]] += 1
        for result in row.results:
            _add_result(counts, result, row)
    share = _share(counts["clean"] + counts["clean_after_code"], counts["clean_share_of"])
    return {**counts, "clean_share": share}


def _share(part: int, whole: int) -> str | None:
    if whole == 0:
        return None
    return str((Decimal(part) / Decimal(whole) * 100).quantize(Decimal("0.1"), ROUND_HALF_UP))


_TOTAL_HEADERS = (
    (
        "sentences (enabled / not)",
        lambda c: f"{c['sentences_enabled']} / {c['sentences_disabled']}",
    ),
    ("gold trades", lambda c: c["gold_trades"]),
    ("not measured", lambda c: c["not_measured"]),
    ("1", lambda c: c["clean"]),
    ("1a after the code", lambda c: c["clean_after_code"]),
    ("1b", lambda c: c["empty_left"]),
    ("2 (code)", lambda c: f"{c['marked']} ({c['marked_answered']})"),
    ("3 (code)", lambda c: f"{c['silent']} ({c['silent_answered']})"),
    ("3 with a passage reminder", lambda c: c["silent_with_passage_reminder"]),
    ("out of 3 by the picked line alone", lambda c: c["picked_saved"]),
    ("guess not marked", lambda c: c["guess_missing"]),
    ("4 rightly asked", lambda c: c["asked_ok"]),
    ("4 not rightly asked", lambda c: c["asked_not_ok"]),
    ("4 not its turn", lambda c: c["not_its_turn"]),
    ("4 (code)", lambda c: c["asked_answered"]),
    ("4 with an unmarked draft error", lambda c: c["draft_unmarked"]),
    ("5 (code)", lambda c: f"{c['not_sent']} ({c['not_sent_answered']})"),
    ("1 and 1a share (of)", lambda c: f"{c['clean_share']}% ({c['clean_share_of']})"),
    ("first tool right", lambda c: f"{c['first_tool_right']} of {c['first_tool_judged']}"),
    (
        "not enabled: told / asked / sent / other",
        lambda c: (
            f"{c['disabled_told']} / {c['disabled_asked']} / {c['disabled_sent']} / "
            f"{c['disabled_other']}"
        ),
    ),
)


def markdown_totals(counts: dict[str, object], head: dict[str, object]) -> str:
    """The counts alone, one table row with the conditions: no sentence, no identifier."""
    names = ["tier", "half", "extraction prompt", "system prompt", *(h for h, _ in _TOTAL_HEADERS)]
    values = [
        head["tier"],
        head["half"],
        head["extraction_prompt"],
        head["prompt"],
        *(str(get(counts)) for _, get in _TOTAL_HEADERS),
    ]
    return "\n".join(
        (
            "| " + " | ".join(names) + " |",
            "|" + " --- |" * len(names),
            "| " + " | ".join(str(value) for value in values) + " |",
        )
    )


def _cell(text: str) -> str:
    return text.replace("|", "/").replace("\n", " ")


def markdown_sentences(rows: Sequence[SentenceRow]) -> str:
    """One row a sentence: its endings, the first tool, the codes answered and what came of it."""
    lines = [
        "| Sentence | Kind | Endings | First tool | Code answered | What came of it |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        endings = "; ".join(
            result.ending.value.split(" ")[0]
            + (f" wrong {','.join(sorted(result.wrong))}" if result.wrong else "")
            + (f" unmarked {','.join(sorted(result.unmarked))}" if result.unmarked else "")
            for result in row.results
        )
        disabled = disabled_ending(row.sentence, row.observed)
        if disabled is not None:
            endings = f"not enabled: {disabled.value}" + (f"; {endings}" if endings else "")
        lines.append(
            f"| {row.sentence.id} | {row.sentence.kind} | {_cell(endings or '-')} | "
            f"{row.first_tool or '-'} | {len(row.observed.answered)} | {_cell(row.came)} |"
        )
    return "\n".join(lines)
