"""The Export button, the warning that always stands beside it, and what became of the last export.

Export writes the saved trades not exported yet into a new file in the
exports folder and marks them as exported (``turns.export_saved``); the page
then says where the file is and how many trades it holds, that there was
nothing new, or why nothing was written or marked. Beside the button, always
and in red, the page says that the file must not be imported into the ledger
yet: the ledger's import replaces the whole ledger with what the file holds.

Names defined here: ``EXPORT_KEY``, ``WARNING_KEY``, ``RESULT_KEY``,
``WARNING`` and ``draw``.
"""

from __future__ import annotations

import streamlit as st

from ledger_hand.ui import notes, session, turns
from ledger_hand.ui.session import Place
from ledger_hand.wiring import Parts

EXPORT_KEY = "export_button"
WARNING_KEY = "export_warning"
RESULT_KEY = "export_result"
WARNING = (
    "Do not import this file into the ledger yet: the ledger's import replaces the whole "
    "ledger with what the file holds, which would leave it with these trades only."
)


def draw(parts: Parts) -> None:
    """Show Export, the warning beside it, and the last export's outcome."""
    st.subheader("Export")
    st.button(
        "Export",
        key=EXPORT_KEY,
        disabled=parts.places is None,
        on_click=turns.export_saved,
        help="Writes the saved trades not exported yet into a new file and marks them.",
    )
    with st.container(key=WARNING_KEY):
        st.markdown(f":red[{WARNING}]")
    notes.draw(session.note(Place.EXPORT), RESULT_KEY)
