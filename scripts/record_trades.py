"""Record trades from a passage at the command line: one question at a time, then the records.

    .venv/bin/python scripts/record_trades.py "昨天买了 0.5 ETH，价格 3,420"
    .venv/bin/python scripts/record_trades.py --answers answers.txt "sold 2 SOL at 150"
    printf '3420\\nnone\\ndone\\n' | .venv/bin/python scripts/record_trades.py --answers - "..."

The passage is the arguments, joined by spaces, or else the first line of
standard input. The model the settings name judges it, extracts its trades,
and words a question about each thing missing, one trade and one field at a
time; the answers are read back in, and each trade is checked again. Once
every trade is settled, the records are listed, with the trades skipped,
those that cannot be recorded and why, the reminders and anything set aside;
then "remove N" leaves a record out, "cancel" drops the whole passage and
"done" ends. "skip" leaves the trade being asked about out, and "cancel"
drops the whole passage at any question. Nothing is saved: saving is a later
step of the program.

Without ``--answers`` the script asks at the terminal, reading each answer
from standard input. With ``--answers FILE`` it is not interactive: the
answers are the lines of the file (``-`` for standard input, after the
passage when the passage is not given as arguments), each printed after
its question as if typed. When they run out before every trade is settled,
the script stops; when they run out once every trade is settled, that
counts as "done".

The current moment is read from the machine's clock and the zone is the
machine's own, read with ``tzlocal``; both are handed in. Nothing is written
to disk, and nothing that was said is kept.

Exit status: 0 done, with the records listed (there may be none); 1 nothing
is kept: the passage was refused, stopped, held no trade, the model failed,
or the passage was dropped; 2 the script could not start (a setting, or the
machine's zone); 3 the answers or the input ran out before the end.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterator, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO

import tzlocal

from ledger_hand.core.numbers import write_number
from ledger_hand.core.timeparse import write_time
from ledger_hand.core.trade import OccurredTime, TradeRecord
from ledger_hand.core.zones import is_zone_name
from ledger_hand.extraction.issues import Issue
from ledger_hand.extraction.screening import REASONS, Report
from ledger_hand.flows.progress import Progress, Stage, TradeStatus, Tuning
from ledger_hand.flows.recording import answer, start, tuning_from
from ledger_hand.llm.local import connect_local_model
from ledger_hand.ports import ModelPort
from ledger_hand.settings import SettingsError, load_model_settings

DONE = 0
NOTHING_KEPT = 1
CANNOT_START = 2
RAN_OUT = 3
_NOTHING = "-"
_INDENT = "    "


def main(
    arguments: Sequence[str],
    *,
    stdin: TextIO = sys.stdin,
    out: TextIO = sys.stdout,
    model: ModelPort | None = None,
    tuning: Tuning | None = None,
    now: datetime | None = None,
    zone: str | None = None,
) -> int:
    """Run the script; the keyword arguments stand in for the outside world in tests."""
    options = _parser().parse_args(arguments)
    lines = iter(stdin.readline, "")
    passage = " ".join(options.passage) if options.passage else next(lines, "").rstrip("\n")
    zone = zone or _machine_zone()
    if zone is None:
        print("cannot tell the machine's time zone by a name the program takes", file=out)
        return CANNOT_START
    if model is None or tuning is None:
        assembled = _assembled(out)
        if assembled is None:
            return CANNOT_START
        model, tuning = model or assembled[0], tuning or assembled[1]
    answers = _answers(options.answers, lines, out)
    print(f"passage: {passage!r}", file=out)
    print(f"zone:    {zone}", file=out)
    progress = start(
        passage, model, now=now or datetime.now(timezone.utc), zone=zone, tuning=tuning
    )
    return _converse(progress, model, answers, out)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Record trades from a passage.")
    parser.add_argument(
        "--answers", metavar="FILE", help="answers, one per line ('-' for standard input)"
    )
    parser.add_argument("passage", nargs="*", help="the passage; else the first line of input")
    return parser


def _machine_zone() -> str | None:
    """The machine's zone name as tzlocal reads it, if the program takes it as it stands."""
    try:
        name = tzlocal.get_localzone_name()
    except (LookupError, OSError, ValueError):
        return None
    return name if is_zone_name(name) else None


def _assembled(out: TextIO) -> tuple[ModelPort, Tuning] | None:
    try:
        settings = load_model_settings()
    except SettingsError as error:
        print(f"setting refused: {error}", file=out)
        return None
    return connect_local_model(settings), tuning_from(settings)


def _answers(source: str | None, lines: Iterator[str], out: TextIO) -> Iterator[str | None]:
    """The answers, each ``None`` once they have run out; typed ones are prompted for."""
    if source is None:
        while True:
            print("> ", end="", file=out, flush=True)
            line = next(lines, None)
            if line is None:
                print(file=out)
                break
            yield line.rstrip("\n")
    else:
        given = lines if source == "-" else iter(Path(source).read_text("utf-8").splitlines())
        for line in given:
            text = line.rstrip("\n")
            print(f"> {text}", file=out)
            yield text
    while True:
        yield None


