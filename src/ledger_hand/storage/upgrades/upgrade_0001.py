"""Upgrade 1: an empty file becomes a book of version 1.

Three tables:

- ``passages``: one row for each save of the trades of one passage: the
  passage's fingerprint and the moment of saving.
- ``trades``: one row for each saved trade: every field of the record, its
  identifier, the moments it was created and last changed, the passage it
  came from, and the moment it was exported, empty until it is.
- ``confirmed_coins``: each coin symbol the user confirmed, with the moment it
  was first saved.

Numbers are kept as the ledger writes them and times as the ledger writes
them, as text: never as floating-point numbers. Bookkeeping moments are kept
in UTC, to the microsecond. ``place`` keeps the order rows were saved in.
The tables are strict, so a value of the wrong type is refused.

Never changed once committed.
"""

NUMBER = 1

STATEMENTS = (
    """CREATE TABLE passages (
    place INTEGER PRIMARY KEY,
    fingerprint TEXT NOT NULL,
    saved_at TEXT NOT NULL
) STRICT""",
    "CREATE INDEX passages_by_fingerprint ON passages (fingerprint)",
    """CREATE TABLE trades (
    place INTEGER PRIMARY KEY,
    id TEXT NOT NULL UNIQUE,
    passage INTEGER NOT NULL REFERENCES passages (place),
    side TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
    coin TEXT NOT NULL,
    quantity TEXT NOT NULL,
    price TEXT NOT NULL,
    total TEXT NOT NULL,
    derived TEXT CHECK (derived IN ('quantity', 'price', 'total')),
    fee TEXT NOT NULL,
    fee_coin TEXT NOT NULL,
    occurred TEXT NOT NULL,
    time_precision TEXT NOT NULL CHECK (time_precision IN ('day', 'minute', 'second')),
    time_zone TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    platform TEXT,
    note TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    exported_at TEXT
) STRICT""",
    "CREATE INDEX trades_by_passage ON trades (passage)",
    """CREATE TABLE confirmed_coins (
    symbol TEXT PRIMARY KEY NOT NULL,
    confirmed_at TEXT NOT NULL
) STRICT""",
)
