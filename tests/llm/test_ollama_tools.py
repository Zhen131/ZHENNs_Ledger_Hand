"""Tests of the local plug's call with tools, against a fake Ollama server.

What is sent: the tools in Ollama's shape, the model's earlier tool calls and
the results handed back, and no schema. What comes back: the text, the calls
in order, or ``MALFORMED_REPLY`` for a reply whose calls cannot be read. The
cloud plug sends such a call the OpenAI way (``test_cloud_tools`` has the
rest), and the retries treat it as any other call. Every tool and reply is invented.
"""

from __future__ import annotations

import dataclasses
import json

import httpx
import pytest

from ledger_hand.llm.cloud import CloudModel
from ledger_hand.llm.ollama import OllamaModel
from ledger_hand.llm.retry import RetryingModel
from ledger_hand.ports import (
    Message,
    ModelError,
    ModelErrorKind,
    Role,
    ToolCall,
    ToolCallTurn,
    ToolReply,
    ToolResult,
    ToolSpec,
)
from ledger_hand.settings import Plug
from tests.fakes.scripted_model import ScriptedModel, scripted_record
from tests.llm.fake_cloud import CLOUD_SETTINGS, completion
from tests.llm.fake_server import SETTINGS, FakeServer, chat_reply, json_response

TOOL = ToolSpec(
    name="count_apples",
    description="Counts the invented apples.",
    parameters={"type": "object", "properties": {"colour": {"type": "string"}}},
)
ASKED = [Message(Role.SYSTEM, "You count apples."), Message(Role.USER, "How many red ones?")]


def plug(server: FakeServer) -> OllamaModel:
    return OllamaModel(SETTINGS, transport=server.transport)


def calling(*calls: object, content: str = "") -> FakeServer:
    message = {"role": "assistant", "content": content, "tool_calls": list(calls)}
    return FakeServer([json_response(200, chat_reply(message=message))])


def function(name: object, arguments: object) -> dict[str, object]:
    return {"id": "call_invented", "function": {"index": 0, "name": name, "arguments": arguments}}


# --- what is sent ------------------------------------------------------------


def test_the_tools_go_in_ollamas_shape_and_no_schema_is_sent() -> None:
    server = FakeServer([json_response(200, chat_reply("Three."))])

    plug(server).chat_with_tools(ASKED, [TOOL])

    sent = server.sent_json()
    assert isinstance(sent, dict)
    assert sent["tools"] == [
        {
            "type": "function",
            "function": {
                "name": "count_apples",
                "description": "Counts the invented apples.",
                "parameters": {"type": "object", "properties": {"colour": {"type": "string"}}},
            },
        }
    ]
    assert "format" not in sent
    assert sent["stream"] is False
    assert sent["messages"] == [
        {"role": "system", "content": "You count apples."},
        {"role": "user", "content": "How many red ones?"},
    ]


def test_earlier_calls_and_their_results_are_sent_back_in_ollamas_shape() -> None:
    server = FakeServer([json_response(200, chat_reply("Three red ones."))])
    turn = ToolCallTurn(text="", calls=(ToolCall(name="count_apples", arguments={"colour": "红"}),))
    result = ToolResult(name="count_apples", content='{"apples": "3"}')

    plug(server).chat_with_tools([*ASKED, turn, result], [TOOL])

    sent = server.sent_json()
    assert isinstance(sent, dict)
    assert sent["messages"][2:] == [  # type: ignore[index]
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"function": {"name": "count_apples", "arguments": {"colour": "红"}}}],
        },
        {"role": "tool", "tool_name": "count_apples", "content": '{"apples": "3"}'},
    ]


@pytest.mark.parametrize(
    "tools",
    [[], [TOOL, TOOL], ["count_apples"]],
    ids=["no tool", "a name twice", "not a ToolSpec"],
)
def test_a_call_with_tools_in_the_wrong_shape_is_refused_before_sending(
    tools: list[object],
) -> None:
    server = FakeServer([])

    with pytest.raises((TypeError, ValueError)):
        plug(server).chat_with_tools(ASKED, tools)  # type: ignore[arg-type]

    assert server.requests == []


# --- what comes back ---------------------------------------------------------


def test_a_reply_with_calls_and_no_text_gives_the_calls_in_order() -> None:
    server = calling(function("count_apples", {"colour": "red"}), function("count_pears", {}))

    reply = plug(server).chat_with_tools(ASKED, [TOOL])

    assert reply.text == ""
    assert reply.calls == (
        ToolCall(name="count_apples", arguments={"colour": "red"}),
        ToolCall(name="count_pears", arguments={}),
    )
    assert reply.record.model == SETTINGS.model


