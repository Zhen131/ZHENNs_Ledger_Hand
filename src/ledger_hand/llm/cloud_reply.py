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
- any other status: as ``exchange.failure_for_status`` sorts it. So 429 is
  ``RATE_LIMITED``, with the wait its Retry-After header asks for; 500 to 599
  is ``SERVER_ERROR``; and every other status (a key refused with 401 or
  403, a request refused with 400, a 404 of something else) is
  ``SERVER_ERROR`` with the raw status and the start of the body, for the
  interface to say by its status.

The record of the call takes the model's name (``model``), the two token
counts (``usage.prompt_tokens``, ``usage.completion_tokens``) and the reason
the model stopped (the first choice's ``finish_reason``: ``stop`` or
``length``) when they are there and well formed. When they are not, the
record says so (the requested model's name, ``None``, ``NOT_REPORTED``)
rather than failing the call.

Whether the text is valid JSON that follows a schema is not checked here; a
model reply is untrusted input, and the caller checks it.

Names defined here: ``read_completion``.
"""

from __future__ import annotations

from ledger_hand.llm.error_text import snippet
from ledger_hand.llm.exchange import Answer, Endpoint, failure_for_status, malformed
from ledger_hand.llm.reply_json import (
    count,
    is_valid_unicode,
    json_object_or_none,
    model_name,
    read_json_object,
)
from ledger_hand.ports import FinishReason, ModelError, ModelErrorKind, ModelReply, ReplyRecord

_FINISH_REASONS = {"stop": FinishReason.STOPPED, "length": FinishReason.LENGTH_LIMIT}
_MODEL_NOT_FOUND_CODE = "model_not_found"
_NOT_THERE = ("not found", "does not exist")


def read_completion(
    answer: Answer, endpoint: Endpoint, *, requested_model: str, elapsed_seconds: float
) -> ModelReply:
    """The reply in ``answer``, or the ``ModelError`` that says why there is none."""
    if answer.status == 404 and _says_model_not_found(answer):
        raise ModelError(
            ModelErrorKind.MODEL_NOT_FOUND,
            f"the model server at {endpoint.base_url} does not have the model {requested_model!r}",
            status=404,
            snippet=snippet(answer.body, endpoint.api_key),
        )
    if answer.status != 200:
        raise failure_for_status(answer, endpoint)
    data = read_json_object(answer, endpoint)
    choice = _first_choice(data, answer, endpoint)
    message = choice.get("message")
    if not isinstance(message, dict):
        raise malformed("has no message in its first choice", answer, endpoint)
    text = message.get("content")
    if not isinstance(text, str):
        raise malformed("has no text in its message", answer, endpoint)
    if not text.strip():
        raise malformed("has an empty reply", answer, endpoint)
    if not is_valid_unicode(text):
        raise malformed("has a reply that is not valid Unicode text", answer, endpoint)
    usage = data.get("usage")
    tokens = usage if isinstance(usage, dict) else {}
    record = ReplyRecord(
        model=model_name(data.get("model"), requested_model),
        elapsed_seconds=elapsed_seconds,
        prompt_tokens=count(tokens.get("prompt_tokens")),
        reply_tokens=count(tokens.get("completion_tokens")),
        finish=_finish(choice.get("finish_reason")),
    )
    return ModelReply(text=text, record=record)


def _first_choice(data: dict[str, object], answer: Answer, endpoint: Endpoint) -> dict[str, object]:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise malformed("has no choices", answer, endpoint)
    choice = choices[0]
    if not isinstance(choice, dict):
        raise malformed("has a first choice that is not an object", answer, endpoint)
    return choice


def _says_model_not_found(answer: Answer) -> bool:
    data = json_object_or_none(answer)
    error = None if data is None else data.get("error")
    if not isinstance(error, dict):
        return False
    if error.get("code") == _MODEL_NOT_FOUND_CODE:
        return True
    said = error.get("message")
    if not isinstance(said, str):
        return False
    said = said.lower()
    return "model" in said and any(words in said for words in _NOT_THERE)


def _finish(value: object) -> FinishReason:
    if isinstance(value, str):
        return _FINISH_REASONS.get(value, FinishReason.NOT_REPORTED)
    return FinishReason.NOT_REPORTED
