"""The numbered upgrade scripts of the book, in order, each one step from a version to the next.

Upgrade ``n`` turns a book of version ``n - 1`` into one of version ``n``; the
first one turns an empty file into a book of version 1. They run in order,
each in a transaction of its own. A script is never changed once committed:
a book written by it may be anywhere. A change to the tables is a new script
with the next number, added to ``UPGRADES``, and a new golden sample of the
version it makes.

Each script is a module ``upgrade_NNNN.py`` holding ``NUMBER`` and
``STATEMENTS``, the SQL statements it runs. Setting the book's version, and
the mark that says the file is this program's book, is done by whoever runs
them (``book_file``), not by the scripts.

Names defined here: ``Upgrade`` and ``UPGRADES``.
"""

from __future__ import annotations

from dataclasses import dataclass

from ledger_hand.storage.upgrades import upgrade_0001


@dataclass(frozen=True)
class Upgrade:
    """One step: the version it makes, and the statements that make it."""

    number: int
    statements: tuple[str, ...]


UPGRADES: tuple[Upgrade, ...] = (Upgrade(upgrade_0001.NUMBER, upgrade_0001.STATEMENTS),)
