"""A passage in the form it is compared in, to tell whether it was saved before.

Two passages count as the same when they differ only in what a person does
not mean to change: whitespace at either end, how many whitespace characters
stand together, and whether a character is written full width or half width
(``０．５`` and ``0.5``, ``ＢＴＣ`` and ``BTC``, the ideographic space and the
ordinary one). Everything else counts: letter case, punctuation other than
its width, and whether whitespace is there at all (``买了0.5`` and ``买了 0.5``
are told apart).

Only characters that Unicode itself calls full width or half width are
folded, each to its ordinary form; other compatibility characters, such as
superscripts or circled digits, are kept as they are.

This module only rewrites text. It makes no fingerprint and decides nothing:
the flows turn this form into a fingerprint and say what follows from a
match.

Names defined here: ``comparison_form``.
"""

from __future__ import annotations

import unicodedata

# What Unicode calls full width and half width: the forms of other characters
# that differ from them only in the space they take up.
_WIDTH_FORMS = frozenset({"F", "H"})


def comparison_form(passage: str) -> str:
    """``passage`` with width folded, each run of whitespace one space, and none around it."""
    folded = "".join(
        unicodedata.normalize("NFKC", character)
        if unicodedata.east_asian_width(character) in _WIDTH_FORMS
        else character
        for character in passage
    )
    return " ".join(folded.split())
