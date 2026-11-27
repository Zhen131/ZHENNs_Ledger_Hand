"""Tests of the cloud plug handing the model tools: the OpenAI way, with ids made on this side.

A call is given the id ``call_<turn>_<call>``; each result carries the id of
its call; a call left without a result is not sent, and nothing is written
in its place; the arguments go as JSON text with Chinese as it is. What
comes back is read into the program's own calls. Every value is invented.
"""

from __future__ import annotations

import json

import httpx
import pytest

from ledger_hand.llm.cloud import CloudModel
from ledger_hand.llm.cloud_request import tool_body
from ledger_hand.ports import (
    ChatItem,
    Message,
    ModelError,
    ModelErrorKind,
    ModelParameters,
    Role,
    ToolCall,
    ToolCallTurn,
    ToolResult,
    ToolSpec,
)
from tests.llm.fake_deepseek import deepseek_settings, sent_body, tool_completion
from tests.llm.fake_server import FakeServer, json_response

TOOLS = [
    ToolSpec(name=name, description=f"Invented {name}.", parameters={"type": "object"})
    for name in ("list_trades", "get_positions", "list_assets")
]
PARAMETERS = ModelParameters(
    temperature=0.0, top_p=1.0, max_reply_tokens=64, context_tokens=64, timeout_seconds=5.0
)
ASKED = Message(Role.USER, "我上个月买了哪些 BTC？")


def messages_of(items: list[ChatItem]) -> list[dict[str, object]]:
    body = tool_body("invented-model", items, TOOLS, PARAMETERS)
    messages = body["messages"]
    assert isinstance(messages, list)
    return messages


def call(name: str, **arguments: object) -> ToolCall:
    return ToolCall(name=name, arguments=arguments)


# --- S8: two calls read, their results sent back with matching ids -----------------


def test_two_calls_come_back_and_their_results_go_back_under_this_sides_ids() -> None:
    server = FakeServer(
        [
            json_response(
                200,
                tool_completion(
                    ("list_trades", '{"period": "上个月", "asset": "BTC"}'), ("get_positions", "{}")
                ),
            ),
            json_response(200, tool_completion(content="你上个月买了两次 BTC。")),
        ]
    )
    model = CloudModel(deepseek_settings(), transport=server.transport)

    first = model.chat_with_tools([ASKED], TOOLS)
    items: list[ChatItem] = [
        ASKED,
        ToolCallTurn(text=first.text, calls=first.calls),
        ToolResult(name="list_trades", content='{"trades": []}'),
        ToolResult(name="get_positions", content='{"positions": []}'),
    ]
    second = model.chat_with_tools(items, TOOLS)

    assert first.calls == (
        call("list_trades", period="上个月", asset="BTC"),
        call("get_positions"),
    )
    assert second.text == "你上个月买了两次 BTC。"
    sent = sent_body(server.requests[1])["messages"]
    assert isinstance(sent, list)
    turn, one, other = sent[1:]
    assert [c["id"] for c in turn["tool_calls"]] == ["call_0_0", "call_0_1"]
    assert (one["tool_call_id"], other["tool_call_id"]) == ("call_0_0", "call_0_1")
    assert turn["tool_calls"][0]["function"]["arguments"] == '{"period": "上个月", "asset": "BTC"}'
    assert turn["tool_calls"][1]["function"]["arguments"] == "{}"
    assert "上个月".encode() in server.requests[1].content
    assert b"\\u" not in server.requests[1].content
    assert "call_from_the_service" not in server.requests[1].content.decode("utf-8")


def test_the_tools_are_sent_the_openai_way_with_thinking_off() -> None:
    server = FakeServer([json_response(200, tool_completion(content="ok"))])

    CloudModel(deepseek_settings(), transport=server.transport).chat_with_tools([ASKED], TOOLS)

    body = sent_body(server.requests[0])
    assert body["tools"][0] == {  # type: ignore[index]
        "type": "function",
        "function": {
            "name": "list_trades",
            "description": "Invented list_trades.",
            "parameters": {"type": "object"},
        },
    }
    assert body["thinking"] == {"type": "disabled"}
    assert "tool_choice" not in body and "parallel_tool_calls" not in body


# --- S9: calls left without results ----------------------------------------------------


def test_a_turn_left_wholly_without_results_is_not_sent() -> None:
    items: list[ChatItem] = [
        ASKED,
        ToolCallTurn(text="", calls=(call("list_trades", period="上个月"),)),
        Message(Role.USER, "再问一次"),
    ]

    assert messages_of(items) == [
        {"role": "user", "content": "我上个月买了哪些 BTC？"},
        {"role": "user", "content": "再问一次"},
    ]


