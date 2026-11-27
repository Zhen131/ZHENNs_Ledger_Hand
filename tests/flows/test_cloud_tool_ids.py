"""Every conversation the flows keep can be sent to a cloud service: each id has its result.

The flows run as they do on the page, with a scripted model; every
conversation they hand the model is then laid out as the cloud plug would
send it (``cloud_request.tool_body``) and checked: each call sent is
followed by its result, each result answers a call just before it, a call
keeps its id in every later request, and the arguments are the call's own.
The paths: a trade recorded (its results added by the program), a change and
a deletion (likewise), the program taking over after two wrong steps, two
calls of one name in one step, and two things said one after the other.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import pytest

from ledger_hand.assistant.tools import tool_specs
from ledger_hand.flows.conversation import Route
from ledger_hand.llm.cloud_request import tool_body
from ledger_hand.ports import ChatItem, ModelParameters, ToolCall, ToolReply
from tests.fakes.scripted_model import RecordedCall, scripted_record
from tests.fakes.usdt_only import usdt_only_ledger
from tests.flows import test_conversation as recording
from tests.flows import test_editing as editing
from tests.flows.scripted_flow import table

PARAMETERS = ModelParameters(
    temperature=0.0, top_p=1.0, max_reply_tokens=64, context_tokens=64, timeout_seconds=5.0
)


def sent(items: Sequence[ChatItem]) -> list[dict[str, object]]:
    body = tool_body("invented-model", items, tool_specs(), PARAMETERS)
    messages = body["messages"]
    assert isinstance(messages, list)
    return messages


def check_pairs(messages: list[dict[str, object]]) -> dict[str, tuple[str, str]]:
    """Each call followed by its result, each result after its call; the calls by id."""
    calls: dict[str, tuple[str, str]] = {}
    waiting: list[str] = []
    for message in messages:
        if message["role"] == "tool":
            assert waiting, message
            assert message["tool_call_id"] == waiting.pop(0)
            continue
        assert waiting == [], ("a call was left without its result", waiting)
        for made in message.get("tool_calls", []):  # type: ignore[attr-defined]
            function = made["function"]
            assert isinstance(function["arguments"], str)
            assert isinstance(json.loads(function["arguments"]), dict)
            assert "\\u" not in function["arguments"]
            calls[made["id"]] = (function["name"], function["arguments"])
            waiting.append(made["id"])
    assert waiting == []
    return calls


def check_all(recorded: Sequence[RecordedCall]) -> int:
    """Check every request; a call keeps its id and arguments in every later one."""
    seen: dict[str, tuple[str, str]] = {}
    checked = 0
    for call in recorded:
        assert call.items is not None
        now = check_pairs(sent(call.items))
        for made, what in now.items():
            assert seen.get(made, what) == what, made
        seen.update(now)
        checked += 1
    return checked


def tool_calls(model: object) -> Sequence[RecordedCall]:
    scripted = getattr(model, "tools", model)
    return scripted.calls  # type: ignore[attr-defined,no-any-return]


def test_a_trade_recorded_then_a_question() -> None:
    saids, model, _ = recording.talk(
        recording.ONE_BUY,
        "我现在持有哪些币？",
        tools=[
            recording.RECORD,
            recording.calls("get_positions"),
            ToolReply(text="你持有 BTC。", calls=(), record=scripted_record()),
        ],
        screen=[recording.SPOT],
        extraction=[table(recording.ONE_BUY_ROW)],
        ledger=usdt_only_ledger(),
    )

    assert saids[0].sent is not None
    assert check_all(tool_calls(model)) == 3


def test_the_program_taking_over_then_a_question() -> None:
    saids, model, _ = recording.talk(
        recording.ONE_BUY,
        "我现在持有哪些币？",
        tools=[
            recording.calls("place_order"),
            recording.calls("place_order"),
            recording.calls("get_positions"),
            ToolReply(text="你持有 BTC。", calls=(), record=scripted_record()),
        ],
        screen=[recording.SPOT],
        extraction=[table(recording.ONE_BUY_ROW)],
        ledger=usdt_only_ledger(),
    )

    assert saids[0].route is Route.TAKEOVER
    assert check_all(tool_calls(model)) == 4


def test_two_calls_of_one_name_in_one_step() -> None:
    _, model, _ = recording.talk(
        "我十月和九月各买了多少？",
        tools=[
            ToolReply(
                text="",
                calls=(
                    ToolCall(name="list_trades", arguments={"period": "10月"}),
                    ToolCall(name="list_trades", arguments={"period": "9月"}),
                ),
                record=scripted_record(),
            ),
            ToolReply(text="查到了。", calls=(), record=scripted_record()),
        ],
    )

    assert check_all(tool_calls(model)) == 2


@pytest.mark.parametrize(
    "step",
    [
        editing.delete(period="9月25号", asset="ADA"),
        editing.update(period="9月25号", asset="ADA", field="platform", new_value="Binance"),
        editing.calls(
            ("list_trades", {"period": "9月25号"}),
            ("propose_trade_delete", {"period": "9月25号", "asset": "ADA"}),
            ("propose_trade_update", {"period": "9月25号", "field": "note", "new_value": "删掉"}),
        ),
    ],
    ids=["a deletion", "a change", "a deletion beside calls not run"],
)
def test_a_change_or_a_deletion_then_a_question(step: object) -> None:
    saids, model, _ = editing.talk(
        "把9月25号那笔ADA删掉，平台改成Binance",
        "我现在持有哪些币？",
        steps=[
            step,  # type: ignore[list-item]
            editing.calls(("get_positions", {})),
            ToolReply(text="你持有 ADA。", calls=(), record=scripted_record()),
        ],
    )

    assert saids[0].edited is not None
    assert check_all(model.calls) == 3
