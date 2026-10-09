"""Tests of the page's two reminders, neither of which holds anything back.

A passage saved before is typed again: the chat says on which day it was
saved and how many trades, and the passage can still be answered and saved.
A trade whose fee is paid in a third coin, neither USDT nor the coin
traded: its row and the chat both say the ledger takes the trade but leaves
that fee out of the cost; a fee in USDT or in the coin traded says nothing.
Every passage and reply below is invented.
"""

from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

from ledger_hand.core.book import Listing
from ledger_hand.settings import DataPlaces
from ledger_hand.storage.sqlite_store import SqliteStore
from ledger_hand.ui.preview import FEE_LEFT_OUT_MARK
from tests.fakes.routed_model import RoutedModel
from tests.flows.scripted_flow import row, screened, table
from tests.ui.app_harness import SAVE_KEY, button, press, program_said, send
from tests.ui.app_harness import table as shown_table
from tests.ui.page_harness import open_with

SPOT = screened(("spot_trade", "Bought 0.02 BTC"))
TWO = "Bought 0.02 BTC at 94,900 yesterday, fee 1 USDT; sold 1.5 ETH at 3,180 yesterday"
TWO_ROWS = table(
    row(
        side="buy", coin="BTC", quantity="0.02 BTC", price="94,900", fee="1 USDT", time="yesterday"
    ),
    row(side="sell", coin="ETH", quantity="1.5 ETH", price="3,180", time="yesterday"),
)
DUPLICATE = "Possible duplicate: this passage, or one that differs from it only in spacing or "


def book_in(tmp_path: Path) -> SqliteStore:
    return SqliteStore(DataPlaces(tmp_path / "data").book)


def saved(book: SqliteStore) -> int:
    return len(book.trades(Listing.ALL)) if book.path.exists() else 0


def recorded_twice(tmp_path: Path, again: str) -> tuple[AppTest, SqliteStore]:
    """The page once ``TWO`` was saved and ``again`` typed."""
    book = book_in(tmp_path)
    model = RoutedModel(screen=[SPOT, SPOT], extraction=[TWO_ROWS, TWO_ROWS])
    page = send(open_with(model, book, tmp_path / "data"), TWO)
    page = press(send(page, "2 USDT"), SAVE_KEY)
    assert saved(book) == 2
    return send(page, again), book


# --- V-9: the same passage again ------------------------------------------------------


def test_a_passage_saved_before_is_said_with_its_day_and_count_and_can_be_saved_again(
    tmp_path: Path,
) -> None:
    page, book = recorded_twice(tmp_path, TWO)

    assert not page.exception
    *_, reminder, question = program_said(page)
    assert reminder == (
        f"{DUPLICATE}full-width characters, was saved before: on 2026-10-07, 2 trade(s). "
        "Nothing is held back for it; Save keeps its trades again."
    )
    assert question.startswith("[Trade 2 of 2: fee] ")

    page = press(send(page, "2 USDT"), SAVE_KEY)

    assert program_said(page)[-1].startswith("Saved 2 trade(s)")
    assert saved(book) == 4


def test_the_same_passage_spaced_differently_is_reminded_too(tmp_path: Path) -> None:
    page, _ = recorded_twice(tmp_path, TWO.replace(" ", "  "))

    assert any(said.startswith(DUPLICATE) for said in program_said(page))


def test_a_passage_never_saved_brings_no_reminder(tmp_path: Path) -> None:
    model = RoutedModel(screen=[SPOT], extraction=[TWO_ROWS])

    page = send(open_with(model, book_in(tmp_path), tmp_path / "data"), TWO)

    assert not any(said.startswith(DUPLICATE) for said in program_said(page))


def test_two_earlier_saves_are_both_named(tmp_path: Path) -> None:
    book = book_in(tmp_path)
    model = RoutedModel(screen=[SPOT] * 3, extraction=[TWO_ROWS] * 3)
    page = open_with(model, book, tmp_path / "data")
    for _ in range(2):
        page = press(send(send(page, TWO), "2 USDT"), SAVE_KEY)

    page = send(page, TWO)

    reminders = [said for said in program_said(page) if said.startswith(DUPLICATE)]
    assert "saved before: on 2026-10-07, 2 trade(s); on 2026-10-07, 2 trade(s)." in reminders[-1]


# --- V-10: a fee in a third coin -----------------------------------------------------------

THREE = (
    "Yesterday bought 0.5 ETH at 3,420, fee 0.001 BNB; bought 0.02 BTC at 94,900, fee 1 USDT; "
    "bought 3 SOL at 150, fee 0.01 SOL"
)
THREE_ROWS = table(
    row(
        side="buy", coin="ETH", quantity="0.5 ETH", price="3,420", fee="0.001 BNB", time="Yesterday"
    ),
    row(
        side="buy", coin="BTC", quantity="0.02 BTC", price="94,900", fee="1 USDT", time="Yesterday"
    ),
    row(side="buy", coin="SOL", quantity="3 SOL", price="150", fee="0.01 SOL", time="Yesterday"),
)
LEFT_OUT = (
    "Trade 1: its fee is paid in BNB, which is neither USDT nor ETH. The ledger takes the trade, "
    "but leaves this fee out when it works out the cost."
)


def three_trades(tmp_path: Path) -> tuple[AppTest, SqliteStore]:
    book = book_in(tmp_path)
    model = RoutedModel(screen=[SPOT], extraction=[THREE_ROWS])
    return send(open_with(model, book, tmp_path / "data"), THREE), book


def test_only_the_fee_in_a_third_coin_is_marked_in_its_row(tmp_path: Path) -> None:
    page, _ = three_trades(tmp_path)

    assert not page.exception
    rows = shown_table(page)
    assert [r["Status"] for r in rows] == ["complete"] * 3
    assert [r["Fee coin"] for r in rows] == [f"BNB{FEE_LEFT_OUT_MARK}", "USDT", "SOL"]
    assert [r["Fee"] for r in rows] == ["0.001", "1", "0.01"]


def test_the_reminder_is_said_under_the_table_and_in_the_chat_for_that_trade_only(
    tmp_path: Path,
) -> None:
    page, _ = three_trades(tmp_path)

    captions = [str(c.value) for c in page.caption]
    assert [c for c in captions if "neither USDT nor" in c] == [LEFT_OUT]
    said = program_said(page)[-1]
    assert LEFT_OUT in said
    assert said.count("neither USDT nor") == 1


def test_the_reminder_holds_nothing_back(tmp_path: Path) -> None:
    page, book = three_trades(tmp_path)
    assert not button(page, SAVE_KEY).disabled

    page = press(page, SAVE_KEY)

    assert program_said(page)[-1].startswith("Saved 3 trade(s)")
    fees = [(t.trade.record.fee_coin, str(t.trade.record.fee)) for t in book.trades(Listing.ALL)]
    assert fees == [("BNB", "0.001"), ("USDT", "1"), ("SOL", "0.01")]
