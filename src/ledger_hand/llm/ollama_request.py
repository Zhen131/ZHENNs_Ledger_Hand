"""What is sent to Ollama's chat endpoint: the body of one request.

``chat_body`` lays out one call in the fields of Ollama's own chat endpoint
(``POST /api/chat``): the model, the messages, the schema in ``format``, the
sampling parameters in ``options``, and ``stream`` set to false, so that the
whole reply comes back at once. ``OPTION_FIELDS`` says which parameter goes
into which field. ``timeout_seconds`` is not among them: it is how long this
side waits, and is never sent.

``encode`` turns the body into the bytes that are sent. A schema or a
message that cannot be written as JSON text is the caller's mistake and is
refused with ``ValueError`` before anything is sent.

Names defined here: ``CHAT_PATH``, ``OPTION_FIELDS``, ``chat_body``,
``encode``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence

from ledger_hand.ports import JsonSchema, Message, ModelParameters

CHAT_PATH = "/api/chat"

# Each sampling parameter and the field of Ollama's ``options`` it goes into.
OPTION_FIELDS = {
    "temperature": "temperature",
    "top_p": "top_p",
    "max_reply_tokens": "num_predict",
    "context_tokens": "num_ctx",
}


def chat_body(
    model: str,
    messages: Sequence[Message],
    reply_schema: JsonSchema | None,
    parameters: ModelParameters,
) -> dict[str, object]:
    """The request body for one call, as plain JSON values."""
    if isinstance(messages, str | bytes) or not isinstance(messages, Sequence):
        raise TypeError("messages must be a sequence of Message")
    if not messages:
        raise ValueError("a call needs at least one message")
    for message in messages:
        if not isinstance(message, Message):
            raise TypeError(f"messages must be Message, not {type(message).__name__}")
    if reply_schema is not None and not isinstance(reply_schema, Mapping):
        raise TypeError(f"a reply schema is a mapping, not {type(reply_schema).__name__}")
    if not isinstance(parameters, ModelParameters):
        raise TypeError(f"parameters must be ModelParameters, not {type(parameters).__name__}")
    body: dict[str, object] = {
        "model": model,
        "messages": [
            {"role": message.role.value, "content": message.content} for message in messages
        ],
        "stream": False,
        "options": {field: getattr(parameters, name) for name, field in OPTION_FIELDS.items()},
    }
    if reply_schema is not None:
        body["format"] = reply_schema
    return body


def encode(body: Mapping[str, object]) -> bytes:
    """The body as UTF-8 JSON text; ``ValueError`` when it cannot be written as JSON."""
    try:
        text = json.dumps(body, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        return text.encode("utf-8")
    except (TypeError, ValueError, RecursionError) as error:
        raise ValueError(f"the request cannot be written as JSON: {error}") from None
