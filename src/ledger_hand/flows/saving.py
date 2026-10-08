"""Saving a passage: the final records of a recorded passage, kept in the book.

``save`` takes a ``Progress`` whose records are final (its stage is
``DONE``), the book (a storage port) and the current moment. Each record
becomes a saved trade with a new identifier (``identifiers``), created and
last changed at that moment; the coins the user confirmed that these trades
use are kept with them, and the passage's fingerprint with them too, so that
the same passage is recognised when it comes again. All of it is saved in
one go, or none of it. A passage with no record left saves nothing and does
not touch the book.

Saving is only ever done when the person asked for it. Nothing here asks;
that is for the command line or the interface.

Names defined here: ``save`` and ``Saved``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ledger_hand.core.book import ConfirmedCoin, PassageSave
from ledger_hand.core.stored import StoredTrade
from ledger_hand.flows.coin_book import coins_to_keep
from ledger_hand.flows.fingerprint import passage_fingerprint
from ledger_hand.flows.identifiers import new_identifier
from ledger_hand.flows.progress import Progress, Stage
from ledger_hand.ports import StoragePort


@dataclass(frozen=True)
class Saved:
    """What was saved: the trades as the book keeps them, and the coins kept with them."""

    trades: tuple[StoredTrade, ...]
    coins: tuple[ConfirmedCoin, ...]


def save(progress: Progress, book: StoragePort, *, now: datetime) -> Saved:
    """Keep the final records of ``progress`` in ``book``, as saved at ``now``.

    Raises ``ValueError`` when the records are not final yet or ``now``
    carries no offset, and the book's ``StorageError`` when it fails; then
    nothing is saved.
    """
    if progress.stage is not Stage.DONE:
        raise ValueError(f"only final records are saved: {progress.stage.value}")
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ValueError("the current moment must be a datetime that carries an offset")
    records = progress.records
    if not records:
        return Saved((), ())
    trades = tuple(
        StoredTrade(id=new_identifier(), record=record, created_at=now, updated_at=now)
        for record in records
    )
    coins = coins_to_keep(records, progress.setting.coins, now)
    passage = PassageSave(
        fingerprint=passage_fingerprint(progress.passage),
        saved_at=now,
        trades=trades,
        coins=coins,
    )
    return Saved(book.save(passage), coins)
