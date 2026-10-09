"""Tests of the page while a passage is recorded: the chat, the table and Save, run headless.

The real page runs under Streamlit's own test runner with a scripted model,
a book in a temporary folder, a fixed clock and a fixed zone. A passage goes
in through the chat; the questions, with the flow's labels, come back in
the chat and are answered there; the table shows each trade with the price
and the total side by side; Save keeps the records in the book. Every
passage and reply below is invented.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ledger_hand.core.book import Listing
from ledger_hand.ports import ModelError, ModelErrorKind
from ledger_hand.storage.sqlite_store import SqliteStore
from tests.fakes.routed_model import RoutedModel
from tests.flows.scripted_flow import row, screened, table
from tests.ui.app_harness import (
    DISCARD_KEY,
    SAVE_KEY,
    button,
    column_names,
    dont_save_key,
    open_page,
    press,
    program_said,
    said,
    send,
)
from tests.ui.app_harness import table as shown_table

SPOT = screened(("spot_trade", "Bought 0.02 BTC"))
# Two trades; the second says no fee.
TWO = "Bought 0.02 BTC at 94,900 yesterday, fee 1 USDT; sold 1.5 ETH at 3,180 yesterday"
TWO_ROWS = table(
    row(
        side="buy",
        coin="BTC",
        quantity="0.02 BTC",
        price="94,900",
        fee="1 USDT",
        time="yesterday",
    ),
    row(side="sell", coin="ETH", quantity="1.5 ETH", price="3,180", time="yesterday"),
)
DAY = "2026-10-06 (Europe/Budapest)"


def two_trades() -> RoutedModel:
    return RoutedModel(screen=[SPOT], extraction=[TWO_ROWS])


def book_at(tmp_path: Path) -> SqliteStore:
    return SqliteStore(tmp_path / "book.sqlite3")


def saved_count(book: SqliteStore) -> int:
    if not book.path.exists():
        return 0
    return len(book.trades(Listing.ALL))


def calls(model: RoutedModel) -> int:
    parts = (model.screen, model.extraction, model.questions, model.answers)
    return sum(len(scripted.calls) for scripted in parts)


# --- a passage of two trades, the second without its fee --------------------


def test_the_question_comes_in_the_chat_with_its_label_and_save_cannot_be_pressed(
    tmp_path: Path,
) -> None:
    page = send(open_page(two_trades(), book_at(tmp_path)), TWO)

    assert not page.exception
    assert said(page)[0] == ("user", TWO)
    question = program_said(page)[-1]
    assert question.startswith("[Trade 2 of 2: fee] ")
    assert "'skip'" in question
    rows = shown_table(page)
    assert [r["#"] for r in rows] == ["1", "2"]
    assert [r["Status"] for r in rows] == ["complete", "asking"]
    assert (rows[1]["Coin"], rows[1]["Fee"], rows[1]["Fee coin"]) == ("ETH", "", "")
    assert button(page, SAVE_KEY).disabled
    assert not button(page, DISCARD_KEY).disabled
    assert button(page, dont_save_key(1)).disabled and button(page, dont_save_key(2)).disabled
    assert "Answer the question in the chat first" in [c.value for c in page.caption][-1]


def test_the_price_and_the_total_stand_side_by_side(tmp_path: Path) -> None:
    page = send(open_page(two_trades(), book_at(tmp_path)), TWO)

    names = column_names(page)
    assert names.index("Total") == names.index("Price") + 1
    assert {
        "Time",
        "Coin",
        "Side",
        "Quantity",
        "Fee",
        "Fee coin",
        "Platform",
        "Note",
        "Status",
    } <= (set(names))


def test_the_answer_completes_the_trade_and_save_keeps_both_in_the_book(tmp_path: Path) -> None:
    book = book_at(tmp_path)
    page = send(send(open_page(two_trades(), book), TWO), "2 USDT")

    rows = shown_table(page)
    assert [r["Status"] for r in rows] == ["complete", "complete"]
    assert (rows[1]["Fee"], rows[1]["Fee coin"]) == ("2", "USDT")
    assert not button(page, SAVE_KEY).disabled
    assert saved_count(book) == 0

    page = press(page, SAVE_KEY)

    assert not page.exception
    assert program_said(page)[-1].startswith("Saved 2 trade(s)")
    listed = book.trades(Listing.ALL)
    assert [(t.trade.record.coin, t.trade.record.fee) for t in listed] == [
        ("BTC", Decimal("1")),
        ("ETH", Decimal("2")),
    ]
    assert shown_table(page) == []
    assert button(page, SAVE_KEY).disabled
    assert button(page, DISCARD_KEY).disabled


def test_after_saving_the_next_passage_is_taken_as_a_new_one(tmp_path: Path) -> None:
    model = RoutedModel(screen=[SPOT, SPOT], extraction=[TWO_ROWS, TWO_ROWS])
    page = press(send(send(open_page(model, book_at(tmp_path)), TWO), "2 USDT"), SAVE_KEY)

    page = send(page, TWO)

    assert len(model.screen.calls) == 2
    assert [r["Status"] for r in shown_table(page)] == ["complete", "asking"]


# --- what the flow works out is marked, and only once the trade has passed ---

QUANTITY_AND_TOTAL = "Bought 0.5 ETH yesterday for 1,710 in all, fee 0"
WITHOUT_THE_FEE = "Bought 0.5 ETH yesterday for 1,710 in all"


def quantity_and_total(*, fee: str) -> RoutedModel:
    reply = table(
        row(side="buy", coin="ETH", quantity="0.5 ETH", total="1,710", fee=fee, time="yesterday")
    )
    return RoutedModel(screen=[SPOT], extraction=[reply])


def test_a_price_worked_out_from_the_quantity_and_the_total_is_marked(tmp_path: Path) -> None:
    page = send(open_page(quantity_and_total(fee="0"), book_at(tmp_path)), QUANTITY_AND_TOTAL)

    (only,) = shown_table(page)
    assert (only["Quantity"], only["Price"], only["Total"]) == ("0.5", "3420 *", "1710")
    assert only["Status"] == "complete"
    assert "* worked out by the program" in [c.value for c in page.caption][0]


def test_the_mark_appears_only_once_the_trade_has_passed_the_check(tmp_path: Path) -> None:
    page = send(open_page(quantity_and_total(fee=""), book_at(tmp_path)), WITHOUT_THE_FEE)

    (asking,) = shown_table(page)
    assert asking["Status"] == "asking"
    assert (asking["Price"], asking["Total"]) == ("", "1710")

    page = send(page, "none")

    (complete,) = shown_table(page)
    assert complete["Status"] == "complete"
    assert (complete["Price"], complete["Total"]) == ("3420 *", "1710")


def test_the_time_is_shown_as_the_record_holds_it(tmp_path: Path) -> None:
    passage = "Bought 0.02 BTC at 94,900 yesterday at 21:40, fee 1 USDT"
    reply = table(
        row(
            side="buy",
            coin="BTC",
            quantity="0.02 BTC",
            price="94,900",
            fee="1 USDT",
            time="yesterday at 21:40",
        )
    )
    model = RoutedModel(screen=[SPOT], extraction=[reply])

    (only,) = shown_table(send(open_page(model, book_at(tmp_path)), passage))

    assert only["Time"] == "2026-10-06 21:40 (Europe/Budapest)"


# --- answers that leave a trade out or end the passage -----------------------


def test_skip_leaves_the_trade_out(tmp_path: Path) -> None:
    page = send(send(open_page(two_trades(), book_at(tmp_path)), TWO), "skip")

    assert [r["Status"] for r in shown_table(page)] == ["complete", "left out"]
    assert not button(page, SAVE_KEY).disabled


def test_cancel_drops_the_passage_and_keeps_nothing(tmp_path: Path) -> None:
    book = book_at(tmp_path)
    page = send(send(open_page(two_trades(), book), TWO), "cancel")

    assert program_said(page)[-1] == "This passage was not saved: nothing from it is kept."
    assert shown_table(page) == []
    assert button(page, SAVE_KEY).disabled
    assert saved_count(book) == 0


def test_a_trade_that_cannot_be_recorded_says_why_and_nothing_can_be_saved(
    tmp_path: Path,
) -> None:
    passage = "昨天买了 2 个 ETH，0.0062 BTC 一个，手续费 0"
    reply = table(
        row(side="buy", coin="ETH", quantity="2 个", price="0.0062 BTC 一个", fee="0", time="昨天")
    )
    model = RoutedModel(screen=[SPOT], extraction=[reply])
    page = send(open_page(model, book_at(tmp_path)), passage)
    assert "'0.0062 BTC 一个'" in program_said(page)[-1]

    page = send(page, "0.0062 BTC")

    (only,) = shown_table(page)
    assert only["Status"].startswith("cannot record: ")
    assert "cannot be recorded" in program_said(page)[-1]
    assert button(page, SAVE_KEY).disabled
    assert button(page, dont_save_key(1)).disabled
    assert not button(page, DISCARD_KEY).disabled


def test_the_persons_words_are_shown_exactly_as_typed(tmp_path: Path) -> None:
    typed = "**bought** _0.5_ ETH # at <b>3,420</b>  yesterday\\n"
    model = RoutedModel(screen=[screened()])

    page = send(open_page(model, book_at(tmp_path)), typed)

    assert said(page)[0] == ("user", typed)


# --- nothing to send, nothing to record, and a model that fails ---------------


@pytest.mark.parametrize("typed", ["", "   ", " \t "])
def test_an_empty_passage_is_answered_in_words_and_no_model_is_asked(
    tmp_path: Path, typed: str
) -> None:
    model = RoutedModel()

    page = send(open_page(model, book_at(tmp_path)), typed)

    assert not page.exception
    assert program_said(page) == ["Nothing was sent to the model: the passage is empty."]
    assert calls(model) == 0
    assert shown_table(page) == []
    assert button(page, SAVE_KEY).disabled


def test_a_passage_of_futures_only_is_stopped_with_the_reason_and_its_own_words(
    tmp_path: Path,
) -> None:
    passage = "Opened a 10x long on BTC at 94,900 yesterday"
    model = RoutedModel(screen=[screened(("futures_or_leverage", "10x long"))])

    page = send(open_page(model, book_at(tmp_path)), passage)

    assert not page.exception
    message = program_said(page)[-1]
    assert message.startswith("Nothing from this passage will be recorded:")
    assert "'10x long'" in message
    assert "futures or leveraged trading" in message
    assert len(model.extraction.calls) == 0
    assert shown_table(page) == []
    assert button(page, SAVE_KEY).disabled


def test_a_passage_without_a_trade_says_so(tmp_path: Path) -> None:
    model = RoutedModel(screen=[screened()])

    page = send(open_page(model, book_at(tmp_path)), "The market was quiet today")

    assert program_said(page) == [
        "No trade was found in this passage, so nothing will be recorded."
    ]
    assert shown_table(page) == []


@pytest.mark.parametrize("kind", list(ModelErrorKind))
@pytest.mark.parametrize("step", ["judging", "extraction"])
def test_a_model_that_fails_gets_one_plain_sentence_and_the_page_does_not_break(
    tmp_path: Path, kind: ModelErrorKind, step: str
) -> None:
    error = ModelError(kind, "invented")
    if step == "judging":
        model = RoutedModel(screen=[error])
    else:
        model = RoutedModel(screen=[SPOT], extraction=[error])

    page = send(open_page(model, book_at(tmp_path)), TWO)

    assert not page.exception
    (message,) = program_said(page)
    assert message.startswith("The model gave no usable reply while ")
    assert "nothing was recorded" in message
    assert shown_table(page) == []
    assert button(page, SAVE_KEY).disabled

    retried = send(page, "")

    assert not retried.exception
