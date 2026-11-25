"""Tests of the words that tell a question about cash, and a figure said beside a money."""

from __future__ import annotations

import pytest

from ledger_hand.core.cash_words import (
    BASE_MONEY_WORDS,
    CashAsk,
    cash_question,
    figure_beside_money,
    held_names,
    may_ask_what_is_left,
    money_words,
)
from ledger_hand.core.ledger_records import Asset, AssetKind, Pricing

EURO = Asset(id="e", code="EUR", name="Euro", kind=AssetKind.CASH, pricing=Pricing.CAN_PRICE)
COIN = Asset(
    id="u", code="UNI", name="Uniswap", kind=AssetKind.CRYPTO, pricing=Pricing.CANNOT_PRICE
)


@pytest.mark.parametrize(
    ("said", "kind"),
    [
        ("现金还有多少", CashAsk.CASH),
        ("USDT余额", CashAsk.CASH),
        ("my USDT balance please", CashAsk.CASH),
        ("what's my buying power", CashAsk.CASH),
        ("我有多少钱", CashAsk.LEFT),
        ("USDT还剩多少", CashAsk.LEFT),
        ("ＵＳＤＴ还剩多少", CashAsk.LEFT),
        ("how many dollars do I have", CashAsk.LEFT),
        ("do I have any USDT", CashAsk.LEFT),
        ("money left?", CashAsk.LEFT),
        ("上个月入金多少", CashAsk.DEPOSIT),
        ("充值了几次", CashAsk.DEPOSIT),
        ("deposits this year", CashAsk.DEPOSIT),
        ("I topped up last week, how much?", CashAsk.DEPOSIT),
        ("出了多少金", CashAsk.WITHDRAWAL),
        ("提现记录", CashAsk.WITHDRAWAL),
        ("how much did I withdraw", CashAsk.WITHDRAWAL),
    ],
)
def test_each_kind_of_question_about_cash_is_told(said: str, kind: CashAsk) -> None:
    assert cash_question(said) is kind


@pytest.mark.parametrize(
    "said",
    [
        "买入金额是多少",
        "卖出金额一共多少",
        "支出金额",
        "收入金额",
        "rebalance my coins",
        "a balanced portfolio",
        "我还有多少BTC",
        "我还有多少UNI",
        "how much UNI do I have left",
        "花了500U买ETH",
        "上个月花了多少USDT",
        "How much USDT did I spend on ETH?",
        "how much do I have left",
    ],
)
def test_what_is_not_a_question_about_cash_is_not_caught(said: str) -> None:
    assert cash_question(said, money_words((EURO, COIN))) is None


def test_a_cash_asset_of_the_ledger_is_a_word_for_a_money_and_a_coin_is_not() -> None:
    words = money_words((EURO, COIN))

    assert "EUR" in words and "Euro" in words
    assert "UNI" not in words
    assert set(BASE_MONEY_WORDS) <= set(words)
    assert cash_question("我还剩多少EUR", words) is CashAsk.LEFT
    assert cash_question("我还剩多少EUR") is None


def test_the_shape_of_what_is_still_had_holds_whatever_is_named() -> None:
    assert may_ask_what_is_left("我还有多少BTC")
    assert may_ask_what_is_left("How much ETH do I have left?")
    assert not may_ask_what_is_left("上个月花了多少USDT")


@pytest.mark.parametrize(
    ("text", "found"),
    [
        ("你还有 50 USDT", "50 usdt"),
        ("You have $50.", "$50"),
        ("大约5U", "5u"),
        ("一共1,250.5 美元", "1,250.5 美元"),
        ("五十美元", "五十美元"),
        ("USDT: 30", "usdt: 30"),
    ],
)
def test_a_figure_beside_a_money_is_found(text: str, found: str) -> None:
    assert figure_beside_money(text) == found


@pytest.mark.parametrize(
    "text",
    ["可以问我 10 月的交易", "用 USDT 记一笔", "You hold 2 UNI", "BTC 0.5", "我有 3 笔交易"],
)
def test_a_figure_beside_no_money_is_not_found(text: str) -> None:
    assert figure_beside_money(text, money_words((COIN,))) is None


NVIDIA = Asset(
    id="n", code="NVDA", name="英伟达", kind=AssetKind.STOCK, pricing=Pricing.CANNOT_PRICE
)
BITCOIN = Asset(
    id="b", code="BTC", name="Bitcoin", kind=AssetKind.CRYPTO, pricing=Pricing.CANNOT_PRICE
)
HELD = held_names((EURO, NVIDIA, BITCOIN))


@pytest.mark.parametrize(
    "said",
    [
        "我的 BTC 余额还有多少个",
        "英伟达的余额",
        "比特币余额是多少",
        "What's my BTC balance?",
        "my bitcoin's balance",
        "the balance of BTC please",
        "balance for NVDA",
    ],
)
def test_a_balance_attached_to_an_asset_that_is_not_cash_is_a_holding(said: str) -> None:
    assert cash_question(said, money_words((EURO, NVIDIA, BITCOIN)), HELD) is None


@pytest.mark.parametrize(
    "said",
    [
        "我的余额还够不够再买一手英伟达",
        "余额够买0.1个BTC吗",
        "Is my balance enough to buy 0.1 BTC?",
        "EUR 余额",
        "my balance",
    ],
)
def test_a_balance_attached_to_no_asset_held_is_cash(said: str) -> None:
    assert cash_question(said, money_words((EURO, NVIDIA, BITCOIN)), HELD) is CashAsk.CASH


def test_the_names_held_are_those_of_assets_that_are_not_cash_with_their_lent_names() -> None:
    assert "EUR" not in HELD and "Euro" not in HELD
    assert {"NVDA", "英伟达", "BTC", "Bitcoin", "比特币"} <= set(HELD)
