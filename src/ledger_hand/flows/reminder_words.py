"""One reminder of extraction, said in the program's own words, the same on every page.

A reminder (``Progress.reminders``) is an issue extraction raised that the
user should keep in mind: a caution on a number or a time, a unit that is
not the one its field is in, a row left out, numbers no trade used. The
Record page says each one before Save, and the assistant says each one
once recording ends; both take the words from here, so they never drift
apart.

``reminder_text`` gives one line without its "Reminder: " lead: which
trade and which field it is about, what kind it is, the core's reason, the
phrase or unit as written, the numbers no trade used and the trade it
repeats. It works nothing out about the trade.

Why it lives here: the words were the Record page's own, and the assistant
needs the same ones, but ``flows/`` may not import ``ui/``. So the one
function moved here, word for word (2026-11-25).

Names defined here: ``reminder_text``.
"""

from __future__ import annotations

from ledger_hand.extraction.issues import Issue


def reminder_text(issue: Issue) -> str:
    """What ``issue`` reminds of, for example ``trade 1, quantity: … 'U'``."""
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
