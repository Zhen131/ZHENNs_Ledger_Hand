"""The Assistant page: a chat with the assistant on the left, the proposals it sent on the right.

Streamlit runs this file, through the entry ``app.py``, every time the
person sends a message, uploads a file or presses a button on this page;
what was sent has been handed to the flows just before
(``assistant_turns``), so the page only draws what is kept
(``assistant_session``).

At the top, one line always says which ledger the assistant reaches, read
from the parts (``Parts.ledger_kind``); today that is the demo ledger, an
invented book in memory. When no ledger is connected, or the settings
choose the cloud plug (the assistant runs on the local plug only), the
page says so in one fixed sentence and greys the input out; nothing is
sent. Under the chat is the screenshot area, the Record page's own, with
keys and a screenshot of this page's (``screenshot_panel.draw_panel``):
greyed out while a question waits for its answer.

New chat forgets this chat; a question left unanswered is dropped with it.
The chat lasts as long as the browser tab and is never written to disk.

When the program's parts cannot be built, the page says why, as the Record
page does, and shows nothing else.

Names defined here: ``LEDGER_LINE_KEY``, ``NOTICE_KEY``, ``INPUT_KEY``,
``LOG_KEY``, ``NEW_CHAT_KEY``, ``PANEL`` and ``main``.
"""

from __future__ import annotations

import streamlit as st

from ledger_hand.ui import (
    assistant_cards,
    assistant_session,
    assistant_turns,
    assistant_view,
    sayings,
    screenshot_panel,
    session,
)
from ledger_hand.ui.assistant_failure_words import stop_words
from ledger_hand.ui.screenshot_panel import Panel
from ledger_hand.ui.session import ASSISTANT_SPOT
from ledger_hand.wiring import AssemblyError, Parts

LEDGER_LINE_KEY = "assistant_ledger_line"
NOTICE_KEY = "assistant_notice"
INPUT_KEY = "assistant_chat_input"
LOG_KEY = "assistant_chat_log"
NEW_CHAT_KEY = "assistant_new_chat"
_EXAMPLE = (
    "Ask about your trades, record one, or change one; for example: What do I hold? / "
    "Bought 2 MSFT at 410 dollars each today at 15:30 on IBKR, fee 1 dollar"
)

PANEL = Panel(
    spot=ASSISTANT_SPOT,
    read="assistant_screenshot_read",
    note="assistant_screenshot_note",
    go_on_key="assistant_screenshot_continue",
    drop_key="assistant_screenshot_drop",
    upload="assistant_screenshot_upload_{round}",
    note_example="For example: the fee, or the platform",
    take=assistant_turns.take_screenshot,
    keep=assistant_turns.keep_box,
    go_on=assistant_turns.continue_screenshot,
    drop=assistant_turns.drop_screenshot,
)


def _ledger_line(parts: Parts) -> str:
    if parts.ledger is None or parts.ledger_kind is None:
        return "Ledger: none connected"
    return f"Ledger: {parts.ledger_kind.value}"


def main() -> None:
    """Draw the page."""
    try:
        parts = session.parts()
    except AssemblyError as error:
        st.error(sayings.assembly_failed(error))
        return
    with st.container(key=LEDGER_LINE_KEY):
        st.caption(_ledger_line(parts))
    stop = assistant_turns.usable(parts)
    if stop is not None:
        with st.container(key=NOTICE_KEY):
            st.warning(stop_words(stop, parts.assistant_steps, parts.steps_refused or ""))
    state = assistant_session.chat()
    waiting = state.recording is not None or state.editing is not None
    talk, side = st.columns([2, 1], gap="large")
    with talk:
        with st.container(height=560, key=LOG_KEY, autoscroll=True):
            exchanges = assistant_session.exchanges()
            if not exchanges:
                st.caption(f"{_EXAMPLE}.")
            assistant_view.draw(parts, exchanges)
        st.chat_input(
            "Ask, record or change a trade, or answer the question",
            key=INPUT_KEY,
            on_submit=assistant_turns.take_typed,
            args=(INPUT_KEY,),
            disabled=stop is not None,
        )
        busy = waiting or parts.ledger is None
        screenshot_panel.draw_panel(parts, PANEL, busy=busy)
    with side:
        st.button(
            "New chat",
            key=NEW_CHAT_KEY,
            on_click=assistant_turns.start_new_chat,
            help="Forgets this chat. A question still waiting for an answer is dropped.",
        )
        assistant_cards.draw(parts, assistant_session.cards())


main()
