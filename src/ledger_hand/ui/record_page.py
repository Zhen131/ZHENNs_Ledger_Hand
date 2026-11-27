"""The Record page: the chat and the screenshot area on the left; the table, Save and Export right.

Streamlit runs this file, through the entry ``app.py``, every time the
person sends a message, uploads a file or presses a button on this page;
what was sent, uploaded or pressed has been handed to the flows just before
(``turns``), so the page only draws what is kept (``session``). The
screenshot area is under the chat (``screenshot_panel``).

With a cloud plug, a line at the top always says that every passage typed
is sent to the service (``cloud_notice``).

When the program's parts cannot be built (a setting refused, or a machine
zone without a name the program takes), the page says why and shows
nothing else; the Settings page still opens.

Names defined here: ``main``.
"""

from __future__ import annotations

import streamlit as st

from ledger_hand.ui import (
    chat,
    cloud_notice,
    export_panel,
    preview,
    sayings,
    screenshot_panel,
    session,
)
from ledger_hand.ui.cloud_notice import RECORD_NOTICE_KEY
from ledger_hand.wiring import AssemblyError


def main() -> None:
    """Draw the page."""
    try:
        parts = session.parts()
    except AssemblyError as error:
        st.error(sayings.assembly_failed(error))
        return
    cloud_notice.draw(cloud_notice.record_words(parts.settings), RECORD_NOTICE_KEY)
    talk, table = st.columns([1, 2], gap="large")
    with talk:
        chat.draw()
        screenshot_panel.draw(parts)
    with table:
        st.subheader("What will be recorded")
        preview.draw(session.progress())
        export_panel.draw(parts)


main()
