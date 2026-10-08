"""Tests of recording a passage, with fake models standing in for every call.

One trade at a time, one field at a time; each answer is put back and the
trade checked again; the passage ends with records, skipped trades and
trades that cannot be recorded. Every passage and reply below is invented.
"""

from __future__ import annotations

import dataclasses
from decimal import Decimal

import pytest

from ledger_hand.asking.question_text import Writer
from ledger_hand.core.followup import AMOUNT_CELLS, AskCell, AskWhichCell, Cell, ConfirmCoin
from ledger_hand.core.trade import Amount, Side
from ledger_hand.core.validation import Missing, Violation
from ledger_hand.extraction.extractor import PassageProblem
from ledger_hand.extraction.screen_table import Kind
from ledger_hand.extraction.screening import Report
from ledger_hand.flows.progress import Stage, Step, TradeStatus, Tuning
from ledger_hand.flows.recording import answer, cancel, finish, remove, start, tuning_from
from ledger_hand.ports import ModelError, ModelErrorKind, ModelParameters
from ledger_hand.settings import ModelSettings
from tests.fakes.routed_model import RoutedModel
from tests.flows.scripted_flow import (
    NOW,
    ZONE,
    begin,
    copied,
    row,
    screened,
    table,
    walk,
    worded,
)

TWO_TRADES = "今天下午 3 点买了 0.5 ETH，又卖了 2 个 SOL，价格 150"
TWO_ROWS = table(
    row(side="buy", coin="ETH", quantity="0.5 ETH", time="今天下午 3 点"),
    row(side="sell", coin="SOL", quantity="2 个", price="150"),
)
SPOT = screened(("spot_trade", "买了 0.5 ETH"))
COMPLETE_TWO = "昨天买了 0.5 ETH，价格 3,420，手续费 0；卖了 2 SOL，价格 150，手续费 0.2 USDT"
COMPLETE_ROWS = table(
    row(side="buy", coin="ETH", quantity="0.5 ETH", price="3,420", fee="0", time="昨天"),
    row(side="sell", coin="SOL", quantity="2 SOL", price="150", fee="0.2 USDT", time="昨天"),
)


def two_trades() -> RoutedModel:
    return RoutedModel(screen=[SPOT], extraction=[TWO_ROWS])


# --- two trades, each missing a few fields ----------------------------------


def test_one_trade_at_a_time_one_field_at_a_time_until_both_are_records() -> None:
    model = two_trades()
    seen = walk(begin(TWO_TRADES, model), model, "3420", "none", "0.2 USDT", "昨天下午 4 点")

    asked = [(p.question.trade, p.question.asked) for p in seen if p.question is not None]
    assert asked == [
        (0, AskCell(Cell.PRICE, Missing.ONE_MORE_OF_QUANTITY_PRICE_TOTAL)),
        (0, AskCell(Cell.FEE, Missing.FEE)),
        (1, AskCell(Cell.FEE, Missing.FEE)),
        (1, AskCell(Cell.OCCURRED, Missing.OCCURRED)),
    ]
    labels = [p.question.label for p in seen if p.question is not None]
    assert labels == [
        "[Trade 1 of 2: price]",
        "[Trade 1 of 2: fee]",
        "[Trade 2 of 2: fee]",
        "[Trade 2 of 2: time]",
    ]
    last = seen[-1]
    assert last.stage is Stage.REVIEWING
    assert [(r.coin, r.side, r.price, r.fee, r.fee_coin) for r in last.records] == [
        ("ETH", Side.BUY, Decimal("3420"), Decimal("0"), "USDT"),
        ("SOL", Side.SELL, Decimal("150"), Decimal("0.2"), "USDT"),
    ]
    assert last.records[0].derived is Amount.TOTAL


def test_each_answer_is_put_back_and_the_trade_checked_again() -> None:
    model = two_trades()
    first = begin(TWO_TRADES, model)

    after = answer(first, "3420", model)

    assert after.trades[0].draft.price == Decimal("3420")
    assert after.trades[0].status is TradeStatus.OPEN
    assert after.question is not None
    assert after.question.asked == AskCell(Cell.FEE, Missing.FEE)
    assert first.trades[0].draft.price is None


