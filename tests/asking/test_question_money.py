"""Tests of asking a price or a total in the money the trade is priced in.

With the asset table the ledger's list makes, a trade may be priced in USD
as well as USDT: the program's sentence names the money of the trade, the
model is told it, and a sentence of the model's that names other money is
not used. Without a money handed in, every sentence is the built-in one.
Every fact and reply is invented.
"""

from __future__ import annotations

import json

from ledger_hand.asking.question_text import (
    Fallback,
    QuestionFacts,
    Writer,
    facts_text,
    write_question,
)
from ledger_hand.asking.templates import template_sentence
from ledger_hand.core.coins import BUILT_IN_TABLE
from ledger_hand.core.followup import AskCell, Cell
from ledger_hand.core.validation import Missing
from tests.fakes.scripted_model import ScriptedModel

PRICE = AskCell(Cell.PRICE, Missing.ONE_MORE_OF_QUANTITY_PRICE_TOTAL)
TOTAL = AskCell(Cell.TOTAL, Missing.ONE_MORE_OF_QUANTITY_PRICE_TOTAL)
MONEY_WORDS = frozenset({"USDT", "U", "USD", "DOLLAR", "DOLLARS"})


def facts(money: str | None) -> QuestionFacts:
    return QuestionFacts(trade=1, trades=1, asked=PRICE, known=(("coin", "MSFT"),), money=money)


def said(question: str) -> str:
    return json.dumps({"question": question})


def test_the_program_names_the_money_the_trade_is_priced_in() -> None:
    assert template_sentence(PRICE, None, "USD") == "What was the price of one unit, in USD?"
    assert template_sentence(TOTAL, None, "USD") == (
        "What was the total paid or received, in USD, without the fee?"
    )


def test_with_the_money_not_known_no_money_is_named() -> None:
    assert template_sentence(PRICE, None, "") == "What was the price of one unit?"


def test_without_a_money_the_built_in_sentence_stands() -> None:
    assert template_sentence(PRICE, None) == "What was the price of one coin, in USDT?"
    assert facts_text(facts(None)) == facts_text(
        QuestionFacts(trade=1, trades=1, asked=PRICE, known=(("coin", "MSFT"),))
    )


def test_the_model_is_told_the_money() -> None:
    assert "Priced in: USD" in facts_text(facts("USD")).splitlines()


def test_a_model_sentence_naming_other_money_gives_way_to_the_program_s() -> None:
    model = ScriptedModel([said("What was the price of one MSFT share, in USDT?")])

    result = write_question(facts("USD"), model, BUILT_IN_TABLE, money_words=MONEY_WORDS)

    assert result.writer is Writer.PROGRAM
    assert result.fallback is Fallback.ADDS_FACTS
    assert result.sentence == "What was the price of one unit, in USD?"


def test_a_model_sentence_naming_the_trade_s_money_is_used() -> None:
    model = ScriptedModel([said("What was the price of one MSFT share, in USD?")])

    result = write_question(facts("USD"), model, BUILT_IN_TABLE, money_words=MONEY_WORDS)

    assert result.writer is Writer.MODEL
    assert result.sentence == "What was the price of one MSFT share, in USD?"


def test_without_money_words_a_sentence_naming_usdt_is_judged_as_before() -> None:
    model = ScriptedModel([said("What was the price of one MSFT share, in USDT?")])

    result = write_question(facts(None), model, BUILT_IN_TABLE)

    assert result.writer is Writer.MODEL
