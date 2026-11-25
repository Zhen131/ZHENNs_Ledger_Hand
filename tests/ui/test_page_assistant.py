"""Tests of the Assistant page: the chat, the tables, the answer buttons, the cards, New chat.

The page runs headless with a scripted model and the demo ledger
(``FakeLedger``, the invented book), "now" the invented book's fixed moment.
What the page shows is read off the flows' results; nothing reaches the
network. Every sentence, reply and trade is invented.
"""

from __future__ import annotations

from ledger_hand.core.ledger_records import TradeFilter
from ledger_hand.core.proposals import ProposalStatus
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ports import ToolCall, ToolReply
from ledger_hand.ui.assistant_cards import REFRESH_KEY, reject_key, save_key
from ledger_hand.ui.assistant_tables import CHANGED_MARK
from ledger_hand.ui.assistant_view import choice_key, exchange_key, how_key, table_key
from tests.fakes.routed_model import RoutedModel
from tests.fakes.scripted_model import scripted_record
from tests.fakes.usdt_only import usdt_only_ledger
from tests.flows.scripted_flow import copied, row, screened, table
from tests.ui.app_harness import APP_FILE
from tests.ui.assistant_harness import (
    INPUT_KEY,
    captions,
    card_text,
    errors,
    open_assistant,
    replies,
    rows_of,
    say_on_page,
    texts_of,
)
from tests.ui.page_harness import to_record, to_settings

NEW_CHAT_KEY = "assistant_new_chat"
LEDGER_LINE_KEY = "assistant_ledger_line"


def calls(name: str, **arguments: object) -> ToolReply:
    return ToolReply(
        text="", calls=(ToolCall(name=name, arguments=dict(arguments)),), record=scripted_record()
    )


RECORD = calls("propose_trade_add")
ONE_BUY = "今天上午9:40在币安买了0.02 BTC，价格94900，手续费2 USDT"
ONE_BUY_ROW = row(
    side="buy",
    coin="BTC",
    quantity="0.02 BTC",
    price="94900",
    fee="2 USDT",
    time="今天上午9:40",
    platform="币安",
)
NO_FEE = "今天上午9:40在币安买了0.02 BTC，价格94900"
NO_FEE_ROW = row(
    side="buy", coin="BTC", quantity="0.02 BTC", price="94900", time="今天上午9:40", platform="币安"
)
SHARES = "今天15:30在IBKR买了2股MSFT，410美元一股，手续费1美元"
SHARES_ROW = row(
    side="buy",
    coin="MSFT",
    quantity="2股",
    price="410美元",
    fee="1美元",
    time="今天15:30",
    platform="IBKR",
)


def one_buy_model() -> RoutedModel:
    return RoutedModel(
        tools=[RECORD],
        screen=[screened(("spot_trade", "买了0.02 BTC"))],
        extraction=[table(ONE_BUY_ROW)],
    )


def pending(ledger: FakeLedger) -> list[str]:
    found = []
    for number in range(1, 10):
        try:
            if ledger.proposal_status(f"proposal-{number}") is ProposalStatus.PENDING:
                found.append(f"proposal-{number}")
        except Exception:  # noqa: BLE001
            break
    return found


# --- the pages -----------------------------------------------------------------


def test_three_pages_and_the_record_page_is_still_the_one_opened_first() -> None:
    from streamlit.testing.v1 import AppTest

    page = AppTest.from_file(str(APP_FILE), default_timeout=30).run()
    assert [box.key for box in page.chat_input] == ["chat_input"]

    assert [box.key for box in to_settings(page).chat_input] == []
    assert [box.key for box in page.switch_page("assistant_page.py").run().chat_input] == [
        INPUT_KEY
    ]
    assert [box.key for box in to_record(page).chat_input] == ["chat_input"]


def test_the_page_always_says_which_ledger_it_reaches() -> None:
    page = open_assistant(RoutedModel(), ledger=FakeLedger())

    (line,) = captions(page, LEDGER_LINE_KEY)
    assert "demo ledger" in line
    assert "not your real ledger" in line


# --- recording ----------------------------------------------------------------


