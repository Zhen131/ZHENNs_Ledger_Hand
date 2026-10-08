"""The fingerprint of a passage: the one place it is worked out.

A passage saved before is recognised by its fingerprint: the SHA-256 digest
of its comparison form (``core.passage_form``), written as ``sha256:`` and
the digest in hexadecimal. Two passages that differ only in spacing or in
the width of their characters have the same fingerprint; any other
difference gives another one. The passage itself is kept in the trades; the
fingerprint only stands for it when passages are compared.

Names defined here: ``passage_fingerprint``.
"""

from __future__ import annotations

import hashlib

from ledger_hand.core.passage_form import comparison_form

_ALGORITHM = "sha256"


def passage_fingerprint(passage: str) -> str:
    """For example ``sha256:3f0a…``, 71 characters in all."""
    # A passage that is not valid Unicode is still given a fingerprint, so
    # that the check that refuses it can say why.
    form = comparison_form(passage).encode("utf-8", "surrogatepass")
    return f"{_ALGORITHM}:{hashlib.sha256(form).hexdigest()}"
