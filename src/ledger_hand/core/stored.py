"""A trade as it is kept: a finished record with its identifier and two moments.

A ``StoredTrade`` is a ``TradeRecord`` that has been saved. Saving gives it
three things the record itself does not have: an identifier, the moment it
was created and the moment it was last changed. All three are handed in by
whoever saves it. Nothing here makes up an identifier or reads the clock.

Both moments must carry an offset and must fall within the years 1 to 9999
once moved to UTC, which is how they are written; and the change cannot come
before the creation. They are compared as instants, whatever zone they are
given in.

Whether an identifier suits the ledger (its length, no surrounding
whitespace, no other entry in the same file using it) is not decided here. It
is decided where a file is written, because that is where the ledger's rules
apply and where every other identifier in the file is known.

Names defined here: ``StoredTrade``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from ledger_hand.core.trade import TradeRecord


@dataclass(frozen=True, kw_only=True)
class StoredTrade:
    """A saved trade: its identifier, the record, and when it was created and last changed."""

    id: str
    record: TradeRecord
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.id, str):
            raise TypeError(f"an identifier is text, not {type(self.id).__name__}")
        if not isinstance(self.record, TradeRecord):
            raise TypeError(f"a stored trade holds a TradeRecord, not {type(self.record).__name__}")
        created = _in_utc("created_at", self.created_at)
        updated = _in_utc("updated_at", self.updated_at)
        # In UTC: two moments that share one zone object would otherwise be
        # compared by their wall clocks, which mixes up the hour that repeats
        # when the clocks go back.
        if updated < created:
            raise ValueError("a trade cannot have been changed before it was created")


def _in_utc(name: str, moment: object) -> datetime:
    """``moment`` in UTC; refused unless it is a datetime with an offset that UTC can hold."""
    if not isinstance(moment, datetime):
        raise TypeError(f"{name} must be a datetime, not {type(moment).__name__}")
    if moment.utcoffset() is None:
        raise ValueError(f"{name} must carry a time zone offset")
    try:
        return moment.astimezone(timezone.utc)
    except OverflowError as error:
        # The first hours of the year 1 east of UTC, or the last of 9999 west of it.
        raise ValueError(f"{name} falls outside the years UTC can hold") from error
