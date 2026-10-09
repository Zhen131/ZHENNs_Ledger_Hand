"""Showing a note: the last word said after Export or on the settings page, in its tone.

Something done is shown as a success, nothing to do as information, and a
failure as an error. Streamlit draws these boxes from Markdown, and a note
holds paths, the names of settings and values as they were typed, so every
character Markdown would act on is escaped and the words come out as
written. Each line of the note stays a line of its own, and an indented
line, one of several reasons, is shown as an item.

Names defined here: ``draw`` and ``as_markdown``.
"""

from __future__ import annotations

import streamlit as st

from ledger_hand.ui.session import Note, Tone

_SHOW = {Tone.DONE: st.success, Tone.NOTHING: st.info, Tone.FAILED: st.error}
# What Markdown, and Streamlit's own additions to it, act on inside a line.
_ACTIVE = frozenset("\\`*_[]<>#$~|:")


def draw(note: Note | None, key: str) -> None:
    """Show ``note`` in a container under ``key``; nothing when there is none."""
    if note is None:
        return
    with st.container(key=key):
        _SHOW[note.tone](as_markdown(note.text))


def as_markdown(text: str) -> str:
    """``text`` as Markdown that shows exactly these words, line by line."""
    return "  \n".join(_line(line) for line in text.split("\n"))


def _line(line: str) -> str:
    escaped = "".join(f"\\{character}" if character in _ACTIVE else character for character in line)
    if line[:1].isspace():
        return f"• {escaped.lstrip()}"
    return escaped
