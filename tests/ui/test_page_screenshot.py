"""Tests of recording from a screenshot on the page, run headless with fake models.

A screenshot uploaded is read by the vision model; the text read fills a box
that can be changed, beside an empty note; Continue joins the two into one
passage, shown in the chat as the person's, which goes on as a typed one
does, to the table, the questions and Save; Drop drops it. While a reading
waits, the upload box is greyed out and a message in the chat is not taken;
while a passage is recorded, the box is greyed out too. What the two boxes
hold lasts while the settings page is shown, and never carries over to the
next screenshot. Every passage, reply and byte here is invented.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit import config
from streamlit.testing.v1 import AppTest

from ledger_hand.core.book import Listing
from ledger_hand.flows.progress import Progress, Step
from ledger_hand.flows.screenshot import joined_passage
from ledger_hand.ports import StorageErrorKind
from ledger_hand.settings import ModelSettings
from ledger_hand.storage.sqlite_store import SqliteStore
from ledger_hand.ui import sayings, turns
from ledger_hand.ui.failure_words import STORAGE_FAILURES
from ledger_hand.ui.screenshot_panel import CONTINUE_KEY, DROP_KEY, NOTE_KEY, READ_KEY
from tests.fakes.memory_store import MemoryStore
from tests.fakes.routed_model import RoutedModel
from tests.fakes.scripted_model import ScriptedModel
from tests.flows.scripted_flow import row, screened, table
from tests.ui.app_harness import SAVE_KEY, button, press, program_said, said, send
from tests.ui.app_harness import table as shown_table
from tests.ui.page_harness import to_record, to_settings
from tests.ui.screenshot_harness import (
    JPEG,
    PNG,
    Check,
    boxes,
    fill,
    open_with_vision,
    upload,
    upload_box,
)

# As read, with a letter O where the zeros are; the person puts it right.
READ = "Side: buy\nPair: BTC/USDT\nFilled: 0.02 BTC\nAverage price: 94,9OO USDT\nTime: yesterday"
RIGHT = READ.replace("94,9OO", "94,900")
NOTE = "on OKX"
JOINED = joined_passage(RIGHT, NOTE)
SPOT = screened(("spot_trade", "Filled: 0.02 BTC"))
NO_FEE = table(
    row(
        side="buy",
        coin="BTC",
        quantity="0.02 BTC",
        price="94,900",
        time="yesterday",
        platform="OKX",
    )
)
OTHER_READ = "Side: sell\nPair: ETH/USDT\nFilled: 1.5 ETH"


def recording() -> RoutedModel:
    return RoutedModel(screen=[SPOT], extraction=[NO_FEE])


def calls(model: RoutedModel) -> int:
    parts = (model.screen, model.extraction, model.questions, model.answers)
    return sum(len(scripted.calls) for scripted in parts)


class Started:
    """Records every ``Progress`` the flow hands back to Continue."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.progress: list[Progress] = []
        real = turns.start_from_reading

        def recorded(*arguments: object, **keywords: object) -> Progress:
            taken = real(*arguments, **keywords)  # type: ignore[arg-type]
            self.progress.append(taken)
            return taken

        monkeypatch.setattr(turns, "start_from_reading", recorded)


def page_reading(
    tmp_path: Path, model: RoutedModel, *readings: str
) -> tuple[AppTest, ScriptedModel, Check]:
    vision = ScriptedModel(readings)
    check = Check()
    page = open_with_vision(
        model, SqliteStore(tmp_path / "book.sqlite3"), vision_model=vision, check=check
    )
    return page, vision, check


# --- V-4: a screenshot recorded -------------------------------------------------


def test_a_screenshot_uploaded_is_read_once_and_its_text_fills_a_box_beside_an_empty_note(
    tmp_path: Path,
) -> None:
    model = recording()
    page, vision, check = page_reading(tmp_path, model, READ)

    page = upload(page, PNG)

    assert not page.exception
    (call,) = vision.calls
    (picture,) = call.pictures
    assert picture.data == PNG
    assert check.asked == 1
    assert boxes(page) == (READ, "")
    assert program_said(page)[-1] == sayings.screenshot_read()
    assert upload_box(page).disabled
    assert calls(model) == 0


