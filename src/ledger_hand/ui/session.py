"""What the interface keeps between reruns: the parts, the passage being recorded, the chat.

Streamlit runs the page from the top on every click and every message;
``st.session_state`` is all that lasts from one run to the next, for as long
as the browser tab is open. This module is the only one that touches it,
and it keeps three things:

- the parts the flows are handed (``wiring.Parts``), built by the wiring
  module the first time they are needed, unless something put them there
  first (the tests put in a scripted model, a book in a temporary folder, a
  fixed clock and zone);
- the ``Progress`` of the passage being recorded, or ``None`` when there is
  none;
- the chat so far, as ``Line``s.

It decides nothing about them; it only keeps them. Nothing here is written
to disk.

Names defined here: ``Speaker``, ``Line``, ``PARTS_KEY``, ``parts``,
``progress``, ``keep``, ``chat``, ``say`` and ``typed``.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

import streamlit as st

from ledger_hand.flows.progress import Progress
from ledger_hand.wiring import Parts, assemble

# Where each thing is kept; the parts' key is also where a test puts its own.
PARTS_KEY = "ledger_hand.parts"
_PROGRESS_KEY = "ledger_hand.progress"
_CHAT_KEY = "ledger_hand.chat"


class Speaker(enum.Enum):
    """Who said a line; the value is the name Streamlit draws the line under."""

    PERSON = "user"
    PROGRAM = "assistant"


@dataclass(frozen=True)
class Line:
    """One message in the chat, as it was said."""

    speaker: Speaker
    text: str


def parts() -> Parts:
    """The parts kept, built by the wiring module the first time; raises its ``AssemblyError``."""
    kept = st.session_state.get(PARTS_KEY)
    if isinstance(kept, Parts):
        return kept
    built = assemble()
    st.session_state[PARTS_KEY] = built
    return built


def progress() -> Progress | None:
    """The passage being recorded, or ``None`` when there is none."""
    kept = st.session_state.get(_PROGRESS_KEY)
    return kept if isinstance(kept, Progress) else None


def keep(current: Progress | None) -> None:
    """Keep ``current`` as the passage being recorded; ``None`` when there is none."""
    st.session_state[_PROGRESS_KEY] = current


def chat() -> tuple[Line, ...]:
    """The chat so far, oldest first."""
    kept = st.session_state.get(_CHAT_KEY, ())
    return tuple(kept)


def say(speaker: Speaker, text: str) -> None:
    """Add one message to the chat."""
    st.session_state[_CHAT_KEY] = (*chat(), Line(speaker, text))


def typed(key: str) -> str | None:
    """What was just sent from the chat input under ``key``, as typed."""
    value = st.session_state.get(key)
    return value if isinstance(value, str) else None
