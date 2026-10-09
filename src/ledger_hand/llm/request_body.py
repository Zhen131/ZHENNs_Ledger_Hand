"""What every plug checks about a call before sending it, and how a body is written.

``check_call`` refuses a call in the wrong shape before anything is sent:
messages that are not a non-empty sequence of ``Message``, a reply schema
that is not a mapping, parameters that are not ``ModelParameters``. These
are mistakes of the caller, raised as ``TypeError`` or ``ValueError``; they
are not model failures and are never turned into one.

``encode`` turns a body into the bytes that are sent: UTF-8 JSON text, with
the text of the messages kept as written. A schema or a message that cannot
be written as JSON text is the caller's mistake and is refused with
``ValueError`` before anything is sent.

Names defined here: ``check_call``, ``encode``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence

from ledger_hand.ports import JsonSchema, Message, ModelParameters


def check_call(
    messages: Sequence[Message], reply_schema: JsonSchema | None, parameters: ModelParameters
) -> None:
    """Refuse a call in the wrong shape; return nothing when it is in the right one."""
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


def encode(body: Mapping[str, object]) -> bytes:
    """The body as UTF-8 JSON text; ``ValueError`` when it cannot be written as JSON."""
    try:
        text = json.dumps(body, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        return text.encode("utf-8")
    except (TypeError, ValueError, RecursionError) as error:
        raise ValueError(f"the request cannot be written as JSON: {error}") from None
