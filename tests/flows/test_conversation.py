"""Tests of what the user says to the assistant when it records a trade.

A scripted model stands in for every call (choosing tools, judging the
passage, extraction, wording a question, reading an answer) and the fake
ledger for the ledger. What the user said is handed to the recording flow
word for word, once; the flow asks what is missing; once every trade is
settled, the program sends one proposal, or says why it sent nothing; no
figure passes through the model that chooses tools. Every sentence, reply
and trade is invented.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from ledger_hand.assistant.outcome import (
    TWO_MISSTEPS_REPLY,
    Chat,
    Ending,
    NotRunCall,
    TakenCall,
)
from ledger_hand.core.ledger_records import Pricing, TradeFilter
from ledger_hand.core.proposals import ProposalStatus
from ledger_hand.core.trade import Side
from ledger_hand.flows.conversation import AssistantChat, Route, Said, say
from ledger_hand.flows.progress import Stage, Tuning
from ledger_hand.flows.recorded import LeftOut, RecordEnding
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ledger.invented_book import INVENTED_ASSETS, INVENTED_NOW, INVENTED_ZONE
from ledger_hand.ports import (
    LedgerError,
    LedgerErrorKind,
    Message,
    ModelParameters,
    Role,
    ToolCall,
    ToolCallTurn,
    ToolReply,
    ToolResult,
)
from tests.fakes.routed_model import RoutedModel
from tests.fakes.scripted_model import Step, scripted_record
from tests.fakes.usdt_only import usdt_only_ledger
from tests.flows.scripted_flow import copied, row, screened, table

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
SPOT = screened(("spot_trade", "买了0.02 BTC"))


def calls(*names: str, **arguments: object) -> ToolReply:
    return ToolReply(
        text="",
        calls=tuple(ToolCall(name=name, arguments=dict(arguments)) for name in names),
        record=scripted_record(),
    )


RECORD = calls("propose_trade_add")


def talk(
    *said: str,
    tools: list[Step],
    screen: list[Step] = (),  # type: ignore[assignment]
    extraction: list[Step] = (),  # type: ignore[assignment]
    answers: list[Step] = (),  # type: ignore[assignment]
    ledger: FakeLedger | None = None,
) -> tuple[list[Said], RoutedModel, FakeLedger]:
    model = RoutedModel(tools=tools, screen=screen, extraction=extraction, answers=answers)
    ledger = ledger or FakeLedger()
    state = AssistantChat()
    seen = []
    for words in said:
        result = say(
            state,
            words,
            model=model,
            ledger=ledger,
            now=INVENTED_NOW,
            zone=INVENTED_ZONE,
            max_steps=6,
        )
        seen.append(result)
        state = result.state
    return seen, model, ledger


def pending(ledger: FakeLedger) -> list[str]:
    """The proposals the fake ledger keeps waiting, by identifier."""
    waiting = []
    number = 1
    while True:
        proposal = f"proposal-{number}"
        try:
            status = ledger.proposal_status(proposal).status
        except LedgerError:
            return waiting
        if status is ProposalStatus.PENDING:
            waiting.append(proposal)
        number += 1


def one_buy(**changed: str) -> tuple[list[Said], RoutedModel, FakeLedger]:
    return talk(ONE_BUY, tools=[RECORD], screen=[SPOT], extraction=[table(ONE_BUY_ROW)], **changed)


# --- a complete trade --------------------------------------------------------


def test_a_complete_trade_goes_to_the_ledger_as_one_pending_proposal() -> None:
    ledger = usdt_only_ledger()
    before = (ledger.list_trades(TradeFilter()).trades, ledger.positions())

    (said,), _, _ = one_buy(ledger=ledger)  # type: ignore[arg-type]

    assert said.route is Route.MODEL
    assert said.recorded is not None
    assert said.recorded.ending is RecordEnding.SENT
    assert said.sent is not None and said.sent.trades == 1
    assert pending(ledger) == [said.sent.proposal]
    (trade,) = said.recorded.trades
    assert trade.occurred == datetime(2026, 11, 24, 9, 40, tzinfo=trade.occurred.tzinfo)
    assert trade.occurred.utcoffset() == INVENTED_NOW.utcoffset()
    assert (trade.side, trade.asset, trade.quantity, trade.price, trade.total) == (
        Side.BUY,
        "BTC",
        Decimal("0.02"),
        Decimal("94900"),
        Decimal("1898"),
    )
    assert (trade.fee, trade.fee_asset, trade.platform, trade.note) == (
        Decimal("2"),
        "USDT",
        "币安",
        "",
    )
    usdt = next(asset for asset in INVENTED_ASSETS if asset.code == "USDT")
    assert trade.quote == usdt.code
    assert (ledger.list_trades(TradeFilter()).trades, ledger.positions()) == before
    assert said.state.chat.proposals == (said.sent.proposals,)
    assert said.well_ended


def test_the_trade_keeps_the_users_words_byte_for_byte() -> None:
    words = "  今天上午9:40在币安买了０.02 BTC，价格94900，手续费2 USDT\n"
    model_row = row(
        side="buy",
        coin="BTC",
        quantity="０.02 BTC",
        price="94900",
        fee="2 USDT",
        time="今天上午9:40",
    )

    (said,), _, _ = talk(
        words,
        tools=[RECORD],
        screen=[SPOT],
        extraction=[table(model_row)],
        ledger=usdt_only_ledger(),
    )

    assert said.recorded is not None
    (trade,) = said.recorded.trades
    assert trade.raw_text.encode("utf-8") == words.encode("utf-8")
    assert trade.platform == ""


def test_every_figure_of_the_proposal_is_the_flows_record_as_it_stands() -> None:
    (said,), _, _ = one_buy(ledger=usdt_only_ledger())  # type: ignore[arg-type]

    assert said.recorded is not None
    (record,) = said.recorded.progress.records
    (trade,) = said.recorded.trades
    assert record.occurred.value == trade.occurred
    for flow, ledger in (
        ("quantity", "quantity"),
        ("price", "price"),
        ("total", "total"),
        ("fee", "fee"),
    ):
        assert str(getattr(record, flow)) == str(getattr(trade, ledger)), flow
    assert (record.coin, record.fee_coin, record.side) == (
        trade.asset,
        trade.fee_asset,
        trade.side,
    )


def test_the_tool_choosing_model_is_asked_once_and_never_again_this_turn() -> None:
    (said,), model, _ = one_buy(ledger=usdt_only_ledger())  # type: ignore[arg-type]

    assert len(model.tools.calls) == 1
    assert said.turn is not None and said.turn.ending is Ending.RECORDING
    (taken,) = said.turn.steps[0].calls
    assert isinstance(taken, TakenCall)
    assert '"status":"sent"' in taken.result
    assert said.reply.startswith("Sent to the ledger.")
    assert "94900" not in said.reply


def test_what_the_user_said_is_handed_to_the_flow_word_for_word() -> None:
    (said,), model, _ = one_buy()

    assert said.recorded is not None
    assert said.recorded.progress.passage == ONE_BUY
    assert said.recorded.progress.seen_before == ()
    assert ONE_BUY in model.screen.calls[0].messages[-1].content


def test_the_question_wording_is_tuned_as_the_caller_says() -> None:
    tuning = Tuning(
        question_parameters=ModelParameters(
            temperature=0.7, top_p=0.9, max_reply_tokens=50, context_tokens=4096, timeout_seconds=9
        )
    )
    no_fee = "今天上午9:40在币安买了0.02 BTC，价格94900"
    model = RoutedModel(
        tools=[RECORD],
        screen=[SPOT],
        extraction=[table(row(side="buy", coin="BTC", quantity="0.02 BTC", price="94900"))],
    )

    say(
        AssistantChat(),
        no_fee,
        model=model,
        ledger=FakeLedger(),
        now=INVENTED_NOW,
        zone=INVENTED_ZONE,
        max_steps=6,
        tuning=tuning,
    )

    assert model.question_parameters
    assert set(model.question_parameters) == {tuning.question_parameters}


# --- two trades --------------------------------------------------------------

TWO = (
    "今天上午9:40在币安买了0.02 BTC，价格94900，手续费0.00002 BTC；"
    "下午2点又买了0.5 ETH，价格2700，手续费1.35 USDT"
)
TWO_ROWS = table(
    row(
        side="buy",
        coin="BTC",
        quantity="0.02 BTC",
        price="94900",
        fee="0.00002 BTC",
        time="今天上午9:40",
    ),
    row(side="buy", coin="ETH", quantity="0.5 ETH", price="2700", fee="1.35 USDT", time="下午2点"),
)


def test_two_trades_go_in_one_sending_a_proposal_each_in_the_order_said() -> None:
    ledger = usdt_only_ledger()
    (said,), _, _ = talk(TWO, tools=[RECORD], screen=[SPOT], extraction=[TWO_ROWS], ledger=ledger)

    assert said.recorded is not None
    assert [trade.asset for trade in said.recorded.trades] == ["BTC", "ETH"]
    assert said.sent is not None and said.sent.trades == 2
    assert said.sent.proposals == ("proposal-1", "proposal-2")
    assert pending(ledger) == ["proposal-1", "proposal-2"]
    assert said.state.chat.proposals == (("proposal-1", "proposal-2"),)
    assert ledger.calls.count("propose_add") == 1


def test_a_fee_taken_in_the_coin_bought_or_in_usdt_names_that_ledger_asset() -> None:
    (said,), _, _ = talk(
        TWO, tools=[RECORD], screen=[SPOT], extraction=[TWO_ROWS], ledger=usdt_only_ledger()
    )

    assert said.recorded is not None
    codes = {asset.code for asset in INVENTED_ASSETS}
    btc, eth = said.recorded.trades
    assert (btc.fee_asset, btc.fee) == ("BTC", Decimal("0.00002"))
    assert (eth.fee_asset, eth.fee) == ("USDT", Decimal("1.35"))
    assert {btc.fee_asset, eth.fee_asset} <= codes


def test_two_calls_to_record_in_one_step_hand_the_words_over_once() -> None:
    ledger = usdt_only_ledger()
    (said,), model, _ = talk(
        TWO,
        tools=[calls("propose_trade_add", "propose_trade_add")],
        screen=[SPOT],
        extraction=[TWO_ROWS],
        ledger=ledger,
    )

    assert len(model.screen.calls) == 1
    assert len(model.extraction.calls) == 1
    assert len(pending(ledger)) == 2
    assert said.sent is not None and said.sent.trades == 2
    assert [type(call) for call in said.turn.steps[0].calls] == [TakenCall, TakenCall]  # type: ignore[union-attr]


def test_a_read_call_beside_a_call_to_record_is_not_run() -> None:
    ledger = usdt_only_ledger()
    (said,), _, _ = talk(
        ONE_BUY,
        tools=[calls("list_assets", "propose_trade_add")],
        screen=[SPOT],
        extraction=[table(ONE_BUY_ROW)],
        ledger=ledger,
    )

    assert said.turn is not None
    not_run, taken = said.turn.steps[0].calls
    assert isinstance(not_run, NotRunCall)
    assert '"status":"not_run"' in not_run.result
    assert isinstance(taken, TakenCall)
    assert not said.turn.steps[0].wrong
    assert ledger.calls == ["list_assets", "market_prices", "propose_add"]
    results = [item for item in said.state.chat.items if isinstance(item, ToolResult)]
    assert [item.name for item in results] == ["list_assets", "propose_trade_add"]


def test_a_trade_whose_asset_is_not_in_the_ledger_is_left_out_and_the_other_sent() -> None:
    words = (
        "今天上午9:40买了0.02 BTC，价格94900，手续费2 USDT；又买了10 SOL，价格150，手续费0.1 USDT"
    )
    rows = table(
        ONE_BUY_ROW | {"platform": ""},
        row(
            side="buy",
            coin="SOL",
            quantity="10 SOL",
            price="150",
            fee="0.1 USDT",
            time="今天上午9:40",
        ),
    )
    ledger = usdt_only_ledger()

    (said,), _, _ = talk(words, tools=[RECORD], screen=[SPOT], extraction=[rows], ledger=ledger)

    assert said.recorded is not None
    assert [trade.asset for trade in said.recorded.trades] == ["BTC"]
    (left,) = said.recorded.left_out
    assert (left.number, left.why, left.code) == (2, LeftOut.NOT_IN_LEDGER, "SOL")
    assert "Trade 2 was not sent: the ledger has no asset SOL yet." in said.reply
    assert len(pending(ledger)) == 1


def test_a_trade_known_only_to_the_day_is_sent_with_its_day_alone() -> None:
    words = (
        "昨天买了0.5 ETH，价格2700，手续费1.35 USDT；"
        "今天上午9:40买了0.02 BTC，价格94900，手续费2 USDT"
    )
    rows = table(
        row(side="buy", coin="ETH", quantity="0.5 ETH", price="2700", fee="1.35 USDT", time="昨天"),
        ONE_BUY_ROW | {"platform": ""},
    )

    (said,), _, _ = talk(
        words, tools=[RECORD], screen=[SPOT], extraction=[rows], ledger=usdt_only_ledger()
    )

    assert said.recorded is not None
    assert [trade.asset for trade in said.recorded.trades] == ["ETH", "BTC"]
    assert said.recorded.left_out == ()
    assert "has no time of day" not in said.reply
    eth = said.recorded.trades[0]
    assert eth.date_only
    assert eth.day == date(2026, 11, 23)
    assert (eth.occurred.hour, eth.occurred.minute) == (0, 0)
    assert not said.recorded.trades[1].date_only


def test_without_usdt_in_the_ledger_nothing_is_sent() -> None:
    assets = tuple(asset for asset in INVENTED_ASSETS if asset.pricing is not Pricing.CAN_PRICE)
    ledger = FakeLedger(assets=assets, trades=())

    (said,), model, _ = one_buy(ledger=ledger)  # type: ignore[arg-type]

    assert said.recorded is not None
    assert said.recorded.ending is RecordEnding.NO_PRICING_MONEY
    assert "it has no currency that trades can be priced in" in said.reply
    assert said.sent is None
    assert ledger.calls == ["list_assets"]
    assert model.screen.calls == []


def test_selling_more_than_is_held_is_turned_down_by_the_ledger() -> None:
    words = "今天上午9:40在币安卖了5 BTC，价格94900，手续费2 USDT"
    sell = row(
        side="sell", coin="BTC", quantity="5 BTC", price="94900", fee="2 USDT", time="今天上午9:40"
    )
    ledger = usdt_only_ledger()

    (said,), _, _ = talk(
        words, tools=[RECORD], screen=[SPOT], extraction=[table(sell)], ledger=ledger
    )

    assert said.recorded is not None
    assert said.recorded.ending is RecordEnding.LEDGER_REFUSED
    assert pending(ledger) == []
    assert said.sent is None
    assert "With this, a sell would take out more than was held at the time." in said.reply
    assert said.well_ended


def test_an_open_order_sends_nothing() -> None:
    words = "在OKX挂了个BTC限价单，59,500买100U"
    ledger = FakeLedger()

    (said,), model, _ = talk(
        words, tools=[RECORD], screen=[screened(("open_order", "挂了个BTC限价单"))], ledger=ledger
    )

    assert said.recorded is not None
    assert said.recorded.ending is RecordEnding.STOPPED
    assert ledger.calls == ["list_assets"]
    assert pending(ledger) == []
    assert model.extraction.calls == []
    assert "open_order" in said.reply


def test_a_ledger_that_cannot_be_reached_ends_it_as_a_failure() -> None:
    failure = LedgerError(LedgerErrorKind.UNREACHABLE, "offline", "The ledger is not open.")

    (said,), _, _ = one_buy(ledger=FakeLedger(failure=failure))  # type: ignore[arg-type]

    assert said.recorded is not None
    assert said.recorded.ending is RecordEnding.LEDGER_FAILED
    assert "The ledger is not open." in said.reply
    assert not said.well_ended


# --- a question, and its answer ------------------------------------------------

NO_FEE = "今天上午9:40在币安买了0.02 BTC，价格94900"
NO_FEE_ROW = row(
    side="buy", coin="BTC", quantity="0.02 BTC", price="94900", time="今天上午9:40", platform="币安"
)


def test_a_missing_fee_is_asked_and_the_answer_sends_the_trade() -> None:
    ledger = usdt_only_ledger()

    (first, second), model, _ = talk(
        NO_FEE,
        "手续费 0.1 USDT",
        tools=[RECORD],
        screen=[SPOT],
        extraction=[table(NO_FEE_ROW)],
        answers=[copied("0.1 USDT")],
        ledger=ledger,
    )

    assert first.recorded is not None and first.recorded.ending is RecordEnding.ASKING
    assert first.recorded.question is not None
    assert first.reply.startswith("[Trade 1 of 1: fee]")
    assert first.sent is None
    assert first.state.recording is not None
    assert second.route is Route.ANSWER
    assert second.turn is None
    assert len(model.tools.calls) == 1
    assert second.recorded is not None
    (trade,) = second.recorded.trades
    assert (trade.fee, trade.fee_asset) == (Decimal("0.1"), "USDT")
    assert second.sent is not None
    assert pending(ledger) == [second.sent.proposal]
    assert second.state.recording is None
    assert second.state.chat.proposals == (second.sent.proposals,)


def test_nothing_waits_in_the_ledger_while_a_question_waits() -> None:
    ledger = FakeLedger()

    talk(NO_FEE, tools=[RECORD], screen=[SPOT], extraction=[table(NO_FEE_ROW)], ledger=ledger)

    assert ledger.calls == ["list_assets"]
    assert pending(ledger) == []


def test_an_answer_that_cannot_be_used_gets_the_same_question_again() -> None:
    (_, second), _, _ = talk(
        NO_FEE,
        "不知道",
        tools=[RECORD],
        screen=[SPOT],
        extraction=[table(NO_FEE_ROW)],
        answers=[copied("")],
        ledger=usdt_only_ledger(),
    )

    assert second.route is Route.ANSWER
    assert second.recorded is not None and second.recorded.ending is RecordEnding.ASKING
    assert second.reply.startswith("(Asked again:")
    assert "[Trade 1 of 1: fee]" in second.reply
    assert second.state.recording is not None


def test_cancel_drops_the_passage_and_the_next_words_go_to_the_model_again() -> None:
    ledger = FakeLedger()

    (_, cancelled, after), model, _ = talk(
        NO_FEE,
        "cancel",
        "我现在手里有哪些币",
        tools=[RECORD, "You hold four assets."],
        screen=[SPOT],
        extraction=[table(NO_FEE_ROW)],
        ledger=ledger,
    )

    assert cancelled.recorded is not None
    assert cancelled.recorded.ending is RecordEnding.CANCELLED
    assert cancelled.sent is None
    assert cancelled.state.recording is None
    assert pending(ledger) == []
    assert after.route is Route.MODEL
    assert after.reply == "You hold four assets."
    assert len(model.tools.calls) == 2


def test_skip_leaves_the_trade_out_and_sends_nothing() -> None:
    (_, skipped), _, ledger = talk(
        NO_FEE, "skip", tools=[RECORD], screen=[SPOT], extraction=[table(NO_FEE_ROW)]
    )

    assert skipped.recorded is not None
    assert skipped.recorded.ending is RecordEnding.NOTHING_TO_SEND
    assert "Trade 1 was left out, as you said." in skipped.reply
    assert pending(ledger) == []


def test_the_chat_holds_each_call_with_its_result_and_the_answer_in_turn() -> None:
    (_, second, third), model, _ = talk(
        NO_FEE,
        "手续费 0.1 USDT",
        "我现在手里有哪些币",
        tools=[RECORD, calls("get_positions"), "Four assets."],
        screen=[SPOT],
        extraction=[table(NO_FEE_ROW)],
        answers=[copied("0.1 USDT")],
        ledger=usdt_only_ledger(),
    )

    sent = model.tools.calls[1].items
    kinds = [type(item).__name__ for item in sent[1:]]
    assert kinds[:6] == [
        "Message",
        "ToolCallTurn",
        "ToolResult",
        "Message",
        "Message",
        "Message",
    ]
    assert sent[5] == Message(Role.USER, "手续费 0.1 USDT")
    assert sent[7] == Message(Role.USER, "我现在手里有哪些币")
    assert isinstance(sent[2], ToolCallTurn) and isinstance(sent[3], ToolResult)
    assert third.reply == "Four assets."
    assert second.state.chat.items == tuple(sent[1:7])


def test_a_figure_the_model_gave_the_recording_tool_never_reaches_the_model_again() -> None:
    (_, second), model, _ = talk(
        ONE_BUY,
        "我现在手里有哪些币",
        tools=[calls("propose_trade_add", quantity="0.0299"), "Four assets."],
        screen=[SPOT],
        extraction=[table(ONE_BUY_ROW)],
        ledger=usdt_only_ledger(),
    )

    assert "0.0299" not in repr(model.tools.calls[1].items)
    assert second.turn is not None
    first_call = model.tools.calls[0]
    assert first_call.items[-1] == Message(Role.USER, ONE_BUY)


# --- the program takes over after two wrong steps ---------------------------------


def test_after_two_wrong_steps_a_trade_said_is_still_recorded() -> None:
    ledger = usdt_only_ledger()

    (said,), model, _ = talk(
        ONE_BUY,
        tools=[calls("place_order"), calls("place_order")],
        screen=[SPOT],
        extraction=[table(ONE_BUY_ROW)],
        ledger=ledger,
    )

    assert said.route is Route.TAKEOVER
    assert said.turn is not None and said.turn.ending is Ending.TWO_MISSTEPS
    assert said.recorded is not None and said.recorded.ending is RecordEnding.SENT
    assert len(pending(ledger)) == 1
    assert said.reply.startswith("Sent to the ledger.")
    assert TWO_MISSTEPS_REPLY not in [
        item.content for item in said.state.chat.items if isinstance(item, Message)
    ]
    assert said.state.chat.items[-1] == Message(Role.ASSISTANT, said.reply)
    assert said.well_ended
    assert len(model.tools.calls) == 2


def test_after_two_wrong_steps_small_talk_is_not_done() -> None:
    (said,), _, ledger = talk(
        "你好呀",
        tools=[calls("place_order"), calls("place_order")],
        screen=[screened()],
    )

    assert said.route is Route.TAKEOVER
    assert said.recorded is not None and said.recorded.ending is RecordEnding.NO_TRADE
    assert said.reply == TWO_MISSTEPS_REPLY
    assert said.sent is None
    assert pending(ledger) == []
    assert not said.well_ended


def test_the_step_limit_is_not_taken_over() -> None:
    (said,), model, _ = talk(ONE_BUY, tools=[calls("list_assets")] * 6)

    assert said.turn is not None and said.turn.ending is Ending.STEP_LIMIT
    assert said.recorded is None
    assert model.screen.calls == []
    assert not said.well_ended


def test_a_chat_with_no_recording_is_the_models_turn_as_it_was() -> None:
    (said,), _, _ = talk("我现在手里有哪些币", tools=[calls("get_positions"), "Four assets."])

    assert said.route is Route.MODEL
    assert said.recorded is None
    assert said.sent is None
    assert said.reply == "Four assets."
    assert said.well_ended
    assert isinstance(said.state.chat, Chat)


def test_a_model_failure_while_judging_ends_it_as_a_failure() -> None:
    from ledger_hand.ports import ModelError, ModelErrorKind

    failure = ModelError(ModelErrorKind.UNREACHABLE, "not running")
    (said,), _, _ = talk(ONE_BUY, tools=[RECORD], screen=[failure, failure, failure, failure])

    assert said.recorded is not None
    assert said.recorded.progress.stage is Stage.FAILED
    assert said.recorded.ending is RecordEnding.MODEL_FAILED
    assert not said.well_ended


def test_after_a_proposal_is_sent_the_next_ask_finds_a_result_after_every_call() -> None:
    (first, _), model, _ = talk(
        ONE_BUY,
        "我现在手里有哪些币",
        tools=[RECORD, calls("get_positions"), "Four assets."],
        screen=[SPOT],
        extraction=[table(ONE_BUY_ROW)],
        ledger=usdt_only_ledger(),
    )

    assert first.sent is not None
    items = model.tools.calls[1].items
    asked = items.index(
        ToolCallTurn(text="", calls=(ToolCall(name="propose_trade_add", arguments={}),))
    )
    after = items[asked + 1]
    assert isinstance(after, ToolResult)
    assert after.name == "propose_trade_add"
    assert '"status":"sent"' in after.content
    assert items[asked + 2] == Message(Role.ASSISTANT, first.reply)
    for position, item in enumerate(items):
        if isinstance(item, ToolCallTurn):
            results = items[position + 1 : position + 1 + len(item.calls)]
            assert all(isinstance(result, ToolResult) for result in results)


def test_after_two_wrong_steps_an_open_order_is_said_with_its_reason() -> None:
    words = "在OKX挂了个BTC限价单，59,500买100U"
    (said,), _, ledger = talk(
        words,
        tools=[calls("place_order"), calls("place_order")],
        screen=[screened(("open_order", "挂了个BTC限价单"))],
    )

    assert said.route is Route.TAKEOVER
    assert said.recorded is not None and said.recorded.ending is RecordEnding.STOPPED
    assert said.reply.startswith("Nothing was sent to the ledger: what you said reports only")
    assert "open_order" in said.reply
    assert said.reply != TWO_MISSTEPS_REPLY
    assert said.state.chat.items[-1] == Message(Role.ASSISTANT, said.reply)
    assert said.sent is None
    assert pending(ledger) == []
    assert said.well_ended
