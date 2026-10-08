"""The check of a passage before it is sent to a model: empty, too long, or not valid text.

``passage_problem`` says why a passage must not be sent, or gives back
``None`` when it may be. A passage is refused when it is empty or holds only
whitespace, when it is longer than the ledger keeps as the original text of
a trade (measured the ledger's way), and when it holds a character that is
not valid Unicode text. Every step that sends the user's passage to a model
asks this one function, so that the steps never disagree about it.

Names defined here: ``PassageProblem`` and ``passage_problem``.
"""

from __future__ import annotations

import enum

from ledger_hand.core.ledger_limits import RAW_TEXT_MAX_LENGTH, text_length, trim


class PassageProblem(enum.Enum):
    """Why a passage was not sent to the model."""

    EMPTY = "the passage is empty"
    TOO_LONG = "the passage is longer than the ledger keeps as the original text"
    NOT_VALID_TEXT = "the passage holds a character that is not valid Unicode text"


def passage_problem(passage: str) -> PassageProblem | None:
    """Why ``passage`` must not be sent to a model, or ``None`` when it may be."""
    # Counted in characters first: a text with more characters than the limit
    # has more UTF-16 units too, and is turned away without being measured.
    if len(passage) > RAW_TEXT_MAX_LENGTH or text_length(passage) > RAW_TEXT_MAX_LENGTH:
        return PassageProblem.TOO_LONG
    if not trim(passage).strip():
        return PassageProblem.EMPTY
    try:
        passage.encode("utf-8")
    except UnicodeEncodeError:
        return PassageProblem.NOT_VALID_TEXT
    return None