def test_the_progress_never_changes_and_each_step_gives_a_new_one() -> None:
    model = two_trades()
    first = begin(TWO_TRADES, model)

    with pytest.raises(dataclasses.FrozenInstanceError):
        first.stage = Stage.DONE  # type: ignore[misc]
    assert answer(first, "3420", model) is not first


def test_the_question_is_put_together_and_labelled_by_the_program() -> None:
    model = RoutedModel(
        screen=[SPOT], extraction=[TWO_ROWS], questions=[worded("What did one ETH cost?")]
    )

    question = begin(TWO_TRADES, model).question

    assert question is not None
    assert question.text == "[Trade 1 of 2: price] What did one ETH cost?"
    assert question.writer is Writer.MODEL
    assert question.notes[-1].startswith("Say 'skip'")


# --- a trade already complete can still be kept out -------------------------


def test_complete_trades_ask_nothing_and_one_can_be_removed() -> None:
    model = RoutedModel(screen=[SPOT], extraction=[COMPLETE_ROWS])
    settled = begin(COMPLETE_TWO, model)
    assert settled.stage is Stage.REVIEWING
    assert settled.question is None
    assert model.question_parameters == []
    assert settled.can_remove and settled.can_cancel

    removed = remove(settled, 2)

    assert [record.coin for record in removed.records] == ["ETH"]
    assert removed.trades[1].status is TradeStatus.SKIPPED
    assert [record.coin for record in finish(removed).records] == ["ETH"]


@pytest.mark.parametrize("said", ["remove 2", "去掉第 2 笔"])
def test_removing_is_said_in_words_too(said: str) -> None:
    model = RoutedModel(screen=[SPOT], extraction=[COMPLETE_ROWS])

    (_, removed, done) = walk(begin(COMPLETE_TWO, model), model, said, "done")

    assert [record.coin for record in removed.records] == ["ETH"]
    assert done.stage is Stage.DONE


@pytest.mark.parametrize("dropping", ["cancel", "放弃整段"])
def test_dropping_the_whole_passage_keeps_nothing(dropping: str) -> None:
    model = RoutedModel(screen=[SPOT], extraction=[COMPLETE_ROWS])

    dropped = answer(begin(COMPLETE_TWO, model), dropping, model)

    assert dropped.stage is Stage.CANCELLED
    assert dropped.records == ()
    assert dropped.over and not dropped.can_remove and not dropped.can_cancel


def test_dropping_works_while_asking_too() -> None:
    model = two_trades()
    asking = begin(TWO_TRADES, model)

    assert cancel(asking).records == ()
    assert answer(asking, "取消整段", model).stage is Stage.CANCELLED


def test_a_number_that_is_no_record_is_said_and_nothing_changes() -> None:
    model = RoutedModel(screen=[SPOT], extraction=[COMPLETE_ROWS])
    settled = begin(COMPLETE_TWO, model)

    for wrong in ("remove 3", "what now"):
        after = answer(settled, wrong, model)
        assert after.stage is Stage.REVIEWING
        assert after.records == settled.records
        assert after.note is not None
    assert remove(remove(settled, 1), 1).note == "there is no recorded trade 1"


def test_steps_that_do_not_fit_the_stage_are_mistakes_of_the_caller() -> None:
    model = two_trades()
    asking = begin(TWO_TRADES, model)

    with pytest.raises(ValueError, match="settled"):
        remove(asking, 1)
    with pytest.raises(ValueError, match="settled"):
        finish(asking)
    done = finish(begin(COMPLETE_TWO, RoutedModel(screen=[SPOT], extraction=[COMPLETE_ROWS])))
    with pytest.raises(ValueError, match="nothing is being asked"):
        answer(done, "3420", model)
    with pytest.raises(ValueError, match="cannot be dropped"):
        cancel(done)


# --- skipping, and answers that cannot be used ------------------------------


def test_skip_leaves_the_trade_out_and_moves_on() -> None:
    model = two_trades()

    (_, after) = walk(begin(TWO_TRADES, model), model, "skip")

    assert after.trades[0].status is TradeStatus.SKIPPED
    assert after.question is not None
    assert after.question.trade == 1


def test_an_empty_answer_asks_the_same_question_again_and_no_model() -> None:
    model = two_trades()
    first = begin(TWO_TRADES, model)
    calls_before = len(first.calls)

    again = answer(first, "  ", model)

    assert again.question is not None and first.question is not None
    assert again.question.asked == first.question.asked
    assert again.question.sentence == first.question.sentence
    assert again.question.again == "no answer was received"
    assert len(again.calls) == calls_before
    assert model.answers.calls == []


