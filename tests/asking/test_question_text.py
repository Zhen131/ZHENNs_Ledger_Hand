"""Tests of wording a follow-up question, with the scripted model as the bookkeeper.

What is asked, and the label that says so, are the program's; the model's
sentence is used only when it is one plain question that brings in nothing
beyond the facts. Every fact and reply below is invented.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from ledger_hand.asking.prompts.bookkeeper import BOOKKEEPER_PROMPT
from ledger_hand.asking.question_text import (
    MAX_SENTENCE_LENGTH,
    QUESTION_TABLE,
    Fallback,
    QuestionFacts,
    Writer,
    WrittenQuestion,
    facts_text,
    label_of,
    write_question,
)
from ledger_hand.asking.templates import template_sentence
from ledger_hand.core.coins import BUILT_IN_TABLE
from ledger_hand.core.followup import (
    FOLLOW_UP_ORDER,
    AskCell,
    AskWhichCell,
    CannotRecord,
    Cell,
    ConfirmCoin,
    next_follow_up,
)
from ledger_hand.core.trade import Side, TradeDraft
from ledger_hand.core.validation import DraftProblems, Missing, Violation
from ledger_hand.ports import (
    FinishReason,
    ModelError,
    ModelErrorKind,
    ModelParameters,
    ModelReply,
    ReplyRecord,
    Role,
)
from tests.fakes.scripted_model import ScriptedModel

PRICE_FACTS = QuestionFacts(
    trade=2,
    trades=3,
    asked=AskCell(Cell.PRICE, Missing.ONE_MORE_OF_QUANTITY_PRICE_TOTAL),
    known=(("side", "buy"), ("coin", "ETH"), ("quantity", "2")),
    quoted="0.0062 BTC 一个",
    notes=("Only trades priced in USDT are recorded.",),
)


def said(question: str) -> str:
    return json.dumps({"question": question}, ensure_ascii=False)


def written(facts: QuestionFacts, *steps: str | ModelReply | ModelError) -> WrittenQuestion:
    model = ScriptedModel(steps)
    result = write_question(facts, model, BUILT_IN_TABLE)
    assert model.steps_left == 0
    return result


def test_the_model_s_question_is_used_behind_the_program_s_label() -> None:
    result = written(PRICE_FACTS, said("What was the price of one ETH, in USDT?"))

    assert result.writer is Writer.MODEL
    assert result.fallback is None
    assert result.label == "[Trade 2 of 3: price]"
    assert result.sentence == "What was the price of one ETH, in USDT?"
    assert result.text == "[Trade 2 of 3: price] What was the price of one ETH, in USDT?"


def test_the_model_is_given_the_persona_and_only_the_facts() -> None:
    parameters = ModelParameters(
        temperature=0.7, top_p=1.0, max_reply_tokens=64, context_tokens=2048, timeout_seconds=9.0
    )
    model = ScriptedModel([said("What was the price?")])

    write_question(PRICE_FACTS, model, BUILT_IN_TABLE, parameters=parameters)

    (call,) = model.calls
    assert [(m.role, m.content) for m in call.messages] == [
        (Role.SYSTEM, BOOKKEEPER_PROMPT.instructions),
        (Role.USER, facts_text(PRICE_FACTS)),
    ]
    assert call.reply_schema == QUESTION_TABLE
    assert call.parameters == parameters
    assert BOOKKEEPER_PROMPT.instructions.startswith("You are a meticulous bookkeeper")


def test_the_facts_are_given_one_per_line() -> None:
    assert facts_text(PRICE_FACTS).splitlines() == [
        "Trade: 2 of 3",
        "Ask for: the price",
        "Why: one more of quantity, price and total",
        "Known: side: buy; coin: ETH; quantity: 2",
        "The passage says: '0.0062 BTC 一个'",
        "Note: Only trades priced in USDT are recorded.",
    ]


def _cut_off() -> ModelReply:
    record = ReplyRecord(
        model="scripted",
        elapsed_seconds=0.0,
        prompt_tokens=None,
        reply_tokens=None,
        finish=FinishReason.LENGTH_LIMIT,
    )
    return ModelReply(text=said("What was the price?"), record=record)


@pytest.mark.parametrize(
    ("step", "fallback"),
    [
        (ModelError(ModelErrorKind.UNREACHABLE, "invented"), Fallback.MODEL_FAILED),
        (ModelError(ModelErrorKind.TIMED_OUT, "invented"), Fallback.MODEL_FAILED),
        ("What was the price?", Fallback.REPLY_UNREADABLE),
        ('{"text": "What was the price?"}', Fallback.REPLY_UNREADABLE),
        (_cut_off(), Fallback.REPLY_UNREADABLE),
        (said(""), Fallback.NOT_ONE_QUESTION),
        (said("What was the price?\n\nAnd the fee?"), Fallback.NOT_ONE_QUESTION),
        (said("What was the price.\nThank you!"), Fallback.NOT_ONE_QUESTION),
        (said("Tell me the price."), Fallback.NOT_ONE_QUESTION),
        (said("What was the price? And the time?"), Fallback.NOT_ONE_QUESTION),
        (said("What " + "very " * 60 + "price?"), Fallback.NOT_ONE_QUESTION),
        (said("Was the price 94900 USDT?"), Fallback.ADDS_FACTS),
        (said("What was the price of one SOL?"), Fallback.ADDS_FACTS),
        (said("你买的价格是多少?"), Fallback.ADDS_FACTS),
    ],
)
def test_the_program_s_sentence_stands_in_whenever_the_model_s_will_not_do(
    step: str | ModelReply | ModelError, fallback: Fallback
) -> None:
    result = written(PRICE_FACTS, step)

    assert result.writer is Writer.PROGRAM
    assert result.fallback is fallback
    assert result.sentence == template_sentence(PRICE_FACTS.asked, None)
    assert result.label == "[Trade 2 of 3: price]"


def test_quoting_the_passage_s_own_words_and_the_known_values_is_allowed() -> None:
    sentence = "The passage says '0.0062 BTC 一个' for the ETH: what was its price in USDT?"

    assert written(PRICE_FACTS, said(sentence)).writer is Writer.MODEL


def test_the_longest_sentence_allowed() -> None:
    sentence = "W" + "h" * (MAX_SENTENCE_LENGTH - 2) + "?"

    assert written(PRICE_FACTS, said(sentence)).writer is Writer.MODEL
    assert written(PRICE_FACTS, said("W" + sentence)).writer is Writer.PROGRAM


# --- every question has the program's sentence and label --------------------


def every_follow_up() -> list[AskCell | ConfirmCoin | AskWhichCell]:
    draft = TradeDraft(side=Side.BUY, quantity=Decimal("1"), price=Decimal("2"))
    asked: list[AskCell | ConfirmCoin | AskWhichCell] = []
    for problem, _ in FOLLOW_UP_ORDER:
        problems = DraftProblems(
            missing=(problem,) if isinstance(problem, Missing) else (),
            violations=(problem,) if isinstance(problem, Violation) else (),
        )
        follow_up = next_follow_up(draft, problems)
        if not isinstance(follow_up, CannotRecord):
            asked.append(follow_up)
    return asked


@pytest.mark.parametrize("asked", every_follow_up(), ids=lambda asked: asked.because.name)
def test_every_question_has_one_plain_sentence_of_the_program_s_own(
    asked: AskCell | ConfirmCoin | AskWhichCell,
) -> None:
    sentence = template_sentence(asked, "PIKA")

    assert sentence.endswith("?")
    assert "\n" not in sentence
    assert sentence.count("?") == 1
    assert len(sentence) <= MAX_SENTENCE_LENGTH


@pytest.mark.parametrize(
    ("asked", "word", "label"),
    [
        (AskCell(Cell.FEE, Missing.FEE), None, "[Trade 1 of 1: fee]"),
        (
            ConfirmCoin(Cell.COIN, Missing.COIN_CONFIRMATION),
            "PIKA",
            "[Trade 1 of 1: is 'PIKA' a coin?]",
        ),
        (
            AskWhichCell((Cell.QUANTITY, Cell.PRICE, Cell.TOTAL), Violation.AMOUNTS_DISAGREE),
            None,
            "[Trade 1 of 1: quantity or price or total]",
        ),
    ],
)
def test_the_label_names_the_trade_and_what_is_asked(
    asked: AskCell | ConfirmCoin | AskWhichCell, word: str | None, label: str
) -> None:
    assert label_of(QuestionFacts(trade=1, trades=1, asked=asked, word=word)) == label
