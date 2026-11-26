"""Tests of the words that tell money the assistant does not record, and a balance of any money.

``statement`` reads a deposit, a withdrawal, an exchange of moneys or a
dividend said, never asked; ``left_asked`` reads how much of any money of
the tables is still had; ``named_money`` which one money was named. No
ledger and no model. Every sentence is invented.
"""

from __future__ import annotations

import pytest

from ledger_hand.core.ledger_table import names_of
from ledger_hand.core.money_asks import (
    Manual,
    Statement,
    asks_or_requests,
    left_asked,
    may_be_exchange,
    money_named,
    named_money,
    statement,
)

BUILT_IN = tuple(name for name, _ in names_of(()).built_in)
HELD = (*BUILT_IN, "KO", "Coca-Cola", "可口可乐")


@pytest.mark.parametrize(
    ("said", "kinds"),
    [
        ("我今天入金了500 USDT", (Manual.DEPOSIT,)),
        ("我入了500美金", (Manual.DEPOSIT,)),
        ("今天转入了300U", (Manual.DEPOSIT,)),
        ("在币安充值了1000 USDT", (Manual.DEPOSIT,)),
        ("I deposited 500 USDT today", (Manual.DEPOSIT,)),
        ("Topped up 200 USD this morning", (Manual.DEPOSIT,)),
        ("昨天从币安提现了200U", (Manual.WITHDRAWAL,)),
        ("今天出金了800 USDT", (Manual.WITHDRAWAL,)),
        ("Withdrew 300 USD to my bank today", (Manual.WITHDRAWAL,)),
        ("今天把100欧元换成了108美元", (Manual.EXCHANGE,)),
        ("Converted 100 EUR to USD today", (Manual.EXCHANGE,)),
        ("用1000人民币兑换了140美元", (Manual.EXCHANGE,)),
        ("可口可乐今天分红了2.1美元", (Manual.DIVIDEND,)),
        ("Got a 2.1 USD dividend from KO today", (Manual.DIVIDEND,)),
        ("苹果派息0.25美元", (Manual.DIVIDEND,)),
    ],
)
def test_a_statement_of_money_moved_is_read_with_its_kind(
    said: str, kinds: tuple[Manual, ...]
) -> None:
    assert statement(said, HELD) == Statement(kinds=kinds, with_trade=False)


@pytest.mark.parametrize(
    "said",
    [
        "入金500U，然后今天上午10点买了0.01个BTC，价格98000 USDT，手续费0",
        "Deposited 500 USDT and bought 0.01 BTC at 98000 USDT, fee 0",
        "提现200U之前卖了0.5个ETH，价格3000 USDT",
    ],
)
def test_a_statement_beside_a_buy_or_a_sell_says_a_trade_was_spoken_of(said: str) -> None:
    found = statement(said, HELD)

    assert found is not None and found.with_trade


@pytest.mark.parametrize(
    "said",
    [
        # Questions and requests go to the question about cash, as before.
        "我一共入了多少金",
        "How much USD did I deposit?",
        "查一下我的入金",
        "看看我的提现记录",
        "我今天入金了500 USDT，现在还有多少？",
        "可口可乐分红了多少",
        # A buy's amount, an income, a buy of 30 dollars' worth.
        "今天买入金额500U的BTC",
        "收入金额是多少不重要，今天买了BTC",
        "买入了30美金的ETH",
        "卖出了200美金的ETH",
        # An exchange fee is a fee of a trade.
        "今天15:30花了128欧元买了2股KO，一股69.5美元，换汇费0.19欧元",
        "花了0.46欧买了KO，然后有一个 FX fee，这个好像是汇率转换的费用，是0.01欧元",
        # A coin or a share named: a buy, not an exchange.
        "今天用100 USDT换了0.001个BTC",
        "把100美元换成了可口可乐的股票",
        # Nothing of the kinds.
        "今天上午10点买了0.01个BTC，价格98000 USDT，手续费0",
        "欧易还有多少币",
    ],
)
def test_no_statement_is_read_where_there_is_none(said: str) -> None:
    assert statement(said, HELD) is None


def test_asking_and_requesting_have_their_own_shapes() -> None:
    assert asks_or_requests("我还有多少USDT")
    assert asks_or_requests("Show me my deposits")
    assert not asks_or_requests("我今天入金了500 USDT")


def test_an_exchange_needs_its_verb_and_two_moneys_before_the_ledger_is_asked() -> None:
    assert may_be_exchange("今天把100欧元换成了108美元")
    assert not may_be_exchange("今天用100 USDT换了0.001个BTC")
    assert not may_be_exchange("换汇费0.19欧元，花了128欧元买了2股KO，一股69.5美元")


@pytest.mark.parametrize(
    ("said", "code"),
    [
        ("我还有多少欧元", "EUR"),
        ("我还剩多少EUR", "EUR"),
        ("我还有多少福林", "HUF"),
        ("我还有多少人民币", "CNY"),
        ("我还有多少欧", "EUR"),
        ("欧还剩多少", "EUR"),
        ("How much euro do I have left?", "EUR"),
        ("我还有多少美金", None),
        ("我还有多少刀", None),
        ("我还有多少$", None),
    ],
)
def test_how_much_of_any_money_is_still_had_is_read_with_the_money_named(
    said: str, code: str | None
) -> None:
    assert left_asked(said)
    assert named_money(said) == code


@pytest.mark.parametrize(
    "said",
    ["欧易还有多少币", "我还有多少BTC", "我现在持有哪些币", "欧洲的股票还有多少"],
)
def test_no_balance_is_read_where_no_money_is_named(said: str) -> None:
    assert not left_asked(said)


def test_the_moneys_named_are_read_in_order_a_vague_word_as_vague() -> None:
    assert money_named("把100欧元换成了108美元") == ("EUR", "USD")
    assert money_named("100U换成美金") == ("USDT", "vague")
    assert money_named("花了0.46欧") == ("EUR",)
    assert money_named("欧易") == ()
    assert money_named("100 GBP", extra=(("GBP", "GBP"),)) == ("GBP",)
