"""The live check of a Chinese name matched by the program's table: a real model. Run only by hand.

Marked ``live_model``, so ordinary runs leave it out. "微软的股票" is said
once, in a chat of its own, to the whole assistant, with a new fake
ledger holding the demo book and the invented book's moment as now; the
table is on, as it is by default, and no file of answers is handed in.
MSFT is sent, its asset cell marked as assumed, the reason saying it was
taken from the program's table.
"""

from __future__ import annotations

import pytest

from ledger_hand.core.marks import Field, MarkKind
from ledger_hand.flows.conversation import AssistantChat, say
from ledger_hand.flows.recording import tuning_from
from ledger_hand.ledger.demo_book import demo_ledger
from ledger_hand.ledger.invented_book import INVENTED_NOW, INVENTED_ZONE
from ledger_hand.llm.local import connect_local_model
from ledger_hand.settings import load_assistant_steps, load_model_settings

pytestmark = pytest.mark.live_model


def test_a_name_of_the_table_is_sent_as_its_code_marked_as_taken_from_the_table() -> None:
    settings = load_model_settings()
    words = "2026年11月20号14:30在IBKR买了2股微软的股票，100美元一股，手续费1美元"

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

    assert said.recorded is not None and said.sent is not None
    assert [trade.asset for trade in said.recorded.trades] == ["MSFT"]
    (marked,) = said.recorded.marked
    (mark,) = [one for one in marked.marks.marks if one.field is Field.ASSET_ID]
    assert mark.kind is MarkKind.INFERRED
    assert mark.reason is not None and "table of common company names" in mark.reason
