"""What the program says in the chat, beside Save, after Export and on the settings page.

Every message is read off a ``Progress`` the flows handed back, or off what
a flow gave back (the trades saved, an export's outcome, the book's error):
the question with the flow's label, its notes and choices, and why it is
asked again; why a passage was stopped, with the passage's own words; what
was set aside and the reminders of extraction; the reminder that the same
passage was saved before (on which day, how many trades); the reminder that
the ledger leaves a fee paid in a third coin out of the cost; why nothing
was sent or nothing could be done; what became of the passage and of an
export. Nothing here works out anything about a trade; it only chooses the
words to show for what the flow, or the core, says. A failure is said in
the words of ``failure_words``.

The words are plain text: the chat shows them without Markdown, so a
passage's own words come back exactly as typed.

Names defined here: ``after_start``, ``after_answer``, ``after_removing``,
``seen_before``, ``fees_left_out``, ``not_taken_yet``, ``saved``,
``not_saved``, ``book_failed``, ``assembly_failed``, ``save_hint``,
``exported``, ``export_failed``, ``settings_applied`` and ``settings_reset``.
"""

from __future__ import annotations

from collections.abc import Sequence

from ledger_hand.core.fee_cost import fee_left_out_of_cost
from ledger_hand.core.ledger_limits import QUOTE_CURRENCY
from ledger_hand.core.zones import zone_named
from ledger_hand.extraction.issues import Issue
from ledger_hand.extraction.screening import REASONS, Report
from ledger_hand.flows.exporting import ExportOutcome, ExportResult
from ledger_hand.flows.progress import Progress, Stage, TradeStatus
from ledger_hand.ports import StorageError
from ledger_hand.settings import ModelSettings, Variable
from ledger_hand.ui import failure_words
from ledger_hand.ui.setting_text import shown
from ledger_hand.wiring import AssemblyError

_INDENT = "    "


def after_start(progress: Progress, settings: ModelSettings) -> str:
    """What is said once a passage is taken: what was set aside, reminders, where it stands.

    ``settings`` are those the model was called with, for saying what went
    wrong when it failed.
    """
    lines = [f"Set aside, not recorded: {_report(report)}" for report in progress.set_aside]
    lines += [f"Reminder: {_issue(issue)}" for issue in progress.reminders]
    return _joined([*lines, *_where_it_stands(progress, settings)])


def after_answer(progress: Progress, settings: ModelSettings) -> str:
    """What is said once an answer has been read: why it is asked again, or what comes next."""
    question = progress.question
    if progress.stage is Stage.ASKING and question is not None and question.again is not None:
        return _joined([f"That answer could not be used: {question.again}.", *_asking(progress)])
    return _joined(_where_it_stands(progress, settings))


def seen_before(progress: Progress) -> str | None:
    """The reminder that this passage was saved before, or ``None`` when it was not.

    Each earlier save is named by its day, in the passage's own time zone,
    and the number of trades it saved. It only reminds: Save still works.
    """
    if not progress.seen_before:
        return None
    zone = zone_named(progress.setting.zone)
    saves = "; ".join(
        f"on {earlier.saved_at.astimezone(zone).date().isoformat()}, {earlier.trades} trade(s)"
        for earlier in progress.seen_before
    )
    return (
        "Possible duplicate: this passage, or one that differs from it only in spacing or "
        f"full-width characters, was saved before: {saves}. Nothing is held back for it; "
        "Save keeps its trades again."
    )


def fees_left_out(progress: Progress | None) -> list[str]:
    """One reminder for each complete trade whose fee the ledger leaves out of the cost."""
    if progress is None:
        return []
    return [
        f"Trade {number}: its fee is paid in {trade.record.fee_coin}, which is neither "
        f"{QUOTE_CURRENCY} nor {trade.record.coin}. The ledger takes the trade, but leaves "
        "this fee out when it works out the cost."
        for number, trade in enumerate(progress.trades, start=1)
        if trade.status is TradeStatus.RECORDED
        and trade.record is not None
        and fee_left_out_of_cost(trade.record)
    ]


def after_removing(number: int, progress: Progress) -> str:
    """What is said once trade ``number`` was left out, or why it could not be."""
    if progress.note is not None:
        return f"Not done: {progress.note}."
    lines = [f"Trade {number} will not be saved."]
    if not progress.can_save:
        lines.append("Nothing is left to save; press Discard all to end this passage.")
    return _joined(lines)


def not_taken_yet(progress: Progress) -> str:
    """What is said when a new passage comes while the last one is settled but not ended."""
    if progress.can_save:
        choice = "Press Save to keep its trades, or Discard all to drop them"
    else:
        choice = "Nothing in it can be saved; press Discard all to drop it"
    return (
        "The last passage is not saved yet, so this was not taken as a new one. "
        f"{choice}, then type the new passage again."
    )


def saved(count: int) -> str:
    """What is said once the records are saved."""
    return f"Saved {count} trade(s) to the book. Type the next passage when you are ready."


def not_saved(error: StorageError) -> str:
    """What is said when saving failed: nothing was saved, and the passage stays as it was."""
    return (
        f"Nothing was saved: the book could not be used. {failure_words.book_trouble(error)} "
        "The passage is still here, so Save can be pressed again."
    )


def book_failed(error: StorageError) -> str:
    """What is said when the book could not be read before a passage was taken."""
    return (
        "The passage was not taken: the book could not be used. "
        f"{failure_words.book_trouble(error)}"
    )


