"""Tests of changing or deleting one trade through the assistant, with a scripted model.

The model only names the trade (the user's words for the time, the asset,
the side), the part and the new value; the program finds the trade, asks
which one when several match, reads the new value, asks which amount
follows when the three fall out of step, and proposes. The fake ledger
stands in for the ledger, with its invented book. Every sentence is
invented.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from ledger_hand.assistant import edit_words
from ledger_hand.assistant.outcome import Ending, NotRunCall, RefusedCall, TakenCall
from ledger_hand.core.ledger_records import TradeFacts, TradeFilter
from ledger_hand.core.proposals import ProposalStatus
from ledger_hand.core.trade import Side
from ledger_hand.flows.conversation import AssistantChat, Route, Said, say
from ledger_hand.flows.editing import Choosing, EditEnding, EditKind, Picking
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ledger.invented_book import INVENTED_NOW, INVENTED_TRADES, INVENTED_ZONE
from ledger_hand.ports import Message, Role, ToolCall, ToolReply
from tests.fakes.scripted_model import ScriptedModel, Step, scripted_record

BOOK = dict(INVENTED_TRADES)


def calls(*pairs: tuple[str, dict[str, object]]) -> ToolReply:
    return ToolReply(
        text="",
        calls=tuple(ToolCall(name=name, arguments=arguments) for name, arguments in pairs),
        record=scripted_record(),
    )


def delete(**arguments: object) -> ToolReply:
    return calls(("propose_trade_delete", arguments))


def update(**arguments: object) -> ToolReply:
    return calls(("propose_trade_update", arguments))


def talk(
    *said: str, steps: list[Step], ledger: FakeLedger | None = None
) -> tuple[list[Said], ScriptedModel, FakeLedger]:
    model = ScriptedModel(steps)
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


def proposed(ledger: FakeLedger) -> list[str]:
    return [call for call in ledger.calls if call.startswith("propose_")]


def book(ledger: FakeLedger) -> list[tuple[str, TradeFacts]]:
    return [(trade.id, trade.facts) for trade in ledger.list_trades(TradeFilter()).trades]


# --- found straight away -----------------------------------------------------


def test_the_only_trade_of_a_day_is_proposed_for_deletion_and_the_book_is_unchanged() -> None:
    (said,), model, ledger = talk(
        "把9月25号那笔ADA删掉",
        steps=[delete(period="9月25号", asset="ADA")],
    )

    assert said.edited is not None
    assert said.edited.ending is EditEnding.SENT
    sent = said.edit_sent
    assert sent is not None
    assert (sent.kind, sent.trade) == (EditKind.DELETE, "t-03")
    assert ledger.proposal_status(sent.proposal).status is ProposalStatus.PENDING
    assert said.state.chat.proposals == ((sent.proposal,),)
    assert said.sent is None
    assert said.well_ended
    assert len(model.calls) == 1
    assert book(ledger) == list(INVENTED_TRADES)
    assert sent.proposal in said.reply
    assert "640" in said.reply


def test_a_change_called_without_listing_first_still_finds_the_one_trade() -> None:
    (said,), _, ledger = talk(
        "把9月25号那笔ADA的平台改成Binance",
        steps=[update(period="9月25号", asset="ADA", field="platform", new_value="Binance")],
    )

    assert ledger.calls[:1] == ["list_assets"]
    assert "list_trades" in ledger.calls
    assert said.edit_sent is not None
    assert said.edit_sent.trade == "t-03"
    assert said.edited is not None
    after = said.edited.after
    assert after is not None
    assert after == dataclasses.replace(BOOK["t-03"], platform="Binance")
    assert "platform | OKX | Binance  <- changed" in said.reply


def test_the_ledger_holds_the_proposal_and_nothing_else_moves_until_it_is_saved() -> None:
    (said,), _, ledger = talk("把9月25号那笔ADA删掉", steps=[delete(period="9月25号", asset="ADA")])
    assert said.edit_sent is not None
    assert len(book(ledger)) == 11

    ledger.save(said.edit_sent.proposal)

    assert "t-03" not in dict(book(ledger))


def test_the_turn_ends_with_the_program_words_and_a_result_after_every_call() -> None:
    (said,), _, _ = talk(
        "把9月25号那笔ADA删掉",
        steps=[
            calls(
                ("list_trades", {"period": "9月25号"}),
                ("propose_trade_delete", {"period": "9月25号", "asset": "ADA"}),
                (
                    "propose_trade_update",
                    {"period": "9月25号", "field": "note", "new_value": "删掉"},
                ),
            )
        ],
    )

    assert said.turn is not None
    assert said.turn.ending is Ending.EDITING
    read, taken, other = said.turn.steps[0].calls
    assert isinstance(read, NotRunCall)
    assert isinstance(other, NotRunCall)
    assert isinstance(taken, TakenCall)
    assert json.loads(taken.result)["status"] == "sent"
    results = [item for item in said.state.chat.items if not isinstance(item, Message)]
    assert len(results) == 4
    assert said.state.chat.items[-1] == Message(Role.ASSISTANT, said.reply)
    assert "this was not done: changing the note to '删掉'" in said.reply


# --- more than one ------------------------------------------------------------


def test_two_trades_of_a_day_are_listed_and_the_second_answer_picks_the_second() -> None:
    (first, second), model, ledger = talk(
        "把10月6号那笔的手续费改成0.000009",
        "第二笔",
        steps=[update(period="10月6号", field="fee", new_value="0.000009")],
    )

    assert first.edited is not None
    assert first.edited.ending is EditEnding.PICKING
    assert first.edit_sent is None
    assert proposed(ledger) == ["propose_update"]
    assert isinstance(first.state.editing, Picking)
    assert first.state.editing.trades == ("t-05", "t-06")
    assert "1. 2026-10-06 11:48" in first.reply
    assert "2. 2026-10-06 16:25" in first.reply
    assert second.route is Route.ANSWER
    assert len(model.calls) == 1
    assert second.edit_sent is not None
    assert second.edit_sent.trade == "t-06"
    assert second.edited is not None
    after = second.edited.after
    assert after is not None
    assert str(after.fee) == "0.000009"
    assert after == dataclasses.replace(BOOK["t-06"], fee=Decimal("0.000009"))
    assert after.raw_text.encode() == BOOK["t-06"].raw_text.encode()
    assert second.state.editing is None
    assert second.state.chat.proposals == ((second.edit_sent.proposal,),)
    assert second.state.chat.items[-2:] == (
        Message(Role.USER, "第二笔"),
        Message(Role.ASSISTANT, second.reply),
    )


def test_a_number_out_of_the_list_asks_the_same_question_again() -> None:
    (_, again, picked), _, ledger = talk(
        "把10月6号那笔删掉",
        "第三笔",
        "the first one",
        steps=[delete(period="10月6号")],
    )

    assert again.edited is not None
    assert again.edited.ending is EditEnding.PICKING
    assert "There is no trade 3 in the list" in again.reply
    assert isinstance(again.state.editing, Picking)
    assert picked.edit_sent is not None
    assert picked.edit_sent.trade == "t-05"
    assert proposed(ledger) == ["propose_delete"]


def test_cancel_drops_what_waits() -> None:
    (_, cancelled), _, ledger = talk("把10月6号那笔删掉", "取消", steps=[delete(period="10月6号")])

    assert cancelled.edited is not None
    assert cancelled.edited.ending is EditEnding.CANCELLED
    assert cancelled.reply == edit_words.CANCELLED
    assert cancelled.state.editing is None
    assert proposed(ledger) == []


def test_a_trade_given_by_the_model_is_dropped_and_no_wrong_step() -> None:
    (said,), _, ledger = talk("把10月6号那笔删掉", steps=[delete(period="10月6号", trade="t-06")])

    assert said.edited is not None
    assert said.edited.ending is EditEnding.PICKING
    assert proposed(ledger) == []


def test_the_trade_picked_is_looked_up_again_and_taken_as_it_stands_now() -> None:
    ledger = FakeLedger()
    (first,), _, _ = talk("把10月6号那笔删掉", steps=[delete(period="10月6号")], ledger=ledger)
    saved = ledger.propose_update(
        "t-06", dataclasses.replace(BOOK["t-06"], note="checked"), "note checked"
    )
    ledger.save(saved.proposal_ids[0])

    model = ScriptedModel([])
    said = say(
        first.state,
        "2",
        model=model,
        ledger=ledger,
        now=INVENTED_NOW,
        zone=INVENTED_ZONE,
        max_steps=6,
    )

    assert said.edit_sent is not None
    assert said.edited is not None
    assert said.edited.before is not None
    assert said.edited.before.facts.note == "checked"


def test_a_trade_gone_before_the_answer_is_said_to_be_gone() -> None:
    ledger = FakeLedger()
    (first,), _, _ = talk(
        "把10月6号那笔的备注改成ok",
        steps=[update(period="10月6号", field="note", new_value="ok")],
        ledger=ledger,
    )
    gone = ledger.propose_delete("t-06", "delete t-06")
    ledger.save(gone.proposal_ids[0])

    said = say(
        first.state,
        "第二笔",
        model=ScriptedModel([]),
        ledger=ledger,
        now=INVENTED_NOW,
        zone=INVENTED_ZONE,
        max_steps=6,
    )

    assert said.reply == edit_words.GONE
    assert said.edit_sent is None


def test_more_than_the_list_holds_asks_to_say_more_and_waits_for_nothing() -> None:
    start = datetime(2026, 8, 1, 9, 0, tzinfo=ZoneInfo(INVENTED_ZONE))
    many = [
        (
            f"t-{number:02d}",
            dataclasses.replace(BOOK["t-03"], occurred=start.replace(day=number)),
        )
        for number in range(1, 13)
    ]
    (said,), _, ledger = talk(
        "把8月那笔ADA删掉",
        steps=[delete(period="8月", asset="ADA")],
        ledger=FakeLedger(trades=many),
    )

    assert said.edited is not None
    assert said.edited.ending is EditEnding.TOO_MANY
    assert len(said.edited.listed) == 10
    assert said.state.editing is None
    assert proposed(ledger) == []


# --- nothing to go by, nothing found -----------------------------------------


def test_no_condition_at_all_looks_up_nothing_and_asks_which_trade() -> None:
    (said,), _, ledger = talk("把那笔删掉", steps=[delete(asset="BTC", side="sell")])

    assert said.edited is not None
    assert said.edited.ending is EditEnding.NO_CONDITIONS
    assert said.reply == edit_words.NO_CONDITIONS
    assert "list_trades" not in ledger.calls


def test_nothing_found_says_what_was_looked_for_and_does_not_look_again() -> None:
    (said,), _, ledger = talk("把10月7号那笔BTC删掉", steps=[delete(period="10月7号", asset="BTC")])

    assert said.edited is not None
    assert said.edited.ending is EditEnding.NOT_FOUND
    assert ledger.calls.count("list_trades") == 1
    assert "Time: 2026-10-07" in said.reply
    assert "Asset: BTC" in said.reply
    assert proposed(ledger) == []


def test_a_period_the_program_cannot_read_is_said_and_nothing_looked_up() -> None:
    (said,), _, ledger = talk("把11月初那笔删掉", steps=[delete(period="11月初")])

    assert said.edited is not None
    assert said.edited.ending is EditEnding.TOLD
    assert "11月初" in said.reply
    assert "list_trades" not in ledger.calls


# --- a period that is not the user's words --------------------------------------


def test_a_year_the_model_wrote_is_a_wrong_step_and_nothing_is_looked_up() -> None:
    (said,), model, ledger = talk(
        "把9月25号那笔ADA删掉",
        steps=[delete(period="2023-09-25", asset="ADA"), "Sorry."],
    )

    assert said.turn is not None
    (refused,) = said.turn.steps[0].calls
    assert isinstance(refused, RefusedCall)
    assert json.loads(refused.result)["user_said"] == "把9月25号那笔ADA删掉"
    assert ledger.calls == []
    assert len(model.calls) == 2


def test_the_year_written_twice_says_the_fixed_words_and_proposes_nothing() -> None:
    (said,), _, ledger = talk(
        "把9月25号那笔ADA删掉",
        steps=[
            delete(period="2023-09-25", asset="ADA"),
            delete(period="2023-09-25", asset="ADA"),
        ],
    )

    assert said.route is Route.TAKEOVER
    assert said.reply == edit_words.PERIOD_AGAIN
    assert ledger.calls == []
    assert said.state.chat.items[-1] == Message(Role.ASSISTANT, edit_words.PERIOD_AGAIN)


def test_a_wrong_year_then_the_users_words_goes_on() -> None:
    (said,), _, _ = talk(
        "把9月25号那笔ADA删掉",
        steps=[delete(period="2023-09-25", asset="ADA"), delete(period="9月25号", asset="ADA")],
    )

    assert said.edit_sent is not None
    assert said.edit_sent.trade == "t-03"


def test_a_new_value_not_copied_twice_asks_for_the_value_again() -> None:
    (said,), _, ledger = talk(
        "把9月25号那笔ADA的数量改成六百四十一",
        steps=[
            update(period="9月25号", asset="ADA", field="quantity", new_value="641"),
            update(period="9月25号", asset="ADA", field="quantity", new_value="641"),
        ],
    )

    assert said.reply == edit_words.VALUE_AGAIN
    assert ledger.calls == []


def test_two_wrong_steps_with_nothing_to_go_on_keep_the_turns_words() -> None:
    (said,), _, ledger = talk(
        "把9月25号那笔ADA删掉",
        steps=[delete(when="9月25号"), delete(when="9月25号")],
    )

    assert said.route is Route.TAKEOVER
    assert said.edited is None
    assert said.recorded is None
    assert ledger.calls == []
    assert not said.well_ended


# --- the new value --------------------------------------------------------------


def test_a_new_quantity_out_of_step_offers_two_ways_worked_out_to_the_digit() -> None:
    (first, second), _, ledger = talk(
        "把10月6号那笔BTC的数量改成0.0081",
        "总额",
        steps=[update(period="10月6号", asset="BTC", field="quantity", new_value="0.0081")],
    )

    assert first.edited is not None
    assert first.edited.ending is EditEnding.CHOOSING
    assert first.edit_sent is None
    assert proposed(ledger) == ["propose_update"]
    assert isinstance(first.state.editing, Choosing)
    assert "the total becomes 501.714 USDT" in first.reply
    assert "the price becomes 62704.69135802 USDT" in first.reply
    assert second.edited is not None
    after = second.edited.after
    assert after is not None
    assert (str(after.quantity), str(after.price), str(after.total)) == (
        "0.0081",
        "61940",
        "501.714",
    )
    assert after == dataclasses.replace(
        BOOK["t-05"], quantity=Decimal("0.0081"), total=Decimal("501.714")
    )
    assert after.quantity * after.price == after.total


def test_choosing_the_price_works_it_out_by_the_ledgers_rules() -> None:
    (_, second), _, _ = talk(
        "把10月6号那笔BTC的数量改成0.0081",
        "2",
        steps=[update(period="10月6号", asset="BTC", field="quantity", new_value="0.0081")],
    )

    assert second.edited is not None
    after = second.edited.after
    assert after is not None
    assert str(after.price) == "62704.69135802"
    assert abs(after.quantity * after.price - after.total) <= Decimal("0.01")
    assert after == dataclasses.replace(
        BOOK["t-05"], quantity=Decimal("0.0081"), price=Decimal("62704.69135802")
    )


def test_an_unreadable_choice_asks_again_and_waits() -> None:
    (_, again), _, ledger = talk(
        "把10月6号那笔BTC的数量改成0.0081",
        "随便",
        steps=[update(period="10月6号", asset="BTC", field="quantity", new_value="0.0081")],
    )

    assert again.edited is not None
    assert again.edited.ending is EditEnding.CHOOSING
    assert isinstance(again.state.editing, Choosing)
    assert proposed(ledger) == []


def test_a_pick_followed_by_a_choice_waits_for_one_thing_at_a_time() -> None:
    (first, second, third), _, _ = talk(
        "把10月6号那笔的数量改成0.0081",
        "1",
        "price",
        steps=[update(period="10月6号", field="quantity", new_value="0.0081")],
    )

    assert isinstance(first.state.editing, Picking)
    assert first.state.recording is None
    assert isinstance(second.state.editing, Choosing)
    assert second.state.recording is None
    assert third.state.editing is None
    assert third.edit_sent is not None


def test_a_change_that_keeps_the_amounts_in_step_is_sent_without_a_question() -> None:
    (said,), _, _ = talk(
        "把10月21号那笔BTC的总额改成396.7249",
        steps=[update(period="10月21号", asset="BTC", field="total", new_value="396.7249")],
    )

    assert said.edit_sent is not None
    assert said.edit_sent.trade == "t-08"


def test_a_time_with_only_the_day_changes_nothing() -> None:
    (said,), _, ledger = talk(
        "把9月25号那笔ADA的时间改成9月24号",
        steps=[update(period="9月25号", asset="ADA", field="time", new_value="9月24号")],
    )

    assert said.edited is not None
    assert said.edited.ending is EditEnding.TOLD
    assert "time of day" in said.reply
    assert proposed(ledger) == []


def test_a_time_with_the_day_and_the_clock_is_proposed() -> None:
    (said,), _, _ = talk(
        "把9月25号那笔ADA的时间改成9月24号20:37",
        steps=[update(period="9月25号", asset="ADA", field="time", new_value="9月24号20:37")],
    )

    assert said.edited is not None
    after = said.edited.after
    assert after is not None
    assert after.occurred == datetime(2026, 9, 24, 20, 37, tzinfo=ZoneInfo(INVENTED_ZONE))


def test_a_unit_that_is_not_what_the_field_is_in_changes_nothing() -> None:
    (said,), _, ledger = talk(
        "把9月25号那笔ADA的手续费改成0.3U",
        steps=[update(period="9月25号", asset="ADA", field="fee", new_value="0.3U")],
    )

    assert said.edited is not None
    assert said.edited.ending is EditEnding.TOLD
    assert "one at a time" in said.reply
    assert proposed(ledger) == []


def test_the_same_value_as_now_is_not_sent() -> None:
    (said,), _, ledger = talk(
        "把9月25号那笔ADA的平台改成OKX",
        steps=[update(period="9月25号", asset="ADA", field="platform", new_value="OKX")],
    )

    assert said.reply == edit_words.NOTHING_TO_CHANGE
    assert proposed(ledger) == []


def test_a_number_that_may_hold_a_thousands_mark_is_not_taken() -> None:
    (said,), _, ledger = talk(
        "把9月25号那笔ADA的数量改成1.500",
        steps=[update(period="9月25号", asset="ADA", field="quantity", new_value="1.500")],
    )

    assert said.edited is not None
    assert said.edited.ending is EditEnding.TOLD
    assert proposed(ledger) == []


def test_the_side_changed_by_its_word() -> None:
    (said,), _, _ = talk(
        "把11月19号那笔ETH改成卖出",
        steps=[update(period="11月19号", asset="ETH", field="side", new_value="卖出")],
    )

    assert said.edited is not None
    after = said.edited.after
    assert after is not None
    assert after.side is Side.SELL


# --- the ledger's check -----------------------------------------------------------


def test_deleting_a_buy_a_later_sell_rests_on_is_turned_down_and_nothing_waits() -> None:
    (said,), _, ledger = talk("把9月18号那笔ETH删掉", steps=[delete(period="9月18号", asset="ETH")])

    assert said.edited is not None
    assert said.edited.ending is EditEnding.LEDGER_REFUSED
    assert "sell would take out more than was held" in said.reply
    assert said.edit_sent is None
    assert said.state.chat.proposals == ()
    assert book(ledger) == list(INVENTED_TRADES)


# --- what was said before -----------------------------------------------------------


def test_the_asset_said_the_time_before_is_used_and_the_table_says_so() -> None:
    model_steps: list[Step] = [
        calls(("list_trades", {"period": "9月25号", "asset": "ADA"})),
        "One ADA buy.",
        delete(period="9月25号", asset="ADA"),
    ]
    (_, said), _, _ = talk("9月25号我买的ADA", "把9月25号那笔删掉", steps=model_steps)

    assert said.edit_sent is not None
    assert said.edit_sent.trade == "t-03"
    assert "Asset: ADA" in said.reply


# --- a period cut out of a longer time ---------------------------------------------

CUT_SENTENCE = "把9月13号那笔BTC的时间改成9月13号上午10点15分"


def test_a_month_cut_out_of_the_day_proposes_nothing_and_says_the_fixed_words() -> None:
    cut = update(period="9月", asset="BTC", field="time", new_value="9月13号上午10点15分")
    (said,), _, ledger = talk(CUT_SENTENCE, steps=[cut, cut])

    assert said.reply == edit_words.PERIOD_AGAIN
    assert ledger.calls == []
    assert said.edit_sent is None


def test_a_month_cut_out_of_the_day_says_the_fixed_words_at_once() -> None:
    cut = update(period="9月", asset="BTC", field="time", new_value="9月13号上午10点15分")
    (said,), model, ledger = talk(CUT_SENTENCE, steps=[cut])

    assert said.route is Route.MODEL
    assert said.reply == edit_words.PERIOD_AGAIN
    assert said.edited is not None
    assert said.edited.ending is EditEnding.TOLD
    assert len(model.calls) == 1
    assert ledger.calls == []
    assert proposed(ledger) == []


@pytest.mark.parametrize(
    ("sentence", "month"),
    [("把9月30号那笔BTC删掉", "9月"), ("把11月4号那笔ADA删掉", "11月")],
)
def test_other_days_cut_to_their_month_propose_nothing(sentence: str, month: str) -> None:
    asset = "BTC" if "BTC" in sentence else "ADA"
    cut = delete(period=month, asset=asset)
    (said,), _, ledger = talk(sentence, steps=[cut, cut])

    assert said.reply == edit_words.PERIOD_AGAIN
    assert ledger.calls == []


def test_a_month_said_as_a_month_still_finds_its_trades() -> None:
    (said,), _, _ = talk("把10月份那笔BTC删掉", steps=[delete(period="10月", asset="BTC")])

    assert said.edited is not None
    assert said.edited.ending is EditEnding.PICKING


@pytest.mark.parametrize(
    ("before", "sentence", "month", "asset"),
    [
        ("9月我都买了什么", "把9月13号那笔BTC删掉", "9月", "BTC"),
        ("11月我买了什么", "把11月4号那笔ADA删掉", "11月", "ADA"),
    ],
)
def test_a_month_said_before_does_not_make_a_cut_day_a_fair_copy(
    before: str, sentence: str, month: str, asset: str
) -> None:
    steps: list[Step] = [
        calls(("list_trades", {"period": month})),
        "Here they are.",
        delete(period=month, asset=asset),
    ]
    (_, said), _, ledger = talk(before, sentence, steps=steps)

    assert said.reply == edit_words.PERIOD_AGAIN
    assert said.edit_sent is None
    assert proposed(ledger) == []


def test_a_month_said_before_still_finds_the_trade_when_this_sentence_names_no_time() -> None:
    steps: list[Step] = [
        calls(("list_trades", {"period": "9月", "asset": "ADA"})),
        "One ADA buy.",
        delete(period="9月", asset="ADA"),
    ]
    (_, said), _, _ = talk("9月我买的ADA", "把那笔ADA删掉", steps=steps)

    assert said.edit_sent is not None
    assert said.edit_sent.trade == "t-03"
