"""What is sent to an OpenAI-style chat endpoint: the body of one request.

Most cloud services offer the same chat endpoint, first made by OpenAI:
``POST <address>/chat/completions``, where the address the settings name
ends with the service's version, such as ``https://api.example.com/v1``.
``chat_body`` lays out one call in its fields: the model, the messages and
the sampling parameters (``PARAMETER_FIELDS`` says which parameter goes into
which field). A reply schema goes into ``response_format`` as a JSON schema
the service is asked to hold the model to strictly, under the name
``SCHEMA_NAME``. That is the way for a service at an address you set. A
service with fixed settings (``settings.SERVICES``) says its own way
(``ReplyFormat``): DeepSeek takes only ``{"type": "json_object"}``, which
asks for some JSON object and not the table, so the program checks the
reply against the table as it always does; or nothing is sent at all. The
fields such a service adds to every body (DeepSeek: thinking turned off)
go in last, the same for every call.

``tool_body`` lays out a call that hands the model tools, the OpenAI way:
each tool as ``{"type": "function", "function": {"name", "description",
"parameters"}}`` in ``tools``; the model's earlier tool-call turn as an
assistant message whose ``tool_calls`` each hold an ``id``, ``"type":
"function"`` and the ``function``'s ``name`` and ``arguments``, the latter
as JSON text; and each result as a message whose role is ``tool``, with the
``tool_call_id`` of its call. The program keeps no ids, so this side makes
them (``call_id``): ``call_<turn>_<call>``, the place of the tool-call turn
among all the turns of the conversation and the place of the call in it,
both counted from 0. A call's id stays the same however the conversation
goes on.

Each result is matched to the nearest tool-call turn before it, to its
first call of the same name not matched yet; the program always hands the
results back in order, right after their turn. A call left without a
result (the ledger failed part way through a step) is not sent, because
the endpoint refuses a call whose result does not follow it; a turn left
with no call and no text is not sent at all, and a result matched to no
call is not sent either. Nothing is written in their place. The local plug
sends such calls as they are; this is a known difference.

The arguments are written as ``json.dumps`` writes them, keeping the keys
in their order and Chinese as it is (``ensure_ascii=False``); no arguments
are written ``{}``.

Two parameters are not sent. ``timeout_seconds`` is how long this side
waits. ``context_tokens``, how much the model reads at once, has no field
in this endpoint: the service decides it. The longest reply goes into
``max_tokens``, the field every such service takes; some services' newer
endpoints name it ``max_completion_tokens`` instead.

A call in the wrong shape is refused before anything is sent, by the checks
every plug shares (``request_body.check_call``, ``request_body.check_tools``).

Names defined here: ``CHAT_PATH``, ``PARAMETER_FIELDS``, ``SCHEMA_NAME``,
``chat_body``, ``tool_body`` and ``call_id``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence

from ledger_hand.llm.request_body import check_call, check_tools
from ledger_hand.ports import (
    ChatItem,
    JsonSchema,
    Message,
    ModelParameters,
    ToolCallTurn,
    ToolResult,
    ToolSpec,
)
from ledger_hand.settings import ReplyFormat

CHAT_PATH = "/chat/completions"

# Each sampling parameter that is sent, and the field it goes into.
PARAMETER_FIELDS = {
    "temperature": "temperature",
    "top_p": "top_p",
    "max_reply_tokens": "max_tokens",
}

# The name the reply schema is sent under; the service only echoes it.
SCHEMA_NAME = "reply"


def chat_body(
    model: str,
    messages: Sequence[Message],
    reply_schema: JsonSchema | None,
    parameters: ModelParameters,
    *,
    reply_format: ReplyFormat = ReplyFormat.JSON_SCHEMA,
    fields: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """The request body for one call, as plain JSON values.

    ``reply_format`` says how a reply schema is asked for; ``fields`` are
    added at the top level of the body.
    """
    check_call(messages, reply_schema, parameters)
    body: dict[str, object] = {
        "model": model,
        "messages": [
            {"role": message.role.value, "content": message.content} for message in messages
        ],
    }
    for name, field in PARAMETER_FIELDS.items():
        body[field] = getattr(parameters, name)
    if reply_schema is not None and reply_format is ReplyFormat.JSON_SCHEMA:
        body["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": SCHEMA_NAME, "schema": reply_schema, "strict": True},
        }
    if reply_schema is not None and reply_format is ReplyFormat.JSON_OBJECT:
        body["response_format"] = {"type": "json_object"}
    body.update(_plain_fields(fields))
    return body


def tool_body(
    model: str,
    items: Sequence[ChatItem],
    tools: Sequence[ToolSpec],
    parameters: ModelParameters,
    *,
    fields: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """The request body for one call that hands the model ``tools``, as plain JSON values."""
    check_tools(items, tools, parameters)
    body: dict[str, object] = {
        "model": model,
        "messages": _messages(items),
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": dict(tool.parameters),
                },
            }
            for tool in tools
        ],
    }
    for name, field in PARAMETER_FIELDS.items():
        body[field] = getattr(parameters, name)
    body.update(_plain_fields(fields))
    return body


def call_id(turn: int, call: int) -> str:
    """The id this side gives a call: ``call_3_1`` is the second call of the fourth turn."""
    return f"call_{turn}_{call}"


class _Matched:
    """Which calls have a result (by turn and call), and the id each result answers."""

    def __init__(self) -> None:
        self.calls: set[tuple[int, int]] = set()
        self.results: dict[int, str] = {}


def _match(items: Sequence[ChatItem]) -> _Matched:
    """Each result matched to the first call of its name, not matched yet, in the turn before it."""
    matched = _Matched()
    turn_number = -1
    turn: ToolCallTurn | None = None
    for place, item in enumerate(items):
        if isinstance(item, ToolCallTurn):
            turn_number += 1
            turn = item
        elif isinstance(item, ToolResult) and turn is not None:
            for number, call in enumerate(turn.calls):
                if call.name == item.name and (turn_number, number) not in matched.calls:
                    matched.calls.add((turn_number, number))
                    matched.results[place] = call_id(turn_number, number)
                    break
    return matched


def _messages(items: Sequence[ChatItem]) -> list[dict[str, object]]:
    """The conversation as messages, each result carrying the id of its call."""
    answered = _match(items)
    messages: list[dict[str, object]] = []
    turn_number = -1
    for place, item in enumerate(items):
        if isinstance(item, Message):
            messages.append({"role": item.role.value, "content": item.content})
        elif isinstance(item, ToolCallTurn):
            turn_number += 1
            message = _turn_message(item, turn_number, answered)
            if message is not None:
                messages.append(message)
        elif place in answered.results:
            messages.append(
                {"role": "tool", "tool_call_id": answered.results[place], "content": item.content}
            )
    return messages


def _turn_message(
    turn: ToolCallTurn, turn_number: int, answered: _Matched
) -> dict[str, object] | None:
    """The assistant message of one tool-call turn, with only its calls that have results."""
    calls = [
        {
            "id": call_id(turn_number, number),
            "type": "function",
            "function": {"name": call.name, "arguments": _arguments(call.arguments)},
        }
        for number, call in enumerate(turn.calls)
        if (turn_number, number) in answered.calls
    ]
    if not calls and not turn.text:
        return None
    message: dict[str, object] = {"role": "assistant", "content": turn.text}
    if calls:
        message["tool_calls"] = calls
    return message


def _arguments(arguments: Mapping[str, object]) -> str:
    """The arguments as JSON text: keys in their order, Chinese as it is, none as ``{}``."""
    return json.dumps(dict(arguments), ensure_ascii=False)


def _plain_fields(fields: Mapping[str, object] | None) -> dict[str, object]:
    """``fields`` with every mapping in them made a plain dict, so they can be written as JSON."""
    return {str(key): _plain(value) for key, value in (fields or {}).items()}


def _plain(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    return value
