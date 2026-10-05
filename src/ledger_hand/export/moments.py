"""Bookkeeping moments written the way the ledger writes them.

A file records three moments that are not the time of a trade: when an entry
was created, when it was last changed, and when the file was exported. The
ledger writes these in UTC, with a ``T`` between date and time, and ends them
with ``Z``. This program writes them to the whole second, dropping any part
of a second, so that one moment is always written the same way.

The time of a trade is written by ``core.timeparse.write_time`` instead: it
keeps the trade's own offset, and may be a date alone.

Names defined here: ``write_moment``.
"""

from __future__ import annotations

from datetime import datetime, timezone


def write_moment(moment: datetime) -> str:
    """``moment`` in UTC, to the second, as in ``2026-10-04T07:41:00Z``.

    Raises ``ValueError`` for a moment without an offset, since which instant
    it means would depend on the machine, and for a moment whose UTC time
    falls outside the years 1 to 9999 (the first hour of the year 1 east of
    UTC, say), which cannot be written.
    """
    if moment.utcoffset() is None:
        raise ValueError("a moment needs a time zone offset")
    try:
        in_utc = moment.astimezone(timezone.utc)
    except OverflowError as error:
        raise ValueError(f"{moment.isoformat()} cannot be written in UTC") from error
    return f"{in_utc.replace(microsecond=0, tzinfo=None).isoformat()}Z"
