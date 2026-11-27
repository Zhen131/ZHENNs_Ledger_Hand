"""What comes back from an OpenAI-style chat endpoint: a reply, or the kind of failure.

``read_completion`` takes the answer to one chat request and returns the
reply, or raises ``ModelError``. Only answers in a recognised shape count;
whatever is not recognised falls to the kind that fits it, with the raw
status and the start of the body attached:

- status 200 with a JSON object whose ``choices`` is a list, the first of
  them an object holding ``message.content`` as non-blank, valid text: the
  reply;
- status 200 in any other shape (not UTF-8, not JSON, not an object, no
  choices or an empty list of them, a choice that is not an object, no
  message, no text, blank text, text that is not valid Unicode, or a body
  that could not be read): ``MALFORMED_REPLY``;
- status 404 whose JSON ``error`` is an object that says the model is not
  there: its ``code`` is ``model_not_found``, or its ``message`` names a
  model and says "not found" or "does not exist" (in any case):
  ``MODEL_NOT_FOUND``;
- status 400 or 404 whose error message names the model that was asked for
  and says it is not one the service has: "not found" or "does not
  exist", or "supported" with "you passed", as DeepSeek answers a model
  name it does not know (measured 2026-11-27, with status 400: "The
  supported API model names are ..., but you passed <name>."):
  ``MODEL_NOT_FOUND``, with the status it came with;
- any other status: as ``exchange.failure_for_status`` sorts it. So 429 is
  ``RATE_LIMITED``, with the wait its Retry-After header asks for; 500 to 599
  is ``SERVER_ERROR``; and every other status (a key refused with 401 or
  403, a request refused with 400, no money left with 402, a 404 of
  something else) is ``SERVER_ERROR`` with the raw status and the start of
  the body, for the interface to say by its status.

The record of the call takes the model's name (``model``), the two token
counts (``usage.prompt_tokens``, ``usage.completion_tokens``), the reason
the model stopped (the first choice's ``finish_reason``: ``stop``,
``length``, or ``tool_calls`` for a reply that calls tools) and the
service's ``system_fingerprint``, which changes when the service changes
the model behind the name, when they are there and well formed. When they
are not, the record says so (the requested model's name, ``None``,
``NOT_REPORTED``, ``None``) rather than failing the call.

A body may start with blank lines: DeepSeek sends them while a call waits
its turn. JSON allows them, so they are read past.

``read_tool_completion`` reads the answer to a call that handed the model
tools. The calls are in ``message.tool_calls``: a list, each an object whose
``function`` holds a ``name`` that is text and ``arguments`` that are JSON
text of an object; empty text or no arguments at all is no arguments. The
service's ids are not kept: this side makes its own (``cloud_request``).
With calls, the text may be empty or ``null``; without, it must be what a
chat reply's text must be. Anything else is ``MALFORMED_REPLY``. The
service's ``reasoning_content``, if it sends one, is not kept.

Whether the text is valid JSON that follows a schema is not checked here; a
model reply is untrusted input, and the caller checks it.

Names defined here: ``read_completion`` and ``read_tool_completion``.
"""

from __future__ import annotations

import json

from ledger_hand.llm.error_text import snippet
from ledger_hand.llm.exchange import Answer, Endpoint, failure_for_status, malformed
from ledger_hand.llm.reply_json import (
    count,
    is_valid_unicode,
    json_object_or_none,
    model_name,
    read_json_object,
)
from ledger_hand.ports import (
    FinishReason,
    ModelError,
    ModelErrorKind,
    ModelReply,
    ReplyRecord,
    ToolCall,
    ToolReply,
)

_FINISH_REASONS = {
    "stop": FinishReason.STOPPED,
    "length": FinishReason.LENGTH_LIMIT,
    "tool_calls": FinishReason.STOPPED,
}
_MODEL_NOT_FOUND_CODE = "model_not_found"
_NOT_THERE = ("not found", "does not exist")


def read_completion(
    answer: Answer, endpoint: Endpoint, *, requested_model: str, elapsed_seconds: float
) -> ModelReply:
    """The reply in ``answer``, or the ``ModelError`` that says why there is none."""
    data, choice, message = _read_message(answer, endpoint, requested_model)
    text = message.get("content")
    if not isinstance(text, str):
        raise malformed("has no text in its message", answer, endpoint)
    if not text.strip():
        raise malformed("has an empty reply", answer, endpoint)
    if not is_valid_unicode(text):
        raise malformed("has a reply that is not valid Unicode text", answer, endpoint)
    return ModelReply(text=text, record=_record(data, choice, requested_model, elapsed_seconds))


