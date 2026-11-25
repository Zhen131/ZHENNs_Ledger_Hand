"""The live check of the whole assistant: a real model, the fake ledger. Run only by hand.

Marked ``live_model``, so ordinary runs leave it out. Two of the shortest
things a person says, each in a chat of its own, through ``say``:

- a trade told in full: a proposal reaches the fake ledger, and waits there;
- a question about one day's trades: a table comes back, its header the day.

Only what the program did is checked (what was sent, what the table was
looked up with), never the model's wording. Each prints what happened, so
the run itself is the record.
"""

from __future__ import annotations

import io

import pytest

from ledger_hand.assistant.lookups import lookup_lines
from ledger_hand.core.proposals import ProposalStatus
from ledger_hand.flows.conversation import AssistantChat, Said, say
from ledger_hand.flows.recording import tuning_from
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ledger.invented_book import INVENTED_NOW, INVENTED_ZONE
from ledger_hand.llm.local import connect_local_model
from ledger_hand.settings import load_assistant_steps, load_model_settings
from scripts.try_assistant import show_said
from tests.fakes.usdt_only import usdt_only_ledger

pytestmark = pytest.mark.live_model

TOLD = "Bought 0.02 BTC at 94900 on Binance at 9:40 this morning, fee 2 USDT."
ASKED = "10月6号那天我都做了什么交易"


def said_once(words: str, ledger: FakeLedger) -> Said:
    settings = load_model_settings()
    said = say(
        AssistantChat(),
        words,
        model=connect_local_model(settings),
        ledger=ledger,
        now=INVENTED_NOW,
        zone=INVENTED_ZONE,
        max_steps=load_assistant_steps(),
        tuning=tuning_from(settings),
    )
    shown = io.StringIO()
    show_said(words, said, shown)
    print("\n" + shown.getvalue())
    return said


def test_a_trade_told_in_full_reaches_the_ledger_as_one_proposal_waiting() -> None:
    ledger = usdt_only_ledger()

    said = said_once(TOLD, ledger)

    assert said.sent is not None, f"nothing was sent: {said.reply}"
    assert said.sent.trades == 1
    assert ledger.proposal_status(said.sent.proposal).status is ProposalStatus.PENDING


def test_a_question_about_one_day_comes_back_as_a_table_of_that_day() -> None:
    said = said_once(ASKED, FakeLedger())

    assert said.turn is not None and said.turn.lookups, f"no table: {said.reply}"
    lookup = said.turn.lookups[-1]
    assert lookup_lines(lookup)[0] == "Time: 2026-10-06"
    assert [trade.id for trade in lookup.trades] == ["t-05", "t-06"]
