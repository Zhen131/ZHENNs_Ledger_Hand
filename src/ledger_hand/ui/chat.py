"""The chat: every message so far, and the one input that takes a passage or an answer.

The person's messages are shown exactly as typed, and the program's as its
words were put (``sayings``); both as plain text, never as Markdown. The
input under them takes a new passage while nothing is being recorded and the
answer while a question waits; what it is taken as is decided where it goes
(``turns``), from the flow's progress. The chat lasts as long as the browser
tab; it is never written to disk.

Names defined here: ``INPUT_KEY``, ``LOG_KEY`` and ``draw``.
"""

from __future__ import annotations

import streamlit as st

from ledger_hand.ui import session, turns

INPUT_KEY = "chat_input"
LOG_KEY = "chat_log"
_EXAMPLE = "Type a trade, for example: Bought 0.02 BTC at 94,900 yesterday"


def draw() -> None:
    """Show the chat so far and the input under it."""
    with st.container(height=560, key=LOG_KEY, autoscroll=True):
        lines = session.chat()
        if not lines:
            st.caption(f"{_EXAMPLE}.")
        for line in lines:
            with st.chat_message(line.speaker.value):
                st.text(line.text)
    st.chat_input(
        "Type a trade, or answer the question",
        key=INPUT_KEY,
        on_submit=turns.take_typed,
        args=(INPUT_KEY,),
    )
