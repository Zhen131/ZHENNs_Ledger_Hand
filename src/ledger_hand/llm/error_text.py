"""Text for error messages: what a server sent, made safe to show.

What a server sends back, and what a failed connection says, can end up in
an error message that is printed. Before that happens it is cut short, every
character that is not printable is written as an escape (so a reply cannot,
for one, move the cursor or clear a terminal), and the key, if there is one,
is replaced by a placeholder wherever it occurs. The key is hidden before
the text is cut short, so that a key straddling the cut cannot leave half of
itself behind.

A server that repeats the key does not always repeat it as it was sent: it
may write it escaped as JSON (once or more), as ``\\uXXXX``, percent-encoded
or as HTML entities. ``key_forms`` finds the key in each of these ways, in
time that grows in step with the length of the text, and every stretch it
finds is hidden whole. Hiding a little more than the key (a stray backslash
in front of it, say) is the safe side.

This module only rewrites text. It decides nothing about kinds of failure.

Names defined here: ``SNIPPET_CHARACTERS``, ``DETAIL_CHARACTERS``,
``HIDDEN``, ``hide``, ``snippet``, ``detail``.
"""

from __future__ import annotations

from ledger_hand.llm.key_forms import key_spans
from ledger_hand.settings import Secret

# Enough of a reply to see what it was, short enough to read in one line.
SNIPPET_CHARACTERS = 200
# Enough of an error raised by the connection to see its cause.
DETAIL_CHARACTERS = 300
HIDDEN = "<hidden>"


def hide(text: str, secret: Secret | None) -> str:
    """``text`` with every occurrence of the secret, written in any of the known ways, hidden."""
    if secret is None or not secret.reveal():
        return text
    pieces: list[str] = []
    after = 0
    for begin, end in key_spans(text, secret.reveal()):
        pieces += [text[after:begin], HIDDEN]
        after = end
    pieces.append(text[after:])
    return "".join(pieces)


def snippet(body: bytes, secret: Secret | None) -> str | None:
    """The start of a reply's bytes, made safe to show; ``None`` when there were none."""
    if not body:
        return None
    return _shorten(hide(body.decode("utf-8", errors="replace"), secret), SNIPPET_CHARACTERS)


def detail(text: str, secret: Secret | None) -> str:
    """A message from the connection or a server, made safe to show."""
    return _shorten(hide(text, secret), DETAIL_CHARACTERS)


def _shorten(text: str, limit: int) -> str:
    cut = text[:limit]
    return _printable(cut) + ("..." if len(text) > limit else "")


def _printable(text: str) -> str:
    return "".join(
        character if character.isprintable() else _escape(character) for character in text
    )


def _escape(character: str) -> str:
    code = ord(character)
    if code <= 0xFF:
        return f"\\x{code:02x}"
    if code <= 0xFFFF:
        return f"\\u{code:04x}"
    return f"\\U{code:08x}"
