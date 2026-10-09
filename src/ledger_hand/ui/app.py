"""The interface's entry, the file Streamlit runs: the title and two pages, Record and Settings.

    streamlit run src/ledger_hand/ui/app.py

Run it from the top of the repository, where Streamlit finds its settings
(``.streamlit/config.toml``: no usage statistics, this machine only, no
questions at the terminal, no developer menu), then open
http://127.0.0.1:8501. Streamlit runs this file from the top every time the
person sends a message or presses a button; it names the two pages, shows
the one chosen (Record unless Settings was chosen, at ``/settings``) and
leaves the drawing to it: ``record_page.py`` and ``settings_page.py``.

Names defined here: ``TITLE``, ``RECORD_PAGE``, ``SETTINGS_PAGE`` and ``main``.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

TITLE = "Ledger Hand"
RECORD_PAGE = Path(__file__).resolve().with_name("record_page.py")
SETTINGS_PAGE = Path(__file__).resolve().with_name("settings_page.py")


def main() -> None:
    """Name the pages, draw the title and the page chosen."""
    st.set_page_config(page_title=TITLE, layout="wide")
    chosen = st.navigation(
        [
            st.Page(RECORD_PAGE, title="Record", default=True),
            st.Page(SETTINGS_PAGE, title="Settings", url_path="settings"),
        ],
        position="top",
    )
    st.title(TITLE)
    chosen.run()


main()
