"""Tests of one turn of the assistant, with a scripted model and the fake ledger.

The model is asked until it answers in words; each call is judged before
the ledger is asked; a wrong step is shown to the model, and two in a row
stop the turn; a step with no wrong call starts the count again; six asks at
most; a model or ledger failure stops the turn; the chat handed back holds
every call and result, so the next turn can use what was listed. Every
reply and every trade is invented.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from ledger_hand.assistant.judging import MisstepKind
from ledger_hand.assistant.outcome import (
    STEP_LIMIT_REPLY,
    TWO_MISSTEPS_REPLY,
    Chat,
    Ending,
    RefusedCall,
    TakenCall,
    TurnResult,
)
from ledger_hand.assistant.results import trades_text
from ledger_hand.assistant.tools import ToolName
from ledger_hand.core.ledger_records import TradeFilter
from ledger_hand.flows.assisting import take_turn
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ledger.invented_book import INVENTED_NOW, INVENTED_ZONE
from ledger_hand.ports import (
    LedgerError,
    LedgerErrorKind,
    LedgerPort,
    Message,
    ModelError,
    ModelErrorKind,
    Role,
    ToolCall,
    ToolCallTurn,
    ToolReply,
    ToolResult,
)
from tests.fakes.scripted_model import ScriptedModel, Step, scripted_record

HOLDINGS = "我现在手里有哪些币"


def calls(*pairs: tuple[str, dict[str, object]], text: str = "") -> ToolReply:
    return ToolReply(
        text=text,
        calls=tuple(ToolCall(name=name, arguments=arguments) for name, arguments in pairs),
        record=scripted_record(),
    )


def turn(
    steps: list[Step],
    said: str = HOLDINGS,
    *,
    chat: Chat | None = None,
    ledger: LedgerPort | None = None,
    max_steps: int = 6,
) -> tuple[TurnResult, ScriptedModel]:
    model = ScriptedModel(steps)
    result = take_turn(
        chat or Chat(),
        said,
        model=model,
        ledger=ledger or FakeLedger(),
        now=INVENTED_NOW,
        zone=INVENTED_ZONE,
        max_steps=max_steps,
    )
    return result, model


def test_a_read_tool_is_run_and_its_result_handed_to_the_model_which_answers() -> None:
    ledger = FakeLedger()

    result, model = turn(
        [calls(("get_positions", {})), "You hold BTC, ETH, ADA and MSFT."], ledger=ledger
    )

    assert result.ending is Ending.ANSWERED
    assert result.reply == "You hold BTC, ETH, ADA and MSFT."
    assert ledger.calls == ["positions"]
    (first, second) = result.steps
    (taken,) = first.calls
    assert isinstance(taken, TakenCall)
    assert taken.tool is ToolName.GET_POSITIONS
    assert [entry["asset"] for entry in json.loads(taken.result)["positions"]] == [
        "ADA",
        "BTC",
        "ETH",
        "MSFT",
    ]
    sent = model.calls[1].items
    assert sent[0] == Message(Role.SYSTEM, sent[0].content)  # type: ignore[union-attr]
    assert "2026-11-24 (Tuesday) 23:55" in sent[0].content  # type: ignore[union-attr]
    assert sent[-1] == ToolResult(name="get_positions", content=taken.result)
    assert len(model.calls[0].tools) == 8


def test_an_unknown_tool_then_a_call_off_its_schema_stop_the_turn_after_two_steps() -> None:
    ledger = FakeLedger()

    result, model = turn(
        [calls(("place_order", {})), calls(("list_trades", {"side": "bought"}))], ledger=ledger
    )

    assert result.ending is Ending.TWO_MISSTEPS
    assert result.reply == TWO_MISSTEPS_REPLY
    assert len(model.calls) == 2
    assert ledger.calls == []
    kinds = []
    for step in result.steps:
        (refused,) = step.calls
        assert isinstance(refused, RefusedCall)
        assert refused.misstep.detail
        assert json.loads(refused.result)["problem"] == refused.misstep.detail
        kinds.append(refused.misstep.kind)
    assert kinds == [MisstepKind.UNKNOWN_TOOL, MisstepKind.NOT_A_CHOICE]


@pytest.mark.parametrize(
    "wrong",
    [
        ("place_order", {}),
        ("get_positions", {"asset": "BTC"}),
        ("propose_trade_update", {"field": "fee"}),
        ("list_trades", {"period": "2023-10-06"}),
    ],
    ids=["unknown tool", "unknown argument", "required argument missing", "not copied"],
)
def test_each_kind_of_wrong_step_is_shown_to_the_model_and_asks_nothing_of_the_ledger(
    wrong: tuple[str, dict[str, object]],
) -> None:
    ledger = FakeLedger()

    result, model = turn([calls(wrong), "Sorry."], "10月6号那天我都做了什么交易", ledger=ledger)

    assert result.ending is Ending.ANSWERED
    assert ledger.calls == []
    (refused,) = result.steps[0].calls
    assert isinstance(refused, RefusedCall)
    assert model.calls[1].items[-1] == ToolResult(name=wrong[0], content=refused.result)


def test_a_date_the_model_wrote_itself_is_judged_not_copied() -> None:
    result, _ = turn(
        [calls(("list_trades", {"period": "2023-10-06"})), "Sorry."],
        "10月6号那天我都做了什么交易",
    )

    (refused,) = result.steps[0].calls
    assert isinstance(refused, RefusedCall)
    assert refused.misstep.kind is MisstepKind.NOT_COPIED
    assert "not copied from what the user said" in refused.misstep.detail


def test_a_right_step_between_two_wrong_ones_starts_the_count_again() -> None:
    result, model = turn(
        [
            calls(("place_order", {})),
            calls(("list_assets", {})),
            calls(("place_order", {})),
            "Done.",
        ]
    )

    assert result.ending is Ending.ANSWERED
    assert len(model.calls) == 4
    assert [step.wrong for step in result.steps] == [True, False, True, False]


def test_six_right_steps_and_no_answer_stop_at_the_step_limit() -> None:
    result, model = turn([calls(("list_assets", {}))] * 7)

    assert result.ending is Ending.STEP_LIMIT
    assert result.reply == STEP_LIMIT_REPLY
    assert len(model.calls) == 6
    assert model.steps_left == 1


def test_several_calls_in_one_step_are_run_in_order_and_count_as_one_ask() -> None:
    ledger = FakeLedger()

    result, model = turn(
        [calls(("list_assets", {}), ("place_order", {}), ("get_positions", {})), "Done."],
        ledger=ledger,
    )

    assert ledger.calls == ["list_assets", "positions"]
    assert [type(call).__name__ for call in result.steps[0].calls] == [
        "TakenCall",
        "RefusedCall",
        "TakenCall",
    ]
    assert result.steps[0].wrong
    assert len(model.calls) == 2
    assert [item.name for item in model.calls[1].items if isinstance(item, ToolResult)] == [
        "list_assets",
        "place_order",
        "get_positions",
    ]


def test_tools_not_built_yet_answer_not_connected() -> None:
    ledger = FakeLedger()

    result, _ = turn(
        [calls(("propose_trade_add", {}), ("list_trades", {"period": "10月6号"})), "Not yet."],
        "10月6号那天我都做了什么交易",
        ledger=ledger,
    )

    assert ledger.calls == []
    for taken in result.steps[0].calls:
        assert isinstance(taken, TakenCall)
        assert json.loads(taken.result)["status"] == "not_connected"


def test_the_status_of_a_proposal_when_the_chat_has_none_and_when_it_has_one() -> None:
    ledger = FakeLedger()
    none_yet, _ = turn([calls(("get_proposal_status", {})), "None."], ledger=ledger)
    proposal = ledger.propose_delete("t-03").proposal_id
    assert proposal is not None

    with_one, _ = turn(
        [calls(("get_proposal_status", {})), "Pending."],
        chat=Chat(proposals=(proposal,)),
        ledger=ledger,
    )

    (no_proposal,) = none_yet.steps[0].calls
    (status,) = with_one.steps[0].calls
    assert json.loads(no_proposal.result)["status"] == "no_proposal"
    assert json.loads(status.result) == {"proposal": proposal, "status": "pending"}


def test_a_model_failure_stops_the_turn() -> None:
    failure = ModelError(ModelErrorKind.UNREACHABLE, "not running")

    result, _ = turn([failure])

    assert result.ending is Ending.MODEL_FAILED
    assert result.failure is failure
    assert result.reply == ""


def test_a_ledger_that_cannot_be_reached_stops_the_turn() -> None:
    failure = LedgerError(LedgerErrorKind.UNREACHABLE, "offline", "The ledger is not open.")

    result, model = turn([calls(("get_positions", {}))], ledger=FakeLedger(failure=failure))

    assert result.ending is Ending.LEDGER_FAILED
    assert result.failure is failure
    assert len(model.calls) == 1


def test_a_ledger_that_does_not_know_a_proposal_is_told_to_the_model() -> None:
    result, _ = turn(
        [calls(("get_proposal_status", {})), "No such proposal."],
        chat=Chat(proposals=("proposal-9",)),
    )

    (taken,) = result.steps[0].calls
    assert json.loads(taken.result)["code"] == "proposal_not_found"
    assert result.ending is Ending.ANSWERED


def test_the_next_turn_is_handed_the_calls_and_the_trades_listed_before() -> None:
    start = datetime(2026, 10, 6, tzinfo=ZoneInfo(INVENTED_ZONE))
    two = FakeLedger().list_trades(TradeFilter(start=start, end=start + timedelta(days=1)))
    listed = trades_text(two)
    assert [trade.id for trade in two] == ["t-05", "t-06"]
    first = Chat(
        items=(
            Message(Role.USER, "10月6号那天我都做了什么交易"),
            ToolCallTurn(text="", calls=(ToolCall(name="list_trades", arguments={}),)),
            ToolResult(name="list_trades", content=listed),
            Message(Role.ASSISTANT, "Two trades: t-05 and t-06."),
        )
    )

    result, model = turn(
        [
            calls(
                (
                    "propose_trade_update",
                    {"trade": "第二笔", "field": "fee", "new_value": "0.000002"},
                )
            ),
            "Not yet.",
        ],
        "第二笔的手续费改成0.000002",
        chat=first,
    )

    sent = model.calls[0].items
    assert sent[1:5] == first.items
    assert ToolResult(name="list_trades", content=listed) in sent
    assert "t-06" in next(item.content for item in sent if isinstance(item, ToolResult))
    assert isinstance(result.steps[0].calls[0], TakenCall)
    assert result.chat.items[: len(first.items)] == first.items
    assert result.chat.items[-1] == Message(Role.ASSISTANT, "Not yet.")


def test_the_chat_handed_back_holds_the_turns_calls_and_results() -> None:
    result, _ = turn([calls(("list_assets", {})), "Six assets."])

    kinds = [type(item).__name__ for item in result.chat.items]
    assert kinds == ["Message", "ToolCallTurn", "ToolResult", "Message"]
    assert result.chat.user_said == (HOLDINGS,)
