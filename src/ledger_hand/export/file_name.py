"""The name of an export file.

The name says three things: which program wrote the file, that it holds only
some trades (``incremental``) and not a whole ledger, and when it was
exported, in UTC to the second. It follows the shape of the ledger's own
backup names and carries the same backup format version, so the two sort
side by side and are still told apart.

The word ``incremental`` matters: the ledger's present import replaces the
whole ledger with what the file holds, and a file of a few new trades must
never be mistaken for a full backup.

Names defined here: ``backup_file_name``.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ledger_hand.export.backup import BACKUP_FORMAT_VERSION


def backup_file_name(exported_at: datetime) -> str:
    """For example ``ledger-hand-incremental-backup-v3-20261004-080000Z.json``.

    ``exported_at`` must carry an offset; ``ValueError`` otherwise.
    """
    if exported_at.utcoffset() is None:
        raise ValueError("the export moment needs a time zone offset")
    try:
        at = exported_at.astimezone(timezone.utc)
    except OverflowError as error:
        raise ValueError(f"{exported_at.isoformat()} cannot be written in UTC") from error
    stamp = f"{at.year:04}{at.month:02}{at.day:02}-{at.hour:02}{at.minute:02}{at.second:02}Z"
    return f"ledger-hand-incremental-backup-v{BACKUP_FORMAT_VERSION}-{stamp}.json"
