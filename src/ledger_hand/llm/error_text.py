"""Text for error messages: what a server sent, made safe to show.

What a server sends back, and what a failed connection says, can end up in
an error message that is printed. Before that happens it is cut short, every
character that is not printable is written as an escape (so a reply cannot,
for one, move the cursor or clear a terminal), and the key, if there is one,
is replaced by a placeholder wherever it occurs. The key is hidden before
the text is cut short, so that a key straddling the cut cannot leave half of
itself behind.

A server that repeats the key does not always repeat it as it was sent. It
may write it inside a JSON string, where a quote or a backslash gets a
backslash in front (twice over, when that JSON is itself put in a string),
any character may become ``\\uXXXX`` and a slash may become ``\\/``; in an
address, where characters become ``%XX`` in either case; or in an HTML
page, where ``&``, ``<``, ``>`` and quotes become entities, named or
numbered. So each character of the key is looked for in every one of these
ways, mixed as they come, and the whole match is hidden. Hiding a little
more than the key (a stray backslash in front of it, say) is the safe side.

This module only rewrites text. It decides nothing about kinds of failure.

Names defined here: ``SNIPPET_CHARACTERS``, ``DETAIL_CHARACTERS``,
``HIDDEN``, ``hide``, ``snippet``, ``detail``.
"""

from __future__ import annotations

import re

from ledger_hand.settings import Secret

# Enough of a reply to see what it was, short enough to read in one line.
SNIPPET_CHARACTERS = 200
# Enough of an error raised by the connection to see its cause.
DETAIL_CHARACTERS = 300
HIDDEN = "<hidden>"


# The names HTML gives the characters a key may hold; numbered entities are
# looked for for every character.
_HTML_NAMES = {
    "&": ("&amp;",),
    "<": ("&lt;",),
    ">": ("&gt;",),
    '"': ("&quot;",),
    "'": ("&apos;",),
}


def hide(text: str, secret: Secret | None) -> str:
    """``text`` with every occurrence of the secret, written in any of the known ways, hidden."""
    if secret is None or not secret.reveal():
        return text
    return _written_back(secret.reveal()).sub(HIDDEN, text)


def _written_back(value: str) -> re.Pattern[str]:
    """A pattern for ``value`` with each character written in any of the known ways."""
    return re.compile("".join(_one_character(character) for character in value))


def _one_character(character: str) -> str:
    code = ord(character)
    percent = "".join(f"%{byte:02x}" for byte in character.encode("utf-8", "surrogatepass"))
    ways = [
        re.escape(character),
        f"(?i:{re.escape(percent)})",
        f"&#0*{code};",
        f"(?i:&#x0*{code:x};)",
        *(re.escape(name) for name in _HTML_NAMES.get(character, ())),
    ]
    if code <= 0xFFFF:
        ways.append(rf"(?i:\\u{code:04x})")
    # Any run of backslashes in front: one for a JSON escape, more for JSON in JSON.
    return rf"\\*(?:{'|'.join(ways)})"


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
