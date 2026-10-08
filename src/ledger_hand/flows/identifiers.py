"""A new identifier for a trade being saved.

``hand-`` and a random UUID (version 4): unique without asking the book or
any other file, never reused, and so never the same as an identifier the
ledger already holds from somewhere else. It is made from random numbers
only, never from the clock (a version 1 UUID would read it), and keeps the
ledger's rules: 41 characters, far below the ledger's limit, with no
whitespace at either end.

Names defined here: ``IDENTIFIER_PREFIX`` and ``new_identifier``.
"""

from __future__ import annotations

import uuid

IDENTIFIER_PREFIX = "hand-"


def new_identifier() -> str:
    """For example ``hand-3f6c1e2a-9b7d-4c58-a1e0-5d2b8f4c7a93``."""
    return f"{IDENTIFIER_PREFIX}{uuid.uuid4()}"
