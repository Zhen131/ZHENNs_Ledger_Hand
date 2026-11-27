"""The line that stays at the top of the Assistant and Record pages while a cloud plug is set.

With the cloud or the deepseek plug, what is typed leaves this machine, and
on the Assistant page so does what the assistant looks up in the ledger.
That is the price of choosing a cloud model, so it is said on the page, in
one line that is always there, naming the service, the address the words
are sent to (the effective one, as the settings were built) and the model.
With the local plug there is no such line, and the pages are as they were.

The Record page reads no ledger, so its line speaks only of what is typed.

Names defined here: ``ASSISTANT_NOTICE_KEY``, ``RECORD_NOTICE_KEY``,
``assistant_words``, ``record_words`` and ``draw``.
"""

from __future__ import annotations

import streamlit as st

from ledger_hand.settings import SERVICES, ModelSettings, Plug

ASSISTANT_NOTICE_KEY = "assistant_cloud_notice"
RECORD_NOTICE_KEY = "record_cloud_notice"


def _model(settings: ModelSettings) -> str:
    service = SERVICES.get(settings.plug)
    name = "a cloud service" if service is None else service.name
    return f"Model: {name} ({settings.base_url}), {settings.model}."


def assistant_words(settings: ModelSettings) -> str | None:
    """The Assistant page's line, or ``None`` with the local plug."""
    if settings.plug is Plug.LOCAL:
        return None
    return (
        f"{_model(settings)} Everything you say here, and what the assistant looks up in your "
        f"ledger (holdings, trades, cash balances), is sent to {settings.base_url}."
    )


def record_words(settings: ModelSettings) -> str | None:
    """The Record page's line, or ``None`` with the local plug."""
    if settings.plug is Plug.LOCAL:
        return None
    return f"{_model(settings)} Every passage you type here is sent to {settings.base_url}."


def draw(words: str | None, key: str) -> None:
    """Show ``words`` as a warning that stays at the top; nothing when there are none."""
    if words is None:
        return
    with st.container(key=key):
        st.warning(words)