def test_an_answer_the_rules_cannot_read_is_copied_by_the_model() -> None:
    model = RoutedModel(screen=[SPOT], extraction=[TWO_ROWS], answers=[copied("3420 刀")])

    after = answer(begin(TWO_TRADES, model), "价格是 3420 刀", model)

    assert after.trades[0].draft.price == Decimal("3420")
    assert after.trades[0].draft.quote == "刀"
    assert (Step.ANSWER, "answer-1") in after.prompts


def test_a_piece_not_in_the_answer_asks_again_with_the_reason() -> None:
    model = RoutedModel(screen=[SPOT], extraction=[TWO_ROWS], answers=[copied("3,000")])

    after = answer(begin(TWO_TRADES, model), "价格是 3420 刀", model)

    assert after.question is not None
    assert after.question.asked.cell is Cell.PRICE  # type: ignore[union-attr]
    assert after.question.again == "the model picked out words that are not in the answer"
    assert after.trades[0].draft.price is None


# --- the total copied into the price ----------------------------------------

TOTAL_AS_PRICE = "买了 0.02 BTC，一共 1898，手续费 0，昨天"
TOTAL_AS_PRICE_ROW = table(
    row(
        side="buy",
        coin="BTC",
        quantity="0.02 BTC",
        price="1898",
        total="1898",
        fee="0",
        time="昨天",
    )
)


@pytest.mark.parametrize("said", ["价格是 94900", "价格原话没说", "price not said"])
def test_one_right_answer_about_which_amount_is_wrong_settles_it(said: str) -> None:
    model = RoutedModel(screen=[SPOT], extraction=[TOTAL_AS_PRICE_ROW])
    first = begin(TOTAL_AS_PRICE, model)
    assert first.question is not None
    assert first.question.asked == AskWhichCell(AMOUNT_CELLS, Violation.AMOUNTS_DISAGREE)
    assert "Now: quantity 0.02, price 1898, total 1898." in first.question.notes

    after = answer(first, said, model)

    assert after.stage is Stage.REVIEWING
    (record,) = after.records
    assert (record.quantity, record.price, record.total) == (
        Decimal("0.02"),
        Decimal("94900"),
        Decimal("1898"),
    )


# --- priced in a coin -------------------------------------------------------

IN_A_COIN = "昨天买了 2 个 ETH，0.0062 BTC 一个，手续费 0"


def test_a_price_in_another_coin_says_only_usdt_is_recorded_and_quotes_the_passage() -> None:
    extraction = table(
        row(side="buy", coin="ETH", quantity="2 个", price="0.0062 BTC 一个", fee="0", time="昨天")
    )
    model = RoutedModel(screen=[SPOT], extraction=[extraction])

    question = begin(IN_A_COIN, model).question

    assert question is not None
    assert question.asked == AskCell(Cell.PRICE, Missing.ONE_MORE_OF_QUANTITY_PRICE_TOTAL)
    notes = " ".join(question.notes)
    assert "'0.0062 BTC 一个'" in notes
    assert "Only trades priced in USDT are recorded" in notes
    assert "'skip'" in notes


def test_a_price_answered_in_another_coin_cannot_be_recorded() -> None:
    extraction = table(
        row(side="buy", coin="ETH", quantity="2 个", price="0.0062 BTC 一个", fee="0", time="昨天")
    )
    model = RoutedModel(screen=[SPOT], extraction=[extraction])

    after = answer(begin(IN_A_COIN, model), "0.0062 BTC", model)

    assert after.stage is Stage.REVIEWING
    assert after.trades[0].status is TradeStatus.CANNOT_RECORD
    assert after.trades[0].reason is Violation.UNSUPPORTED_QUOTE


# --- the coin to confirm ----------------------------------------------------

NEW_COIN = "昨天买了 100 PIKA，价格 0.5，手续费 0；又买了 50 PIKA，价格 0.6，手续费 0"


