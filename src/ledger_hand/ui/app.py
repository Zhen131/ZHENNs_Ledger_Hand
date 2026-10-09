"""The interface's page, the file Streamlit runs: the chat on the left, the table on the right.

    streamlit run src/ledger_hand/ui/app.py

Run it from the top of the repository, where Streamlit finds its settings
(``.streamlit/config.toml``: no usage statistics, this machine only, no
questions at the terminal), then open http://127.0.0.1:8501. Streamlit runs
this file from the top every time the person sends a message or presses a
button; what was sent or pressed has been handed to the flows just before
(``turns``), so the page only draws what is kept (``session``).

When the program's parts cannot be built (a setting refused, or a machine
zone without a name the program takes), the page says why and shows
nothing else.

Names defined here: ``main``.
"""

from __future__ import annotations

import streamlit as st

from ledger_hand.ui import chat, preview, sayings, session
from ledger_hand.wiring import AssemblyError

TITLE = "Ledger Hand"


def main() -> None:
    """Draw the page."""
    st.set_page_config(page_title=TITLE, layout="wide")
    st.title(TITLE)
    try:
        session.parts()
    except AssemblyError as error:
        st.error(sayings.assembly_failed(error))
        return
    talk, table = st.columns([2, 3], gap="large")
    with talk:
        chat.draw()
    with table:
        st.subheader("What will be recorded")
        preview.draw(session.progress())


main()
