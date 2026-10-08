"""Tests of reading an answer to a follow-up question, with the scripted model copying.

The rules read a whole answer first; only when they cannot is the model
asked to copy one piece out of it, and the piece has to be a piece of the
answer. Every answer and reply below is invented.
"""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from ledger_hand.core.coins import BUILT_IN_TABLE
from ledger_hand.core.followup import AMOUNT_CELLS, AskCell, AskWhichCell, Cell, ConfirmCoin
from ledger_hand.core.numbers import Doubt
from ledger_hand.core.timeparse import Refusal
from ledger_hand.core.trade import OccurredTime, Side, TimePrecision
from ledger_hand.core.validation import Missing, Violation
from ledger_hand.extraction.answer_phrase import (
    AnswerProblem,
    AnswerReading,
    AnswerSetting,
    Asked,
    Command,
    Commanded,
    Confirmation,
    Confirmed,
    Filled,
    NotRead,
    RemoveTrade,
    Review,
    TwoTimes,
    read_answer,
    read_review_answer,
)
from ledger_hand.extraction.answer_table import ANSWER_TABLE, CopyProblem
from ledger_hand.extraction.prompts.answer import ANSWER_PROMPT
from ledger_hand.ports import ModelError, ModelErrorKind, Role
from tests.fakes.scripted_model import ScriptedModel

ZONE = "Europe/Budapest"
NOW = datetime(2026, 10, 7, 9, 30, tzinfo=ZoneInfo(ZONE))
SETTING = AnswerSetting(now=NOW, zone=ZONE, coins=BUILT_IN_TABLE, coin="BTC")
PRICE = AskCell(Cell.PRICE, Missing.ONE_MORE_OF_QUANTITY_PRICE_TOTAL)
QUANTITY = AskCell(Cell.QUANTITY, Missing.TWO_OF_QUANTITY_PRICE_TOTAL)
FEE = AskCell(Cell.FEE, Missing.FEE)
TIME = AskCell(Cell.OCCURRED, Missing.OCCURRED)
WHICH_AMOUNT = AskWhichCell(AMOUNT_CELLS, Violation.AMOUNTS_DISAGREE)


def copied(phrase: str) -> str:
    return json.dumps({"phrase": phrase}, ensure_ascii=False)


def read(
    answer: str, asked: Asked, *steps: str | ModelError, setting: AnswerSetting = SETTING
) -> tuple[AnswerReading, ScriptedModel]:
    model = ScriptedModel(steps)
    return read_answer(answer, asked, model, setting), model


def outcome(answer: str, asked: Asked, *steps: str | ModelError) -> object:
    reading, model = read(answer, asked, *steps)
    assert model.steps_left == 0
    return reading.outcome


# --- the four answers of the contract ---------------------------------------


def test_a_price_with_words_around_it_is_copied_by_the_model_and_read_by_the_rules() -> None:
    reading, model = read("价格是 94900 刀", PRICE, copied("94900 刀"))

    assert reading.outcome == Filled(Cell.PRICE, Decimal("94900"), "刀")
    assert reading.copied == "94900 刀"
    assert len(model.calls) == 1


def test_no_said_for_the_fee_is_a_fee_of_zero() -> None:
    assert outcome("没有", FEE) == Filled(Cell.FEE, Decimal("0"))


def test_skip_leaves_the_trade_out() -> None:
    assert outcome("skip", PRICE) == Commanded(Command.SKIP)


@pytest.mark.parametrize("answer", ["", "   ", "\n"])
def test_an_empty_answer_asks_no_model(answer: str) -> None:
    reading, model = read(answer, PRICE)

    assert reading.outcome == NotRead(AnswerProblem.NO_ANSWER)
    assert model.calls == []


# --- the model's piece has to be a piece of the answer ----------------------


@pytest.mark.parametrize("phrase", ["94,000", "price 94900", "900"])
def test_a_piece_that_is_not_in_the_answer_is_not_used(phrase: str) -> None:
    assert outcome("价格是 94900", PRICE, copied(phrase)) == NotRead(AnswerProblem.NOT_IN_ANSWER)


def test_nothing_copied_is_not_understood() -> None:
    assert outcome("I don't remember", PRICE, copied("")) == NotRead(AnswerProblem.NOT_UNDERSTOOD)


def test_a_piece_the_rules_cannot_read_is_not_understood() -> None:
    assert outcome("about a lot", PRICE, copied("a lot")) == NotRead(AnswerProblem.NOT_UNDERSTOOD)