def test_a_coin_confirmed_once_is_known_for_the_rest_of_the_run() -> None:
    extraction = table(
        row(side="buy", coin="PIKA", quantity="100 PIKA", price="0.5", fee="0", time="昨天"),
        row(side="buy", coin="PIKA", quantity="50 PIKA", price="0.6", fee="0", time="昨天"),
    )
    model = RoutedModel(screen=[SPOT], extraction=[extraction])
    first = begin(NEW_COIN, model)
    assert first.question is not None
    assert first.question.asked == ConfirmCoin(Cell.COIN, Missing.COIN_CONFIRMATION)
    assert first.question.label == "[Trade 1 of 2: is 'PIKA' a coin?]"

    after = answer(first, "yes", model)

    assert after.stage is Stage.REVIEWING
    assert [record.coin for record in after.records] == ["PIKA", "PIKA"]
    assert after.setting.coins.find("PIKA") is not None
    assert first.setting.coins.find("PIKA") is None


def test_a_coin_denied_is_asked_for_again() -> None:
    extraction = table(
        row(side="buy", coin="PIKA", quantity="100", price="0.5", fee="0", time="昨天")
    )
    model = RoutedModel(screen=[SPOT], extraction=[extraction])

    after = answer(begin(NEW_COIN, model), "no", model)

    assert after.question is not None
    assert after.question.asked == AskCell(Cell.COIN, Missing.COIN)


# --- a time the clocks showed twice -----------------------------------------


def test_a_time_shown_twice_lists_both_and_takes_the_choice() -> None:
    late_october = NOW.replace(month=10, day=25, hour=12)
    extraction = table(row(side="buy", coin="ETH", quantity="1", price="2400", fee="0"))
    model = RoutedModel(screen=[SPOT], extraction=[extraction])
    first = start("今天买了 1 ETH，价格 2400，手续费 0", model, now=late_october, zone=ZONE)

    twice = answer(first, "2:30", model)
    assert twice.question is not None
    assert [choice[:3] for choice in twice.question.choices] == ["1: ", "2: "]
    assert len(twice.question.candidates) == 2

    chosen = answer(twice, "2", model)
    (record,) = chosen.records
    assert record.occurred == twice.question.candidates[1]


# --- judging the passage first ----------------------------------------------


@pytest.mark.parametrize(
    ("kind", "evidence"),
    [("futures_or_leverage", "开了 5 倍杠杆做多"), ("plan", "打算周末再买")],
)
def test_a_passage_of_only_what_is_not_recorded_is_stopped_without_extraction(
    kind: str, evidence: str
) -> None:
    passage = f"昨天{evidence} ETH"
    model = RoutedModel(screen=[screened((kind, evidence))])

    stopped = begin(passage, model)

    assert stopped.stage is Stage.STOPPED
    assert stopped.stopped == (Report(Kind(kind), evidence),)
    assert stopped.question is None and stopped.records == ()
    assert model.extraction.calls == []
    assert model.question_parameters == []
    assert stopped.over


def test_a_passage_with_nothing_in_it_has_no_trade_and_no_extraction() -> None:
    model = RoutedModel(screen=[screened()])

    nothing = begin("行情好无聊", model)

    assert nothing.stage is Stage.NO_TRADE
    assert model.extraction.calls == []


def test_a_trade_beside_a_plan_goes_on_with_the_plan_set_aside() -> None:
    passage = "刚才买了 1 ETH，价格 2400，手续费 0；打算明天再买 1 个"
    extraction = table(
        row(side="buy", coin="ETH", quantity="1 ETH", price="2400", fee="0", time="刚才")
    )
    model = RoutedModel(
        screen=[screened(("spot_trade", "刚才买了 1 ETH"), ("plan", "打算明天再买 1 个"))],
        extraction=[extraction],
    )

    progress = begin(passage, model)

    assert len(model.extraction.calls) == 1
    assert progress.set_aside == (Report(Kind.PLAN, "打算明天再买 1 个"),)
    assert [record.coin for record in progress.records] == ["ETH"]


def test_extraction_with_no_trade_ends_with_no_trade() -> None:
    model = RoutedModel(screen=[SPOT], extraction=['{"trades": []}'])

    assert begin("买了点东西", model).stage is Stage.NO_TRADE


