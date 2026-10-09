"""Shared pieces of the interface tests: the page run headless, with fakes for the outside world.

``open_page`` runs the real page (``src/ledger_hand/ui/app.py``) with
Streamlit's own headless test runner, after putting the parts in the
session where the page looks for them first: a scripted model, a book in a
temporary folder, a fixed clock and a fixed zone. Nothing reaches the
network and nothing is written outside the temporary folder.

Controls are found by their keys only, never by their place on the page.

Names defined here: ``APP_FILE``, ``ZONE``, ``NOW``, ``open_page``,
``send``, ``press``, ``table``, ``column``, ``said``, ``program_said``,
``button`` and the keys.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from streamlit.testing.v1 import AppTest
from streamlit.testing.v1.element_tree import Button

from ledger_hand.core.coins import BUILT_IN_TABLE
from ledger_hand.flows.progress import DEFAULT_TUNING
from ledger_hand.ports import ModelPort, StoragePort
from ledger_hand.wiring import Parts

APP_FILE = Path(__file__).resolve().parents[2] / "src" / "ledger_hand" / "ui" / "app.py"
ZONE = "Europe/Budapest"
# An invented evening, so that "yesterday" and "昨天" lie in the past.
NOW = datetime(2026, 10, 7, 21, 0, tzinfo=ZoneInfo(ZONE))

PARTS_KEY = "ledger_hand.parts"
INPUT_KEY = "chat_input"
TABLE_KEY = "preview_table"
SAVE_KEY = "save_button"
DISCARD_KEY = "discard_all_button"


def dont_save_key(number: int) -> str:
    return f"dont_save_trade_{number}"


def open_page(model: ModelPort, book: StoragePort) -> AppTest:
    """The page, run once, with the parts the tests hand in."""
    page = AppTest.from_file(str(APP_FILE), default_timeout=30)
    page.session_state[PARTS_KEY] = Parts(
        model=model,
        tuning=DEFAULT_TUNING,
        book=book,
        coins=BUILT_IN_TABLE,
        clock=lambda: NOW,
        zone=ZONE,
    )
    return page.run()


def send(page: AppTest, text: str) -> AppTest:
    """Type ``text`` into the chat and send it."""
    return page.chat_input(key=INPUT_KEY).set_value(text).run()


def button(page: AppTest, key: str) -> Button:
    return page.button(key=key)


def press(page: AppTest, key: str) -> AppTest:
    return page.button(key=key).click().run()


def table(page: AppTest) -> list[dict[str, str]]:
    """The rows of the table of what will be recorded, as the page shows them."""
    frame = page.container(key=TABLE_KEY).dataframe[0].value
    return [
        {str(name): str(value) for name, value in row.items()}
        for row in frame.to_dict(orient="records")
    ]


def column_names(page: AppTest) -> list[str]:
    return [str(name) for name in page.container(key=TABLE_KEY).dataframe[0].value.columns]


def said(page: AppTest) -> list[tuple[str, str]]:
    """Every message in the chat: who said it and what, in order."""
    return [
        (message.name, "\n".join(text.value for text in message.text))
        for message in page.chat_message
    ]


def program_said(page: AppTest) -> list[str]:
    """What the program said in the chat, in order."""
    return [text for name, text in said(page) if name == "assistant"]
