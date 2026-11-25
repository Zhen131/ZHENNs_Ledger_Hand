"""Tests of picking, from the ledger's list, the asset a name the program does not know names.

A scripted model stands in for every call. What is checked: when the model
is asked at all, what it is handed, and each check the program makes of
its reply: a code of the list, words the user said, nothing left over but
filler words, the agreed shape. Every name and list here is invented or the
demo book's.
"""

from __future__ import annotations

import json

import pytest

from ledger_hand.core.assets import BUILT_IN_ASSETS
from ledger_hand.core.ledger_records import Asset, AssetKind, Pricing
from ledger_hand.core.ledger_table import table_of
from ledger_hand.extraction.asset_picking import (
    FILLER_WORDS,
    MOST_LISTED,
    PICK_TABLE,
    PickMiss,
    only_filler,
    pick_asset,
    picking_list,
    should_pick,
)
from ledger_hand.extraction.prompts.asset_pick import ASSET_PICK_PROMPT, ListedAsset
from ledger_hand.ledger.demo_book import DEMO_ASSETS
from ledger_hand.ledger.invented_book import INVENTED_ASSETS
from ledger_hand.ports import (
    FinishReason,
    ModelError,
    ModelErrorKind,
    ModelReply,
    ReplyRecord,
    Role,
)
from tests.fakes.scripted_model import ScriptedModel

DEMO = table_of(DEMO_ASSETS)
assert DEMO is not None


def reply(said: str, code: str) -> str:
    return json.dumps({"said": said, "code": code}, ensure_ascii=False)


def picked(word: str, *steps: str | ModelReply | ModelError) -> tuple[str | None, PickMiss | None]:
    found = pick_asset(word, DEMO, ScriptedModel(steps))
    return found.code, found.miss


# --- when the model is asked ------------------------------------------------------


@pytest.mark.parametrize("word", ["微软", "微软的股票", "COCA COLA", "APPLE STOCK", "以太坊经典"])
def test_a_name_the_table_does_not_find_and_cannot_be_a_code_is_handed_over(word: str) -> None:
    assert should_pick(word, DEMO)


@pytest.mark.parametrize(
    "word",
    [
        "TSLA",  # can be a code: told plainly that the ledger lacks it
        "狗狗币",  # a coin the built-in table knows and the ledger lacks
        "USDT",  # money
        "美元",  # money
        "Microsoft",  # the ledger's own name
        "MSFT",  # the ledger's own code
        "波卡",  # a name the built-in table lends DOT
        "",
        "  ",
    ],
)
def test_a_name_found_money_shielded_or_writable_as_a_code_is_not_handed_over(word: str) -> None:
    assert not should_pick(word, DEMO)


def test_with_the_built_in_table_nothing_is_handed_over() -> None:
    assert not should_pick("微软", BUILT_IN_ASSETS)
    assert not should_pick(None, DEMO)


def test_the_list_holds_the_assets_traded_with_their_names_and_kinds_and_no_money() -> None:
    listing = picking_list(DEMO)

    assert ListedAsset("MSFT", "Microsoft", "stock") in listing
    assert ListedAsset("SOL", "Solana", "crypto") in listing
    assert ListedAsset("PEP", "PepsiCo", "stock") in listing
    assert {asset.code for asset in listing} & {"USD", "USDT"} == set()
    assert len(listing) == 11


def test_the_model_is_handed_the_words_and_the_list_at_temperature_given_and_nothing_else() -> None:
    model = ScriptedModel([reply("微软", "MSFT")])

    found = pick_asset("微软的股票", DEMO, model)

    assert found.code == "MSFT" and found.picked
    (call,) = model.calls
    assert call.reply_schema is PICK_TABLE
    last = call.messages[-1]
    assert last.role is Role.USER
    assert last.content.startswith("Words: 微软的股票\nList:\n")
    assert "MSFT | Microsoft | stock" in last.content
    assert "USD" not in last.content.split("\n")
    assert call.messages[0].content == ASSET_PICK_PROMPT.instructions
    assert found.prompt == "asset-pick-1"


def test_a_list_too_long_is_not_handed_over() -> None:
    many = [
        Asset(
            id="usd", code="USD", name="US dollar", kind=AssetKind.CASH, pricing=Pricing.CAN_PRICE
        )
    ]
    many += [
        Asset(
            id=f"a{number}",
            code=f"A{number}",
            name=f"Company {number}",
            kind=AssetKind.STOCK,
            pricing=Pricing.CANNOT_PRICE,
        )
        for number in range(MOST_LISTED + 1)
    ]
    table = table_of(many)
    assert table is not None
    model = ScriptedModel([])

    found = pick_asset("微软", table, model)

    assert (found.code, found.miss) == (None, PickMiss.LIST_TOO_LONG)
    assert model.calls == []


