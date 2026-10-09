"""Tests of the page's choices once a passage is settled: Don't save, Discard all, a new passage.

A trade seen to be wrong in the table can be kept out of the book, and the
whole passage dropped, both through the flow. A new passage typed while the
last one is settled but neither saved nor discarded is not taken: the page
says so and nothing is dropped or saved without a word. The book failing
breaks nothing. Every passage and reply below is invented.
"""

from __future__ import annotations

from pathlib import Path

from ledger_hand.core.book import Listing
from ledger_hand.ports import StorageErrorKind
from ledger_hand.storage.sqlite_store import SqliteStore
from tests.fakes.memory_store import MemoryStore
from tests.fakes.routed_model import RoutedModel
from tests.flows.scripted_flow import row, screened, table
from tests.ui.app_harness import (
    DISCARD_KEY,
    SAVE_KEY,
    button,
    dont_save_key,
    open_page,
    press,
    program_said,
    send,
)
from tests.ui.app_harness import table as shown_table

SPOT = screened(("spot_trade", "Bought 0.02 BTC"))
# Two trades, both complete: nothing is asked.
COMPLETE = (
    "Bought 0.02 BTC at 94,900 yesterday, fee 1 USDT; sold 1.5 ETH at 3,180 yesterday, fee 2 USDT"
)
COMPLETE_ROWS = table(
    row(
        side="buy",
        coin="BTC",
        quantity="0.02 BTC",
        price="94,900",
        fee="1 USDT",
        time="yesterday",
    ),
    row(
        side="sell",
        coin="ETH",
        quantity="1.5 ETH",
        price="3,180",
        fee="2 USDT",
        time="yesterday",
    ),
)
ANOTHER = "Sold 3 SOL at 150 today, fee 0.1 USDT"


def complete_two() -> RoutedModel:
    return RoutedModel(screen=[SPOT], extraction=[COMPLETE_ROWS])


def book_at(tmp_path: Path) -> SqliteStore:
    return SqliteStore(tmp_path / "book.sqlite3")


def saved_coins(book: SqliteStore) -> list[str]:
    if not book.path.exists():
        return []
    return [listed.trade.record.coin for listed in book.trades(Listing.ALL)]


def test_two_complete_trades_ask_nothing_and_each_can_be_left_out(tmp_path: Path) -> None:
    model = complete_two()

    page = send(open_page(model, book_at(tmp_path)), COMPLETE)

    assert len(model.questions.calls) == 0
    assert [r["Status"] for r in shown_table(page)] == ["complete", "complete"]
    assert not button(page, dont_save_key(1)).disabled
    assert not button(page, dont_save_key(2)).disabled
    assert not button(page, SAVE_KEY).disabled
    assert program_said(page)[-1].startswith("Every trade is settled; 2 will be saved.")


def test_dont_save_keeps_that_trade_out_of_the_book(tmp_path: Path) -> None:
    book = book_at(tmp_path)
    page = press(send(open_page(complete_two(), book), COMPLETE), dont_save_key(2))

    assert not page.exception
    assert program_said(page)[-1] == "Trade 2 will not be saved."
    assert [r["Status"] for r in shown_table(page)] == ["complete", "left out"]
    assert button(page, dont_save_key(2)).disabled
    assert not button(page, dont_save_key(1)).disabled

    page = press(page, SAVE_KEY)

    assert program_said(page)[-1].startswith("Saved 1 trade(s)")
    assert saved_coins(book) == ["BTC"]


def test_with_every_trade_left_out_nothing_can_be_saved(tmp_path: Path) -> None:
    page = send(open_page(complete_two(), book_at(tmp_path)), COMPLETE)

    page = press(press(page, dont_save_key(1)), dont_save_key(2))

    assert button(page, SAVE_KEY).disabled
    assert not button(page, DISCARD_KEY).disabled
    assert "Nothing is left to save" in program_said(page)[-1]


def test_discard_all_drops_the_passage_and_the_book_gets_nothing(tmp_path: Path) -> None:
    book = book_at(tmp_path)
    page = press(send(open_page(complete_two(), book), COMPLETE), DISCARD_KEY)

    assert not page.exception
    assert program_said(page)[-1] == "This passage was not saved: nothing from it is kept."
    assert shown_table(page) == []
    assert button(page, SAVE_KEY).disabled
    assert saved_coins(book) == []


def test_discard_all_while_a_question_waits_drops_the_passage(tmp_path: Path) -> None:
    passage = "Sold 1.5 ETH at 3,180 yesterday"
    reply = table(row(side="sell", coin="ETH", quantity="1.5 ETH", price="3,180", time="yesterday"))
    page = send(
        open_page(RoutedModel(screen=[SPOT], extraction=[reply]), book_at(tmp_path)), passage
    )
    assert not button(page, DISCARD_KEY).disabled

    page = press(page, DISCARD_KEY)

    assert shown_table(page) == []
    assert program_said(page)[-1] == "This passage was not saved: nothing from it is kept."


def test_a_new_passage_while_the_last_is_not_saved_is_not_taken(tmp_path: Path) -> None:
    model = complete_two()
    book = book_at(tmp_path)
    page = send(open_page(model, book), COMPLETE)

    page = send(page, ANOTHER)

    assert not page.exception
    message = program_said(page)[-1]
    assert message.startswith("The last passage is not saved yet")
    assert "Save" in message and "Discard all" in message
    assert len(model.screen.calls) == 1
    assert [r["Coin"] for r in shown_table(page)] == ["BTC", "ETH"]
    assert not button(page, SAVE_KEY).disabled
    assert not button(page, DISCARD_KEY).disabled
    assert saved_coins(book) == []

    page = press(page, SAVE_KEY)

    assert saved_coins(book) == ["BTC", "ETH"]


def test_a_new_passage_after_discarding_is_taken(tmp_path: Path) -> None:
    another = table(
        row(side="sell", coin="SOL", quantity="3 SOL", price="150", fee="0.1 USDT", time="today")
    )
    model = RoutedModel(screen=[SPOT, SPOT], extraction=[COMPLETE_ROWS, another])
    page = press(send(open_page(model, book_at(tmp_path)), COMPLETE), DISCARD_KEY)

    page = send(page, ANOTHER)

    assert [r["Coin"] for r in shown_table(page)] == ["SOL"]


# --- the book failing ---------------------------------------------------------


def test_a_book_that_cannot_be_read_stops_the_passage_before_the_model(tmp_path: Path) -> None:
    book = MemoryStore()
    book.fail_next("earlier_saves", StorageErrorKind.LOCKED)
    model = complete_two()

    page = send(open_page(model, book), COMPLETE)

    assert not page.exception
    assert program_said(page)[-1].startswith("The passage was not taken: the book could not")
    assert len(model.screen.calls) == 0
    assert shown_table(page) == []


def test_a_save_that_fails_keeps_the_passage_so_save_can_be_pressed_again() -> None:
    book = MemoryStore()
    page = send(open_page(complete_two(), book), COMPLETE)
    book.fail_next("save", StorageErrorKind.LOCKED)

    page = press(page, SAVE_KEY)

    assert not page.exception
    assert program_said(page)[-1].startswith("Nothing was saved: the book could not be used")
    assert [r["Coin"] for r in shown_table(page)] == ["BTC", "ETH"]
    assert not button(page, SAVE_KEY).disabled

    page = press(page, SAVE_KEY)

    assert program_said(page)[-1].startswith("Saved 2 trade(s)")
    assert [listed.trade.record.coin for listed in book.trades(Listing.ALL)] == ["BTC", "ETH"]
