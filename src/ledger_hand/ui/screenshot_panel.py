"""The screenshot area of the Record page: the upload box, and the two boxes of a screenshot read.

Under the chat, the person can upload a screenshot of an order instead of
typing it, one file at a time. Once the vision model has read it
(``turns.take_screenshot``), two boxes that can be changed appear: the text
read off the screenshot, as it was read, and a note, empty, for what the
screen leaves out. Continue records the two as one passage, which then goes
on as a typed one does; Drop the screenshot drops it.

The upload box can be used while nothing is being recorded and no
screenshot read waits; otherwise it is greyed out. It is offered for the
cloud plug too, which then says why it sends no pictures. It takes any file:
the browser is not told which kinds to offer, and Streamlit is not given a
limit of its own, so that the program's checks, on what the file holds and
on the size the settings allow, are the ones that speak. Parts handed in
with the local plug but without a vision model, as only tests hand them in,
show no screenshot area.

The two boxes are drawn from the text kept in ``session`` (the boxes' own
keys only show it), and what is typed into them is kept there as it is
typed, so that going to the settings page and back leaves them as they
were. Nothing here says anything in a caption or an error box: what goes
wrong is said in the chat, and what each control does is in its help.

The same area is drawn on the assistant page (``draw_panel``), with keys,
a place to keep its screenshot (``session.Spot``) and controls' actions of
its own (``Panel``), so that the two pages never share a screenshot; the
Record page's ``draw`` hands in its own, as they always were.

Names defined here: ``READ_KEY``, ``NOTE_KEY``, ``CONTINUE_KEY``,
``DROP_KEY``, ``Panel``, ``upload_key``, ``draw`` and ``draw_panel``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import streamlit as st

from ledger_hand.settings import ModelSettings, Plug, Variable
from ledger_hand.ui import session, turns
from ledger_hand.ui.session import RECORD_SPOT, Box, Spot
from ledger_hand.wiring import Parts

READ_KEY = "screenshot_read"
NOTE_KEY = "screenshot_note"
CONTINUE_KEY = "screenshot_continue"
DROP_KEY = "screenshot_drop"
_UPLOAD_KEY = "screenshot_upload_{round}"
_NOTE_EXAMPLE = "For example: fee 0.2 USDT, bought on OKX"


@dataclass(frozen=True, kw_only=True)
class Panel:
    """One page's screenshot area: where it keeps the screenshot, its keys, its actions.

    ``upload`` is the upload box's key with ``{round}`` in it. ``take`` is
    handed the upload box's key and the two boxes' keys; ``keep`` a box and
    its key; ``go_on`` and ``drop`` the two boxes' keys.
    """

    spot: Spot
    read: str
    note: str
    go_on_key: str
    drop_key: str
    upload: str
    note_example: str
    take: Callable[[str, str, str], None]
    keep: Callable[[Box, str], None]
    go_on: Callable[[str, str], None]
    drop: Callable[[str, str], None]


_RECORD_PANEL = Panel(
    spot=RECORD_SPOT,
    read=READ_KEY,
    note=NOTE_KEY,
    go_on_key=CONTINUE_KEY,
    drop_key=DROP_KEY,
    upload=_UPLOAD_KEY,
    note_example=_NOTE_EXAMPLE,
    take=turns.take_screenshot,
    keep=turns.keep_box,
    go_on=turns.continue_screenshot,
    drop=turns.drop_screenshot,
)


def upload_key(round_number: int) -> str:
    """The key of the upload box in round ``round_number`` (counting from 0)."""
    return _UPLOAD_KEY.format(round=round_number)


def draw(parts: Parts) -> None:
    """Show the upload box and, while a screenshot read waits, its two boxes and the two buttons."""
    draw_panel(parts, _RECORD_PANEL, busy=session.progress() is not None)


def draw_panel(parts: Parts, panel: Panel, *, busy: bool) -> None:
    """Show ``panel``'s upload box, greyed out while ``busy``, and a screenshot read that waits."""
    if parts.vision_model is None and parts.settings.plug is Plug.LOCAL:
        return
    key = panel.upload.format(round=session.upload_round(panel.spot))
    waiting = session.reading(panel.spot) is not None
    st.file_uploader(
        "Or record from a screenshot of an order (PNG or JPEG)",
        key=key,
        on_change=panel.take,
        args=(key, panel.read, panel.note),
        disabled=busy or waiting,
        help=_upload_help(parts.settings),
    )
    if not waiting:
        return
    session.offer(panel.read, session.box_text(Box.READ, panel.spot))
    session.offer(panel.note, session.box_text(Box.NOTE, panel.spot))
    st.text_area(
        "Text read off the screenshot",
        key=panel.read,
        on_change=panel.keep,
        args=(Box.READ, panel.read),
        help="As the vision model read it. Put right what is wrong before you press Continue.",
    )
    st.text_area(
        "Note",
        key=panel.note,
        on_change=panel.keep,
        args=(Box.NOTE, panel.note),
        placeholder=panel.note_example,
        help="What the screen leaves out, such as a fee or the platform; recorded after the text.",
    )
    with st.container(horizontal=True):
        st.button(
            "Continue",
            key=panel.go_on_key,
            type="primary",
            on_click=panel.go_on,
            args=(panel.read, panel.note),
            help="Records the text read and the note as one passage, as if typed.",
        )
        st.button(
            "Drop the screenshot",
            key=panel.drop_key,
            on_click=panel.drop,
            args=(panel.read, panel.note),
            help="Drops what was read; nothing is recorded.",
        )


def _upload_help(settings: ModelSettings) -> str:
    return (
        f"The vision model, {settings.vision_model}, reads the order on it out as text, which "
        "you check and change before anything is recorded; reading can take a minute. One "
        f"file at a time, a PNG or a JPEG of at most {settings.screenshot_max_mb} MB "
        f"({Variable.SCREENSHOT_MAX_MB.value}). Read through the local plug only."
    )
