"""What the assistant page keeps between reruns: its chat, what was said in it, and its cards.

The assistant page keeps its own things under keys of its own, apart from
the Record page's: the Record page's chat, passage and screenshot are never
seen here, nor these there. It keeps, for as long as the browser tab is
open and never on disk (the assistant's record is written apart, by
``assistant_turns``):

- the chat as the flows hand it back (``conversation.AssistantChat``): what
  the model is shown the next time, and what waits for the user's answer;
- every exchange so far (``Exchange``): what the person said and what came
  of it (``conversation.Said``), and whether it was kept in the assistant's
  record on this machine (``flows.assistant_record``), or a note the page
  said by itself, such as a screenshot read or not read;
- one card for every proposal sent in this chat (``Card``): its identifier,
  which exchange sent it and what it holds. With the demo ledger, where it
  stands is not kept: the page asks the ledger each time it is drawn. With
  the ledger page, the page asks only when the person presses "Check with
  the ledger", and keeps what came back (``checked``), since a ledger page
  left in the background can take most of a minute to answer;
- which ledger this tab reaches (``ledger_choice``), kept apart from the
  choice's own control, which Streamlit forgets while another page is
  shown;
- whether the token of the assistant link is shown now (``token_shown``),
  never the token itself, and the last start of the link that failed in
  this tab (``start_failure``).

``new_chat`` forgets the chat, its exchanges, its cards and what was
checked. The assistant page's screenshot is kept by ``session``, at
``session.ASSISTANT_SPOT``.

Names defined here: ``NoteTone``, ``Exchange``, ``Card``, ``chat``,
``keep_chat``, ``exchanges``, ``add_exchange``, ``cards``, ``add_card``,
``checked``, ``keep_checked``, ``ledger_choice``, ``keep_ledger_choice``,
``token_shown``, ``show_token``, ``hide_token``, ``start_failure``, ``keep_start_failure``,
``value``, ``offer_value`` and ``new_chat``.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

import streamlit as st

from ledger_hand.flows.assistant_record import Kept, NotKept
from ledger_hand.flows.conversation import AssistantChat, Said
from ledger_hand.flows.standing import Standing
from ledger_hand.ledger.link_failures import LedgerLinkError
from ledger_hand.settings import AssistantLedger

_CHAT_KEY = "ledger_hand.assistant.chat"
_EXCHANGES_KEY = "ledger_hand.assistant.exchanges"
_CARDS_KEY = "ledger_hand.assistant.cards"
_CHECKED_KEY = "ledger_hand.assistant.checked"
_CHOICE_KEY = "ledger_hand.assistant.ledger_choice"
_TOKEN_SHOWN_KEY = "ledger_hand.assistant.token_shown"
_START_FAILURE_KEY = "ledger_hand.assistant.start_failure"


class NoteTone(enum.Enum):
    """How a note the page said by itself is shown: as news, or as a failure."""

    NEWS = "news"
    FAILED = "failed"


@dataclass(frozen=True, kw_only=True)
class Exchange:
    """One thing in the chat, numbered from 1: what the person said and what came of it.

    ``words`` are the person's, ``None`` for a note the page said by itself;
    ``said`` is what the flows handed back, when anything was handed to
    them; ``note`` the page's own words otherwise. ``kept`` says whether
    what came of it was added to the assistant's record, or why not.
    """

    number: int
    words: str | None = None
    said: Said | None = None
    note: str | None = None
    tone: NoteTone = NoteTone.NEWS
    kept: Kept | NotKept | None = None


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
    kept: Kept | NotKept | None = None,
) -> Exchange:
    """Add one exchange, numbered after the last, and give it back."""
    added = Exchange(
        number=len(exchanges()) + 1, words=words, said=said, note=note, tone=tone, kept=kept
    )
    st.session_state[_EXCHANGES_KEY] = (*exchanges(), added)
    return added


def cards() -> tuple[Card, ...]:
    """One card for every proposal sent in this chat, oldest first."""
    return tuple(st.session_state.get(_CARDS_KEY, ()))


def add_card(card: Card) -> None:
    """Add one card."""
    st.session_state[_CARDS_KEY] = (*cards(), card)


def checked() -> dict[str, Standing]:
    """Where each proposal stood when last checked with the ledger page, by its identifier."""
    kept = st.session_state.get(_CHECKED_KEY)
    return dict(kept) if isinstance(kept, dict) else {}


def keep_checked(now: Standing) -> None:
    """Keep ``now`` as where its proposal stood when last checked."""
    st.session_state[_CHECKED_KEY] = {**checked(), now.proposal: now}


def ledger_choice(first: AssistantLedger) -> AssistantLedger:
    """Which ledger this tab reaches; ``first`` until the person chooses."""
    kept = st.session_state.get(_CHOICE_KEY)
    return kept if isinstance(kept, AssistantLedger) else first


def keep_ledger_choice(choice: AssistantLedger) -> None:
    """Keep ``choice`` as the ledger this tab reaches."""
    st.session_state[_CHOICE_KEY] = choice


def token_shown() -> bool:
    """Whether the link's token is shown now in this tab."""
    return st.session_state.get(_TOKEN_SHOWN_KEY) is True


def show_token() -> None:
    """Show the link's token in this tab from now on; only that it is shown is kept."""
    st.session_state[_TOKEN_SHOWN_KEY] = True


def hide_token() -> None:
    """Stop showing the link's token in this tab."""
    st.session_state[_TOKEN_SHOWN_KEY] = False


def start_failure() -> LedgerLinkError | None:
    """The last start of the link that failed in this tab, or ``None``."""
    kept = st.session_state.get(_START_FAILURE_KEY)
    return kept if isinstance(kept, LedgerLinkError) else None


def keep_start_failure(failure: LedgerLinkError | None) -> None:
    """Keep ``failure`` as the last failed start in this tab; ``None`` forgets it."""
    st.session_state[_START_FAILURE_KEY] = failure


def value(key: str) -> object:
    """What is kept under ``key``: a control's value, or what a test put there; ``None`` if none."""
    return st.session_state.get(key)


def offer_value(key: str, given: object) -> None:
    """Give the control under ``key`` the value ``given``, unless it holds one already."""
    if key not in st.session_state:
        st.session_state[key] = given


def new_chat() -> None:
    """Forget the chat, its exchanges, its cards and what was checked."""
    st.session_state[_CHAT_KEY] = AssistantChat()
    st.session_state[_EXCHANGES_KEY] = ()
    st.session_state[_CARDS_KEY] = ()
    st.session_state[_CHECKED_KEY] = {}
