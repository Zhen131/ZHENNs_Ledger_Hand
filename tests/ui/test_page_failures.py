"""Tests of the page when something fails: one plain sentence for each failure, and nothing breaks.

Each of the six kinds of model failure, and replies that cannot be read as
a table, gets its own sentence in the chat, saying what happened and what
can be done. A passage that is empty or too long is not sent, and says so.
A book written by a newer version of the program, or a file that is not a
book, is said in plain words when a passage is typed, on Save and on Export,
and its bytes are left exactly as they were. Every passage and reply below
is invented.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from contextlib import closing
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from ledger_hand.core.book import Listing
from ledger_hand.ports import ModelError, ModelErrorKind
from ledger_hand.settings import DataPlaces, ModelSettings
from ledger_hand.storage.book_file import BOOK_VERSION
from ledger_hand.storage.sqlite_store import SqliteStore
from ledger_hand.ui.export_panel import EXPORT_KEY
from tests.fakes.memory_store import MemoryStore
from tests.fakes.routed_model import RoutedModel
from tests.flows.scripted_flow import row, screened, table
from tests.ui.app_harness import SAVE_KEY, button, press, program_said, send
from tests.ui.app_harness import table as shown_table
from tests.ui.page_harness import note, open_with

ADDRESS = "http://127.0.0.1:59999"
SETTINGS = ModelSettings(base_url=ADDRESS, model="invented-model:3b", timeout_seconds=45)
SPOT = screened(("spot_trade", "Bought 0.02 BTC"))
COMPLETE = "Bought 0.02 BTC at 94,900 yesterday, fee 1 USDT"
COMPLETE_ROWS = table(
    row(side="buy", coin="BTC", quantity="0.02 BTC", price="94,900", fee="1 USDT", time="yesterday")
)
# What each kind of failure is said with, beyond what every one of them says.
OWN_WORDS = {
    ModelErrorKind.UNREACHABLE: f"No model answered at {ADDRESS}. If the model runs on this "
    "machine, check that Ollama is running",
    ModelErrorKind.TIMED_OUT: "No whole reply came within 45 seconds.",
    ModelErrorKind.MODEL_NOT_FOUND: f"The server at {ADDRESS} has no model named invented-model:3b",
    ModelErrorKind.RATE_LIMITED: "turned the call away because it was called too often",
    ModelErrorKind.SERVER_ERROR: "reported an error of its own (status 503)",
    ModelErrorKind.MALFORMED_REPLY: "answered, but not in the agreed form",
}
STEPS = {"judging the passage": "screen", "extracting the trades": "extraction"}


def calls(model: RoutedModel) -> int:
    parts = (model.screen, model.extraction, model.questions, model.answers)
    return sum(len(scripted.calls) for scripted in parts)


def page_with(model: RoutedModel, tmp_path: Path) -> AppTest:
    return open_with(model, MemoryStore(), tmp_path / "data", settings=SETTINGS)


# --- V-6: each kind of model failure, and replies that cannot be read ----------------


@pytest.mark.parametrize("step", list(STEPS))
@pytest.mark.parametrize("kind", list(ModelErrorKind))
def test_each_kind_of_model_failure_gets_its_own_plain_sentence(
    tmp_path: Path, kind: ModelErrorKind, step: str
) -> None:
    error = ModelError(
        kind, "invented", status=503 if kind is ModelErrorKind.SERVER_ERROR else None
    )
    if STEPS[step] == "screen":
        model = RoutedModel(screen=[error])
    else:
        model = RoutedModel(screen=[SPOT], extraction=[error])

    page = send(page_with(model, tmp_path), COMPLETE)

    assert not page.exception
    (said,) = program_said(page)
    assert said.startswith(
        f"The model gave no usable reply while {step}, so nothing was recorded. "
    )
    assert OWN_WORDS[kind] in said
    assert shown_table(page) == []
    assert button(page, SAVE_KEY).disabled


def test_the_six_sentences_are_six_different_ones(tmp_path: Path) -> None:
    errors = [ModelError(kind, "invented") for kind in ModelErrorKind]
    page = page_with(RoutedModel(screen=errors), tmp_path)
    for _ in errors:
        page = send(page, COMPLETE)

    assert not page.exception
    said = program_said(page)
    assert len(said) == len(set(said)) == len(ModelErrorKind)


@pytest.mark.parametrize("step", list(STEPS))
def test_replies_that_cannot_be_read_as_a_table_are_said_apart(tmp_path: Path, step: str) -> None:
    unreadable = ["this is not the table", "nor is this", "nor this"]
    if STEPS[step] == "screen":
        model = RoutedModel(screen=unreadable)
    else:
        model = RoutedModel(screen=[SPOT], extraction=unreadable)

    page = send(page_with(model, tmp_path), COMPLETE)

    assert not page.exception
    (said,) = program_said(page)
    assert said.startswith(
        f"The model gave no usable reply while {step}, so nothing was recorded. "
    )
    assert "could not be read as the table it was asked for" in said
    assert all(words not in said for words in OWN_WORDS.values())


# --- V-7: nothing to send, or too much -------------------------------------------------


def test_an_empty_passage_is_not_sent(tmp_path: Path) -> None:
    model = RoutedModel()

    page = send(page_with(model, tmp_path), "  ")

    assert program_said(page) == ["Nothing was sent to the model: the passage is empty."]
    assert calls(model) == 0


def test_a_passage_too_long_names_the_limit_and_is_not_sent(tmp_path: Path) -> None:
    model = RoutedModel()

    page = send(page_with(model, tmp_path), "买" * 16_385)

    assert not page.exception
    (said,) = program_said(page)[-1:]
    assert said.startswith("Nothing was sent to the model: the passage is longer than the 16,384 ")
    assert "Split it into shorter passages" in said
    assert calls(model) == 0
    assert shown_table(page) == []


# --- V-8: a book of a newer version, and a file that is not a book ----------------------


def newer_book(path: Path) -> None:
    SqliteStore(path).trades(Listing.ALL)
    with closing(sqlite3.connect(path)) as connection:
        connection.execute(f"PRAGMA user_version = {BOOK_VERSION + 1}")


def not_a_book(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"these bytes are not a database at all\n" * 200)


BAD_BOOKS: dict[str, tuple[Callable[[Path], None], str]] = {
    "newer": (newer_book, "The book was written by a newer version of this program"),
    "not a book": (not_a_book, "The book's file is not a database, so it was left as it is"),
}


def bad_book(tmp_path: Path, which: str) -> tuple[Path, bytes]:
    path = DataPlaces(tmp_path / "data").book
    BAD_BOOKS[which][0](path)
    return path, path.read_bytes()


@pytest.mark.parametrize("which", list(BAD_BOOKS))
def test_a_bad_book_is_said_plainly_when_a_passage_is_typed_and_left_as_it_is(
    tmp_path: Path, which: str
) -> None:
    path, before = bad_book(tmp_path, which)
    model = RoutedModel(screen=[SPOT], extraction=[COMPLETE_ROWS])

    page = send(open_with(model, SqliteStore(path), tmp_path / "data"), COMPLETE)

    assert not page.exception
    said = program_said(page)[-1]
    assert said.startswith("The passage was not taken: the book could not be used. ")
    assert BAD_BOOKS[which][1] in said
    assert str(path) in said
    assert calls(model) == 0
    assert path.read_bytes() == before


@pytest.mark.parametrize("which", list(BAD_BOOKS))
def test_a_bad_book_is_said_plainly_on_export_and_left_as_it_is(tmp_path: Path, which: str) -> None:
    path, before = bad_book(tmp_path, which)

    page = press(open_with(RoutedModel(), SqliteStore(path), tmp_path / "data"), EXPORT_KEY)

    assert not page.exception
    tone, words = note(page) or ("", "")
    assert tone == "error"
    assert words.startswith("Nothing was exported: the book could not be used. ")
    assert BAD_BOOKS[which][1] in words
    assert path.read_bytes() == before
    assert not DataPlaces(tmp_path / "data").exports.exists()


@pytest.mark.parametrize("which", list(BAD_BOOKS))
def test_a_book_gone_bad_before_save_is_said_plainly_and_the_passage_stays(
    tmp_path: Path, which: str
) -> None:
    path = DataPlaces(tmp_path / "data").book
    model = RoutedModel(screen=[SPOT], extraction=[COMPLETE_ROWS])
    page = send(open_with(model, SqliteStore(path), tmp_path / "data"), COMPLETE)
    assert not button(page, SAVE_KEY).disabled
    path.unlink()
    BAD_BOOKS[which][0](path)
    before = path.read_bytes()

    page = press(page, SAVE_KEY)

    assert not page.exception
    said = program_said(page)[-1]
    assert said.startswith("Nothing was saved: the book could not be used. ")
    assert BAD_BOOKS[which][1] in said
    assert said.endswith("The passage is still here, so Save can be pressed again.")
    assert path.read_bytes() == before
    assert [r["Coin"] for r in shown_table(page)] == ["BTC"]
