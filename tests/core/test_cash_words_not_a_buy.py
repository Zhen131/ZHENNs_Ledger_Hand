"""Tests that a buy said with "买入了 … 美金" is not taken for a question about money put in.

"买入了30美金的ETH" holds "入了", three characters and "金", the shape of
"入了多少金"; a buy said so must reach recording. Questions about money put
in are still caught. The sentences of questions are those of the cash
tests and of ``evals/sets/cash.json``, and two more the rule caught before.
"""

from __future__ import annotations

import pytest

from ledger_hand.core.cash_words import CashAsk, cash_question
from ledger_hand.flows.cash_question import caught
from ledger_hand.ledger.demo_book import demo_ledger


@pytest.mark.parametrize(
    "said",
    [
        "我在2026年10月9号下午16点21分买入了30美金的ETH",
        "今天买入了三十美金的ETH",
        "买入了100美金的BTC",
        "我在2026年10月9号下午16点21分买入了30美金的ETH，成交均价是在2580 USDT",
    ],
)
def test_a_buy_said_with_meijin_is_not_a_question_about_cash(said: str) -> None:
    assert cash_question(said) is None
    assert caught(said, demo_ledger()) is None


@pytest.mark.parametrize(
    "said",
    ["我一共入了多少金", "上个月入了多少金", "我入了30美金", "上个月入金多少", "充值了几次"],
)
def test_money_put_in_is_still_a_question_about_cash(said: str) -> None:
    assert cash_question(said) is CashAsk.DEPOSIT
