"""What the upload box does under Streamlit's headless test runner, which the page relies on.

A page with nothing but an upload box: a file handed to it reaches the box's
callback as the same bytes; a box drawn under a new key is empty, which is
how the page empties its box after each file; and a box greyed out cannot
be handed a file. Every byte here is invented.
"""

from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest
from streamlit.testing.v1.errors import AppTestError

BYTES = b"\x89PNG\r\n\x1a\n" + b"invented" * 5


def page() -> None:
    import streamlit as st

    def took() -> None:
        key = f"box_{st.session_state.get('round', 0)}"
        st.session_state["read"] = st.session_state[key].getvalue()
        st.session_state["round"] = st.session_state.get("round", 0) + 1

    key = f"box_{st.session_state.get('round', 0)}"
    st.file_uploader("A file", key=key, on_change=took, disabled=st.session_state.get("off", False))


def test_the_callback_reads_the_bytes_and_a_new_key_gives_an_empty_box() -> None:
    at = AppTest.from_function(page, default_timeout=30).run()

    at = at.file_uploader(key="box_0").set_value(("a.png", BYTES, "image/png")).run()

    assert not at.exception
    assert at.session_state["read"] == BYTES
    assert [box.key for box in at.file_uploader] == ["box_1"]
    assert at.file_uploader(key="box_1").value is None


def test_a_box_greyed_out_cannot_be_handed_a_file() -> None:
    at = AppTest.from_function(page, default_timeout=30)
    at.session_state["off"] = True
    at = at.run()

    box = at.file_uploader(key="box_0")
    assert box.disabled
    with pytest.raises(AppTestError):
        box.set_value(("a.png", BYTES, "image/png"))
