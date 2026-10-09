"""What the interface keeps between reruns: the parts, the passage, the chat, the settings changes.

Streamlit runs the page from the top on every click and every message;
``st.session_state`` is all that lasts from one run to the next, for as long
as the browser tab is open. This module is the only one that touches it,
and it keeps:

- the parts the flows are handed (``wiring.Parts``), built the first time
  they are needed, unless something put them there first (the tests put in
  a scripted model, a book in a temporary folder, a fixed clock and zone);
- how they are built: the wiring module's ``assemble``, unless something put
  its own way of building them there first (the tests build the real parts
  and put a scripted model in, so that a change of setting can be seen to
  reach the model);
- the changes made on the settings page (variable to text). The parts are
  built again with all of them whenever one is applied, and both are kept
  only when that works; they last as long as the browser tab and are never
  written anywhere, so a new tab, or a restart, goes back to the
  environment and the defaults;
- the ``Progress`` of the passage being recorded, or ``None`` when there is
  none;
- the chat so far, as ``Line``s;
- the last word said after Export and on the settings page, as a ``Note``;
- the text in the settings page's inputs, which Streamlit keeps under the
  inputs' keys; it is offered here when an input first appears and put back
  after a change is applied.

It decides nothing about them; it only keeps them. Nothing here is written
to disk.

Names defined here: ``Speaker``, ``Line``, ``Tone``, ``Note``, ``Place``,
``Builder``, ``PARTS_KEY``, ``BUILDER_KEY``, ``parts``, ``rebuild``,
``changes``, ``progress``, ``keep``, ``chat``, ``say``, ``typed``,
``note``, ``keep_note``, ``offer`` and ``put``.
"""

from __future__ import annotations

import enum
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

import streamlit as st

from ledger_hand.flows.progress import Progress
from ledger_hand.settings import Variable
from ledger_hand.wiring import Parts, assemble

type Builder = Callable[[Mapping[Variable, str]], Parts]

# Where each thing is kept; the parts' key and the builder's key are also
# where a test puts its own.
PARTS_KEY = "ledger_hand.parts"
BUILDER_KEY = "ledger_hand.builder"
_CHANGES_KEY = "ledger_hand.changes"
_PROGRESS_KEY = "ledger_hand.progress"
_CHAT_KEY = "ledger_hand.chat"
_NOTE_KEY = "ledger_hand.note.{place}"


class Speaker(enum.Enum):
    """Who said a line; the value is the name Streamlit draws the line under."""

    PERSON = "user"
    PROGRAM = "assistant"


@dataclass(frozen=True)
class Line:
    """One message in the chat, as it was said."""

    speaker: Speaker
    text: str


class Tone(enum.Enum):
    """How a note is shown: something done, nothing to do, or a failure."""

    DONE = "done"
    NOTHING = "nothing"
    FAILED = "failed"


@dataclass(frozen=True)
class Note:
    """The last word said in one place of the page, and how to show it."""

    tone: Tone
    text: str


class Place(enum.Enum):
    """Where a note is shown."""

    EXPORT = "export"
    SETTINGS = "settings"


def parts() -> Parts:
    """The parts kept, built the first time with the changes kept; raises ``AssemblyError``."""
    kept = st.session_state.get(PARTS_KEY)
    if isinstance(kept, Parts):
        return kept
    built = _builder()(changes())
    st.session_state[PARTS_KEY] = built
    return built


def rebuild(wanted: Mapping[Variable, str]) -> Parts:
    """Build the parts again with ``wanted`` as every change; keep both only when that works.

    Raises the builder's ``AssemblyError``; then the parts and the changes
    kept stay as they were.
    """
    built = _builder()(MappingProxyType(dict(wanted)))
    st.session_state[PARTS_KEY] = built
    st.session_state[_CHANGES_KEY] = dict(wanted)
    return built


def changes() -> Mapping[Variable, str]:
    """The changes made on the settings page and applied, in this browser tab."""
    kept = st.session_state.get(_CHANGES_KEY)
    return MappingProxyType(dict(kept) if isinstance(kept, dict) else {})


def _builder() -> Builder:
    given = st.session_state.get(BUILDER_KEY)
    return given if callable(given) else assemble


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


def note(place: Place) -> Note | None:
    """The last word said in ``place``, if any."""
    kept = st.session_state.get(_NOTE_KEY.format(place=place.value))
    return kept if isinstance(kept, Note) else None


def keep_note(place: Place, said: Note) -> None:
    """Keep ``said`` as the last word in ``place``."""
    st.session_state[_NOTE_KEY.format(place=place.value)] = said


def offer(key: str, text: str) -> None:
    """Give the input under ``key`` the text ``text``, unless it holds one already."""
    if key not in st.session_state:
        st.session_state[key] = text


def put(key: str, text: str) -> None:
    """Put ``text`` into the input under ``key``; only before the inputs are drawn again."""
    st.session_state[key] = text
