"""The live check of picking an asset from the demo book's list: a real model. Run only by hand.

Marked ``live_model``, so ordinary runs leave it out. The step is off on
the assistant (``conversation.ASSISTANT_PICKS_ASSETS``); this check turns
it on, to see the model pick Microsoft for "微软" and nothing for "特斯拉",
each said once in a chat of its own to the whole assistant, with a new
fake ledger holding the demo book and the invented book's moment as now.
"""

from __future__ import annotations

import pytest

from ledger_hand.flows import conversation
from ledger_hand.flows.conversation import AssistantChat, Said, say
from ledger_hand.flows.recording import tuning_from
from ledger_hand.ledger.demo_book import demo_ledger
from ledger_hand.ledger.invented_book import INVENTED_NOW, INVENTED_ZONE
from ledger_hand.llm.local import connect_local_model
from ledger_hand.settings import load_assistant_steps, load_model_settings

pytestmark = pytest.mark.live_model


@pytest.fixture(autouse=True)
def _picking_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(conversation, "ASSISTANT_PICKS_ASSETS", True)


def said_once(words: str) -> Said:
    settings = load_model_settings()
    said = say(
        AssistantChat(),
        words,
        model=connect_local_model(settings),
        ledger=demo_ledger(),
        now=INVENTED_NOW,
        zone=INVENTED_ZONE,
        max_steps=load_assistant_steps(),
        tuning=tuning_from(settings),
    )
    print(f"\n{words}\n{said.reply}")
    return said


def test_a_chinese_name_on_the_list_is_picked() -> None:
    said = said_once("2026年11月20号14:30在IBKR买了2股微软的股票，100美元一股，手续费1美元")

    assert said.recorded is not None
    assert [found.code for found in said.recorded.progress.picks] == ["MSFT"]
    assert said.sent is not None
    assert [trade.asset for trade in said.recorded.trades] == ["MSFT"]


def test_a_name_the_list_lacks_is_not_picked_and_nothing_is_sent() -> None:
    said = said_once("2026年11月20号14:30在IBKR买了2股特斯拉，340美元一股，手续费1美元")

    assert said.recorded is not None
    assert all(found.code is None for found in said.recorded.progress.picks)
    assert said.sent is None