@pytest.mark.parametrize("step", [Step.SCREENING, Step.EXTRACTION])
def test_a_model_failure_while_judging_or_extracting_keeps_nothing(step: Step) -> None:
    error = ModelError(ModelErrorKind.UNREACHABLE, "invented")
    if step is Step.SCREENING:
        model = RoutedModel(screen=[error])
    else:
        model = RoutedModel(screen=[SPOT], extraction=[error])

    failed = begin(TWO_TRADES, model)

    assert failed.stage is Stage.FAILED
    assert failed.failure is not None
    assert failed.failure.step is step
    assert failed.failure.error is error
    assert failed.records == () and failed.over


def test_replies_that_stay_unreadable_keep_nothing() -> None:
    model = RoutedModel(screen=["not json", "still not"])

    failed = begin(TWO_TRADES, model)

    assert failed.stage is Stage.FAILED
    assert failed.failure is not None
    assert failed.failure.problems == ("the reply is not valid JSON", "the reply is not valid JSON")


@pytest.mark.parametrize(
    ("passage", "problem"), [("", PassageProblem.EMPTY), ("   ", PassageProblem.EMPTY)]
)
def test_an_empty_passage_is_never_sent(passage: str, problem: PassageProblem) -> None:
    model = RoutedModel()

    refused = begin(passage, model)

    assert refused.stage is Stage.REFUSED
    assert refused.refused is problem
    assert model.screen.calls == []


# --- a trade that cannot be recorded ----------------------------------------


def test_a_trade_that_cannot_be_recorded_is_set_aside_without_a_question() -> None:
    passage = "昨天用 USDT 买了 100 USDT，价格 1，手续费 0；还买了 1 ETH，价格 2400，手续费 0"
    extraction = table(
        row(side="buy", coin="USDT", quantity="100 USDT", price="1", fee="0", time="昨天"),
        row(side="buy", coin="ETH", quantity="1 ETH", price="2400", fee="0", time="昨天"),
    )
    model = RoutedModel(screen=[SPOT], extraction=[extraction])

    progress = begin(passage, model)

    assert progress.stage is Stage.REVIEWING
    assert progress.trades[0].status is TradeStatus.CANNOT_RECORD
    assert progress.trades[0].reason is Violation.COIN_IS_USDT
    assert [record.coin for record in progress.records] == ["ETH"]


# --- what the progress records ----------------------------------------------


def test_the_prompts_used_and_every_call_are_recorded() -> None:
    model = RoutedModel(screen=[SPOT], extraction=[TWO_ROWS], questions=[worded("Price?")])

    progress = begin(TWO_TRADES, model)

    assert progress.prompts == (
        (Step.SCREENING, "screen-1"),
        (Step.EXTRACTION, "first"),
        (Step.QUESTION, "bookkeeper-1"),
    )
    assert [call.step for call in progress.calls] == [
        Step.SCREENING,
        Step.EXTRACTION,
        Step.QUESTION,
    ]


def test_questions_are_worded_with_their_own_parameters() -> None:
    settings = ModelSettings(question_temperature=0.9, timeout_seconds=30.0)
    tuning = tuning_from(settings)
    model = two_trades()

    start(TWO_TRADES, model, now=NOW, zone=ZONE, tuning=tuning)

    assert model.question_parameters == [
        ModelParameters(
            temperature=0.9,
            top_p=settings.top_p,
            max_reply_tokens=settings.max_reply_tokens,
            context_tokens=settings.context_tokens,
            timeout_seconds=30.0,
        )
    ]
    assert model.screen.calls[0].parameters is None
    assert model.extraction.calls[0].parameters is None
    assert tuning != Tuning()


def test_a_failure_to_word_a_question_uses_the_program_s_sentence_and_the_same_label() -> None:
    model = RoutedModel(
        screen=[SPOT],
        extraction=[TWO_ROWS],
        questions=[ModelError(ModelErrorKind.TIMED_OUT, "invented")],
    )

    question = begin(TWO_TRADES, model).question

    assert question is not None
    assert question.writer is Writer.PROGRAM
    assert question.label == "[Trade 1 of 2: price]"
    assert question.asked == AskCell(Cell.PRICE, Missing.ONE_MORE_OF_QUANTITY_PRICE_TOTAL)


def test_now_and_zone_are_checked() -> None:
    with pytest.raises(ValueError, match="offset"):
        start(TWO_TRADES, RoutedModel(), now=NOW.replace(tzinfo=None), zone=ZONE)
    with pytest.raises(ValueError, match="zone"):
        start(TWO_TRADES, RoutedModel(), now=NOW, zone="Mars/Olympus")
