"""Shared pieces of the interface tests of a screenshot: the page with a vision model, and uploads.

``open_with_vision`` runs the real page headless, as ``app_harness`` and
``page_harness`` do, with parts the test makes: the model, a book, a fixed
clock and zone, the settings it names, and for a screenshot the vision model
and a stand-in for asking the server whether it has it (``Check``). Nothing
reaches the network.

``upload`` hands the one upload box on the page a file, as a name, its bytes
and a type; the bytes are made in memory by each test, never read from a
file. The upload box is found by its key, which changes each time it is
emptied (``screenshot_panel.upload_key``); the two boxes and the two
buttons by theirs.

Names defined here: ``PNG``, ``JPEG``, ``Check``, ``open_with_vision``,
``upload_box``, ``upload``, ``boxes`` and ``fill``.
"""

from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest
from streamlit.testing.v1.element_tree import FileUploader

from ledger_hand.core.assets import BUILT_IN_ASSETS
from ledger_hand.flows.recording import tuning_from
from ledger_hand.flows.uploading import VisionModelPresence
from ledger_hand.ports import ModelError, ModelPort, StoragePort
from ledger_hand.settings import DataPlaces, ModelSettings
from ledger_hand.ui.screenshot_panel import NOTE_KEY, READ_KEY, upload_key
from ledger_hand.ui.session import PARTS_KEY
from ledger_hand.wiring import Parts
from tests.ui.app_harness import APP_FILE, NOW, ZONE

# Pictures by their first bytes only, as the checks read them; the rest is invented.
PNG = b"\x89PNG\r\n\x1a\n" + b"invented picture bytes " * 4
JPEG = b"\xff\xd8\xff\xe0" + b"invented picture bytes " * 4
# More rounds of the upload box than any test uses.
_ROUNDS = 64


class Check:
    """Stands in for asking the server about the vision model; counts the asks."""

    def __init__(self, answer: VisionModelPresence | ModelError = VisionModelPresence.PRESENT):
        self.answer = answer
        self.asked = 0

    def __call__(self) -> VisionModelPresence:
        self.asked += 1
        if isinstance(self.answer, ModelError):
            raise self.answer
        return self.answer


def open_with_vision(
    model: ModelPort,
    book: StoragePort,
    *,
    vision_model: ModelPort | None,
    check: Check | None,
    settings: ModelSettings | None = None,
    data: Path | None = None,
) -> AppTest:
    """The page, run once, with the parts the test makes, the vision model and its check too."""
    chosen = ModelSettings() if settings is None else settings
    page = AppTest.from_file(str(APP_FILE), default_timeout=30)
    page.session_state[PARTS_KEY] = Parts(
        model=model,
        tuning=tuning_from(chosen),
        book=book,
        assets=BUILT_IN_ASSETS,
        clock=lambda: NOW,
        zone=ZONE,
        settings=chosen,
        places=None if data is None else DataPlaces(data),
        vision_model=vision_model,
        vision_check=check,
    )
    return page.run()


def upload_box(page: AppTest) -> FileUploader:
    """The one upload box on the page, found by its key."""
    keys = {upload_key(number) for number in range(_ROUNDS)}
    (box,) = [box for box in page.file_uploader if box.key in keys]
    return box


def upload(page: AppTest, data: bytes, name: str = "order.png", kind: str = "image/png") -> AppTest:
    """Hand the upload box a file: ``name``, ``data`` and the type a browser would give."""
    return upload_box(page).set_value((name, data, kind)).run()


def boxes(page: AppTest) -> tuple[str | None, str | None]:
    """What the box of the text read and the note's box show."""
    return page.text_area(key=READ_KEY).value, page.text_area(key=NOTE_KEY).value


def fill(page: AppTest, read: str | None = None, note: str | None = None) -> AppTest:
    """Type into the two boxes (not yet run): ``None`` leaves a box as it is."""
    if read is not None:
        page.text_area(key=READ_KEY).input(read)
    if note is not None:
        page.text_area(key=NOTE_KEY).input(note)
    return page
