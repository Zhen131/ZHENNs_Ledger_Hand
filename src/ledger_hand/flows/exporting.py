"""Exporting: the saved trades not exported yet, written as one file the ledger can import.

``export`` takes the book (a storage port), the folder export files go into,
the current moment and the time zone of the person exporting. In order:

1. The trades not exported yet are read from the book. With none, there is
   nothing new to export, and nothing is written.
2. The file's text is made by ``export.backup.export_backup``, from those
   trades and the coin table with the coins the user confirmed and saved.
   The export moment is the current moment, and today is the current
   moment's date in the person's time zone, the same today the ledger is to
   be given. When the export refuses, every reason is handed back and
   nothing is written.
3. The text is written to a new file named by ``export.file_name``, with the
   word ``incremental`` in it (``export_file``). A file of that name that is
   already there is never replaced: then nothing is marked.
4. Only once the file is there are its trades marked as exported, at the
   export moment.

A file and the book cannot be changed together in one step. If the marking
fails after the file was written, the file is there and its trades are not
marked: the next export writes them again, which the person can see. The
other way round, trades marked but no file, would lose them, and the order
above rules it out.

Names defined here: ``export``, ``ExportOutcome``, ``ExportResult`` and
``APP_NAME``.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ledger_hand import __version__
from ledger_hand.core.book import ExportMark, Listing
from ledger_hand.core.coins import BUILT_IN_TABLE, CoinTable
from ledger_hand.core.zones import is_zone_name, zone_named
from ledger_hand.export.backup import ExportIssue, ExportRefused, export_backup
from ledger_hand.export.file_name import backup_file_name
from ledger_hand.flows.coin_book import with_confirmed_coins
from ledger_hand.flows.export_file import NotWritten, WriteProblem, write_new_file
from ledger_hand.ports import StorageError, StoragePort

# The program's name as an export file records it, beside its version.
APP_NAME = "ledger-hand"


class ExportResult(enum.Enum):
    """How an export ended; the value says it in words."""

    EXPORTED = "the file was written and its trades are marked as exported"
    NOTHING_NEW = "there is nothing new to export; no file was written"
    REFUSED = "the trades cannot be exported as they are; no file was written"
    NOT_WRITTEN = "the file could not be written; nothing was marked"
    NOT_MARKED = (
        "the file was written, but its trades could not be marked as exported; "
        "the next export will write them again"
    )


@dataclass(frozen=True)
class ExportOutcome:
    """How an export ended, and what goes with it.

    ``path`` is the file written (``EXPORTED``, ``NOT_MARKED``);
    ``identifiers`` the trades in it; ``issues`` every reason for a
    refusal; ``problem`` and ``detail`` why the file was not written; and
    ``error`` the book's failure when the marking failed.
    """

    result: ExportResult
    path: Path | None = None
    identifiers: tuple[str, ...] = ()
    issues: tuple[ExportIssue, ...] = ()
    problem: WriteProblem | None = None
    detail: str | None = None
    error: StorageError | None = None


def export(
    book: StoragePort,
    folder: Path,
    *,
    now: datetime,
    zone: str,
    coins: CoinTable = BUILT_IN_TABLE,
    app_name: str = APP_NAME,
    app_version: str = __version__,
) -> ExportOutcome:
    """Export the trades of ``book`` not exported yet into a new file in ``folder``.

    Raises ``ValueError`` when ``now`` carries no offset or ``zone`` is not
    a time zone name, and the book's ``StorageError`` when reading the book
    fails; then nothing is written and nothing marked.
    """
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ValueError("the current moment must be a datetime that carries an offset")
    if not is_zone_name(zone):
        raise ValueError(f"not a time zone name: {zone!r}")
    pending = book.trades(Listing.NOT_EXPORTED)
    if not pending:
        return ExportOutcome(ExportResult.NOTHING_NEW)
    trades = tuple(listed.trade for listed in pending)
    text = export_backup(
        trades,
        with_confirmed_coins(coins, book.confirmed_coins()),
        exported_at=now,
        today=now.astimezone(zone_named(zone)).date(),
        app_name=app_name,
        app_version=app_version,
    )
    if isinstance(text, ExportRefused):
        return ExportOutcome(ExportResult.REFUSED, issues=text.issues)
    identifiers = tuple(trade.id for trade in trades)
    written = write_new_file(folder, backup_file_name(now), text)
    if isinstance(written, NotWritten):
        return ExportOutcome(
            ExportResult.NOT_WRITTEN, problem=written.problem, detail=written.detail
        )
    try:
        book.mark_exported(ExportMark(identifiers=identifiers, exported_at=now))
    except StorageError as error:
        return ExportOutcome(
            ExportResult.NOT_MARKED, path=written, identifiers=identifiers, error=error
        )
    return ExportOutcome(ExportResult.EXPORTED, path=written, identifiers=identifiers)
