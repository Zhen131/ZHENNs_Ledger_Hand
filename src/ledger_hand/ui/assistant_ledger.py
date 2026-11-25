"""Which ledger the assistant page reaches, and the one assistant link every tab shares.

The assistant page reaches one of two ledgers, chosen in each browser tab
(``assistant_session.ledger_choice``; a new tab starts with the parts'
``first_ledger``, the demo ledger unless the settings say otherwise):

- the demo ledger, an invented book in memory, held by the parts as
  before;
- the person's own ledger page, reached through the ledger's assistant
  link. Its port is fixed, so the whole program has one link, kept by one
  ``LinkKeeper``: built by ``wiring.link_keeper`` the first time a tab asks
  and kept for the whole process with ``st.cache_resource``, not in a
  global variable, which Streamlit loses when it reloads the code after a
  change, leaving a link running on the port a new one would then find
  taken (68B3, part two, 2). Every tab sees the same keeper; one tab
  pressing Stop stops it for all. A test puts its own keeper under
  ``KEEPER_KEY``.

``parts_now`` gives the parts with the ledger this tab reaches; every
control of the assistant page hands the flows those, never the kept parts
alone. With the ledger page, the parts' ledger is the keeper's plug for the
model the settings name, and ``ledger_kind`` is ``LedgerKind.PAGE``;
without the ledger's folder it is ``None``, so nothing can be sent.

``switch`` changes this tab's ledger, clears its chat and says why.
``start``, ``stop``, ``show_token`` and ``hide_token`` are what the page's
buttons do. The token is never kept in the session: it is asked of the
keeper each time it is shown.

Names defined here: ``KEEPER_KEY``, ``keeper``, ``choice``, ``parts_now``,
``link_state``, ``page_connected``, ``switch``, ``start``, ``stop``,
``show_token`` and ``hide_token``.
"""

from __future__ import annotations

from dataclasses import replace

import streamlit as st

from ledger_hand import wiring
from ledger_hand.flows.standing import LedgerKind
from ledger_hand.ledger.link_keeper import LinkKeeper, LinkState
from ledger_hand.settings import AssistantLedger
from ledger_hand.ui import assistant_session, session
from ledger_hand.ui.assistant_link_words import SWITCHED
from ledger_hand.ui.session import ASSISTANT_SPOT
from ledger_hand.wiring import NoLink, Parts

# Where a test puts its own keeper, in place of the one shared by the process.
KEEPER_KEY = "ledger_hand.assistant.link_keeper"

_LEDGER_NAMES = {
    AssistantLedger.DEMO: "the demo ledger",
    AssistantLedger.PAGE: "your ledger page",
}


@st.cache_resource(show_spinner=False)
def _shared_keeper() -> LinkKeeper | NoLink:
    """The keeper of the program's one link, built once for the whole process."""
    return wiring.link_keeper()


def keeper() -> LinkKeeper | NoLink:
    """The keeper every tab shares, or why there is none; a test's own when it put one."""
    given = assistant_session.value(KEEPER_KEY)
    if isinstance(given, (LinkKeeper, NoLink)):
        return given
    return _shared_keeper()


def choice(parts: Parts) -> AssistantLedger:
    """Which ledger this tab reaches."""
    return assistant_session.ledger_choice(parts.first_ledger)


def parts_now(parts: Parts | None = None) -> Parts:
    """``parts`` (the kept ones when ``None``) with the ledger this tab reaches."""
    kept = session.parts() if parts is None else parts
    if choice(kept) is not AssistantLedger.PAGE:
        return kept
    found = keeper()
    if isinstance(found, NoLink):
        return replace(kept, ledger=None, ledger_kind=LedgerKind.PAGE)
    return replace(kept, ledger=found.plug(kept.settings.model), ledger_kind=LedgerKind.PAGE)


def link_state() -> LinkState | None:
    """Where the shared link stands, or ``None`` when there can be none."""
    found = keeper()
    return None if isinstance(found, NoLink) else found.state()


def page_connected(parts: Parts) -> bool:
    """Whether ``parts`` reach the demo ledger, or a ledger page that is connected now."""
    if parts.ledger_kind is not LedgerKind.PAGE:
        return True
    return link_state() is LinkState.CONNECTED


def switch(key: str) -> None:
    """Take the choice made under ``key``: reach that ledger, and clear this tab's chat."""
    chosen = assistant_session.value(key)
    parts = session.parts()
    if not isinstance(chosen, AssistantLedger) or chosen is choice(parts):
        return
    assistant_session.keep_ledger_choice(chosen)
    assistant_session.new_chat()
    session.keep_reading(None, ASSISTANT_SPOT)
    assistant_session.add_exchange(note=SWITCHED.format(ledger=_LEDGER_NAMES[chosen]))


def start() -> None:
    """Start the shared link, unless one runs; keep why not in this tab when it fails."""
    found = keeper()
    if isinstance(found, NoLink):
        return
    assistant_session.hide_token()
    assistant_session.keep_start_failure(found.start())


def stop() -> None:
    """Stop the shared link, for every tab."""
    found = keeper()
    assistant_session.hide_token()
    assistant_session.keep_start_failure(None)
    if not isinstance(found, NoLink):
        found.stop()


def show_token() -> None:
    """Show the token in this tab."""
    assistant_session.show_token()


def hide_token() -> None:
    """Stop showing the token in this tab."""
    assistant_session.hide_token()