def test_the_model_is_asked_with_the_field_and_the_answer() -> None:
    reading, model = read("价格是 94900 刀", PRICE, copied("94900 刀"))

    (call,) = model.calls
    assert call.reply_schema == ANSWER_TABLE
    assert call.messages[0].role is Role.SYSTEM
    assert call.messages[0].content == ANSWER_PROMPT.instructions
    assert "the price of one coin" in call.messages[1].content
    assert call.messages[1].content.endswith("价格是 94900 刀")
    assert reading.calls == (reading.calls[0],)


def test_an_unreadable_reply_is_asked_again_once_then_given_up() -> None:
    reading, model = read("价格是 94900", PRICE, "not json", "still not")

    assert reading.outcome == NotRead(AnswerProblem.MODEL_REPLY_UNREADABLE, CopyProblem.NOT_JSON)
    assert len(model.calls) == 2
    assert CopyProblem.NOT_JSON.value in model.calls[1].messages[-1].content


def test_a_model_error_is_a_reason_to_ask_again() -> None:
    error = ModelError(ModelErrorKind.TIMED_OUT, "invented")

    assert outcome("价格是 94900", PRICE, error) == NotRead(
        AnswerProblem.MODEL_FAILED, ModelErrorKind.TIMED_OUT
    )


# --- numbers and their units ------------------------------------------------


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("94900", Filled(Cell.PRICE, Decimal("94900"))),
        ("94,900 USDT", Filled(Cell.PRICE, Decimal("94900"), "USDT")),
        ("9.49万刀", Filled(Cell.PRICE, Decimal("94900"), "刀")),
        ("0.0062 BTC", Filled(Cell.PRICE, Decimal("0.0062"), "BTC")),
    ],
)
def test_a_number_said_alone_is_read_with_its_unit(answer: str, expected: Filled) -> None:
    assert outcome(answer, PRICE) == expected


def test_a_number_the_reader_is_unsure_of_is_not_sent_to_the_model() -> None:
    assert outcome("1,5", PRICE) == NotRead(AnswerProblem.NUMBER_UNSURE, Doubt.AMBIGUOUS_SEPARATOR)


def test_a_fee_names_its_coin_with_its_unit() -> None:
    assert outcome("2 BNB", FEE) == Filled(Cell.FEE, Decimal("2"), "BNB")


@pytest.mark.parametrize("answer", ["none", "No fee", "免手续费", "ｎｏｎｅ"])
def test_the_words_for_no_fee_are_a_fee_of_zero(answer: str) -> None:
    assert outcome(answer, FEE) == Filled(Cell.FEE, Decimal("0"))


def test_a_quantity_may_name_the_trade_s_coin_but_no_other() -> None:
    assert outcome("0.5 BTC", QUANTITY) == Filled(Cell.QUANTITY, Decimal("0.5"))
    assert outcome("0.5 个", QUANTITY) == Filled(Cell.QUANTITY, Decimal("0.5"))
    assert outcome("0.5 ETH", QUANTITY) == NotRead(AnswerProblem.UNIT_NOT_THE_COIN)


# --- times ------------------------------------------------------------------


def test_a_time_is_read_with_the_passage_s_moment_and_zone() -> None:
    expected = OccurredTime(
        datetime(2026, 10, 6, 21, 0, tzinfo=ZoneInfo(ZONE)), TimePrecision.MINUTE, ZONE
    )

    assert outcome("昨天晚上 9 点", TIME) == Filled(Cell.OCCURRED, expected)


def test_a_time_in_the_future_says_so_without_asking_the_model() -> None:
    assert outcome("明天", TIME) == NotRead(AnswerProblem.TIME_REFUSED, Refusal.IN_THE_FUTURE)


def test_a_time_said_with_words_around_it_is_copied_by_the_model() -> None:
    expected = OccurredTime(datetime(2026, 10, 6).date(), TimePrecision.DAY, ZONE)

    assert outcome("I think it was yesterday", TIME, copied("yesterday")) == Filled(
        Cell.OCCURRED, expected
    )


def test_a_time_the_clocks_showed_twice_offers_both_and_either_can_be_chosen() -> None:
    late_october = datetime(2026, 10, 25, 12, 0, tzinfo=ZoneInfo(ZONE))
    setting = AnswerSetting(now=late_october, zone=ZONE, coins=BUILT_IN_TABLE)
    reading, _ = read("2:30", TIME, setting=setting)
    assert isinstance(reading.outcome, TwoTimes)
    both = (reading.outcome.earlier, reading.outcome.later)

    choosing = AnswerSetting(now=late_october, zone=ZONE, coins=BUILT_IN_TABLE, candidates=both)
    first, _ = read("first", TIME, setting=choosing)
    second, _ = read("第二个", TIME, setting=choosing)

    assert first.outcome == Filled(Cell.OCCURRED, both[0])
    assert second.outcome == Filled(Cell.OCCURRED, both[1])


