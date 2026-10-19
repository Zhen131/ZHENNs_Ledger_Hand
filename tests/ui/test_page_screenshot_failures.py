"""Tests of every way an uploaded screenshot may not be read, on the page, run headless.

Each is said in the chat as one line of the program's, in the words of
``failure_words``; nothing of it is kept, the upload box is empty and can be
used again, and the page does not break. The plug, the size and the kind of
file are checked before the vision model or the server is asked anything;
the server is asked before any picture is sent. The key never shows. Every
byte, reply and name here is invented.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from ledger_hand.flows.uploading import (
    BYTES_PER_MB,
    EMPTY_REPLY_WORDS,
    UploadNotRead,
    UploadProblem,
    VisionModelPresence,
)
from ledger_hand.ports import FinishReason, ModelError, ModelErrorKind, ModelReply, ReplyRecord
from ledger_hand.settings import ModelSettings, Plug, Secret
from ledger_hand.storage.sqlite_store import SqliteStore
from ledger_hand.ui.failure_words import screenshot_not_read
from tests.fakes.routed_model import RoutedModel
from tests.fakes.scripted_model import ScriptedModel, Step
from tests.ui.app_harness import open_page, program_said
from tests.ui.app_harness import table as shown_table
from tests.ui.page_harness import every_text
from tests.ui.screenshot_harness import PNG, Check, open_with_vision, upload, upload_box

KEY = "sk-invented-page-screenshot-0123456789"
LOCAL = ModelSettings(model="invented-text:7b", vision_model="invented-vision:3b")
CLOUD = ModelSettings(plug=Plug.CLOUD, base_url="https://api.example.com/v1", api_key=Secret(KEY))
SMALL = ModelSettings(screenshot_max_mb=1)
TEXT = b"Bought 0.02 BTC at 94,900 yesterday; not a picture"
CUT_OFF = ModelReply(
    text="Side: buy\nPair: BT",
    record=ReplyRecord(
        model="invented-vision:3b",
        elapsed_seconds=2.0,
        prompt_tokens=30,
        reply_tokens=1024,
        finish=FinishReason.LENGTH_LIMIT,
    ),
)
EMPTY = ModelError(
    ModelErrorKind.MALFORMED_REPLY,
    f"the model server's answer {EMPTY_REPLY_WORDS}; the model wrote only its thinking",
    status=200,
)


def a_failure(kind: ModelErrorKind) -> ModelError:
    if kind is ModelErrorKind.MALFORMED_REPLY:
        return ModelError(kind, "the answer is not marked as complete", status=200)
    return ModelError(kind, "the invented server broke", status=503, snippet=f"key {KEY}")


def opened(
    tmp_path: Path,
    *,
    settings: ModelSettings = LOCAL,
    readings: list[Step] | None = None,
    check: Check | None = None,
) -> tuple[AppTest, RoutedModel, ScriptedModel | None, Check | None]:
    model = RoutedModel()
    local = settings.plug is Plug.LOCAL
    vision = ScriptedModel(readings or []) if local else None
    used = (Check() if check is None else check) if local else None
    page = open_with_vision(
        model,
        SqliteStore(tmp_path / "book.sqlite3"),
        vision_model=vision,
        check=used,
        settings=settings,
    )
    return page, model, vision, used


def nothing_kept(page: AppTest, model: RoutedModel) -> None:
    assert not page.exception
    assert len(page.text_area) == 0
    box = upload_box(page)
    assert not box.disabled
    assert box.value is None
    assert shown_table(page) == []
    calls = (model.screen, model.extraction, model.questions, model.answers, model.pictures)
    assert all(scripted.calls == [] for scripted in calls)


# --- before anything is asked ----------------------------------------------------


def test_the_cloud_plug_says_so_and_sends_nothing(tmp_path: Path) -> None:
    page, model, _, _ = opened(tmp_path, settings=CLOUD)

    page = upload(page, PNG)

    expected = UploadNotRead(UploadProblem.CLOUD_PLUG, len(PNG), CLOUD.screenshot_max_mb)
    assert program_said(page) == [screenshot_not_read(expected, CLOUD)]
    nothing_kept(page, model)
    assert KEY not in every_text(page)


def test_a_file_one_byte_over_the_limit_says_so_and_asks_nothing(tmp_path: Path) -> None:
    data = PNG + b"\0" * (BYTES_PER_MB + 1 - len(PNG))
    page, model, vision, check = opened(tmp_path, settings=SMALL)

    page = upload(page, data)

    expected = UploadNotRead(UploadProblem.TOO_LARGE, BYTES_PER_MB + 1, 1)
    assert program_said(page) == [screenshot_not_read(expected, SMALL)]
    assert "1.01 MB" in program_said(page)[0]
    nothing_kept(page, model)
    assert vision is not None and check is not None
    assert (vision.calls, check.asked) == ([], 0)


@pytest.mark.parametrize(
    ("data", "name", "kind"),
    [
        (TEXT, "order.png", "image/png"),
        (b"", "order.png", "image/png"),
        (b"GIF89a invented", "order.gif", "image/gif"),
    ],
    ids=["text named as a png", "an empty file", "a gif"],
)
def test_a_file_that_is_neither_a_png_nor_a_jpeg_says_so_and_asks_nothing(
    tmp_path: Path, data: bytes, name: str, kind: str
) -> None:
    page, model, vision, check = opened(tmp_path)

    page = upload(page, data, name=name, kind=kind)

    expected = UploadNotRead(UploadProblem.NOT_A_PICTURE, len(data), LOCAL.screenshot_max_mb)
    assert program_said(page) == [screenshot_not_read(expected, LOCAL)]
    nothing_kept(page, model)
    assert vision is not None and check is not None
    assert (vision.calls, check.asked) == ([], 0)


# --- the server asked, no picture sent -----------------------------------------------


def test_a_server_without_the_vision_model_says_so_and_sends_no_picture(tmp_path: Path) -> None:
    page, model, vision, check = opened(tmp_path, check=Check(VisionModelPresence.MISSING))

    page = upload(page, PNG)

    expected = UploadNotRead(UploadProblem.VISION_MODEL_MISSING, len(PNG), LOCAL.screenshot_max_mb)
    assert program_said(page) == [screenshot_not_read(expected, LOCAL)]
    assert "invented-vision:3b" in program_said(page)[0]
    nothing_kept(page, model)
    assert vision is not None and check is not None
    assert (vision.calls, check.asked) == ([], 1)


@pytest.mark.parametrize("kind", list(ModelErrorKind))
def test_a_server_that_cannot_be_asked_says_how_and_sends_no_picture(
    tmp_path: Path, kind: ModelErrorKind
) -> None:
    error = a_failure(kind)
    page, model, vision, _ = opened(tmp_path, check=Check(error))

    page = upload(page, PNG)

    expected = UploadNotRead(
        UploadProblem.VISION_MODEL_UNCHECKED, len(PNG), LOCAL.screenshot_max_mb, error=error
    )
    assert program_said(page) == [screenshot_not_read(expected, LOCAL)]
    nothing_kept(page, model)
    assert vision is not None and vision.calls == []


# --- the picture sent, nothing read --------------------------------------------------


@pytest.mark.parametrize("kind", list(ModelErrorKind))
def test_a_model_failure_while_reading_is_said_for_the_vision_model(
    tmp_path: Path, kind: ModelErrorKind
) -> None:
    error = a_failure(kind)
    page, model, vision, _ = opened(tmp_path, readings=[error])

    page = upload(page, PNG)

    expected = UploadNotRead(
        UploadProblem.MODEL_FAILED, len(PNG), LOCAL.screenshot_max_mb, error=error
    )
    (sentence,) = program_said(page)
    assert sentence == screenshot_not_read(expected, LOCAL)
    assert "invented-vision:3b" in sentence
    assert "invented-text:7b" not in sentence
    nothing_kept(page, model)
    assert vision is not None and len(vision.calls) == 1


def test_an_empty_reading_says_so(tmp_path: Path) -> None:
    page, model, _, _ = opened(tmp_path, readings=[EMPTY])

    page = upload(page, PNG)

    expected = UploadNotRead(UploadProblem.EMPTY, len(PNG), LOCAL.screenshot_max_mb)
    assert program_said(page) == [screenshot_not_read(expected, LOCAL)]
    nothing_kept(page, model)


def test_a_reading_cut_off_says_so(tmp_path: Path) -> None:
    page, model, _, _ = opened(tmp_path, readings=[CUT_OFF])

    page = upload(page, PNG)

    expected = UploadNotRead(UploadProblem.CUT_OFF, len(PNG), LOCAL.screenshot_max_mb)
    assert program_said(page) == [screenshot_not_read(expected, LOCAL)]
    nothing_kept(page, model)


def test_after_a_failure_the_same_file_can_be_uploaded_again_and_read(tmp_path: Path) -> None:
    page, _, vision, _ = opened(tmp_path, readings=[CUT_OFF, "Side: buy"])
    page = upload(page, PNG)

    page = upload(page, PNG)

    assert not page.exception
    assert page.text_area[0].value == "Side: buy"
    assert vision is not None and len(vision.calls) == 2


# --- the key never shows -----------------------------------------------------------------


def test_no_failure_ever_shows_the_key(tmp_path: Path) -> None:
    keyed = ModelSettings(api_key=Secret(KEY))
    error = ModelError(
        ModelErrorKind.SERVER_ERROR, "turned down", status=400, snippet=f"bad key {KEY}"
    )
    page, _, _, _ = opened(
        tmp_path, settings=keyed, readings=[error, EMPTY, CUT_OFF], check=Check()
    )
    for data in (PNG, PNG, PNG, TEXT):
        page = upload(page, data)

    assert len(program_said(page)) == 4
    assert KEY not in "\n".join(program_said(page))
    assert KEY not in every_text(page)


# --- where the area is drawn ---------------------------------------------------------------


def test_parts_handed_in_without_a_vision_model_show_no_upload_box(tmp_path: Path) -> None:
    page = open_page(RoutedModel(), SqliteStore(tmp_path / "book.sqlite3"))

    assert len(page.file_uploader) == 0
