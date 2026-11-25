"""The settings page's part on the assistant's record: where it is, what it holds, how to clear it.

Drawn under the rest of the settings page, and only once the parts are
built. It says which file the record is, that it is plain text holding
what the person said to the assistant, word for word, with its numbers,
kept on this computer only, and how many entries it holds now; when the
file cannot be read, it says so and why (``assistant_record_words``).
Reading it changes nothing.

Clearing takes two presses: "Clear the assistant's record" asks first,
and only "Yes, delete the record" deletes the file
(``assistant_record.clear_record``); "Keep it" asks no more. A file this
program cannot read can be cleared too, and the question then says that
once deleted it is gone. Nothing here is drawn as an error box: none of it
stops the program.

Names defined here: ``RECORD_KEY``, ``CLEAR_KEY``, ``CONFIRM_KEY``,
``KEEP_KEY`` and ``draw``.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from ledger_hand.flows.assistant_record import (
    Cleared,
    RecordRead,
    Unreadable,
    clear_record,
    read_record,
)
from ledger_hand.settings import DataPlaces
from ledger_hand.ui.assistant_record_words import PLAIN_TEXT, count_words

RECORD_KEY = "settings_assistant_record"
CLEAR_KEY = "settings_record_clear"
CONFIRM_KEY = "settings_record_confirm"
KEEP_KEY = "settings_record_keep"
_ASKING_KEY = "ledger_hand.settings.record_clear_asked"
_DONE_KEY = "ledger_hand.settings.record_clear_done"


def draw(places: DataPlaces | None) -> None:
    """Draw the part on the assistant's record kept where ``places`` say."""
    with st.container(key=RECORD_KEY):
        st.subheader("The assistant's record")
        if places is None:
            st.text(
                "None: these parts were handed in without a data folder, so the assistant "
                "keeps no record."
            )
            return
        place = places.assistant_record
        st.text(f"File: {place}")
        st.caption(PLAIN_TEXT)
        read = read_record(place)
        st.text(count_words(read))
        done = st.session_state.pop(_DONE_KEY, None)
        if done is not None:
            st.text(str(done))
        _clearing(place, read)


def _clearing(place: Path, read: RecordRead | Unreadable) -> None:
    there = isinstance(read, Unreadable) or bool(read.entries) or read.cut_line
    if not st.session_state.get(_ASKING_KEY, False):
        st.button(
            "Clear the assistant's record",
            key=CLEAR_KEY,
            on_click=_ask,
            disabled=not there,
            help="Asks first; nothing is deleted by this press.",
        )
        return
    question = f"Delete {place}? It cannot be undone."
    if isinstance(read, Unreadable):
        question += " This version of the program cannot read this file; once deleted it is gone."
    st.text(question)
    with st.container(horizontal=True):
        st.button("Yes, delete the record", key=CONFIRM_KEY, on_click=_clear, args=(place,))
        st.button("Keep it", key=KEEP_KEY, on_click=_keep)


def _ask() -> None:
    st.session_state[_ASKING_KEY] = True


def _keep() -> None:
    st.session_state[_ASKING_KEY] = False


def _clear(place: Path) -> None:
    st.session_state[_ASKING_KEY] = False
    try:
        cleared = clear_record(place)
    except OSError as error:
        st.session_state[_DONE_KEY] = (
            f"Not cleared: the record file could not be deleted ({error})."
        )
        return
    if cleared is Cleared.DELETED:
        st.session_state[_DONE_KEY] = "Cleared: the record file was deleted."
    else:
        st.session_state[_DONE_KEY] = "Nothing to clear: there was no record file."