# --- words ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("answer", "side"), [("buy", Side.BUY), ("卖了", Side.SELL), ("SOLD", Side.SELL)]
)
def test_buy_and_sell_are_read_from_the_list(answer: str, side: Side) -> None:
    assert outcome(answer, AskCell(Cell.SIDE, Missing.SIDE)) == Filled(Cell.SIDE, side)


def test_a_side_said_in_a_sentence_is_copied_by_the_model() -> None:
    asked = AskCell(Cell.SIDE, Missing.SIDE)

    assert outcome("I bought it", asked, copied("bought")) == Filled(Cell.SIDE, Side.BUY)


@pytest.mark.parametrize(
    ("answer", "confirmation"),
    [("yes", Confirmation.YES), ("是的", Confirmation.YES), ("no", Confirmation.NO)],
)
def test_yes_and_no_are_read_from_the_list(answer: str, confirmation: Confirmation) -> None:
    asked = ConfirmCoin(Cell.COIN, Missing.COIN_CONFIRMATION)

    assert outcome(answer, asked) == Confirmed(confirmation)


@pytest.mark.parametrize(
    ("answer", "coin"), [("比特币", "BTC"), ("eth", "ETH"), ("pika", "PIKA"), ("USDT", "USDT")]
)
def test_a_coin_is_read_with_the_coin_table(answer: str, coin: str) -> None:
    assert outcome(answer, AskCell(Cell.COIN, Missing.COIN)) == Filled(Cell.COIN, coin)


@pytest.mark.parametrize(("answer", "value"), [("Binance", "Binance"), ("none", None)])
def test_a_platform_is_taken_as_written_or_left_out(answer: str, value: str | None) -> None:
    asked = AskCell(Cell.PLATFORM, Violation.PLATFORM_TOO_LONG)

    assert outcome(answer, asked) == Filled(Cell.PLATFORM, value)


@pytest.mark.parametrize("answer", ["cancel", "取消整段", "放弃整段", "Skip.", "跳过这笔"])
def test_the_commands_are_read_whatever_is_asked(answer: str) -> None:
    result = outcome(answer, PRICE)

    assert isinstance(result, Commanded)


# --- which of several cells is wrong ----------------------------------------


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("价格是 94900", Filled(Cell.PRICE, Decimal("94900"))),
        # The rest of an answer that names a cell is read tidied: lower case.
        ("price: 94,900 USDT", Filled(Cell.PRICE, Decimal("94900"), "usdt")),
        ("the total is 1898", Filled(Cell.TOTAL, Decimal("1898"))),
        ("总价应该是 1898", Filled(Cell.TOTAL, Decimal("1898"))),
        ("价格原话没说", Filled(Cell.PRICE, None)),
        ("the price was not said", Filled(Cell.PRICE, None)),
        ("数量 0.02", Filled(Cell.QUANTITY, Decimal("0.02"))),
    ],
)
def test_the_answer_names_one_cell_and_its_value(answer: str, expected: Filled) -> None:
    assert outcome(answer, WHICH_AMOUNT) == expected


@pytest.mark.parametrize("answer", ["94900", "数量和价格都对", "手续费是 2"])
def test_an_answer_that_names_no_one_cell_asked_about_is_asked_again(answer: str) -> None:
    assert outcome(answer, WHICH_AMOUNT) == NotRead(AnswerProblem.NO_CELL_NAMED)


def test_a_named_cell_whose_value_the_rules_cannot_read_is_copied_by_the_model() -> None:
    reading, model = read("价格好像是九万四千九吧", WHICH_AMOUNT, copied("九万四千九"))

    assert reading.outcome == Filled(Cell.PRICE, Decimal("94900"))
    assert "the price of one coin" in model.calls[0].messages[1].content


# --- once every trade is settled --------------------------------------------


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("done", Review.DONE),
        ("完成", Review.DONE),
        ("放弃整段", Review.CANCEL),
        ("cancel", Review.CANCEL),
        ("remove 2", RemoveTrade(2)),
        ("去掉第 2 笔", RemoveTrade(2)),
        ("去掉第二笔", RemoveTrade(2)),
        ("remove trade #3", RemoveTrade(3)),
        ("remove 0", NotRead(AnswerProblem.NOT_UNDERSTOOD)),
        ("remove 1.5", NotRead(AnswerProblem.NOT_UNDERSTOOD)),
        ("save it", NotRead(AnswerProblem.NOT_UNDERSTOOD)),
        ("", NotRead(AnswerProblem.NO_ANSWER)),
    ],
)
def test_once_settled_the_answer_is_done_cancel_or_remove(answer: str, expected: object) -> None:
    assert read_review_answer(answer) == expected