def read_tool_completion(
    answer: Answer, endpoint: Endpoint, *, requested_model: str, elapsed_seconds: float
) -> ToolReply:
    """The text and the calls in ``answer``, or the ``ModelError`` that says why there are none."""
    data, choice, message = _read_message(answer, endpoint, requested_model)
    calls = _calls(message.get("tool_calls"), answer, endpoint)
    text = message.get("content")
    if text is None and calls:
        text = ""
    if not isinstance(text, str):
        raise malformed("has no text in its message", answer, endpoint)
    if not calls and not text.strip():
        raise malformed("has an empty reply and no tool call", answer, endpoint)
    if not is_valid_unicode(text):
        raise malformed("has a reply that is not valid Unicode text", answer, endpoint)
    record = _record(data, choice, requested_model, elapsed_seconds)
    return ToolReply(text=text, calls=calls, record=record)


def _read_message(
    answer: Answer, endpoint: Endpoint, requested_model: str
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    """The body, its first choice and that choice's message; or the failure there is."""
    if answer.status in (400, 404) and _says_model_not_found(answer, requested_model):
        raise ModelError(
            ModelErrorKind.MODEL_NOT_FOUND,
            f"the model server at {endpoint.base_url} does not have the model {requested_model!r}",
            status=answer.status,
            snippet=snippet(answer.body, endpoint.api_key),
        )
    if answer.status != 200:
        raise failure_for_status(answer, endpoint)
    data = read_json_object(answer, endpoint)
    choice = _first_choice(data, answer, endpoint)
    message = choice.get("message")
    if not isinstance(message, dict):
        raise malformed("has no message in its first choice", answer, endpoint)
    return data, choice, message


def _first_choice(data: dict[str, object], answer: Answer, endpoint: Endpoint) -> dict[str, object]:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise malformed("has no choices", answer, endpoint)
    choice = choices[0]
    if not isinstance(choice, dict):
        raise malformed("has a first choice that is not an object", answer, endpoint)
    return choice


def _record(
    data: dict[str, object],
    choice: dict[str, object],
    requested_model: str,
    elapsed_seconds: float,
) -> ReplyRecord:
    usage = data.get("usage")
    tokens = usage if isinstance(usage, dict) else {}
    fingerprint = model_name(data.get("system_fingerprint"), "")
    return ReplyRecord(
        model=model_name(data.get("model"), requested_model),
        elapsed_seconds=elapsed_seconds,
        prompt_tokens=count(tokens.get("prompt_tokens")),
        reply_tokens=count(tokens.get("completion_tokens")),
        finish=_finish(choice.get("finish_reason")),
        service_fingerprint=fingerprint or None,
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
        arguments = _arguments(function.get("arguments"), answer, endpoint)
        calls.append(ToolCall(name=name, arguments=arguments))
    return tuple(calls)


def _arguments(value: object, answer: Answer, endpoint: Endpoint) -> dict[str, object]:
    """A call's arguments: JSON text of an object; none for empty text or no arguments."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return {}
    if not isinstance(value, str) or not is_valid_unicode(value):
        raise malformed("has a tool call whose arguments are not text", answer, endpoint)
    try:
        read = json.loads(value)
    except (ValueError, RecursionError):
        raise malformed("has a tool call whose arguments are not JSON", answer, endpoint) from None
    if not isinstance(read, dict):
        raise malformed("has a tool call whose arguments are not an object", answer, endpoint)
    return read


def _says_model_not_found(answer: Answer, requested_model: str) -> bool:
    data = json_object_or_none(answer)
    error = None if data is None else data.get("error")
    if not isinstance(error, dict):
        return False
    said = error.get("message")
    lowered = said.lower() if isinstance(said, str) else ""
    if answer.status == 404 and (
        error.get("code") == _MODEL_NOT_FOUND_CODE
        or ("model" in lowered and any(words in lowered for words in _NOT_THERE))
    ):
        return True
    if not isinstance(said, str) or requested_model not in said:
        return False
    passed = "supported" in lowered and "you passed" in lowered
    return passed or any(words in lowered for words in _NOT_THERE)


def _finish(value: object) -> FinishReason:
    if isinstance(value, str):
        return _FINISH_REASONS.get(value, FinishReason.NOT_REPORTED)
    return FinishReason.NOT_REPORTED
