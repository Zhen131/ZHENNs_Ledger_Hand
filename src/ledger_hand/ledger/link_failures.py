"""Link failures: how starting or talking to the ledger's assistant link can fail, and the token.

The assistant link is the small Node.js program in the ledger's own folder
that passes tool calls to the ledger page (``link_client``). Every way of
failing to start it or to hear from it is one ``LinkFailure``, whose value
is the plain sentence said about it; ``LedgerLinkError`` carries one of
them and, in ``detail``, what was seen (a version number, the link's own
line of English). Neither ever holds the token.

``LinkToken`` keeps the token the link and the ledger page share. Printing
it, or anything holding it, shows a placeholder; ``reveal`` gives the value
to the one place that hands it to the link, and to the interface that shows
it to the person.

This module only names things. It starts nothing and reads nothing.

Names defined here: ``LinkFailure``, ``LedgerLinkError``, ``LinkToken``,
``TOKEN_MIN_LENGTH``.
"""

from __future__ import annotations

import enum
import re

# The ledger's rule for a token it is handed (assistant-link/README.md in the
# ledger, "The token"): at least 32 characters of A-Z, a-z, 0-9, "-", "_".
TOKEN_MIN_LENGTH = 32
_TOKEN_CHARACTERS = re.compile(r"[A-Za-z0-9_-]+")


class LinkFailure(enum.Enum):
    """Why the assistant link could not be started or answered nothing usable."""

    NODE_MISSING = "Node.js was not found, so the ledger's assistant link cannot start."
    NODE_TOO_OLD = "Node.js is older than the ledger needs, so its assistant link cannot start."
    LEDGER_FOLDER_WRONG = (
        "The folder named as the ledger's is not a ledger with its programs installed."
    )
    PORT_IN_USE = "The port the assistant link listens on is already used by another program."
    CANNOT_START = "The ledger's assistant link did not start."
    HANDSHAKE_REFUSED = "The ledger's assistant link refused this program's name or version."
    CALL_REFUSED = "The ledger's assistant link refused the call before the ledger saw it."
    TIMED_OUT = "The ledger's assistant link did not answer in time."
    LINK_GONE = "The ledger's assistant link stopped before it answered."
    REPLY_NOT_JSON = "The ledger's assistant link answered something that is not JSON."
    REPLY_UNEXPECTED = "The ledger's assistant link answered in a shape this program does not know."
    NOT_STARTED = "The ledger's assistant link is not running."


class LedgerLinkError(Exception):
    """The link failed as ``failure`` says; ``detail`` is what was seen, never the token."""

    def __init__(self, failure: LinkFailure, detail: str = "") -> None:
        self.failure = failure
        self.detail = detail
        super().__init__(f"{failure.value} {detail}".strip())


class LinkToken:
    """The token the link and the ledger page share. Printing it shows a placeholder."""

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        if len(value) < TOKEN_MIN_LENGTH or not _TOKEN_CHARACTERS.fullmatch(value):
            raise ValueError(
                f"a link token is at least {TOKEN_MIN_LENGTH} characters of "
                "A-Z, a-z, 0-9, '-' or '_'"
            )
        self._value = value

    def reveal(self) -> str:
        """The token itself, for the link's environment and for showing to the person."""
        return self._value

    def hide_in(self, text: str) -> str:
        """``text`` with every copy of the token replaced by a placeholder."""
        return text.replace(self._value, "<token>")

    def __repr__(self) -> str:
        return "LinkToken('<hidden>')"

    def __str__(self) -> str:
        return "<hidden>"