def assembly_failed(error: AssemblyError) -> str:
    """What is said when the program's parts could not be built, or a change could not be made."""
    return failure_words.assembly_failed(error)


def exported(outcome: ExportOutcome) -> str:
    """What is said once Export was pressed: the file and how many trades, or why not."""
    result = outcome.result
    if result is ExportResult.EXPORTED:
        return (
            f"Exported {len(outcome.identifiers)} trade(s) to {outcome.path}. They are marked "
            "as exported, so the next export leaves them out."
        )
    if result is ExportResult.NOTHING_NEW:
        return (
            "Nothing new to export: every saved trade has been exported already, so no file "
            "was written."
        )
    if result is ExportResult.REFUSED:
        return failure_words.export_refused(outcome.issues)
    if result is ExportResult.NOT_WRITTEN and outcome.problem is not None:
        return failure_words.export_not_written(outcome.problem, outcome.detail)
    return failure_words.export_not_marked(outcome.path, outcome.error)


def export_failed(error: StorageError) -> str:
    """What is said when the book could not be read for an export."""
    return f"Nothing was exported: the book could not be used. {failure_words.book_trouble(error)}"


def settings_applied(changed: Sequence[Variable], now: ModelSettings) -> str:
    """What the settings page says once changes were applied: which values changed, and to what."""
    if not changed:
        return "Nothing was changed: every value is as it was."
    return (
        f"Applied: {_values(changed, now)}. The next call to the model uses them, in this "
        "browser tab only."
    )


def settings_reset(changed: Sequence[Variable], now: ModelSettings) -> str:
    """What the settings page says once it went back to the environment and the defaults."""
    if not changed:
        return "Nothing was changed: the settings already were the environment's and the defaults."
    return (
        f"Back to the environment and the defaults: {_values(changed, now)}. The next call "
        "to the model uses them."
    )


def _values(changed: Sequence[Variable], now: ModelSettings) -> str:
    return "; ".join(f"{variable.value} is now {shown(now, variable)}" for variable in changed)


def save_hint(progress: Progress | None) -> str:
    """The sentence beside Save, saying why it cannot be pressed now, or what it does."""
    if progress is None:
        return "Type a trade in the chat to begin."
    if progress.stage is Stage.ASKING:
        return "Answer the question in the chat first, or say 'skip' to leave that trade out."
    if progress.can_save:
        return f"Saves {len(progress.records)} trade(s) to the book."
    return "Nothing here can be saved: every trade is left out or cannot be recorded."


# --- where the passage stands -------------------------------------------------


def _where_it_stands(progress: Progress, settings: ModelSettings) -> list[str]:
    stage = progress.stage
    if stage is Stage.ASKING:
        return _asking(progress)
    if stage is Stage.REVIEWING:
        return _settled(progress)
    if stage is Stage.STOPPED:
        lines = ["Nothing from this passage will be recorded:"]
        return lines + [f"{_INDENT}{_report(report)}" for report in progress.stopped]
    if stage is Stage.REFUSED and progress.refused is not None:
        return [failure_words.passage_refused(progress.refused)]
    if stage is Stage.FAILED and progress.failure is not None:
        return [failure_words.model_failed(progress.failure, settings)]
    return [_ENDINGS.get(stage, f"{stage.value}.")]


_ENDINGS = {
    Stage.NO_TRADE: "No trade was found in this passage, so nothing will be recorded.",
    Stage.CANCELLED: "This passage was not saved: nothing from it is kept.",
}


def _asking(progress: Progress) -> list[str]:
    question = progress.question
    if question is None:
        return []
    return [
        question.text,
        *(f"{_INDENT}{choice}" for choice in question.choices),
        *(f"{_INDENT}{note}" for note in question.notes),
    ]


def _settled(progress: Progress) -> list[str]:
    lines = [
        f"Trade {number}: cannot be recorded: {trade.reason.value}."
        for number, trade in enumerate(progress.trades, start=1)
        if trade.status is TradeStatus.CANNOT_RECORD and trade.reason is not None
    ]
    lines += fees_left_out(progress)
    if progress.can_save:
        lines.append(
            f"Every trade is settled; {len(progress.records)} will be saved. Check the table, "
            "then press Save. Don't save leaves one trade out; Discard all drops the passage."
        )
    else:
        lines.append(
            "Every trade is settled, but none can be saved. Press Discard all to end this passage."
        )
    if progress.note is not None:
        lines.append(f"Not done: {progress.note}.")
    return lines


def _report(report: Report) -> str:
    reason = REASONS.get(report.kind, report.kind.value)
    if report.evidence is None:
        return reason
    return f"'{report.evidence}': {reason}"


def _issue(issue: Issue) -> str:
    where = "the passage" if issue.draft is None else f"trade {issue.draft + 1}"
    if issue.field is not None:
        where += f", {issue.field.value}"
    line = f"{where}: {issue.kind.value}"
    if issue.cause is not None:
        line += f" ({issue.cause.value})"
    if issue.phrase is not None:
        line += f" '{issue.phrase}'"
    if issue.numbers:
        line += ": " + ", ".join(issue.numbers)
    if issue.same_as is not None:
        line += f": the same as trade {issue.same_as + 1}"
    return line


def _joined(lines: list[str]) -> str:
    return "\n".join(lines)
