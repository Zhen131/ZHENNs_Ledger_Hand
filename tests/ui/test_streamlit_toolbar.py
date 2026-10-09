"""Streamlit's menu at the top right shows no developer options, the Deploy button among them.

Deploy offers to publish the app on Streamlit's cloud; nothing here is ever
published, so ``.streamlit/config.toml`` sets the toolbar to ``minimal``.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

CONFIG_FILE = Path(__file__).resolve().parents[2] / ".streamlit" / "config.toml"


def test_the_menu_shows_no_developer_options() -> None:
    with CONFIG_FILE.open("rb") as handle:
        settings = tomllib.load(handle)

    assert settings["client"]["toolbarMode"] == "minimal"
