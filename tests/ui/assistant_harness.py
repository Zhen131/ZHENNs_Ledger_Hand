"""Shared pieces of the assistant page's tests: the page run headless with the demo ledger.

``open_assistant`` runs the real entry (``src/ledger_hand/ui/app.py``) once,
with parts the test makes, then switches to the Assistant page. The model
is a ``RoutedModel``, the ledger a ``FakeLedger`` (the demo ledger), the
book a ``CountingBook`` that counts every call made to it, the clock the
invented book's fixed moment and its zone. Nothing reaches the network.

Controls are found by their keys only.

Names defined here: ``CountingBook``, ``open_assistant``, ``to_assistant``,
``say_on_page``, ``replies``, ``rows_of``, ``texts_of``, ``card_text``,
``captions`` and ``errors``.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from streamlit.testing.v1 import AppTest

from ledger_hand.core.assets import BUILT_IN_ASSETS
from ledger_hand.core.book import EarlierSave, ExportMark, Listing, PassageSave
from ledger_hand.flows.recording import tuning_from
from ledger_hand.flows.standing import LedgerKind
from ledger_hand.flows.uploading import VisionModelCheck
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ledger.invented_book import INVENTED_NOW, INVENTED_ZONE
from ledger_hand.ports import ModelPort
from ledger_hand.settings import ModelSettings
from ledger_hand.ui.assistant_cards import card_key
from ledger_hand.ui.assistant_view import exchange_key
from ledger_hand.ui.session import PARTS_KEY
from ledger_hand.wiring import Parts
from tests.fakes.memory_store import MemoryStore
from tests.ui.app_harness import APP_FILE

# The page's own constant; not imported, since importing the page draws it.
INPUT_KEY = "assistant_chat_input"


class CountingBook:
    """The book in memory, counting every call made to it, by name."""

    def __init__(self) -> None:
        self.inner = MemoryStore()
        self.calls: list[str] = []

    def save(self, passage: PassageSave) -> Any:
        self.calls.append("save")
        return self.inner.save(passage)

    def earlier_saves(self, fingerprint: str) -> tuple[EarlierSave, ...]:
        self.calls.append("earlier_saves")
        return self.inner.earlier_saves(fingerprint)

    def trades(self, listing: Listing) -> Any:
        self.calls.append("trades")
        return self.inner.trades(listing)

    def mark_exported(self, mark: ExportMark) -> None:
        self.calls.append("mark_exported")
        self.inner.mark_exported(mark)

    def confirmed_coins(self) -> Any:
        self.calls.append("confirmed_coins")
        return self.inner.confirmed_coins()


def open_assistant(
    model: ModelPort,
    *,
    ledger: FakeLedger | None = None,
    kind: LedgerKind | None = LedgerKind.DEMO,
    settings: ModelSettings | None = None,
    book: CountingBook | None = None,
    vision_model: ModelPort | None = None,
    check: VisionModelCheck | None = None,
    steps: int = 6,
) -> AppTest:
    """The app run once with the parts the test makes, then the Assistant page."""
    chosen = ModelSettings() if settings is None else settings
    page = AppTest.from_file(str(APP_FILE), default_timeout=30)
    page.session_state[PARTS_KEY] = Parts(
        model=model,
        tuning=tuning_from(chosen),
        book=book if book is not None else CountingBook(),  # type: ignore[arg-type]
        assets=BUILT_IN_ASSETS,
        clock=lambda: INVENTED_NOW,
        zone=INVENTED_ZONE,
        settings=chosen,
        vision_model=vision_model,
        vision_check=check,
        ledger=ledger,
        ledger_kind=kind if ledger is not None else None,
        assistant_steps=steps,
    )
    page.run()
    return to_assistant(page)


def to_assistant(page: AppTest) -> AppTest:
    return page.switch_page("assistant_page.py").run()


def say_on_page(page: AppTest, text: str) -> AppTest:
    """Type ``text`` into the assistant's chat input and send it."""
    return page.chat_input(key=INPUT_KEY).set_value(text).run()


def texts_of(page: AppTest, key: str) -> list[str]:
    """Every plain text drawn in the container under ``key``, in order."""
    return [str(text.value) for text in page.container(key=key).text]


def captions(page: AppTest, key: str) -> list[str]:
    return [str(caption.value) for caption in page.container(key=key).caption]


def errors(page: AppTest, key: str) -> list[str]:
    return [str(error.value) for error in page.container(key=key).error]


def replies(page: AppTest, number: int) -> list[str]:
    """The plain texts of exchange ``number``'s reply: the reply itself first."""
    return texts_of(page, exchange_key(number))


def rows_of(page: AppTest, key: str) -> list[dict[str, str]]:
    """The rows of the one table in the container under ``key``, as shown."""
    frame = page.container(key=key).dataframe[0].value
    return [
        {str(name): str(value) for name, value in row.items()}
        for row in frame.to_dict(orient="records")
    ]


def card_text(page: AppTest, proposal: str) -> Sequence[str]:
    return texts_of(page, card_key(proposal))