def _converse(
    progress: Progress, model: ModelPort, answers: Iterator[str | None], out: TextIO
) -> int:
    while not progress.over:
        _show(progress, out)
        given = next(answers)
        if given is None and progress.stage is Stage.REVIEWING:
            given = "done"
            print(f"> {given}", file=out)
        if given is None:
            print("\nthe answers ran out before every trade was settled", file=out)
            _show_calls(progress, out)
            return RAN_OUT
        progress = answer(progress, given, model)
    _show(progress, out)
    _show_calls(progress, out)
    return DONE if progress.stage is Stage.DONE else NOTHING_KEPT


# --- showing ----------------------------------------------------------------


def _show(progress: Progress, out: TextIO) -> None:
    stage = progress.stage
    if stage is Stage.ASKING and progress.question is not None:
        question = progress.question
        if question.again is not None:
            print(f"{_INDENT}(asked again: {question.again})", file=out)
        print(question.text, file=out)
        for line in (*question.choices, *question.notes):
            print(f"{_INDENT}{line}", file=out)
        return
    if stage is Stage.REVIEWING:
        _show_settled(progress, out)
        if progress.note is not None:
            print(f"{_INDENT}(not taken: {progress.note})", file=out)
        print(
            "Say 'remove N' to leave record N out, 'cancel' to drop the whole passage, or 'done'.",
            file=out,
        )
        return
    _show_end(progress, out)


def _show_end(progress: Progress, out: TextIO) -> None:
    stage = progress.stage
    print(f"{stage.name.lower()}: {stage.value}", file=out)
    if progress.refused is not None:
        print(f"{_INDENT}{progress.refused.value}", file=out)
    for report in progress.stopped:
        print(f"{_INDENT}{_report_line(report)}", file=out)
    if progress.failure is not None:
        failure = progress.failure
        what = str(failure.error) if failure.error is not None else "; ".join(failure.problems)
        print(f"{_INDENT}{failure.step.value}: {what}", file=out)
    if stage is Stage.DONE:
        _show_settled(progress, out)
        print(f"{len(progress.records)} record(s); nothing is saved yet.", file=out)


def _show_settled(progress: Progress, out: TextIO) -> None:
    print("Records:" if progress.records else "Records: none", file=out)
    for position, trade in enumerate(progress.trades, start=1):
        if trade.status is TradeStatus.RECORDED and trade.record is not None:
            print(f"{_INDENT}{position}. {_record_line(trade.record)}", file=out)
        elif trade.status is TradeStatus.SKIPPED:
            print(f"{_INDENT}{position}. skipped", file=out)
        elif trade.status is TradeStatus.CANNOT_RECORD and trade.reason is not None:
            print(f"{_INDENT}{position}. cannot be recorded: {trade.reason.value}", file=out)
    for report in progress.set_aside:
        print(f"Set aside: {_report_line(report)}", file=out)
    for issue in progress.reminders:
        print(f"Reminder: {_issue_line(issue)}", file=out)


def _record_line(record: TradeRecord) -> str:
    derived = f" ({record.derived.value} worked out)" if record.derived is not None else ""
    return (
        f"{record.side.value} {write_number(record.quantity)} {record.coin}"
        f" at {write_number(record.price)}, total {write_number(record.total)}{derived},"
        f" fee {write_number(record.fee)} {record.fee_coin},"
        f" {_time(record.occurred)}, platform {record.platform or _NOTHING},"
        f" note {record.note or _NOTHING}"
    )


def _time(occurred: OccurredTime) -> str:
    return f"{write_time(occurred)} ({occurred.precision.value})"


def _report_line(report: Report) -> str:
    words = f" {report.evidence!r}" if report.evidence is not None else ""
    return f"{report.kind.value}{words}: {REASONS.get(report.kind, '')}"


def _issue_line(issue: Issue) -> str:
    where = "passage" if issue.draft is None else f"trade {issue.draft + 1}"
    if issue.field is not None:
        where += f", {issue.field.value}"
    line = f"{where}: {issue.kind.value}"
    if issue.cause is not None:
        line += f" ({issue.cause.value})"
    if issue.phrase is not None:
        line += f" [{issue.phrase!r}]"
    if issue.numbers:
        line += ": " + ", ".join(issue.numbers)
    if issue.same_as is not None:
        line += f": the same as trade {issue.same_as + 1}"
    return line


def _show_calls(progress: Progress, out: TextIO) -> None:
    seconds = sum(call.record.elapsed_seconds for call in progress.calls)
    print(f"calls to the model: {len(progress.calls)}, {seconds:.2f} s in all", file=out)
    for step, version in progress.prompts:
        print(f"{_INDENT}prompt for {step.value}: {version}", file=out)


if __name__ == "__main__":
    # A passage with characters the terminal cannot show is still shown, escaped.
    sys.stdout.reconfigure(errors="backslashreplace")  # type: ignore[union-attr]
    sys.exit(main(sys.argv[1:]))
