"""The settings Streamlit reads from the top of the repository: nothing sent, this machine only.

``.streamlit/config.toml`` must keep three settings: no usage statistics
are gathered, the server listens on this machine's own address only, and it
starts headless, so that it never stops at the terminal to ask for an
e-mail address and never writes a credentials file into the home folder.
The folder holds that one file and nothing else.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from streamlit import config

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / ".streamlit"
CONFIG_FILE = CONFIG_DIR / "config.toml"


def settings() -> dict[str, dict[str, object]]:
    with CONFIG_FILE.open("rb") as handle:
        return tomllib.load(handle)


def test_no_usage_statistics_are_gathered() -> None:
    assert settings()["browser"]["gatherUsageStats"] is False


def test_the_server_listens_on_this_machine_only() -> None:
    assert settings()["server"]["address"] == "127.0.0.1"


def test_the_server_starts_headless() -> None:
    assert settings()["server"]["headless"] is True


def test_streamlit_knows_every_option_set_here() -> None:
    # A misspelt or retired option would be ignored without a word.
    for section, options in settings().items():
        known = config.get_options_for_section(section)
        assert set(options) <= set(known), (section, set(options) - set(known))


def test_the_folder_holds_only_the_settings_file() -> None:
    assert sorted(path.name for path in CONFIG_DIR.iterdir()) == ["config.toml"]
