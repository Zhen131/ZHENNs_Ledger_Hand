"""What is sent to an OpenAI-style chat endpoint: the body of one request.

Most cloud services offer the same chat endpoint, first made by OpenAI:
``POST <address>/chat/completions``, where the address the settings name
ends with the service's version, such as ``https://api.example.com/v1``.
``chat_body`` lays out one call in its fields: the model, the messages and
the sampling parameters (``PARAMETER_FIELDS`` says which parameter goes into
which field). A reply schema goes into ``response_format`` as a JSON schema
the service is asked to hold the model to strictly, under the name
``SCHEMA_NAME``. A service that does not take a schema that way refuses the
call with 400; there is no second way of asking.

Two parameters are not sent. ``timeout_seconds`` is how long this side
waits. ``context_tokens``, how much the model reads at once, has no field
in this endpoint: the service decides it. The longest reply goes into
``max_tokens``, the field every such service takes; some services' newer
endpoints name it ``max_completion_tokens`` instead.

A call in the wrong shape is refused before anything is sent, by the checks
every plug shares (``request_body.check_call``).

Names defined here: ``CHAT_PATH``, ``PARAMETER_FIELDS``, ``SCHEMA_NAME``,
``chat_body``.
"""

from __future__ import annotations

from collections.abc import Sequence

from ledger_hand.llm.request_body import check_call
from ledger_hand.ports import JsonSchema, Message, ModelParameters

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
) -> dict[str, object]:
    """The request body for one call, as plain JSON values."""
    check_call(messages, reply_schema, parameters)
    body: dict[str, object] = {
        "model": model,
        "messages": [
            {"role": message.role.value, "content": message.content} for message in messages
        ],
    }
    for name, field in PARAMETER_FIELDS.items():
        body[field] = getattr(parameters, name)
    if reply_schema is not None:
        body["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": SCHEMA_NAME, "schema": reply_schema, "strict": True},
        }
    return body
