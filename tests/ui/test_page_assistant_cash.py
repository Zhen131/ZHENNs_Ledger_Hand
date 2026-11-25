"""Tests of the Assistant page when cash comes up: the fixed words, no table, the line under one.

The page runs headless with a scripted model and the demo ledger. Every
sentence and reply is invented.
"""

from __future__ import annotations

from ledger_hand.flows.cash_question import CASH_WORDS
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ports import ToolCall, ToolReply
from ledger_hand.ui.assistant_tables import NO_CASH
from ledger_hand.ui.assistant_view import exchange_key, how_key
from tests.fakes.routed_model import RoutedModel
from tests.fakes.scripted_model import scripted_record
from tests.ui.assistant_harness import captions, open_assistant, replies, say_on_page, texts_of


def calls(name: str, **arguments: object) -> ToolReply:
    return ToolReply(
        text="", calls=(ToolCall(name=name, arguments=dict(arguments)),), record=scripted_record()
    )


def test_a_question_about_cash_shows_the_fixed_words_and_no_table() -> None:
    model = RoutedModel()

    page = say_on_page(open_assistant(model, ledger=FakeLedger()), "我还有多少USDT")

    assert replies(page, 1)[0] == CASH_WORDS
    assert len(page.container(key=exchange_key(1)).dataframe) == 0
    assert captions(page, exchange_key(1))[0] == "Words: the program's own words"
    lines = texts_of(page, how_key(1))
    assert lines[0].startswith("Way: answered by the program itself: a question about cash")
    assert "Caught as a question about cash: how much of a money is still had" in lines
    assert model.tools.steps_left == 0


def test_the_model_saying_a_figure_beside_a_money_unasked_shows_the_fixed_words() -> None:
    model = RoutedModel(tools=["你账上还有 50 USDT。"])

    page = say_on_page(open_assistant(model, ledger=FakeLedger()), "帮我看看账户")

    assert replies(page, 1)[0] == CASH_WORDS
    assert not any("50 USDT" in line for line in texts_of(page, exchange_key(1)))


def test_holdings_and_sums_each_say_under_them_that_they_hold_no_cash() -> None:
    model = RoutedModel(
        tools=[calls("get_positions"), "这是你的持仓。", calls("get_period_summary"), "这是汇总。"]
    )

    page = say_on_page(open_assistant(model, ledger=FakeLedger()), "我现在持有哪些币")
    page = say_on_page(page, "一共花了多少")

    assert NO_CASH in captions(page, exchange_key(1))
    assert NO_CASH in captions(page, exchange_key(2))


def test_a_list_of_trades_has_no_such_line() -> None:
    model = RoutedModel(tools=[calls("list_trades", period="10月6号"), "10月6号有这些交易。"])

    page = say_on_page(open_assistant(model, ledger=FakeLedger()), "10月6号我买了什么")

    assert NO_CASH not in captions(page, exchange_key(1))