def test_only_the_calls_with_results_are_sent_and_nothing_is_written_for_the_rest() -> None:
    items: list[ChatItem] = [
        ASKED,
        ToolCallTurn(
            text="我查一下。",
            calls=(call("list_trades"), call("get_positions"), call("list_assets")),
        ),
        ToolResult(name="list_trades", content="[]"),
        Message(Role.USER, "再问一次"),
        ToolCallTurn(text="", calls=(call("get_positions"),)),
        ToolResult(name="get_positions", content="{}"),
    ]

    sent = messages_of(items)

    assert sent[1] == {
        "role": "assistant",
        "content": "我查一下。",
        "tool_calls": [
            {
                "id": "call_0_0",
                "type": "function",
                "function": {"name": "list_trades", "arguments": "{}"},
            }
        ],
    }
    assert sent[2] == {"role": "tool", "tool_call_id": "call_0_0", "content": "[]"}
    assert sent[4]["tool_calls"][0]["id"] == "call_1_0"  # type: ignore[index]
    assert sent[5] == {"role": "tool", "tool_call_id": "call_1_0", "content": "{}"}
    words = json.dumps(sent, ensure_ascii=False)
    assert "get_positions" not in json.dumps(sent[:4], ensure_ascii=False)
    assert len(sent) == 6
    assert words.count('"content"') == 6


def test_a_turn_without_results_keeps_its_words_and_the_ids_after_it_do_not_move() -> None:
    items: list[ChatItem] = [
        ASKED,
        ToolCallTurn(text="稍等。", calls=(call("list_trades"),)),
        ToolCallTurn(text="", calls=(call("list_assets"), call("get_positions"))),
        ToolResult(name="get_positions", content="{}"),
    ]

    sent = messages_of(items)

    assert sent[1] == {"role": "assistant", "content": "稍等。"}
    assert sent[2]["tool_calls"][0]["id"] == "call_1_1"  # type: ignore[index]
    assert sent[3]["tool_call_id"] == "call_1_1"


def test_a_result_that_answers_no_call_is_not_sent() -> None:
    items: list[ChatItem] = [ASKED, ToolResult(name="list_trades", content="[]")]

    assert messages_of(items) == [{"role": "user", "content": "我上个月买了哪些 BTC？"}]


def test_two_calls_of_one_name_are_matched_in_order() -> None:
    items: list[ChatItem] = [
        ASKED,
        ToolCallTurn(
            text="",
            calls=(call("list_trades", asset="BTC"), call("list_trades", asset="ETH")),
        ),
        ToolResult(name="list_trades", content="btc"),
        ToolResult(name="list_trades", content="eth"),
    ]

    sent = messages_of(items)

    assert [m["tool_call_id"] for m in sent[2:]] == ["call_0_0", "call_0_1"]
    assert [m["content"] for m in sent[2:]] == ["btc", "eth"]


# --- S10: arguments that are not an object ------------------------------------------


@pytest.mark.parametrize(
    ("arguments", "read"),
    [("", {}), ("   ", {}), ('{"asset": "比特币"}', {"asset": "比特币"})],
)
def test_arguments_read_as_an_object_or_as_none(arguments: str, read: dict[str, object]) -> None:
    server = FakeServer([json_response(200, tool_completion(("list_trades", arguments)))])

    reply = CloudModel(deepseek_settings(), transport=server.transport).chat_with_tools(
        [ASKED], TOOLS
    )

    assert reply.calls == (ToolCall(name="list_trades", arguments=read),)


@pytest.mark.parametrize("arguments", ["not json", "[1, 2]", '"text"', "{"])
def test_arguments_that_are_not_an_object_are_a_malformed_reply(arguments: str) -> None:
    server = FakeServer([json_response(200, tool_completion(("list_trades", arguments)))])

    with pytest.raises(ModelError) as caught:
        CloudModel(deepseek_settings(), transport=server.transport).chat_with_tools([ASKED], TOOLS)

    assert caught.value.kind is ModelErrorKind.MALFORMED_REPLY


def test_no_call_and_no_words_is_a_malformed_reply() -> None:
    server = FakeServer([json_response(200, tool_completion(content="  "))])

    with pytest.raises(ModelError) as caught:
        CloudModel(deepseek_settings(), transport=server.transport).chat_with_tools([ASKED], TOOLS)

    assert caught.value.kind is ModelErrorKind.MALFORMED_REPLY


def test_a_null_text_beside_calls_is_no_text_and_reasoning_is_not_kept() -> None:
    body = tool_completion(("get_positions", "{}"), content=None)
    body["choices"][0]["message"]["reasoning_content"] = "invented thinking"  # type: ignore[index]
    body["system_fingerprint"] = "fp_invented_0001"
    server = FakeServer([httpx.Response(200, content=json.dumps(body).encode("utf-8"))])

    reply = CloudModel(deepseek_settings(), transport=server.transport).chat_with_tools(
        [ASKED], TOOLS
    )

    assert reply.text == ""
    assert reply.calls == (call("get_positions"),)
    assert reply.record.service_fingerprint == "fp_invented_0001"
    assert reply.record.model == "deepseek-v4-pro"
