"""Tests of the Assistant page with a ledger that has a tool for cash balances.

Asked about cash, the page lays out the ledger's balances under the
program's words, one row a money as the ledger gave them; under a table
of holdings it says how to see them; told of money moved, it shows the
program's words and sends nothing. Drawing again never asks the ledger.
The page runs headless with a scripted model; every figure is invented.
"""

from __future__ import annotations

from decimal import Decimal

from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ledger.invented_book import INVENTED_ASSETS
from ledger_hand.ports import ToolCall, ToolReply
from ledger_hand.ui.assistant_tables import NO_CASH, NO_CASH_ASKABLE
from ledger_hand.ui.assistant_view import exchange_key, how_key, table_key
from tests.fakes.routed_model import RoutedModel
from tests.fakes.scripted_model import scripted_record
from tests.flows.test_cash_balances_examples import EURO, YUAN
from tests.ui.assistant_harness import (
    captions,
    open_assistant,
    replies,
    rows_of,
    say_on_page,
    texts_of,
)


def calls(name: str) -> ToolReply:
    return ToolReply(text="", calls=(ToolCall(name=name, arguments={}),), record=scripted_record())


def with_cash() -> FakeLedger:
    return FakeLedger(
        assets=(*INVENTED_ASSETS, YUAN, EURO),
        cash={"USDT": Decimal("1200.5"), "USD": Decimal("-30"), "EUR": Decimal("250")},
    )


def test_the_balances_are_laid_out_one_row_a_money_as_the_ledger_gave_them() -> None:
    model = RoutedModel()

    page = say_on_page(open_assistant(model, ledger=with_cash()), "我还有多少USDT")

    reply = replies(page, 1)[0]
    assert reply.startswith("These are the cash balances in the ledger, counted up to 2026-11-24.")
    assert rows_of(page, table_key(1, "cash")) == [
        {"Money": "USDT", "Name": "Tether", "Balance": "1,200.5 USDT"},
        {"Money": "USD", "Name": "US dollar", "Balance": "-30 USD"},
        {"Money": "CNY", "Name": "Chinese yuan", "Balance": "0 CNY"},
        {"Money": "EUR", "Name": "Euro", "Balance": "250 EUR"},
    ]
    assert captions(page, exchange_key(1))[0] == "Words: the program's own words"
    lines = texts_of(page, how_key(1))
    assert "Cash balances in the ledger: read from the ledger, counted up to 2026-11-24" in lines


def test_k11_under_holdings_the_line_says_how_to_see_cash_and_drawing_again_asks_nothing() -> None:
    model = RoutedModel(tools=[calls("get_positions"), "这是你的持仓。"])
    ledger = with_cash()
    page = say_on_page(open_assistant(model, ledger=ledger), "我现在持有哪些币")
    asked = list(ledger.calls)

    page = page.run()
    page = page.run()

    assert NO_CASH_ASKABLE in captions(page, exchange_key(1))
    assert NO_CASH not in captions(page, exchange_key(1))
    assert ledger.calls == asked
    assert asked.count("cash_balances") == 1


def test_money_moved_said_shows_the_programs_words_and_sends_nothing() -> None:
    model = RoutedModel()
    ledger = with_cash()

    page = say_on_page(open_assistant(model, ledger=ledger), "我今天入金了500 USDT")

    assert replies(page, 1)[0] == (
        "The assistant does not record deposits, so nothing was sent to the ledger. "
        "Please record it in the ledger yourself."
    )
    assert len(page.container(key=exchange_key(1)).dataframe) == 0
    assert "propose_add" not in ledger.calls
    lines = texts_of(page, how_key(1))
    assert "Money moved that the assistant does not record: deposits" in lines
