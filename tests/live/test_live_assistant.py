"""The live check of the assistant: a real model, the fake ledger. Run only by hand.

Marked ``live_model``, so ordinary runs leave it out. ``scripts/check.sh
live`` runs it with the settings read from the environment. It asks what is
held now and checks that the model's first step is to ask for the holdings,
and that the turn ends with the model's own answer. It prints every step,
so the run itself is the record.
"""

from __future__ import annotations

import io

import pytest

from ledger_hand.assistant.outcome import Chat, Ending, TakenCall
from ledger_hand.assistant.tools import ToolName
from ledger_hand.flows.assisting import take_turn
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ledger.invented_book import INVENTED_NOW, INVENTED_ZONE
from ledger_hand.llm.local import connect_local_model
from ledger_hand.settings import load_assistant_steps, load_model_settings
from scripts.try_assistant import show_turn

pytestmark = pytest.mark.live_model

SAID = "我现在手里有哪些币"


def test_asked_what_is_held_the_model_first_asks_for_the_holdings_and_then_answers() -> None:
    model = connect_local_model(load_model_settings())

    result = take_turn(
        Chat(),
        SAID,
        model=model,
        ledger=FakeLedger(),
        now=INVENTED_NOW,
        zone=INVENTED_ZONE,
        max_steps=load_assistant_steps(),
    )

    shown = io.StringIO()
    show_turn(SAID, result, shown)
    print("\n" + shown.getvalue())
    assert result.failure is None, f"the turn failed: {result.failure}"
    first = result.steps[0].calls
    assert [type(call) for call in first] == [TakenCall]
    assert isinstance(first[0], TakenCall)
    assert first[0].tool is ToolName.GET_POSITIONS
    assert result.ending is Ending.ANSWERED
