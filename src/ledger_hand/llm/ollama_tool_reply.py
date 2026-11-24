"""What comes back from Ollama's chat endpoint when the model was handed tools.

``read_tool_answer`` takes the answer to one chat request that carried
tools, and returns the model's text and the tools it asked for
(``ToolReply``), or raises ``ModelError``. Every failure of the answer as a
whole is sorted as for any chat answer (``ollama_reply.read_message``).

Ollama puts the tools the model asks for in ``message.tool_calls``: a list,
each item an object whose ``function`` holds the tool's ``name`` and its
``arguments`` as a JSON object (checked against Ollama 0.34.3:
``{"id": "call_...", "function": {"index": 0, "name": "get_positions",
"arguments": {}}}``). The ``id`` and ``index`` are not kept: Ollama matches a
result to its call by the tool's name, and the calls are read in order.

A model that asks for a tool often writes no text beside it, so blank text
is taken when there is a call. Without a call the text must be what a chat
reply's text must be: not blank and valid Unicode. The calls are untrusted
input: a list that is not a list, an item that is not an object, a name that
is not text or arguments that are not a JSON object are a
``MALFORMED_REPLY``. Whether the tool is on the list and its arguments
follow its schema is not checked here; the caller judges that. NaN and
Infinity never get this far: the body is refused as not JSON; text holding
a lone surrogate, which JSON can carry but UTF-8 cannot, is refused here.

Names defined here: ``read_tool_answer``.
"""

from __future__ import annotations

import json

from ledger_hand.llm.exchange import Answer, Endpoint, malformed
from ledger_hand.llm.ollama_reply import call_record, read_message
from ledger_hand.llm.reply_json import is_valid_unicode
from ledger_hand.ports import ToolCall, ToolReply


def read_tool_answer(
    answer: Answer, endpoint: Endpoint, *, requested_model: str, elapsed_seconds: float
) -> ToolReply:
    """The text and the calls in ``answer``, or the ``ModelError`` that says why there are none."""
    data, message = read_message(answer, endpoint, requested_model=requested_model)
    calls = _calls(message.get("tool_calls"), answer, endpoint)
    text = message.get("content", "")
    if not isinstance(text, str):
        raise malformed("has text that is not text in its message", answer, endpoint)
    if not calls and not text.strip():
        raise malformed("has an empty reply and no tool call", answer, endpoint)
    if not is_valid_unicode(text):
        raise malformed("has a reply that is not valid Unicode text", answer, endpoint)
    if data.get("done") is not True:
        raise malformed("is not marked as complete", answer, endpoint)
    return ToolReply(
        text=text, calls=calls, record=call_record(data, requested_model, elapsed_seconds)
    )


def _calls(value: object, answer: Answer, endpoint: Endpoint) -> tuple[ToolCall, ...]:
    """The tool calls of a message; none when it has none."""
    if value is None:
        return ()
    if not isinstance(value, list):
        raise malformed("has tool calls that are not a list", answer, endpoint)
    calls: list[ToolCall] = []
    for item in value:
        function = item.get("function") if isinstance(item, dict) else None
        if not isinstance(function, dict):
            raise malformed("has a tool call with no function", answer, endpoint)
        name = function.get("name")
        if not isinstance(name, str) or not is_valid_unicode(name):
            raise malformed("has a tool call whose name is not text", answer, endpoint)
        arguments = function.get("arguments", {})
        if not isinstance(arguments, dict):
            raise malformed("has a tool call whose arguments are not an object", answer, endpoint)
        if not is_valid_unicode(json.dumps(arguments, ensure_ascii=False)):
            raise malformed("has a tool call whose arguments are not valid text", answer, endpoint)
        calls.append(ToolCall(name=name, arguments=arguments))
    return tuple(calls)