# --- the checks of the reply --------------------------------------------------------


def test_a_name_taken_whole() -> None:
    assert picked("微软", reply("微软", "MSFT")) == ("MSFT", None)


def test_a_code_written_in_small_letters_is_taken_in_capitals() -> None:
    assert picked("微软", reply("微软", "msft")) == ("MSFT", None)


def test_an_english_name_in_the_cells_own_writing_is_taken() -> None:
    assert picked("COCA COLA", reply("Coca Cola", "KO")) == ("KO", None)


def test_the_list_does_not_hold_it() -> None:
    assert picked("特斯拉", reply("特斯拉", "")) == (None, PickMiss.NONE_ON_LIST)


@pytest.mark.parametrize("code", ["TSLA", "USD", "USDT"])
def test_a_code_not_of_the_list_money_among_them_is_not_taken(code: str) -> None:
    assert picked("微软", reply("微软", code)) == (None, PickMiss.CODE_NOT_ON_LIST)


@pytest.mark.parametrize("said", ["苹果", "", "微软公司"])
def test_words_not_in_the_cell_are_not_taken(said: str) -> None:
    assert picked("微软", reply(said, "MSFT")) == (None, PickMiss.SAID_NOT_IN_WORDS)


@pytest.mark.parametrize(
    ("word", "said", "code"),
    [
        ("以太坊经典", "以太坊", "ETH"),
        ("比特币ETF", "比特币", "BTC"),
        ("微博", "微", "MSFT"),
        ("微软和英特尔", "微软", "MSFT"),
        ("苹果期货", "苹果", "AAPL"),
        ("可口可乐装瓶公司", "可口可乐", "KO"),
        ("微软的期权", "微软", "MSFT"),
    ],
)
def test_words_left_over_that_are_not_filler_are_not_taken(word: str, said: str, code: str) -> None:
    assert picked(word, reply(said, code)) == (None, PickMiss.WORDS_LEFT_OVER)


@pytest.mark.parametrize(
    "text",
    [
        "not json",
        json.dumps({"said": "微软"}),
        json.dumps({"said": "微软", "code": "MSFT", "why": "x"}),
        json.dumps({"said": 1, "code": "MSFT"}),
        json.dumps(["微软", "MSFT"]),
    ],
)
def test_a_reply_not_of_the_agreed_shape_is_not_taken(text: str) -> None:
    assert picked("微软", text) == (None, PickMiss.REPLY_UNREADABLE)


def test_a_reply_cut_off_is_not_taken() -> None:
    record = ReplyRecord(
        model="scripted",
        elapsed_seconds=0.0,
        prompt_tokens=None,
        reply_tokens=None,
        finish=FinishReason.LENGTH_LIMIT,
    )
    cut = ModelReply(text=reply("微软", "MSFT"), record=record)

    assert picked("微软", cut) == (None, PickMiss.REPLY_UNREADABLE)


@pytest.mark.parametrize("kind", list(ModelErrorKind))
def test_a_model_that_fails_is_a_miss(kind: ModelErrorKind) -> None:
    found = pick_asset("微软", DEMO, ScriptedModel([ModelError(kind, "failed")]))

    assert (found.code, found.miss, found.calls) == (None, PickMiss.MODEL_FAILED, ())


# --- the filler words -----------------------------------------------------------------


@pytest.mark.parametrize(("word", "why"), FILLER_WORDS)
def test_each_filler_word_alone_twice_and_beside_another_is_filler(word: str, why: str) -> None:
    assert why
    assert only_filler(word)
    assert only_filler(word + word)
    assert only_filler(f"{word} 的")


@pytest.mark.parametrize(("word", "_why"), FILLER_WORDS)
def test_each_filler_word_left_round_a_name_still_takes_it(word: str, _why: str) -> None:
    assert picked(f"英特尔{word}", reply("英特尔", "INTC")) == ("INTC", None)


@pytest.mark.parametrize("rest", ["", " ", "的股票", "公司", "这只", " SHARES"])
def test_nothing_left_or_only_filler_is_filler(rest: str) -> None:
    assert only_filler(rest)


@pytest.mark.parametrize(
    "rest", ["经典", "ETF", "博", "和英特尔", "期权", "期货", "装瓶公司", "A股"]
)
def test_anything_else_left_is_not_filler(rest: str) -> None:
    assert not only_filler(rest)


def test_the_invented_book_lists_four_assets_to_pick_from() -> None:
    table = table_of(INVENTED_ASSETS)
    assert table is not None

    assert [asset.code for asset in picking_list(table)] == ["BTC", "ETH", "ADA", "MSFT"]
