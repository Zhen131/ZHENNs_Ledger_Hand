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
repeats. It works nothing out about the trade. With ``ledger`` (the
assistant, on the ledger's own asset table) the one kind whose words say
"coin" is said with "asset" instead (``LEDGER_KIND_WORDS``); the Record
page says every kind as it always has.

Why it lives here: the words were the Record page's own, and the assistant
needs the same ones, but ``flows/`` may not import ``ui/``. So the one
function moved here, word for word (2026-11-25).

Names defined here: ``reminder_text`` and ``LEDGER_KIND_WORDS``.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from ledger_hand.extraction.issues import Issue, IssueKind

# The kinds of reminder whose words say "coin", in words for the ledger's own table.
LEDGER_KIND_WORDS: Mapping[IssueKind, str] = MappingProxyType(
    {IssueKind.UNIT_NOT_THE_COIN: "the quantity carries a unit that is not the trade's asset"}
)


def reminder_text(issue: Issue, *, ledger: bool = False) -> str:
    """What ``issue`` reminds of, for example ``trade 1, quantity: … 'U'``."""
    where = "the passage" if issue.draft is None else f"trade {issue.draft + 1}"
    if issue.field is not None:
        where += f", {issue.field.value}"
    kind = LEDGER_KIND_WORDS.get(issue.kind, issue.kind.value) if ledger else issue.kind.value
    line = f"{where}: {kind}"
    if issue.cause is not None:
        line += f" ({issue.cause.value})"
    if issue.phrase is not None:
        line += f" '{issue.phrase}'"
    if issue.numbers:
        line += ": " + ", ".join(issue.numbers)
    if issue.same_as is not None:
        line += f": the same as trade {issue.same_as + 1}"
    return line