def test_a_complete_trade_shows_the_table_the_sent_line_and_a_pending_card() -> None:
    ledger = usdt_only_ledger()
    page = open_assistant(one_buy_model(), ledger=ledger)

    page = say_on_page(page, ONE_BUY)

    (proposal,) = pending(ledger)
    (trade,) = rows_of(page, table_key(1, "proposed"))
    assert (trade["Asset"], trade["Quantity"], trade["Price"], trade["Total"], trade["Fee"]) == (
        "BTC",
        "0.02",
        "94,900 USDT",
        "1,898 USDT",
        "2 USDT",
    )
    lines = captions(page, exchange_key(1))
    assert lines[0] == "Words: the program's own words"
    sent = f"Sent to the ledger: {proposal} (1 trade to record), waiting for you to confirm"
    assert sent in lines
    assert f"{proposal}: 1 trade to record, sent by message 1" in card_text(page, proposal)
    assert "Status: waiting for you to confirm on the ledger's own page" in card_text(
        page, proposal
    )


def test_a_demo_save_makes_the_card_saved_and_the_trade_is_in_the_demo_ledger() -> None:
    ledger = usdt_only_ledger()
    page = say_on_page(open_assistant(one_buy_model(), ledger=ledger), ONE_BUY)
    (proposal,) = pending(ledger)
    before = len(ledger.list_trades(TradeFilter()))

    page = page.button(key=save_key(proposal)).click().run()

    assert "Status: saved" in card_text(page, proposal)
    assert len(ledger.list_trades(TradeFilter())) == before + 1
    assert [b.key for b in page.button if b.key in (save_key(proposal), reject_key(proposal))] == []


def test_refresh_asks_again_and_a_reject_shows_rejected() -> None:
    ledger = usdt_only_ledger()
    page = say_on_page(open_assistant(one_buy_model(), ledger=ledger), ONE_BUY)
    (proposal,) = pending(ledger)
    ledger.reject(proposal)

    page = page.button(key=REFRESH_KEY).click().run()

    assert "Status: rejected" in card_text(page, proposal)


def test_a_missing_fee_is_asked_answered_and_sent() -> None:
    ledger = usdt_only_ledger()
    model = RoutedModel(
        tools=[RECORD],
        screen=[screened(("spot_trade", "买了0.02 BTC"))],
        extraction=[table(NO_FEE_ROW)],
        answers=[copied("0.1 USDT")],
    )
    page = say_on_page(open_assistant(model, ledger=ledger), NO_FEE)
    assert replies(page, 1)[0].startswith("[Trade 1 of 1: fee]")
    assert "Sent to the ledger: nothing" in captions(page, exchange_key(1))
    assert pending(ledger) == []

    page = say_on_page(page, "手续费 0.1 USDT")

    (proposal,) = pending(ledger)
    (trade,) = rows_of(page, table_key(2, "proposed"))
    assert trade["Fee"] == "0.1 USDT"
    assert any(proposal in line for line in captions(page, exchange_key(2)))


def test_a_share_bought_with_dollars_shows_dollars_in_the_table() -> None:
    ledger = FakeLedger()
    model = RoutedModel(
        tools=[RECORD],
        screen=[screened(("spot_trade", "今天15:30在IBKR买了2股MSFT"))],
        extraction=[table(SHARES_ROW)],
    )

    page = say_on_page(open_assistant(model, ledger=ledger), SHARES)

    (trade,) = rows_of(page, table_key(1, "proposed"))
    assert (trade["Asset"], trade["Price"], trade["Total"], trade["Fee"]) == (
        "MSFT",
        "410 USD",
        "820 USD",
        "1 USD",
    )


# --- asking -----------------------------------------------------------------------


def test_a_question_about_the_ledger_shows_the_header_and_the_table() -> None:
    model = RoutedModel(tools=[calls("list_trades", period="10月6号"), "10月6号有这些交易。"])

    page = say_on_page(open_assistant(model, ledger=FakeLedger()), "10月6号我买了什么")

    key = table_key(1, "lookup", 0)
    header = texts_of(page, key)[0]
    assert header.startswith("Time: 2026-10-06\nAsset: all assets\nSide: buys and sells")
    shown = rows_of(page, key)
    assert len(shown) == 2
    assert {"Time", "Side", "Asset", "Quantity", "Price", "Total", "Fee", "Realized"} <= set(
        shown[0]
    )
    assert captions(page, exchange_key(1))[0] == "Words: the model"
    assert "Sent to the ledger: nothing" in captions(page, exchange_key(1))


