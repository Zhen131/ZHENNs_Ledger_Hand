"""What the program says in the chat, and the hint beside Save, put in words from the progress.

Every message is read off a ``Progress`` the flows handed back, or off what
a flow gave back (the trades saved, the book's error): the question with the
flow's label, its notes and choices, and why it is asked again; why a
passage was stopped, with the passage's own words; what was set aside and
the reminders of extraction; why nothing was sent or nothing could be done;
what became of the passage. Nothing here works out anything about a trade;
it only chooses the words to show for what the flow says.

The words are plain text: the chat shows them without Markdown, so a
passage's own words come back exactly as typed.

Names defined here: ``after_start``, ``after_answer``, ``after_removing``,
``not_taken_yet``, ``saved``, ``not_saved``, ``book_failed``,
``assembly_failed`` and ``save_hint``.
"""

from __future__ import annotations

from ledger_hand.extraction.issues import Issue
from ledger_hand.extraction.screening import REASONS, Report
from ledger_hand.flows.progress import Progress, Stage, TradeStatus
from ledger_hand.ports import StorageError
from ledger_hand.wiring import AssemblyError

_INDENT = "    "


def after_start(progress: Progress) -> str:
    """What is said once a passage is taken: what was set aside, reminders, where it stands."""
    lines = [f"Set aside, not recorded: {_report(report)}" for report in progress.set_aside]
    lines += [f"Reminder: {_issue(issue)}" for issue in progress.reminders]
    return _joined([*lines, *_where_it_stands(progress)])


def after_answer(progress: Progress) -> str:
    """What is said once an answer has been read: why it is asked again, or what comes next."""
    question = progress.question
    if progress.stage is Stage.ASKING and question is not None and question.again is not None:
        return _joined([f"That answer could not be used: {question.again}.", *_asking(progress)])
    return _joined(_where_it_stands(progress))


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
    return f"Nothing was saved: the book could not be used ({error}). Try Save again."


def book_failed(error: StorageError) -> str:
    """What is said when the book could not be read before a passage was taken."""
    return f"The passage was not taken: the book could not be used ({error})."


def assembly_failed(error: AssemblyError) -> str:
    """What the page says when the program's parts could not be built."""
    return f"The program cannot start: {error}."


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


def _where_it_stands(progress: Progress) -> list[str]:
    stage = progress.stage
    if stage is Stage.ASKING:
        return _asking(progress)
    if stage is Stage.REVIEWING:
        return _settled(progress)
    if stage is Stage.STOPPED:
        lines = ["Nothing from this passage will be recorded:"]
        return lines + [f"{_INDENT}{_report(report)}" for report in progress.stopped]
    if stage is Stage.REFUSED and progress.refused is not None:
        return [f"Nothing was sent to the model: {progress.refused.value}."]
    if stage is Stage.FAILED and progress.failure is not None:
        return [
            f"The model gave no usable reply while {progress.failure.step.value}, so nothing "
            "was recorded. Check that the model server is running, then type the passage again."
        ]
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
