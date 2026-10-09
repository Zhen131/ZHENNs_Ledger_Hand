"""What comes back from Ollama's chat endpoint: a reply, or the kind of failure.

``read_chat_answer`` takes the answer to one chat request and returns the
reply, or raises ``ModelError``. Only answers in a recognised shape count;
whatever is not recognised falls to the kind that fits it, with the raw
status and the start of the body attached:

- status 200 with a JSON object that holds ``message.content`` as non-blank
  text and ``done`` as true: the reply;
- status 200 in any other shape (not UTF-8, not JSON, not an object, no
  message, no text, blank text, text that is not valid Unicode, not marked
  done, or a body that could not be read): ``MALFORMED_REPLY``;
- status 404 with a JSON object whose ``error`` text says "not found" and
  names a model (both in any case): this is how Ollama says it does not have
  the model; ``MODEL_NOT_FOUND``. A 404 that says only "Not Found" comes
  from something else at the address, and falls to the next line;
- any other status: as ``exchange.failure_for_status`` sorts it.

The record of the call takes the model's name, the two token counts
(``prompt_eval_count``, ``eval_count``) and the reason the model stopped
(``done_reason``: ``stop`` or ``length``) from the answer when they are
there and well formed. When they are not, the record says so (the requested
model's name, ``None``, ``NOT_REPORTED``) rather than failing the call: the
text is what matters.

Whether the text is valid JSON that follows a schema is not checked here; a
model reply is untrusted input, and the caller checks it. Reading the body
as JSON, and the fields every chat reply shares, are in ``reply_json``.

Names defined here: ``read_chat_answer``.
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


def read_chat_answer(
    answer: Answer, endpoint: Endpoint, *, requested_model: str, elapsed_seconds: float
) -> ModelReply:
    """The reply in ``answer``, or the ``ModelError`` that says why there is none."""
    if answer.status == 404 and _says_not_found(answer):
        raise ModelError(
            ModelErrorKind.MODEL_NOT_FOUND,
            f"the model server at {endpoint.base_url} does not have the model {requested_model!r}",
            status=404,
            snippet=snippet(answer.body, endpoint.api_key),
        )
    if answer.status != 200:
        raise failure_for_status(answer, endpoint)
    data = read_json_object(answer, endpoint)
    message = data.get("message")
    if not isinstance(message, dict):
        raise malformed("has no message", answer, endpoint)
    text = message.get("content")
    if not isinstance(text, str):
        raise malformed("has no text in its message", answer, endpoint)
    if not text.strip():
        raise malformed("has an empty reply", answer, endpoint)
    if not is_valid_unicode(text):
        raise malformed("has a reply that is not valid Unicode text", answer, endpoint)
    if data.get("done") is not True:
        raise malformed("is not marked as complete", answer, endpoint)
    record = ReplyRecord(
        model=model_name(data.get("model"), requested_model),
        elapsed_seconds=elapsed_seconds,
        prompt_tokens=count(data.get("prompt_eval_count")),
        reply_tokens=count(data.get("eval_count")),
        finish=_finish(data.get("done_reason")),
    )
    return ModelReply(text=text, record=record)


def _says_not_found(answer: Answer) -> bool:
    data = json_object_or_none(answer)
    error = None if data is None else data.get("error")
    if not isinstance(error, str):
        return False
    said = error.lower()
    return "not found" in said and "model" in said


def _finish(value: object) -> FinishReason:
    if isinstance(value, str):
        return _FINISH_REASONS.get(value, FinishReason.NOT_REPORTED)
    return FinishReason.NOT_REPORTED
