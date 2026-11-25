"""The assistant page's proposal cards: one for each proposal of this chat, and the demo buttons.

Each card says the proposal's identifier, which message sent it, what it
holds, and where it stands now. Where it stands is asked of the ledger
every time the page is drawn (``standing.standing``); Refresh draws the
page again, and so asks again. A ledger that cannot say is said as such,
never as the last status seen.

The demo buttons, "Save in the demo ledger" and "Reject", are drawn only
when the parts say the ledger is the demo ledger (``standing.LedgerKind``)
and the proposal waits: they do what the person does on the real ledger's
own page, on the invented book alone. With any other ledger this block is
not drawn: a proposal is confirmed on the ledger's own page.

Names defined here: ``STATUS_WORDS``, ``CARDS_KEY``, ``REFRESH_KEY``,
``card_key``, ``save_key``, ``reject_key`` and ``draw``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import MappingProxyType

import streamlit as st

from ledger_hand.core.proposals import ProposalStatus
from ledger_hand.flows.standing import LedgerKind, Standing, standing
from ledger_hand.ui import assistant_turns
from ledger_hand.ui.assistant_failure_words import ledger_trouble
from ledger_hand.ui.assistant_session import Card
from ledger_hand.wiring import Parts

CARDS_KEY = "assistant_cards"
REFRESH_KEY = "assistant_refresh"

STATUS_WORDS: Mapping[ProposalStatus, str] = MappingProxyType(
    {
        ProposalStatus.PENDING: "waiting for you to confirm on the ledger's own page",
        ProposalStatus.SAVED: "saved",
        ProposalStatus.REJECTED: "rejected",
        ProposalStatus.VOID: "void: the ledger changed after it was sent, so it cannot be saved",
    }
)


def card_key(proposal: str) -> str:
    """The key of the card of ``proposal``."""
    return f"assistant_card_{proposal}"


def save_key(proposal: str) -> str:
    """The key of the demo save button of ``proposal``."""
    return f"assistant_demo_save_{proposal}"


def reject_key(proposal: str) -> str:
    """The key of the demo reject button of ``proposal``."""
    return f"assistant_demo_reject_{proposal}"


def _status_text(now: Standing) -> str:
    if now.status is not None:
        return f"Status: {STATUS_WORDS[now.status]}"
    failure = now.failure
    reason = ledger_trouble(failure) if failure is not None else "no answer"
    return f"Status: could not be asked. {reason}"


def draw(parts: Parts, cards: Sequence[Card]) -> None:
    """Show a card for each proposal of this chat, newest first, and Refresh."""
    with st.container(key=CARDS_KEY):
        st.subheader("Proposals sent")
        st.button(
            "Refresh",
            key=REFRESH_KEY,
            help="Asks the ledger again where each proposal stands.",
        )
        if not cards:
            st.caption("None yet in this chat.")
            return
        demo = parts.ledger_kind is LedgerKind.DEMO
        if demo:
            st.caption(
                "Demo only: the two buttons below work on the demo ledger alone. With your "
                "real ledger, you confirm a proposal on the ledger's own page."
            )
        for card in reversed(cards):
            _card(parts, card, demo=demo)


def _card(parts: Parts, card: Card, *, demo: bool) -> None:
    ledger = parts.ledger
    with st.container(key=card_key(card.proposal), border=True):
        st.text(f"{card.proposal}: {card.holds}, sent by message {card.exchange}")
        if ledger is None:
            st.text("Status: no ledger is connected")
            return
        now = standing(ledger, card.proposal)
        st.text(_status_text(now))
        if not demo or now.status is not ProposalStatus.PENDING:
            return
        with st.container(horizontal=True):
            st.button(
                "Save in the demo ledger",
                key=save_key(card.proposal),
                on_click=assistant_turns.save_in_demo,
                args=(card.proposal,),
                help="Saves it in the demo ledger only, as you would on the ledger's own page.",
            )
            st.button(
                "Reject in the demo ledger",
                key=reject_key(card.proposal),
                on_click=assistant_turns.reject_in_demo,
                args=(card.proposal,),
                help="Rejects it in the demo ledger only, as you would on the ledger's own page.",
            )
