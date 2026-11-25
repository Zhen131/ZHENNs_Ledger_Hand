"""Tests of a question about cash: caught before the model, answered with the program's words.

The assistant cannot look up cash. A question about it is caught from the
user's own words before the model is asked, and the program says its fixed
words; when one is not caught and the model answers with a figure beside a
money, having looked nothing up, its words give way to the same fixed words.
A scripted model stands in for every call; every sentence is invented.
"""

from __future__ import annotations

import pytest

from ledger_hand.assistant.outcome import Ending
from ledger_hand.core.cash_words import CashAsk
from ledger_hand.core.ledger_records import Asset, AssetKind, MoneyAmount, Pricing
from ledger_hand.flows.assistant_record import entry_for
from ledger_hand.flows.cash_question import CASH_WORDS, caught, withheld_cash
from ledger_hand.flows.conversation import AssistantChat, Route, WordsBy, say
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ledger.invented_book import INVENTED_ASSETS, INVENTED_NOW, INVENTED_ZONE
from ledger_hand.ports import LedgerError, LedgerErrorKind, Message, Role, ToolCall, ToolReply
from tests.fakes.routed_model import RoutedModel
from tests.fakes.scripted_model import scripted_record
from tests.fakes.usdt_only import usdt_only_ledger
from tests.flows.scripted_flow import copied, table
from tests.flows.test_conversation import NO_FEE, NO_FEE_ROW, RECORD, SPOT, talk

EURO = Asset(
    id="asset-eur", code="EUR", name="Euro", kind=AssetKind.CASH, pricing=Pricing.CAN_PRICE
)


def words(text: str) -> ToolReply:
    return ToolReply(text=text, calls=(), record=scripted_record())


def calls(name: str) -> ToolReply:
    return ToolReply(text="", calls=(ToolCall(name=name, arguments={}),), record=scripted_record())


def said_once(text: str, model: RoutedModel, ledger: FakeLedger | None = None):  # type: ignore[no-untyped-def]
    return say(
        AssistantChat(),
        text,
        model=model,
        ledger=ledger or FakeLedger(),
        now=INVENTED_NOW,
        zone=INVENTED_ZONE,
        max_steps=6,
    )


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("我还有多少USDT", CashAsk.LEFT),
        ("现金余额是多少", CashAsk.CASH),
        ("How much USD did I deposit?", CashAsk.DEPOSIT),
        ("Do I still have cash to buy more BTC?", CashAsk.CASH),
    ],
)
def test_a_question_about_cash_is_answered_by_the_program_and_the_model_is_not_asked(
    text: str, kind: CashAsk
) -> None:
    model = RoutedModel()
    ledger = FakeLedger()

    said = said_once(text, model, ledger)

    assert said.route is Route.CASH
    assert said.cash is kind
    assert said.reply == CASH_WORDS
    assert said.turn is None and said.recorded is None and said.edited is None
    assert said.words_by is WordsBy.PROGRAM
    assert said.well_ended
    assert model.tools.steps_left == 0
    assert "positions" not in ledger.calls and "period_summary" not in ledger.calls
    assert said.state.chat.items == (
        Message(Role.USER, text),
        Message(Role.ASSISTANT, CASH_WORDS),
    )


def test_the_fixed_words_say_it_cannot_be_looked_up_where_to_look_and_no_figure() -> None:
    assert "cannot look up cash" in CASH_WORDS
    assert "home page" in CASH_WORDS
    assert "will not work a figure out from your trades" in CASH_WORDS
    assert not any(character.isdigit() for character in CASH_WORDS)


def test_the_ledger_is_asked_for_its_cash_only_for_the_shape_of_what_is_still_had() -> None:
    ledger = FakeLedger(assets=(*INVENTED_ASSETS, EURO))

    assert caught("现金余额是多少", ledger) is CashAsk.CASH
    assert ledger.calls == []
    assert caught("我还剩多少Euro", ledger) is CashAsk.LEFT
    assert caught("How much EUR do I have left?", ledger) is CashAsk.LEFT
    assert ledger.calls == ["list_assets", "list_assets"]


