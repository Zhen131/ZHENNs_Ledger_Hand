"""Record trades from a passage at the command line: one question at a time, then the records.

    .venv/bin/python scripts/record_trades.py "昨天买了 0.5 ETH，价格 3,420"
    .venv/bin/python scripts/record_trades.py --answers answers.txt "sold 2 SOL at 150"
    printf '3420\\nnone\\ndone\\n' | .venv/bin/python scripts/record_trades.py --answers - "..."
    .venv/bin/python scripts/record_trades.py --save "昨天买了 0.5 ETH，价格 3,420，手续费 0"
    .venv/bin/python scripts/record_trades.py --list
    .venv/bin/python scripts/record_trades.py --export

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
its question as if typed. When the answers, or the input at the terminal,
run out before every trade is settled, the script stops; once every trade
is settled, running out counts as "done".

The current moment is read from the machine's clock and the zone is the
machine's own, read with ``tzlocal``; both are handed in. Without one of the
three options below, nothing is written to disk, nothing that was said is
kept, and no book is opened.

``--save`` records the passage the same way with the book open: first it
says whether the passage, or one that differs only in spacing or character
width, was saved before (when, and how many trades), without holding
anything back; the coins confirmed and saved before are known. Once the
records are final, it asks whether to save them, and saves them only when
the answer is "save" (or "yes", "y", "存", "保存"); any other answer, or none
when the answers run out, saves nothing. ``--list`` lists every saved trade,
when it was saved and whether and when it was exported. ``--export`` writes
the saved trades not exported yet into a new file in the exports folder and
marks them. The book and the exports folder are in the data folder
(``LEDGER_HAND_DATA_DIR``, or ``data`` in the working directory).

Exit status: 0 done, with the records listed (there may be none), saved when
``--save`` asked for it, listed or exported (or nothing new to export); 1
nothing is kept: the passage was refused, stopped, held no trade, the model
failed, or the passage was dropped; or the records were not saved; or the
export was refused or could not be written; 2 the script could not start (a
setting, or the machine's zone); 3 the answers or the input ran out before
the end; 4 the book failed, or the export file was written but its trades
could not be marked.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterator, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO

import tzlocal

from ledger_hand.core.book import Listing
from ledger_hand.core.numbers import write_number
from ledger_hand.core.timeparse import write_time
from ledger_hand.core.trade import OccurredTime, TradeRecord
from ledger_hand.core.zones import is_zone_name, zone_named
from ledger_hand.extraction.issues import Issue
from ledger_hand.extraction.screening import REASONS, Report
from ledger_hand.flows.exporting import ExportOutcome, ExportResult, export
from ledger_hand.flows.progress import Progress, Stage, TradeStatus, Tuning
from ledger_hand.flows.recording import answer, start, tuning_from
from ledger_hand.flows.saving import save
from ledger_hand.llm.local import connect_local_model
from ledger_hand.ports import ModelPort, StorageError, StoragePort
from ledger_hand.settings import DataPlaces, SettingsError, load_data_places, load_model_settings
from ledger_hand.storage.sqlite_store import SqliteStore

DONE = 0
NOTHING_KEPT = 1
CANNOT_START = 2
RAN_OUT = 3
BOOK_FAILED = 4
# The answers that save the records; anything else saves nothing.
SAVE_WORDS = frozenset({"save", "yes", "y", "存", "保存"})
_EXIT_OF_EXPORT = {
    ExportResult.EXPORTED: DONE,
    ExportResult.NOTHING_NEW: DONE,
    ExportResult.REFUSED: NOTHING_KEPT,
    ExportResult.NOT_WRITTEN: NOTHING_KEPT,
    ExportResult.NOT_MARKED: BOOK_FAILED,
}
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
    places: DataPlaces | None = None,
) -> int:
    """Run the script; the keyword arguments stand in for the outside world in tests."""
    options = _parser().parse_args(arguments)
    if options.list or options.export:
        return _book_task(options, out=out, now=now, zone=zone, places=places)
    lines = iter(stdin.readline, "")
    passage = " ".join(options.passage) if options.passage else next(lines, "").rstrip("\n")
    zone = zone or _machine_zone()
    if zone is None:
        print(_NO_ZONE, file=out)
        return CANNOT_START
    book = _book_at(places, out) if options.save else None
    if options.save and book is None:
        return CANNOT_START
    if model is None or tuning is None:
        assembled = _assembled(out)
        if assembled is None:
            return CANNOT_START
        model, tuning = model or assembled[0], tuning or assembled[1]
    answers = _answers(options.answers, lines, out)
    print(f"passage: {passage!r}", file=out)
    print(f"zone:    {zone}", file=out)
    try:
        progress = start(passage, model, now=now or _now(), zone=zone, tuning=tuning, book=book)
    except StorageError as error:
        return _book_failed(error, out)
    _show_seen_before(progress, zone, out)
    status, progress = _converse(progress, model, answers, out)
    if book is None or status != DONE:
        return status
    return _offer_to_save(progress, book, answers, now, out)


_NO_ZONE = "cannot tell the machine's time zone by a name the program takes"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Record trades from a passage.")
    parser.add_argument(
        "--answers", metavar="FILE", help="answers, one per line ('-' for standard input)"
    )
    task = parser.add_mutually_exclusive_group()
    task.add_argument(
        "--save", action="store_true", help="record, then save the records if the answer is save"
    )
    task.add_argument("--list", action="store_true", help="list the saved trades")
    task.add_argument("--export", action="store_true", help="export the trades not exported yet")
    parser.add_argument("passage", nargs="*", help="the passage; else the first line of input")
    return parser


def _now() -> datetime:
    return datetime.now(timezone.utc)


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
) -> tuple[int, Progress]:
    while not progress.over:
        _show(progress, out)
        given = next(answers)
        if given is None and progress.stage is Stage.REVIEWING:
            given = "done"
            print(f"> {given}", file=out)
        if given is None:
            print("\nthe answers ran out before every trade was settled", file=out)
            _show_calls(progress, out)
            return RAN_OUT, progress
        progress = answer(progress, given, model)
    _show(progress, out)
    _show_calls(progress, out)
    return (DONE if progress.stage is Stage.DONE else NOTHING_KEPT), progress


# --- the book -----------------------------------------------------------------


def _book_at(places: DataPlaces | None, out: TextIO) -> StoragePort | None:
    """The book where the settings keep it; it is opened by each use, not here."""
    try:
        where = places or load_data_places()
    except SettingsError as error:
        print(f"setting refused: {error}", file=out)
        return None
    return SqliteStore(where.book)


def _book_failed(error: StorageError, out: TextIO) -> int:
    print(f"the book failed: {error}", file=out)
    return BOOK_FAILED


def _show_seen_before(progress: Progress, zone: str, out: TextIO) -> None:
    for earlier in progress.seen_before:
        day = earlier.saved_at.astimezone(zone_named(zone)).date().isoformat()
        print(
            f"Reminder: this passage, or one that differs from it only in spacing or "
            f"full-width characters, was saved on {day}, {earlier.trades} trade(s). "
            "Nothing is held back for it; saving again keeps the trades twice.",
            file=out,
        )


def _offer_to_save(
    progress: Progress,
    book: StoragePort,
    answers: Iterator[str | None],
    now: datetime | None,
    out: TextIO,
) -> int:
    count = len(progress.records)
    if not count:
        print("nothing to save", file=out)
        return DONE
    print(
        f"Save {count} record(s) to the book? Say 'save' to save them; anything else saves "
        "nothing.",
        file=out,
    )
    given = next(answers)
    if given is None or given.strip().lower() not in SAVE_WORDS:
        print("not saved: nothing was kept", file=out)
        return NOTHING_KEPT
    try:
        saved = save(progress, book, now=now or _now())
    except StorageError as error:
        return _book_failed(error, out)
    print(f"saved {len(saved.trades)} record(s):", file=out)
    for trade in saved.trades:
        print(f"{_INDENT}{trade.id}", file=out)
    for coin in saved.coins:
        print(f"{_INDENT}coin kept as confirmed: {coin.symbol}", file=out)
    return DONE


def _book_task(
    options: argparse.Namespace,
    *,
    out: TextIO,
    now: datetime | None,
    zone: str | None,
    places: DataPlaces | None,
) -> int:
    zone = zone or _machine_zone()
    if zone is None:
        print(_NO_ZONE, file=out)
        return CANNOT_START
    try:
        where = places or load_data_places()
    except SettingsError as error:
        print(f"setting refused: {error}", file=out)
        return CANNOT_START
    book = SqliteStore(where.book)
    print(f"book:    {where.book}", file=out)
    try:
        if options.list:
            return _list(book, zone, out)
        print(f"exports: {where.exports}", file=out)
        outcome = export(book, where.exports, now=now or _now(), zone=zone)
    except StorageError as error:
        return _book_failed(error, out)
    _show_export(outcome, out)
    return _EXIT_OF_EXPORT[outcome.result]


def _list(book: StoragePort, zone: str, out: TextIO) -> int:
    listed = book.trades(Listing.ALL)
    for number, entry in enumerate(listed, start=1):
        trade = entry.trade
        print(f"{_INDENT}{number}. {trade.id}: {_record_line(trade.record)}", file=out)
        exported = (
            "not exported"
            if entry.exported_at is None
            else f"exported {_moment(entry.exported_at, zone)}"
        )
        print(f"{_INDENT}{_INDENT}saved {_moment(trade.created_at, zone)}; {exported}", file=out)
    waiting = sum(1 for entry in listed if entry.exported_at is None)
    print(f"{len(listed)} trade(s) saved; {waiting} not exported yet.", file=out)
    return DONE


def _moment(moment: datetime, zone: str) -> str:
    return moment.astimezone(zone_named(zone)).isoformat(timespec="seconds")


def _show_export(outcome: ExportOutcome, out: TextIO) -> None:
    print(f"{outcome.result.name.lower()}: {outcome.result.value}", file=out)
    if outcome.path is not None:
        print(f"{_INDENT}file: {outcome.path}", file=out)
    if outcome.identifiers:
        print(f"{_INDENT}{len(outcome.identifiers)} trade(s) in it", file=out)
    for issue in outcome.issues:
        print(f"{_INDENT}{issue.problem.value}: {issue.subject}", file=out)
    if outcome.problem is not None:
        print(f"{_INDENT}{outcome.problem.value}: {outcome.detail}", file=out)
    if outcome.error is not None:
        print(f"{_INDENT}the book said: {outcome.error}", file=out)


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