def test_continue_records_the_text_put_right_and_the_note_as_typed_through_save(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    started = Started(monkeypatch)
    model = recording()
    book = SqliteStore(tmp_path / "book.sqlite3")
    vision = ScriptedModel([READ])
    page = upload(open_with_vision(model, book, vision_model=vision, check=Check()), PNG)

    page = fill(page, read=RIGHT, note=NOTE).button(key=CONTINUE_KEY).click().run()

    assert not page.exception
    assert said(page)[-2] == ("user", JOINED)
    assert JOINED in model.screen.calls[0].messages[-1].content
    assert JOINED in model.extraction.calls[0].messages[-1].content
    (progress,) = started.progress
    assert progress.passage == JOINED
    assert progress.calls[0].step is Step.READING
    assert progress.prompts[0] == (Step.READING, "read-1")
    (asking,) = shown_table(page)
    assert (asking["Status"], asking["Coin"], asking["Platform"]) == ("asking", "BTC", "OKX")
    assert program_said(page)[-1].startswith("[Trade 1 of 1: fee] ")
    assert len(page.text_area) == 0
    assert upload_box(page).disabled
    assert len(vision.calls) == 1

    page = press(send(page, "1 USDT"), SAVE_KEY)

    assert program_said(page)[-1].startswith("Saved 1 trade(s)")
    (saved,) = book.trades(Listing.ALL)
    assert saved.trade.record.raw_text == JOINED
    assert not upload_box(page).disabled


def test_the_text_read_left_as_it_is_is_the_one_used(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    started = Started(monkeypatch)
    model = RoutedModel(screen=[SPOT], extraction=[NO_FEE])
    page, _, _ = page_reading(tmp_path, model, RIGHT)

    page = fill(upload(page, PNG), note=NOTE).button(key=CONTINUE_KEY).click().run()

    assert started.progress[0].passage == joined_passage(RIGHT, NOTE)
    assert ("user", joined_passage(RIGHT, NOTE)) in said(page)


def test_a_jpeg_is_read_too(tmp_path: Path) -> None:
    page, vision, _ = page_reading(tmp_path, recording(), READ)

    page = upload(page, JPEG, name="order.jpg", kind="image/jpeg")

    assert boxes(page) == (READ, "")
    assert vision.calls[0].pictures[0].data == JPEG


# --- V-8: what the page offers, and what lasts ------------------------------------


def test_drop_keeps_nothing_and_calls_no_model(tmp_path: Path) -> None:
    model = recording()
    page, vision, _ = page_reading(tmp_path, model, READ, OTHER_READ)
    page = fill(upload(page, PNG), note="a note").run()

    page = page.button(key=DROP_KEY).click().run()

    assert not page.exception
    assert program_said(page)[-1] == sayings.screenshot_dropped()
    assert len(page.text_area) == 0
    assert not upload_box(page).disabled
    assert (len(vision.calls), calls(model)) == (1, 0)
    assert shown_table(page) == []

    page = upload(page, PNG)

    assert boxes(page) == (OTHER_READ, "")


def test_while_a_reading_waits_the_upload_box_is_grey_and_a_message_is_not_taken(
    tmp_path: Path,
) -> None:
    model = recording()
    page, _, _ = page_reading(tmp_path, model, READ)
    page = fill(upload(page, PNG), note=NOTE).run()

    page = send(page, "Bought 1 ETH at 3,000 yesterday")

    assert not page.exception
    assert said(page)[-2] == ("user", "Bought 1 ETH at 3,000 yesterday")
    assert program_said(page)[-1] == sayings.screenshot_waiting()
    assert calls(model) == 0
    assert upload_box(page).disabled
    assert boxes(page) == (READ, NOTE)
    assert shown_table(page) == []


def test_while_a_passage_is_recorded_the_upload_box_is_grey(tmp_path: Path) -> None:
    passage = "Bought 0.02 BTC at 94,900 yesterday on OKX"
    model = RoutedModel(screen=[screened(("spot_trade", "Bought 0.02 BTC"))], extraction=[NO_FEE])
    page, _, _ = page_reading(tmp_path, model)
    assert not upload_box(page).disabled

    page = send(page, passage)

    assert [r["Status"] for r in shown_table(page)] == ["asking"]
    assert upload_box(page).disabled


def test_continue_when_the_book_cannot_be_read_keeps_the_reading_and_the_boxes(
    tmp_path: Path,
) -> None:
    model = recording()
    book = MemoryStore()
    vision = ScriptedModel([READ])
    page = open_with_vision(model, book, vision_model=vision, check=Check())
    page = fill(upload(page, PNG), read=RIGHT, note=NOTE).run()
    book.fail_next("earlier_saves", StorageErrorKind.LOCKED)

    page = page.button(key=CONTINUE_KEY).click().run()

    assert not page.exception
    assert program_said(page)[-1].startswith("The passage was not taken: the book could not")
    assert STORAGE_FAILURES[StorageErrorKind.LOCKED] in program_said(page)[-1]
    assert boxes(page) == (RIGHT, NOTE)
    assert not button(page, CONTINUE_KEY).disabled
    assert calls(model) == 0

    page = page.button(key=CONTINUE_KEY).click().run()

    assert ("user", JOINED) in said(page)
    assert [r["Status"] for r in shown_table(page)] == ["asking"]


def test_after_continue_the_next_screenshot_has_an_empty_note(tmp_path: Path) -> None:
    model = RoutedModel(screen=[SPOT, SPOT], extraction=[NO_FEE, NO_FEE])
    page, _, _ = page_reading(tmp_path, model, RIGHT, OTHER_READ)
    page = fill(upload(page, PNG), note=NOTE).button(key=CONTINUE_KEY).click().run()
    page = press(send(page, "1 USDT"), SAVE_KEY)

    page = upload(page, PNG)

    assert boxes(page) == (OTHER_READ, "")


def test_after_a_failure_nothing_is_kept_and_the_next_screenshot_has_its_own_text(
    tmp_path: Path,
) -> None:
    page, vision, _ = page_reading(tmp_path, recording(), READ, OTHER_READ)
    page = fill(upload(page, PNG), read="changed", note=NOTE).run()
    page = page.button(key=DROP_KEY).click().run()

    page = upload(page, b"not a picture", name="order.png")

    assert len(page.text_area) == 0
    assert not upload_box(page).disabled
    assert len(vision.calls) == 1

    page = upload(page, PNG)

    assert boxes(page) == (OTHER_READ, "")


def test_the_boxes_last_while_the_settings_page_is_shown_and_are_what_continue_takes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    started = Started(monkeypatch)
    page, _, _ = page_reading(tmp_path, recording(), READ)
    page = fill(upload(page, PNG), read=RIGHT, note=NOTE).run()

    page = to_record(to_settings(page))

    assert not page.exception
    assert boxes(page) == (RIGHT, NOTE)

    page = page.button(key=CONTINUE_KEY).click().run()

    assert started.progress[0].passage == JOINED


def test_both_boxes_emptied_make_an_empty_passage_which_is_not_sent(tmp_path: Path) -> None:
    model = recording()
    page, _, _ = page_reading(tmp_path, model, READ)

    page = fill(upload(page, PNG), read="", note="").button(key=CONTINUE_KEY).click().run()

    assert not page.exception
    assert program_said(page)[-1] == "Nothing was sent to the model: the passage is empty."
    assert calls(model) == 0
    assert len(page.text_area) == 0
    assert not upload_box(page).disabled


# --- what the page draws ----------------------------------------------------------


def test_the_upload_box_takes_any_kind_of_file_and_no_limit_of_its_own(tmp_path: Path) -> None:
    page, _, _ = page_reading(tmp_path, recording())

    box = upload_box(page)
    assert box.allowed_type == []
    assert not box.accept_multiple_files
    assert box.proto.max_upload_size_mb == config.get_option("server.maxUploadSize")
    assert f"{ModelSettings().screenshot_max_mb} MB" in box.help


def test_the_screenshot_area_draws_no_caption_and_no_error(tmp_path: Path) -> None:
    page, _, _ = page_reading(tmp_path, recording(), READ)

    page = fill(upload(page, PNG), note=NOTE).run()

    # Only the two under the table: the first is the legend, the last the word beside Save.
    first, last = (str(caption.value) for caption in page.caption)
    assert first.startswith("An amount marked * was worked out by the program")
    assert last == sayings.save_hint(None)
    assert not page.error
    assert {NOTE_KEY, READ_KEY} == {area.key for area in page.text_area}
