"""What is sent to Ollama's chat endpoint: the body of one request.

``chat_body`` lays out one call in the fields of Ollama's own chat endpoint
(``POST /api/chat``): the model, the messages, the schema in ``format``, the
sampling parameters in ``options``, and ``stream`` set to false, so that the
whole reply comes back at once. ``OPTION_FIELDS`` says which parameter goes
into which field. ``timeout_seconds`` is not among them: it is how long this
side waits, and is never sent.

``picture_body`` lays out a call that shows the model pictures: the same
body with no schema, and the pictures in the ``images`` field of the last
message, each as the standard base64 of its bytes (not the URL-safe kind,
and with no ``data:`` prefix). Their media type is not sent: Ollama tells
the kind from the bytes.

A call in the wrong shape is refused before anything is sent, by the
checks every plug shares (``request_body.check_call``, and
``request_body.check_pictures`` for the pictures). ``encode``, also shared
and kept in ``request_body``, turns the body into the bytes that are sent;
it can be imported from here as well.

Names defined here: ``CHAT_PATH``, ``OPTION_FIELDS``, ``chat_body``,
``picture_body``.
"""

from __future__ import annotations

import base64
from collections.abc import Sequence

from ledger_hand.llm.request_body import check_call, check_pictures
from ledger_hand.llm.request_body import encode as encode
from ledger_hand.ports import JsonSchema, Message, ModelParameters, Picture

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
    check_call(messages, reply_schema, parameters)
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


def picture_body(
    model: str,
    messages: Sequence[Message],
    pictures: Sequence[Picture],
    parameters: ModelParameters,
) -> dict[str, object]:
    """The request body for one call with ``pictures`` on the last message, as plain JSON values."""
    body = chat_body(model, messages, None, parameters)
    check_pictures(messages, pictures)
    *earlier, last = messages
    images = [base64.b64encode(picture.data).decode("ascii") for picture in pictures]
    body["messages"] = [
        *({"role": message.role.value, "content": message.content} for message in earlier),
        {"role": last.role.value, "content": last.content, "images": images},
    ]
    return body
