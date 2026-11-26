"""Tests that money moved said beside a coin or share never swallows the trade whole.

Since the rework of 2026-11-26 the reading of money moved answers a
sentence whole only when it names no coin or share and says no buy or
sell; otherwise it goes to the model, the reply ending with the line that
the rest is recorded by hand. A question about cash said, not asked, that
names a coin or share ends with a line that a trade meant is to be said
again. A scripted model stands in; every sentence and figure is invented,
the trades of ``sentences/trades_beside_money_moved.txt`` written by the
independent check of that day.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ledger_hand.core.cash_words import held_names
from ledger_hand.core.ledger_table import names_of
from ledger_hand.core.money_asks import statement
from ledger_hand.core.spoken_text import tidy_spoken
from ledger_hand.flows.cash_answers import NOT_RECORDED_EITHER, TRADE_AS_CASH_WORDS
from ledger_hand.flows.cash_question import CASH_WORDS
from ledger_hand.flows.conversation import AssistantChat, Route, Said, say
from ledger_hand.ledger.demo_book import DEMO_ASSETS
from ledger_hand.ledger.demo_cash import demo_ledger_with_cash
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ledger.invented_book import INVENTED_NOW, INVENTED_ZONE
from ledger_hand.ports import ToolReply
from tests.fakes.routed_model import RoutedModel
from tests.fakes.scripted_model import scripted_record

TRADES = [
    line
    for line in (Path(__file__).parent / "sentences" / "trades_beside_money_moved.txt")
    .read_text(encoding="utf-8")
    .splitlines()
    if line.strip() and not line.startswith("#")
]
HELD = (*(name for name, _ in names_of(()).built_in), *held_names(DEMO_ASSETS))
THAT_PART = "Please record that part in the ledger yourself"

# The sentences the check found swallowed whole before the rework.
SWALLOWED = [
    "股息再投资了0.1股KO，一股70美元",
    "Dividend reinvested into 0.1 KO at 70 USD today",
    "今天分红到账，又补了0.1股KO，一股70美元",
    "Topped up my ETH position with 0.2 ETH at 2500 USDT today",
    "Topped up 0.1 BTC at 98000 USDT today",
    "今天入金后入了0.01个BTC，价格98000 USDT",
    "今天充值500U，上车了0.01个BTC，价格98000 USDT",
    "今天入金500U，梭哈了0.005个BTC，价格98000 USDT",
    "Deposited 500 USDT and went long 0.01 BTC at 98000 today",
    "Deposited 500 USDT, got 0.01 BTC at 98000 today",
]


def said_once(text: str, ledger: FakeLedger, *words: str) -> Said:
    replies = [ToolReply(text=one, calls=(), record=scripted_record()) for one in words]
    return say(
        AssistantChat(),
        text,
        model=RoutedModel(tools=replies),
        ledger=ledger,
        now=INVENTED_NOW,
        zone=INVENTED_ZONE,
        max_steps=6,
    )


@pytest.mark.parametrize("text", SWALLOWED)
def test_a_trade_beside_money_moved_goes_to_the_model_with_both_lines(text: str) -> None:
    said = said_once(text, demo_ledger_with_cash(), "好的。")

    assert said.route is not Route.MANUAL
    if said.manual is not None:
        assert said.route is Route.MODEL
        assert THAT_PART in said.reply
        assert NOT_RECORDED_EITHER in said.reply


@pytest.mark.parametrize(
    "text",
    ["我今天入金了500 USDT", "昨天分红到账2.1美元", "换了300欧元", "出金200 USDT"],
)
def test_a_pure_statement_is_still_answered_whole(text: str) -> None:
    said = said_once(text, demo_ledger_with_cash())

    assert said.route is Route.MANUAL
    assert said.reply.endswith("Please record it in the ledger yourself.")


def test_no_trade_of_the_check_is_swallowed_whole_by_the_first_reading() -> None:
    swallowed = []
    for text in TRADES:
        tidied = tidy_spoken(text, INVENTED_ZONE).text
        found = statement(tidied, HELD)
        if found is not None and not found.with_trade:
            swallowed.append(text)

    assert len(TRADES) >= 75
    assert swallowed == []


@pytest.mark.parametrize(
    "text",
    [
        "今天现金买了2股KO，一股70美元",
        "入金500U到现金账户，然后今天上午10点买了0.01个BTC，价格98000 USDT",
        "用U剩下的500买了3个SOL，价格160 USDT",
        "Bought 0.01 BTC with cash today at 98000 USDT",
    ],
)
def test_a_trade_taken_for_a_question_about_cash_says_to_say_it_again(text: str) -> None:
    said = said_once(text, demo_ledger_with_cash())

    assert said.route is Route.CASH
    assert said.reply.endswith(TRADE_AS_CASH_WORDS)
    assert said.state.chat.items[-1].content == said.reply


def test_a_question_about_cash_naming_a_coin_gets_no_such_line() -> None:
    said = said_once("Do I still have cash to buy more BTC?", FakeLedger())

    assert said.reply == CASH_WORDS