def test_a_reply_with_text_only_gives_the_text_and_no_call() -> None:
    server = FakeServer([json_response(200, chat_reply("There are three."))])

    reply = plug(server).chat_with_tools(ASKED, [TOOL])

    assert (reply.text, reply.calls) == ("There are three.", ())


@pytest.mark.parametrize(
    "tool_calls",
    [
        "count_apples",
        ["count_apples"],
        [{"function": "count_apples"}],
        [function(7, {})],
        [function(None, {})],
        [function("count_apples", '{"colour": "red"}')],
        [function("count_apples", ["red"])],
        [function("count_apples", {"colour": "\ud800"})],
    ],
    ids=[
        "calls not a list",
        "a call not an object",
        "no function object",
        "a name that is a number",
        "no name",
        "arguments as a string",
        "arguments as a list",
        "arguments with a lone surrogate",
    ],
)
def test_calls_that_cannot_be_read_are_a_malformed_reply(tool_calls: object) -> None:
    message = {"role": "assistant", "content": "", "tool_calls": tool_calls}
    server = FakeServer([json_response(200, chat_reply(message=message))])

    with pytest.raises(ModelError) as caught:
        plug(server).chat_with_tools(ASKED, [TOOL])

    assert caught.value.kind is ModelErrorKind.MALFORMED_REPLY


def test_a_reply_with_neither_text_nor_a_call_is_a_malformed_reply() -> None:
    server = FakeServer([json_response(200, chat_reply("  "))])

    with pytest.raises(ModelError) as caught:
        plug(server).chat_with_tools(ASKED, [TOOL])

    assert caught.value.kind is ModelErrorKind.MALFORMED_REPLY


def test_a_value_that_is_not_json_in_the_arguments_is_a_malformed_reply() -> None:
    body = (
        b'{"model": "m", "message": {"role": "assistant", "content": "", "tool_calls": '
        b'[{"function": {"name": "count_apples", "arguments": {"colour": NaN}}}]}, "done": true}'
    )
    server = FakeServer([httpx.Response(200, content=body)])

    with pytest.raises(ModelError) as caught:
        plug(server).chat_with_tools(ASKED, [TOOL])

    assert caught.value.kind is ModelErrorKind.MALFORMED_REPLY


# --- the cloud plug and the retries -----------------------------------------


def test_the_cloud_plug_hands_the_model_tools_and_reads_its_calls() -> None:
    called = completion(
        "",
        finish="tool_calls",
    )
    called["choices"][0]["message"]["tool_calls"] = [  # type: ignore[index]
        {
            "id": "call_from_the_service",
            "type": "function",
            "function": {"name": "count_apples", "arguments": '{"colour": "red"}'},
        }
    ]
    server = FakeServer([json_response(200, called)])
    cloud = dataclasses.replace(CLOUD_SETTINGS, plug=Plug.CLOUD)

    reply = CloudModel(cloud, transport=server.transport).chat_with_tools(ASKED, [TOOL])

    assert reply.calls == (ToolCall(name="count_apples", arguments={"colour": "red"}),)
    (sent,) = server.requests
    assert [tool["function"]["name"] for tool in json.loads(sent.content)["tools"]] == [
        "count_apples"
    ]


def test_a_call_with_tools_is_tried_again_by_the_same_rules_as_any_other() -> None:
    called = ToolReply(
        text="", calls=(ToolCall(name="count_apples", arguments={}),), record=scripted_record()
    )
    inner = ScriptedModel(
        [
            ModelError(ModelErrorKind.TIMED_OUT, "slow"),
            ModelError(ModelErrorKind.SERVER_ERROR, "busy", status=503),
            called,
        ]
    )
    waits: list[float] = []
    model = RetryingModel(inner, retries=2, first_wait_seconds=1.0, sleep=waits.append)

    reply = model.chat_with_tools(ASKED, [TOOL])

    assert reply is called
    assert waits == [1.0, 2.0]
    assert [call.tools for call in inner.calls] == [(TOOL,)] * 3


def test_a_malformed_reply_to_a_call_with_tools_is_not_tried_again() -> None:
    inner = ScriptedModel([ModelError(ModelErrorKind.MALFORMED_REPLY, "garbled")])
    model = RetryingModel(inner, retries=2, first_wait_seconds=1.0, sleep=lambda _: None)

    with pytest.raises(ModelError):
        model.chat_with_tools(ASKED, [TOOL])

    assert len(inner.calls) == 1
