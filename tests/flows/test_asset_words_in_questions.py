"""Tests of the word a question calls the asset by, on the ledger's own table and the built-in one.

With the asset table the ledger's list makes, the program calls a share a
share, a coin a coin and an asset it has not recognised an asset, in the
label, the facts handed to the model and its own sentence; it never says
"币". A sentence of the model's that calls a share or an unknown asset a
coin is not used. With the built-in table every word stays as it was. A
scripted model stands in for every call; every sentence is invented.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from ledger_hand.asking.question_text import Fallback, QuestionFacts, write_question
from ledger_hand.asking.templates import template_sentence
from ledger_hand.core.asset_words import (
    LEDGER_CELL_NAMES,
    LEDGER_PROBLEM_WORDS,
    AssetWord,
    cell_name,
    problem_words,
    word_for,
)
from ledger_hand.core.assets import BUILT_IN_ASSETS
from ledger_hand.core.followup import AskCell, Cell
from ledger_hand.core.ledger_table import table_of
from ledger_hand.core.validation import Missing, Violation
from ledger_hand.flows.conversation import AssistantChat, Said, say
from ledger_hand.flows.questions import ADD_IN_LEDGER_FIRST
from ledger_hand.flows.recorded import RecordEnding
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ledger.invented_book import INVENTED_ASSETS, INVENTED_NOW, INVENTED_ZONE
from ledger_hand.ports import ToolCall, ToolReply
from tests.fakes.routed_model import RoutedModel
from tests.fakes.scripted_model import ScriptedModel, Step, scripted_record
from tests.flows.scripted_flow import row, screened, table, worded

RECORD = ToolReply(
    text="", calls=(ToolCall(name="propose_trade_add", arguments={}),), record=scripted_record()
)
LEDGER_TABLE = table_of(INVENTED_ASSETS)
assert LEDGER_TABLE is not None

SHARE_NO_FEE = "今天15:30在IBKR买了2股MSFT，410美元一股"
SHARE_NO_FEE_ROW = row(
    side="buy", coin="MSFT", quantity="2股", price="410美元", time="今天15:30", platform="IBKR"
)
COIN_NO_QUANTITY = "今天上午9:40在币安买了BTC，价格94900 USDT，手续费0 USDT"
COIN_NO_QUANTITY_ROW = row(
    side="buy",
    coin="BTC",
    price="94900 USDT",
    fee="0 USDT",
    time="今天上午9:40",
    platform="币安",
)
UNKNOWN = "今天15:30在IBKR买了2股宝洁，150美元一股，手续费1美元"
UNKNOWN_ROW = row(
    side="buy",
    coin="宝洁",
    quantity="2股",
    price="150美元",
    fee="1美元",
    time="今天15:30",
    platform="IBKR",
)


def talk(said: str, rows: Sequence[dict[str, str]], questions: Sequence[Step] = ()) -> Said:
    model = RoutedModel(
        tools=[RECORD],
        screen=[screened(("spot_trade", said.split("，")[0]))],
        extraction=[table(*rows)],
        questions=questions,
    )
    return say(
        AssistantChat(),
        said,
        model=model,
        ledger=FakeLedger(),
        now=INVENTED_NOW,
        zone=INVENTED_ZONE,
        max_steps=6,
        # The program's table of company names would match "宝洁" first; turned off here.
        name_table=False,
    )


def asked(said: Said) -> str:
    assert said.recorded is not None and said.recorded.ending is RecordEnding.ASKING
    return said.reply


# --- the word for each kind ---------------------------------------------------------


def test_the_ledgers_table_calls_a_stock_a_share_a_coin_a_coin_and_the_rest_an_asset() -> None:
    assert word_for(LEDGER_TABLE, "MSFT") is AssetWord.SHARE
    assert word_for(LEDGER_TABLE, "msft") is AssetWord.SHARE
    assert word_for(LEDGER_TABLE, "Microsoft") is AssetWord.SHARE
    assert word_for(LEDGER_TABLE, "BTC") is AssetWord.COIN
    assert word_for(LEDGER_TABLE, "比特币") is AssetWord.COIN
    assert word_for(LEDGER_TABLE, "微软") is AssetWord.ASSET
    assert word_for(LEDGER_TABLE, None) is AssetWord.ASSET


def test_the_built_in_table_has_no_word_of_its_own() -> None:
    assert word_for(BUILT_IN_ASSETS, "BTC") is None
    assert word_for(BUILT_IN_ASSETS, "MSFT") is None


def test_the_ledgers_table_knows_each_assets_kind_and_the_built_in_one_none() -> None:
    assert LEDGER_TABLE.kind_of("MSFT") == "stock"
    assert LEDGER_TABLE.kind_of("ADA") == "crypto"
    assert LEDGER_TABLE.kind_of("USD") is None
    assert BUILT_IN_ASSETS.kinds == ()


@pytest.mark.parametrize("problem", [*Missing, *Violation])
def test_every_reason_that_says_coin_has_the_ledgers_own_words(
    problem: Missing | Violation,
) -> None:
    said = problem_words(problem, ledger=True)

    assert "coin" not in said.casefold()
    assert "币" not in said
    assert problem_words(problem, ledger=False) == problem.value
    if "coin" not in problem.value.casefold():
        assert problem not in LEDGER_PROBLEM_WORDS


@pytest.mark.parametrize("cell", list(Cell))
def test_every_cell_name_that_says_coin_has_the_ledgers_own_name(cell: Cell) -> None:
    assert "coin" not in cell_name(cell, ledger=True)
    assert cell_name(cell, ledger=False) == cell.value
    assert ("coin" in cell.value) == (cell in LEDGER_CELL_NAMES)


@pytest.mark.parametrize("cell", list(Cell))
@pytest.mark.parametrize("word", [AssetWord.SHARE, AssetWord.ASSET])
def test_no_sentence_of_the_program_says_coin_of_a_share_or_an_unknown_asset(
    cell: Cell, word: AssetWord
) -> None:
    problems: list[Missing | Violation] = [*Missing, *Violation]
    for because in problems:
        sentence = template_sentence(AskCell(cell, because), None, "USD", word)

        assert "coin" not in sentence.casefold(), (cell, because, sentence)
        assert "币" not in sentence


def test_a_coin_is_still_asked_about_as_a_coin() -> None:
    sentence = template_sentence(AskCell(Cell.QUANTITY, Missing.TWO_OF_QUANTITY_PRICE_TOTAL), None)
    ledger_s = template_sentence(
        AskCell(Cell.QUANTITY, Missing.TWO_OF_QUANTITY_PRICE_TOTAL), None, "USDT", AssetWord.COIN
    )

    assert sentence == ledger_s == "How much of the coin was bought or sold?"


# --- what the user is asked, through the whole assistant -----------------------------


def test_a_share_whose_fee_is_missing_is_asked_about_without_coin() -> None:
    reply = asked(talk(SHARE_NO_FEE, [SHARE_NO_FEE_ROW]))

    assert reply.startswith("[Trade 1 of 1: fee] What was the fee for this trade?")
    assert "coin" not in reply.casefold()
    assert "币" not in reply


def test_a_coin_whose_quantity_is_missing_may_still_be_called_a_coin() -> None:
    reply = asked(talk(COIN_NO_QUANTITY, [COIN_NO_QUANTITY_ROW]))

    assert reply.startswith("[Trade 1 of 1: quantity] How much of the coin was bought or sold?")


def test_an_asset_not_recognised_is_asked_about_as_an_asset_with_the_ledger_named() -> None:
    reply = asked(talk(UNKNOWN, [UNKNOWN_ROW]))

    assert reply.startswith(
        "[Trade 1 of 1: asset] The ledger lists no asset by that name; which asset was it?"
    )
    assert ADD_IN_LEDGER_FIRST in reply
    assert "coin" not in reply.casefold()
    assert "币" not in reply


def test_the_facts_handed_to_the_model_name_the_asset_by_its_kind() -> None:
    model = ScriptedModel([worded("What was the fee for these shares?")])
    facts = QuestionFacts(
        trade=1,
        trades=1,
        asked=AskCell(Cell.FEE_COIN, Missing.FEE_COIN),
        known=(("asset", "MSFT"),),
        money="USD",
        asset=AssetWord.SHARE,
    )

    written = write_question(facts, model, LEDGER_TABLE.coins)

    given = model.calls[0].messages[1].content
    assert "Ask for: the fee asset" in given
    assert "Why: the asset or currency the fee was paid in" in given
    assert "The asset traded is called: a share" in given
    assert "coin" not in given.casefold()
    assert written.label == "[Trade 1 of 1: fee asset]"


@pytest.mark.parametrize(
    ("sentence", "word"),
    [
        ("How many coins did you buy?", AssetWord.SHARE),
        ("Which coin did you buy?", AssetWord.ASSET),
        ("Which 币 was the fee paid in?", AssetWord.COIN),
    ],
)
def test_a_models_sentence_with_the_wrong_word_gives_way_to_the_programs(
    sentence: str, word: AssetWord
) -> None:
    model = ScriptedModel([worded(sentence)])
    # The passage's own words hold "币", so only the word for the asset is wrong.
    facts = QuestionFacts(
        trade=1,
        trades=1,
        asked=AskCell(Cell.COIN, Missing.COIN),
        quoted="狗狗币",
        money="USD",
        asset=word,
    )

    written = write_question(facts, model, LEDGER_TABLE.coins)

    assert written.fallback is Fallback.WRONG_ASSET_WORD
    assert written.sentence == "Which asset was bought or sold in this trade?"


def test_a_models_sentence_may_call_a_coin_a_coin() -> None:
    model = ScriptedModel([worded("How much of the coin did you buy?")])
    facts = QuestionFacts(
        trade=1,
        trades=1,
        asked=AskCell(Cell.QUANTITY, Missing.TWO_OF_QUANTITY_PRICE_TOTAL),
        money="USDT",
        asset=AssetWord.COIN,
    )

    written = write_question(facts, model, LEDGER_TABLE.coins)

    assert written.fallback is None
    assert written.sentence == "How much of the coin did you buy?"


def test_with_the_built_in_table_a_models_coin_stands() -> None:
    model = ScriptedModel([worded("Which coin did you buy?")])
    facts = QuestionFacts(trade=1, trades=1, asked=AskCell(Cell.COIN, Missing.COIN))

    written = write_question(facts, model, BUILT_IN_ASSETS.coins)

    assert written.fallback is None
    assert written.label == "[Trade 1 of 1: coin]"
    assert "Why: the coin" in model.calls[0].messages[1].content


def test_a_share_with_a_question_of_the_models_that_says_coin_is_asked_in_the_programs_words() -> (
    None
):
    reply = asked(
        talk(SHARE_NO_FEE, [SHARE_NO_FEE_ROW], questions=[worded("What fee did this coin cost?")])
    )

    assert reply.startswith("[Trade 1 of 1: fee] What was the fee for this trade?")
