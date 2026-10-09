"""Changing the model settings on the page: one input for each, Apply, and back to the defaults.

Every model setting but the key has an input holding its value now, as it
would be typed into the environment. Apply hands the ones whose text was
changed, together with those changed before, to the wiring module, which
reads the environment first and puts the changes in with the settings'
own reading and checks (``session.rebuild``). When that works, the parts
are built again from the result, so the next call to the model, even in the
middle of a passage, uses the new values; when a change is refused, the
page says which setting and what its rule is, and nothing changes. "Back to
the environment and the defaults" drops every change made here.

The key is not an input: the page says only whether there is one. Nothing
here reads the environment or writes anything; the changes last as long as
the browser tab (``session``).

Names defined here: ``CHANGEABLE``, ``APPLY_KEY``, ``RESET_KEY``,
``NOTE_KEY``, ``input_key``, ``draw``, ``apply`` and ``reset``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

import streamlit as st

from ledger_hand.settings import ABOUT, ModelSettings, Variable
from ledger_hand.ui import notes, sayings, session
from ledger_hand.ui.session import Note, Place, Tone
from ledger_hand.ui.setting_text import key_state, shown
from ledger_hand.wiring import AssemblyError

CHANGEABLE = tuple(variable for variable in Variable if variable is not Variable.KEY)
APPLY_KEY = "settings_apply"
RESET_KEY = "settings_reset"
NOTE_KEY = "settings_note"

# What is said once the parts were built again: which values changed, to what.
type _Saying = Callable[[Sequence[Variable], ModelSettings], str]


def input_key(variable: Variable) -> str:
    """The key of the input for ``variable``, such as ``setting_temperature``."""
    return f"setting_{variable.name.lower()}"


def draw(settings: ModelSettings) -> None:
    """Show one input for each setting but the key, Apply, the way back, and the last word."""
    st.subheader("Change a setting")
    st.caption(
        "Type a new value and press Apply. A blank value takes the default, as a blank "
        "environment variable does."
    )
    for variable in CHANGEABLE:
        key = input_key(variable)
        session.offer(key, shown(settings, variable))
        st.text_input(variable.value, key=key, help=ABOUT[variable].sets)
    st.text(
        f"{Variable.KEY.value}: {key_state(settings.api_key)}. "
        "The key is set in the environment only and cannot be changed here."
    )
    with st.container(horizontal=True):
        st.button("Apply", key=APPLY_KEY, type="primary", on_click=apply)
        st.button("Back to the environment and the defaults", key=RESET_KEY, on_click=reset)
    notes.draw(session.note(Place.SETTINGS), NOTE_KEY)


def apply() -> None:
    """Build the parts again with every change typed so far; or say why not, changing nothing."""
    before = session.parts().settings
    wanted = dict(session.changes())
    for variable in CHANGEABLE:
        typed = session.typed(input_key(variable))
        if typed is not None and typed.strip() != shown(before, variable):
            wanted[variable] = typed
    _rebuild(wanted, before, said=sayings.settings_applied)


def reset() -> None:
    """Drop every change made on the page: back to the environment and the defaults."""
    _rebuild({}, session.parts().settings, said=sayings.settings_reset)


def _rebuild(
    wanted: Mapping[Variable, str],
    before: ModelSettings,
    *,
    said: _Saying,
) -> None:
    try:
        built = session.rebuild(wanted)
    except AssemblyError as error:
        session.keep_note(Place.SETTINGS, Note(Tone.FAILED, sayings.assembly_failed(error)))
        return
    now = built.settings
    changed = [variable for variable in Variable if shown(now, variable) != shown(before, variable)]
    for variable in CHANGEABLE:
        session.put(input_key(variable), shown(now, variable))
    tone = Tone.DONE if changed else Tone.NOTHING
    session.keep_note(Place.SETTINGS, Note(tone, said(changed, now)))
