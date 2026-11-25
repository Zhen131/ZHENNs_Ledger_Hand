"""Tests of the assistant saying the reminders, and holding back a quantity said in another unit.

A trade whose quantity carries a unit that is not the asset traded ("25U"
of ETH) is not sent through the assistant and nothing is asked about it;
the reply says why, with the number and the unit as read. Every other
reminder is said, one line each, once recording ends with a proposal sent,
turned down or nothing sent. The record page keeps the number and only
reminds, as before. A scripted model stands in for every call and the fake
ledger for the ledger. Every sentence, reply and trade is invented.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from ledger_hand.core.assets import BUILT_IN_ASSETS
from ledger_hand.extraction.issues import IssueKind
from ledger_hand.flows.conversation import AssistantChat, Said, say
from ledger_hand.flows.progress import Stage, TradeStatus
from ledger_hand.flows.record_words import ENDING_WORDS, SPOKEN_REMINDERS
from ledger_hand.flows.recorded import LeftOut, RecordEnding
from ledger_hand.flows.recording import start
from ledger_hand.flows.reminder_words import reminder_text
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ledger.invented_book import INVENTED_NOW, INVENTED_ZONE
from ledger_hand.ports import ToolCall, ToolReply
from tests.fakes.routed_model import RoutedModel
from tests.fakes.scripted_model import Step, scripted_record
from tests.flows.scripted_flow import copied, row, screened, table

RECORD = ToolReply(
    text="", calls=(ToolCall(name="propose_trade_add", arguments={}),), record=scripted_record()
)

U25 = "今天下午3点OKX顺手25U买了点ETH，2,388一个，跟着BTC一起补仓"
U25_ROW = row(
    side="buy", coin="ETH", quantity="25U", price="2,388", time="今天下午3点", platform="OKX"
)
BTC = "今天上午9:40在币安买了0.02 BTC，价格94900 USDT，手续费2 USDT"
BTC_ROW = row(
    side="buy",
    coin="BTC",
    quantity="0.02 BTC",
    price="94900 USDT",
    fee="2 USDT",
    time="今天上午9:40",
    platform="币安",
)
ETH = "今天上午9:40在币安买了0.5 ETH，价格2388 USDT，手续费0 USDT"
ETH_ROW = row(
    side="buy",
    coin="ETH",
    quantity="0.5 ETH",
    price="2388 USDT",
    fee="0 USDT",
    time="今天上午9:40",
    platform="币安",
)


def talk(
    *said: str,
    rows: Sequence[dict[str, str]],
    answers: list[Step] = (),  # type: ignore[assignment]
    ledger: FakeLedger | None = None,
) -> tuple[list[Said], RoutedModel, FakeLedger]:
    ledger = FakeLedger() if ledger is None else ledger
    model = RoutedModel(
        tools=[RECORD],
        screen=[screened(("spot_trade", said[0][:6]))],
        extraction=[table(*rows)],
        answers=answers,
    )
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


# --- a quantity said in another unit ------------------------------------------


def test_25u_of_eth_is_not_sent_nothing_is_asked_and_the_reply_says_why() -> None:
    (said,), model, ledger = talk(U25, rows=[U25_ROW])

    recorded = said.recorded
    assert recorded is not None and recorded.ending is RecordEnding.NOTHING_TO_SEND
    (left,) = recorded.left_out
    assert (left.number, left.why, left.code) == (1, LeftOut.QUANTITY_IN_OTHER_UNIT, "ETH")
    assert (left.quantity, left.unit) == (Decimal("25"), "U")
    assert ledger.calls == ["list_assets"]
    assert model.questions.calls == [] and model.answers.calls == []
    lines = said.reply.splitlines()
    assert lines[0] == ENDING_WORDS[RecordEnding.NOTHING_TO_SEND]
    assert lines[1].startswith("Trade 1 was not sent: its quantity was said as 25 U")
    assert "U is not ETH" in lines[1]
    assert "in total" in lines[1]
    assert said.state.recording is None


def test_the_reminder_that_held_the_trade_back_is_not_said_twice() -> None:
    (said,), _, _ = talk(U25, rows=[U25_ROW])

    assert "a unit that is not the trade's coin" not in said.reply


def test_of_two_trades_the_one_in_another_unit_is_held_and_the_other_sent() -> None:
    (said,), _, ledger = talk(U25 + "；" + BTC, rows=[U25_ROW, BTC_ROW])

    recorded = said.recorded
    assert recorded is not None and recorded.ending is RecordEnding.SENT
    assert recorded.numbers == (2,)
    (trade,) = recorded.trades
    assert (trade.asset, trade.quantity, trade.quote) == ("BTC", Decimal("0.02"), "USDT")
    (left,) = recorded.left_out
    assert (left.number, left.why) == (1, LeftOut.QUANTITY_IN_OTHER_UNIT)
    assert said.reply.splitlines()[1].startswith("Trade 1 was not sent:")
    assert ledger.calls == ["list_assets", "propose_add"]


def test_the_other_trade_is_still_asked_about_and_the_held_one_said_when_it_ends() -> None:
    no_fee = dict(BTC_ROW, fee="")
    (first, second), _, _ = talk(
        U25 + "；" + BTC, "0", rows=[U25_ROW, no_fee], answers=[copied("0")]
    )

    assert first.recorded is not None and first.recorded.ending is RecordEnding.ASKING
    assert first.reply.startswith("[Trade 2 of 2: fee]")
    assert "Trade 1 was not sent" not in first.reply
    assert second.recorded is not None and second.recorded.ending is RecordEnding.SENT
    assert second.reply.splitlines()[1].startswith("Trade 1 was not sent:")


def test_a_quantity_in_the_assets_own_unit_is_sent_with_nothing_more_said() -> None:
    (said,), _, _ = talk(ETH, rows=[ETH_ROW])

    recorded = said.recorded
    assert recorded is not None and recorded.ending is RecordEnding.SENT
    (trade,) = recorded.trades
    assert (trade.asset, trade.quantity) == ("ETH", Decimal("0.5"))
    # The words are as they were before any reminder was said: the ending's sentence alone.
    assert said.reply == ENDING_WORDS[RecordEnding.SENT]


def test_with_no_asset_said_a_unit_that_is_money_holds_the_trade_back() -> None:
    no_coin = dict(U25_ROW, coin="")
    (said,), model, _ = talk(U25, rows=[no_coin])

    recorded = said.recorded
    assert recorded is not None and recorded.ending is RecordEnding.NOTHING_TO_SEND
    (left,) = recorded.left_out
    assert (left.why, left.code, left.unit) == (LeftOut.QUANTITY_IN_OTHER_UNIT, None, "U")
    assert "U is not the asset traded" in said.reply
    assert model.questions.calls == []


def test_with_no_asset_said_a_unit_that_is_an_asset_is_asked_about_as_before() -> None:
    passage = "今天上午9:40在币安买了0.1个BTC，价格94900 USDT，手续费0 USDT"
    no_coin = row(
        side="buy",
        quantity="0.1个BTC",
        price="94900 USDT",
        fee="0 USDT",
        time="今天上午9:40",
        platform="币安",
    )
    (said,), _, _ = talk(passage, rows=[no_coin])

    recorded = said.recorded
    assert recorded is not None and recorded.ending is RecordEnding.ASKING
    assert recorded.progress.trades[0].status is TradeStatus.OPEN
    assert said.reply.startswith("[Trade 1 of 1: asset]")


def test_a_trade_in_another_unit_that_is_also_money_traded_is_told_by_the_unit() -> None:
    passage = "今天上午9:40在币安用25U买了USD，价格1 USDT，手续费0 USDT"
    money_row = row(
        side="buy",
        coin="USD",
        quantity="25U",
        price="1 USDT",
        fee="0 USDT",
        time="今天上午9:40",
        platform="币安",
    )
    (said,), _, _ = talk(passage, rows=[money_row])

    recorded = said.recorded
    assert recorded is not None
    (left,) = recorded.left_out
    assert left.why is LeftOut.QUANTITY_IN_OTHER_UNIT


# --- the other reminders ----------------------------------------------------------


def test_a_number_no_trade_used_is_said_as_a_reminder_and_the_trade_still_sent() -> None:
    passage = BTC + "，第3次补仓"
    (said,), _, _ = talk(passage, rows=[BTC_ROW])

    recorded = said.recorded
    assert recorded is not None and recorded.ending is RecordEnding.SENT
    (issue,) = recorded.progress.reminders
    assert issue.kind is IssueKind.NUMBERS_LEFT_OVER
    assert said.reply.splitlines() == [
        ENDING_WORDS[RecordEnding.SENT],
        f"Reminder: {reminder_text(issue)}",
    ]
    assert said.reply.splitlines()[1] == (
        "Reminder: the passage: numbers in the passage that no trade used; "
        "a trade may be missing: 3"
    )


def test_a_question_waiting_says_no_reminder() -> None:
    no_fee = dict(BTC_ROW, fee="")
    (said,), _, _ = talk(BTC + "，第3次补仓", rows=[no_fee])

    assert said.recorded is not None and said.recorded.ending is RecordEnding.ASKING
    assert "Reminder:" not in said.reply


def test_every_reminder_kind_is_said_unless_taken_off_the_list() -> None:
    from ledger_hand.flows.progress import REMINDER_KINDS

    assert SPOKEN_REMINDERS == REMINDER_KINDS


# --- the record page keeps the number ---------------------------------------------


def test_the_record_page_keeps_25u_as_the_quantity_and_only_reminds() -> None:
    model = RoutedModel(
        screen=[screened(("spot_trade", "今天下午3点"))], extraction=[table(U25_ROW)]
    )

    progress = start(U25, model, now=INVENTED_NOW, zone=INVENTED_ZONE, assets=BUILT_IN_ASSETS)

    assert progress.stage is Stage.ASKING
    (trade,) = progress.trades
    assert trade.status is TradeStatus.OPEN
    assert trade.draft.quantity == Decimal("25")
    assert IssueKind.UNIT_NOT_THE_COIN in {issue.kind for issue in progress.reminders}
