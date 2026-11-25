"""What the pages say about the assistant's record on this machine, in fixed words.

The record is a plain text file in the data folder (``flows.assistant_record``).
The assistant page says, under a reply, when that reply was not kept in it
and why; the settings page says where the file is, what it holds, how many
entries it holds, and when it cannot be read, why.

- ``PROBLEMS``: one sentence for every ``RecordProblem``; a test walks the
  enumeration, so a new problem cannot go without one.
- ``not_kept_words``: under a reply, when nothing was added. A missing data
  folder is said plainly as "no record this time"; every other reason says
  that the thing said was still done, and where to look.
- ``PLAIN_TEXT``: what the file holds, said on the settings page.
- ``count_words``: how many entries, or why they cannot be read.

Names defined here: ``PROBLEMS``, ``PLAIN_TEXT``, ``NO_RECORD``,
``not_kept_words``, ``unreadable_words`` and ``count_words``.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from ledger_hand.flows.assistant_record import (
    KEPT_AT_MOST,
    NotKept,
    RecordProblem,
    RecordRead,
    Unreadable,
)

PROBLEMS: Mapping[RecordProblem, str] = MappingProxyType(
    {
        RecordProblem.NEWER_VERSION: (
            "the record file was written by a newer version of this program, so this one "
            "leaves it as it is"
        ),
        RecordProblem.LINE_NOT_READ: (
            "a line of the record file cannot be read, so the file is left as it is"
        ),
        RecordProblem.CANNOT_READ: "the record file cannot be read",
        RecordProblem.CANNOT_WRITE: "the record file cannot be written",
        RecordProblem.NO_DATA_FOLDER: "these parts were handed in without a data folder",
    }
)

PLAIN_TEXT = (
    "Plain text, not encrypted: it holds what you said to the assistant, word for word, "
    "with its numbers, and what came of it. It stays on this computer; it is not in Git "
    "and not in the book of the Record page."
)

NO_RECORD = "No record this time: these parts have no data folder, so nothing was kept."


def not_kept_words(not_kept: NotKept) -> str:
    """What the assistant page says under a reply that was not kept in the record."""
    if not_kept.problem is RecordProblem.NO_DATA_FOLDER:
        return NO_RECORD
    detail = f" ({not_kept.detail})" if not_kept.detail else ""
    return (
        "This was done, but it was not kept in the assistant's record: "
        f"{PROBLEMS[not_kept.problem]}{detail}. The Settings page shows the file and can "
        "clear it."
    )


def unreadable_words(unreadable: Unreadable) -> str:
    """Why the record cannot be read, in one line."""
    return f"{PROBLEMS[unreadable.problem]} ({unreadable.detail})"


def count_words(read: RecordRead | Unreadable) -> str:
    """How many entries the record holds, or that it cannot be read and why."""
    if isinstance(read, Unreadable):
        return f"Entries: cannot be read: {unreadable_words(read)}."
    count = len(read.entries)
    if count == 0:
        return f"Entries: none yet. The most recent {KEPT_AT_MOST:,} are kept."
    plural = "entry" if count == 1 else "entries"
    return f"Entries: {count:,} {plural}. The most recent {KEPT_AT_MOST:,} are kept."