def test_how_it_was_done_names_the_tool_its_arguments_and_the_steps() -> None:
    model = RoutedModel(tools=[calls("list_trades", period="10月6号"), "10月6号有这些交易。"])

    page = say_on_page(open_assistant(model, ledger=FakeLedger()), "10月6号我买了什么")

    lines = texts_of(page, how_key(1))
    assert lines[0] == "Way: the model chose the tools"
    assert "Step 1: the model asked for 1 tool(s)" in lines
    assert 'Tool: list_trades {"period": "10月6号"}' in lines
    assert any(line.startswith("Handed back: ") for line in lines)
    assert "Step 2: the model answered" in lines
    assert "Steps of the model: 2 of at most 6" in lines
    assert "Taken over by the program: no" in lines


# --- changing: two trades match, the second picked by its button ----------------------


def test_two_trades_listed_the_second_button_pressed_and_the_change_sent() -> None:
    ledger = FakeLedger()
    model = RoutedModel(
        tools=[calls("propose_trade_update", period="10月6号", field="fee", new_value="0.000009")]
    )
    page = say_on_page(open_assistant(model, ledger=ledger), "把10月6号那笔的手续费改成0.000009")
    assert len(rows_of(page, table_key(1, "listed"))) == 2
    assert pending(ledger) == []

    page = page.button(key=choice_key(1, 1)).click().run()

    (proposal,) = pending(ledger)
    assert [m.name for m in page.chat_message][-2:] == ["user", "assistant"]
    changed = {r["Part"]: r for r in rows_of(page, table_key(2, "change"))}
    assert changed["Fee"]["Changes"] == CHANGED_MARK
    assert changed["Fee"]["After"] == "0.000009 USDT"
    assert changed["Asset"]["Changes"] == ""
    assert f"{proposal}: change of trade t-06, sent by message 2" in card_text(page, proposal)


def test_the_answer_buttons_are_gone_once_answered() -> None:
    ledger = FakeLedger()
    model = RoutedModel(
        tools=[calls("propose_trade_update", period="10月6号", field="fee", new_value="0.000009")]
    )
    page = say_on_page(open_assistant(model, ledger=ledger), "把10月6号那笔的手续费改成0.000009")

    page = page.button(key=choice_key(1, 1)).click().run()

    assert [b.key for b in page.button if b.key.startswith("assistant_choice_")] == []


# --- New chat, and a ledger that is not the demo ledger ---------------------------------


def test_new_chat_forgets_the_chat_and_its_cards_but_not_the_ledger() -> None:
    ledger = usdt_only_ledger()
    page = say_on_page(open_assistant(one_buy_model(), ledger=ledger), ONE_BUY)
    (proposal,) = pending(ledger)

    page = page.button(key=NEW_CHAT_KEY).click().run()

    assert [m for m in page.chat_message] == []
    assert "None yet in this chat." in [str(c.value) for c in page.caption]
    assert pending(ledger) == [proposal]


def test_with_a_ledger_not_the_demo_one_no_demo_button_is_drawn() -> None:
    ledger = usdt_only_ledger()
    page = say_on_page(open_assistant(one_buy_model(), ledger=ledger, kind=None), ONE_BUY)
    (proposal,) = pending(ledger)

    assert "Status: waiting for you to confirm on the ledger's own page" in card_text(
        page, proposal
    )
    assert [b.key for b in page.button if "demo" in b.key] == []
    assert not any("Demo only" in str(c.value) for c in page.caption)


def test_with_no_ledger_the_page_says_so_and_the_input_is_grey() -> None:
    page = open_assistant(RoutedModel())

    assert captions(page, LEDGER_LINE_KEY) == ["Ledger: none connected"]
    assert page.chat_input(key=INPUT_KEY).proto.disabled
    assert "No ledger is connected" in str(page.container(key="assistant_notice").warning[0].value)
    assert errors(page, "assistant_notice") == []
