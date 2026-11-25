"""The block at the top of the assistant page: which ledger it reaches, and the assistant link.

The person chooses between the demo ledger and their own ledger page; the
choice takes at once, with no restart, and clears this tab's chat
(``assistant_ledger.switch``). The choice's control is offered the kept
choice before it is drawn, since Streamlit forgets a control's value while
another page is shown.

With the ledger page chosen, the block says where the one assistant link
stands (``assistant_link_words.STATE_WORDS``), read each time the page is
drawn, with Refresh to read it again, and holds Start and Stop. A start
that failed is said in a plain sentence with what to do. While the link
runs, it shows the port, the three steps to connect the ledger page, and
"Show token". The token is drawn only after "Show token" is pressed, as
read-only text that can be copied, and is not drawn at all once "Hide
token" is pressed: no password box, which would send it to the browser
whether shown or not, and it is never kept in the session. Without the
ledger's folder the block says what to set instead.

A setting of the first ledger that was refused is said here too: the tab
then starts with the demo ledger.

Names defined here: ``PANEL_KEY``, ``CHOICE_KEY``, ``START_KEY``, ``STOP_KEY``,
``LINK_REFRESH_KEY``, ``SHOW_TOKEN_KEY``, ``HIDE_TOKEN_KEY``, ``STATE_KEY``,
``TOKEN_KEY`` and ``draw``.
"""

from __future__ import annotations

import streamlit as st

from ledger_hand.ledger.link_keeper import LinkKeeper, LinkState
from ledger_hand.settings import AssistantLedger
from ledger_hand.ui import assistant_ledger, assistant_session
from ledger_hand.ui.assistant_link_words import (
    STATE_WORDS,
    THREE_STEPS,
    no_link,
    start_failed,
)
from ledger_hand.wiring import NoLink, Parts

PANEL_KEY = "assistant_link_panel"
CHOICE_KEY = "assistant_ledger_choice"
START_KEY = "assistant_link_start"
STOP_KEY = "assistant_link_stop"
LINK_REFRESH_KEY = "assistant_link_refresh"
SHOW_TOKEN_KEY = "assistant_link_show_token"
HIDE_TOKEN_KEY = "assistant_link_hide_token"
STATE_KEY = "assistant_link_state"
TOKEN_KEY = "assistant_link_token"

_CHOICE_LABELS = {
    AssistantLedger.DEMO: "The demo ledger (invented, in memory)",
    AssistantLedger.PAGE: "Your ledger page (your real ledger)",
}


def draw(parts: Parts) -> None:
    """Draw the block: the choice, and the link while the ledger page is chosen."""
    with st.container(key=PANEL_KEY):
        if parts.first_ledger_refused is not None:
            st.warning(
                f"{parts.first_ledger_refused}. The demo ledger is used first until it is "
                "corrected."
            )
        chosen = assistant_ledger.choice(parts)
        if assistant_session.value(CHOICE_KEY) is None:
            assistant_session.offer_value(CHOICE_KEY, chosen)
        st.radio(
            "Which ledger the assistant reaches",
            list(AssistantLedger),
            format_func=_CHOICE_LABELS.__getitem__,
            key=CHOICE_KEY,
            horizontal=True,
            on_change=assistant_ledger.switch,
            args=(CHOICE_KEY,),
        )
        if chosen is AssistantLedger.PAGE:
            _link(assistant_ledger.keeper())


def _link(found: LinkKeeper | NoLink) -> None:
    if isinstance(found, NoLink):
        st.warning(no_link(found))
        return
    state = found.state()
    running = state not in (LinkState.NOT_STARTED, LinkState.STOPPED)
    with st.container(key=STATE_KEY):
        st.text(f"Assistant link: {STATE_WORDS[state]}")
    failure = assistant_session.start_failure()
    if failure is not None and not running:
        st.warning(start_failed(failure))
    with st.container(horizontal=True):
        st.button("Start", key=START_KEY, on_click=assistant_ledger.start, disabled=running)
        st.button("Stop", key=STOP_KEY, on_click=assistant_ledger.stop, disabled=not running)
        st.button("Refresh", key=LINK_REFRESH_KEY, help="Reads again where the link stands.")
    port, page_port = found.port, found.page_port
    if port is None or page_port is None or state is LinkState.CONNECTED:
        return
    st.text(f"Port: {port}")
    st.text("\n".join(step.format(port=port, page_port=page_port) for step in THREE_STEPS))
    _token(found)


def _token(found: LinkKeeper) -> None:
    """The token, drawn only while shown; asked of the keeper each time, never kept."""
    if not assistant_session.token_shown():
        st.button("Show token", key=SHOW_TOKEN_KEY, on_click=assistant_ledger.show_token)
        return
    st.button("Hide token", key=HIDE_TOKEN_KEY, on_click=assistant_ledger.hide_token)
    token = found.token_to_show()
    if token is not None:
        with st.container(key=TOKEN_KEY):
            st.code(token, language=None)
