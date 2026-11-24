"""Tests of a period cut out of a longer time, given to a read tool: a wrong step, nothing asked."""

from __future__ import annotations

import json

from ledger_hand.assistant.outcome import Chat, Ending, RefusedCall, TakenCall, TurnResult
from ledger_hand.flows.assisting import take_turn
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ledger.invented_book import INVENTED_NOW, INVENTED_ZONE
from ledger_hand.ports import ToolCall, ToolReply
from tests.fakes.scripted_model import ScriptedModel, Step, scripted_record


def asks(**arguments: object) -> ToolReply:
    return ToolReply(
        text="",
        calls=(ToolCall(name="list_trades", arguments=arguments),),
        record=scripted_record(),
    )


def turn(said: str, steps: list[Step], ledger: FakeLedger) -> TurnResult:
    return take_turn(
        Chat(),
        said,
        model=ScriptedModel(steps),
        ledger=ledger,
        now=INVENTED_NOW,
        zone=INVENTED_ZONE,
        max_steps=6,
    )


def test_a_month_cut_out_of_the_day_asked_is_a_wrong_step_and_the_ledger_is_not_asked() -> None:
    ledger = FakeLedger()
    result = turn("10月6号那天我都做了什么交易", [asks(period="10月"), "Sorry."], ledger)

    (refused,) = result.steps[0].calls
    assert isinstance(refused, RefusedCall)
    assert json.loads(refused.result)["user_said"] == "10月6号那天我都做了什么交易"
    assert ledger.calls == []
    assert result.ending is Ending.ANSWERED


def test_a_month_said_with_its_word_for_month_is_asked() -> None:
    ledger = FakeLedger()
    result = turn("10月份我卖了什么", [asks(period="10月"), "Two sells."], ledger)

    (taken,) = result.steps[0].calls
    assert isinstance(taken, TakenCall)
    assert ledger.calls == ["list_trades"]
