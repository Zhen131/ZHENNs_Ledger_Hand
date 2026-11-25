"""What the assistant page keeps between reruns: its chat, what was said in it, and its cards.

The assistant page keeps its own things under keys of its own, apart from
the Record page's: the Record page's chat, passage and screenshot are never
seen here, nor these there. It keeps, for as long as the browser tab is
open and never on disk:

- the chat as the flows hand it back (``conversation.AssistantChat``): what
  the model is shown the next time, and what waits for the user's answer;
- every exchange so far (``Exchange``): what the person said and what came
  of it (``conversation.Said``), or a note the page said by itself, such
  as a screenshot read or not read;
- one card for every proposal sent in this chat (``Card``): its identifier,
  which exchange sent it and what it holds. Where it stands is not kept:
  the page asks the ledger each time it is drawn.

``new_chat`` forgets all three. The assistant page's screenshot is kept by
``session``, at ``session.ASSISTANT_SPOT``.

Names defined here: ``NoteTone``, ``Exchange``, ``Card``, ``chat``,
``keep_chat``, ``exchanges``, ``add_exchange``, ``cards``, ``add_card`` and
``new_chat``.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

import streamlit as st

from ledger_hand.flows.conversation import AssistantChat, Said

_CHAT_KEY = "ledger_hand.assistant.chat"
_EXCHANGES_KEY = "ledger_hand.assistant.exchanges"
_CARDS_KEY = "ledger_hand.assistant.cards"


class NoteTone(enum.Enum):
    """How a note the page said by itself is shown: as news, or as a failure."""

    NEWS = "news"
    FAILED = "failed"


@dataclass(frozen=True, kw_only=True)
class Exchange:
    """One thing in the chat, numbered from 1: what the person said and what came of it.

    ``words`` are the person's, ``None`` for a note the page said by itself;
    ``said`` is what the flows handed back, when anything was handed to
    them; ``note`` the page's own words otherwise.
    """

    number: int
    words: str | None = None
    said: Said | None = None
    note: str | None = None
    tone: NoteTone = NoteTone.NEWS


@dataclass(frozen=True, kw_only=True)
class Card:
    """One proposal sent in this chat: its identifier, the exchange that sent it, what it holds."""

    proposal: str
    exchange: int
    holds: str


def chat() -> AssistantChat:
    """The chat as the flows handed it back last; an empty one at first."""
    kept = st.session_state.get(_CHAT_KEY)
    return kept if isinstance(kept, AssistantChat) else AssistantChat()


def keep_chat(state: AssistantChat) -> None:
    """Keep ``state`` as the chat to hand the flows the next time."""
    st.session_state[_CHAT_KEY] = state


def exchanges() -> tuple[Exchange, ...]:
    """Every exchange so far, oldest first."""
    return tuple(st.session_state.get(_EXCHANGES_KEY, ()))


def add_exchange(
    *,
    words: str | None = None,
    said: Said | None = None,
    note: str | None = None,
    tone: NoteTone = NoteTone.NEWS,
) -> Exchange:
    """Add one exchange, numbered after the last, and give it back."""
    added = Exchange(number=len(exchanges()) + 1, words=words, said=said, note=note, tone=tone)
    st.session_state[_EXCHANGES_KEY] = (*exchanges(), added)
    return added


def cards() -> tuple[Card, ...]:
    """One card for every proposal sent in this chat, oldest first."""
    return tuple(st.session_state.get(_CARDS_KEY, ()))


def add_card(card: Card) -> None:
    """Add one card."""
    st.session_state[_CARDS_KEY] = (*cards(), card)


def new_chat() -> None:
    """Forget the chat, its exchanges and its cards; what waited for an answer is dropped."""
    st.session_state[_CHAT_KEY] = AssistantChat()
    st.session_state[_EXCHANGES_KEY] = ()
    st.session_state[_CARDS_KEY] = ()
