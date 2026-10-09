"""The Record page: the chat on the left; on the right the table, Save, and Export under it.

Streamlit runs this file, through the entry ``app.py``, every time the
person sends a message or presses a button on this page; what was sent or
pressed has been handed to the flows just before (``turns``), so the page
only draws what is kept (``session``).

When the program's parts cannot be built (a setting refused, or a machine
zone without a name the program takes), the page says why and shows
nothing else; the Settings page still opens.

Names defined here: ``main``.
"""

from __future__ import annotations

import streamlit as st

from ledger_hand.ui import chat, export_panel, preview, sayings, session
from ledger_hand.wiring import AssemblyError


def main() -> None:
    """Draw the page."""
    try:
        parts = session.parts()
    except AssemblyError as error:
        st.error(sayings.assembly_failed(error))
        return
    talk, table = st.columns([1, 2], gap="large")
    with talk:
        chat.draw()
    with table:
        st.subheader("What will be recorded")
        preview.draw(session.progress())
        export_panel.draw(parts)


main()
