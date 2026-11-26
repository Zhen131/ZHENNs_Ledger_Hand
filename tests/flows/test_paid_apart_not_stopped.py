"""Sentences of euros paid for a share or a coin are never stopped before the model.

The readings that come before the model (money moved recorded by hand,
questions about cash) must let every one of them through, with no closing
line about money moved: "换汇费" and "FX fee" are a fee, never an exchange
of moneys. Five sentences said the owner's way (the exam's practice half)
and ten written for this test; each is said to the whole assistant against
the demo ledger with a euro, with a model that only answers in words.
"""

from __future__ import annotations

import pytest

from ledger_hand.flows.conversation import AssistantChat, Route, say
from ledger_hand.ledger.demo_euro import demo_ledger_with_euro
from ledger_hand.ledger.invented_book import INVENTED_NOW, INVENTED_ZONE
from ledger_hand.ports import ToolReply
from tests.fakes.routed_model import RoutedModel
from tests.fakes.scripted_model import scripted_record

WORDS = ToolReply(text="Noted.", calls=(), record=scripted_record())
SENTENCES = [
    "可口可乐我在2026年的10月6号的晚上20点02分还花了0.46欧买了0.0061629股。当时的股价是落在一股81.13美金。"
    "但是我花的是欧元啊，请注意。然后好像有一个 FX fee，这个好像是汇率转换的费用，是0.01欧元。",
    "可口可乐我在2026年的11月8号的上午9点31分还花了210.6欧买了3.1657591股。当时的股价是落在一股78.97美金。"
    "但是我花的是欧元啊，请注意。然后好像有一个 FX fee，这个好像是汇率转换的费用，是0.32欧元。",
    "苹果我在2026年的9月1号的晚上21点00分还花了223.67欧买了1.0822979股。当时的股价是落在一股230.99美金。"
    "但是我花的是欧元啊，请注意。然后好像有一个 FX fee，这个好像是汇率转换的费用，是0.34欧元。",
    "我在2026年9月3号下午14点55分花了231.61欧元买了1.1283116股苹果，当时股价是一股221.57美金，"
    "另外有一笔换汇费0.35欧元。",
    "我在2026年10月15号晚上21点14分花了128.53欧元买了2.0408163股可口可乐，当时股价是一股73.5美金，"
    "另外有一笔换汇费0.19欧元。",
    "今天15:30花了128欧元买了2股KO，一股69.5美元，换汇费0.19欧元",
    "今天15:30花了128欧元买了2股可口可乐，一股69.5美金，换汇费0.19欧元",
    "今天15:30花了128欧元买了2股KO，换汇费0.19欧元",
    "今天15:30花了100欧元买了3股KO，一股36.2美元，手续费0",
    "今天15:30卖了2股KO，收到130欧元，一股70美元，手续费0",
    "今天上午10点花了95欧元买了0.001个BTC，价格98000 USDT，手续费0",
    "今天15:30花了1000人民币买了1股KO，一股140美元，手续费0",
    "昨天晚上用欧元买了1股苹果，花了210欧，一股230美金，FX fee 0.3欧元",
    "Bought 2 KO shares today at 3:30pm for 128 EUR, 69.5 USD a share, FX fee 0.19 EUR",
    "Paid 95 euros for 0.001 BTC this morning at 98000 USDT, exchange fee 0.2 EUR",
]


@pytest.mark.parametrize("sentence", SENTENCES)
def test_a_sentence_of_euros_paid_goes_to_the_model_with_nothing_about_money_moved(
    sentence: str,
) -> None:
    said = say(
        AssistantChat(),
        sentence,
        model=RoutedModel(tools=[WORDS]),
        ledger=demo_ledger_with_euro().taking_cards(),
        now=INVENTED_NOW,
        zone=INVENTED_ZONE,
        max_steps=6,
    )

    assert said.route is Route.MODEL
    assert said.manual is None
    assert "record that part in the ledger yourself" not in said.reply