def test_a_coin_still_held_is_not_cash_and_goes_to_the_model() -> None:
    model = RoutedModel(tools=[calls("get_positions"), words("You hold BTC.")])

    said = said_once("我现在还有多少BTC", model)

    assert said.route is Route.MODEL
    assert said.cash is None
    assert said.turn is not None and said.turn.ending is Ending.ANSWERED


def test_a_ledger_that_cannot_be_asked_still_leaves_the_base_words() -> None:
    failing = FakeLedger(failure=LedgerError(LedgerErrorKind.UNREACHABLE, "X", "gone"))

    assert caught("我还有多少USDT", failing) is CashAsk.LEFT
    assert caught("我还有多少Euro", failing) is None


def test_while_a_question_waits_a_question_about_cash_is_its_answer_as_before() -> None:
    (first, second), _, _ = talk(
        NO_FEE,
        "现金余额是多少",
        tools=[RECORD],
        screen=[SPOT],
        extraction=[table(NO_FEE_ROW)],
        answers=[copied("")],
        ledger=usdt_only_ledger(),
    )

    assert first.state.recording is not None
    assert second.route is Route.ANSWER
    assert second.cash is None
    assert second.reply != CASH_WORDS


# --- the check behind it ---------------------------------------------------------


@pytest.mark.parametrize(
    "reply",
    [
        "你还有 50 USDT。",
        "You have $50 left.",
        "你账上大概有5U",
        "余额是五十美元",
        "You still have 20 EUR.",
    ],
)
def test_a_figure_beside_a_money_with_nothing_looked_up_gives_way_to_the_fixed_words(
    reply: str,
) -> None:
    model = RoutedModel(tools=[words(reply)])
    ledger = FakeLedger(assets=(*INVENTED_ASSETS, EURO))

    said = said_once("帮我看一下账户情况", model, ledger)

    assert said.route is Route.MODEL
    assert said.reply == CASH_WORDS
    assert said.turn is not None
    assert said.turn.withheld is not None
    assert said.turn.chat.items[-1] == Message(Role.ASSISTANT, CASH_WORDS)
    assert said.state.chat.items[-1] == Message(Role.ASSISTANT, CASH_WORDS)
    assert said.words_by is WordsBy.PROGRAM
    assert reply in said.turn.steps[-1].text


def test_words_with_no_figure_beside_a_money_are_shown_as_the_model_wrote_them() -> None:
    model = RoutedModel(tools=[words("你可以问我 10 月的交易，或者用 USDT 记一笔。")])

    said = said_once("你能做什么", model)

    assert said.reply == "你可以问我 10 月的交易，或者用 USDT 记一笔。"
    assert said.turn is not None and said.turn.withheld is None


def test_a_turn_that_looked_something_up_is_left_as_it_is() -> None:
    held = FakeLedger().positions()[0]
    assert isinstance(held.cost, MoneyAmount)
    line = f"{held.asset} cost {held.cost.amount} {held.cost.currency}."
    model = RoutedModel(tools=[calls("get_positions"), words(line)])

    said = said_once("我现在持有哪些币", model)

    assert said.reply == line
    assert said.turn is not None and said.turn.lookups


def test_withheld_cash_asks_the_ledger_only_when_the_reply_holds_a_digit() -> None:
    ledger = FakeLedger()

    assert withheld_cash("没有数字的话", ledger) is None
    assert ledger.calls == []
    assert withheld_cash("一共 3 笔", ledger) is None
    assert ledger.calls == ["list_assets"]


def test_the_record_keeps_the_way_a_question_about_cash_went() -> None:
    said = said_once("What is my cash balance?", RoutedModel())

    entry = entry_for(said, words="What is my cash balance?", at=INVENTED_NOW, model="m")

    assert entry["route"] == "cash"
    assert entry["words_by"] == "program"
    assert entry["reply"] == CASH_WORDS
    assert entry["steps"] == []


def test_the_demo_ledger_hands_back_no_holding_of_cash() -> None:
    ledger = FakeLedger()
    cash = {asset.code for asset in ledger.list_assets() if asset.kind is AssetKind.CASH}

    held = {position.asset for position in ledger.positions()}

    assert cash == {"USDT", "USD"}
    assert held and not held & cash
