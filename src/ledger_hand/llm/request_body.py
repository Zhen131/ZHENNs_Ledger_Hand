"""What every plug checks about a call before sending it, and how a body is written.

``check_call`` refuses a call in the wrong shape before anything is sent:
messages that are not a non-empty sequence of ``Message``, a reply schema
that is not a mapping, parameters that are not ``ModelParameters``. These
are mistakes of the caller, raised as ``TypeError`` or ``ValueError``; they
are not model failures and are never turned into one.

``check_pictures`` does the same for a call that shows the model pictures:
the pictures must be a non-empty sequence of ``Picture``, and the last
message, which they are attached to, must be the user's.

``check_tools`` does the same for a call that hands the model tools: the
conversation must be a non-empty sequence of messages, the model's earlier
tool-call turns and the results handed back for them, and the tools a
non-empty sequence of ``ToolSpec`` with no name twice.

``encode`` turns a body into the bytes that are sent: UTF-8 JSON text, with
the text of the messages kept as written. A schema or a message that cannot
be written as JSON text is the caller's mistake and is refused with
``ValueError`` before anything is sent.

Names defined here: ``check_call``, ``check_pictures``, ``check_tools``, ``encode``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence

from ledger_hand.ports import (
    ChatItem,
    JsonSchema,
    Message,
    ModelParameters,
    Picture,
    Role,
    ToolCallTurn,
    ToolResult,
    ToolSpec,
)


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


def check_pictures(messages: Sequence[Message], pictures: Sequence[Picture]) -> None:
    """Refuse pictures in the wrong shape, or a last message that is not the user's.

    It reads the last message, so ``check_call`` is called on the messages first.
    """
    if isinstance(pictures, str | bytes) or not isinstance(pictures, Sequence):
        raise TypeError("pictures must be a sequence of Picture")
    if not pictures:
        raise ValueError("a call with pictures needs at least one picture")
    for picture in pictures:
        if not isinstance(picture, Picture):
            raise TypeError(f"pictures must be Picture, not {type(picture).__name__}")
    if messages[-1].role is not Role.USER:
        raise ValueError(
            f"the pictures go with the last message, which must be the user's, "
            f"not the {messages[-1].role.value}'s"
        )


def check_tools(
    items: Sequence[ChatItem], tools: Sequence[ToolSpec], parameters: ModelParameters
) -> None:
    """Refuse a call with tools in the wrong shape; return nothing when it is in the right one."""
    if isinstance(items, str | bytes) or not isinstance(items, Sequence):
        raise TypeError("the conversation must be a sequence of messages, calls and results")
    if not items:
        raise ValueError("a call needs at least one message")
    for item in items:
        if not isinstance(item, Message | ToolCallTurn | ToolResult):
            raise TypeError(f"a conversation holds no {type(item).__name__}")
    if isinstance(tools, str | bytes) or not isinstance(tools, Sequence) or not tools:
        raise ValueError("a call with tools needs a sequence of at least one ToolSpec")
    if not all(isinstance(tool, ToolSpec) for tool in tools):
        raise TypeError("the tools must be ToolSpec values")
    if len({tool.name for tool in tools}) != len(tools):
        raise ValueError("two tools share a name")
    if not isinstance(parameters, ModelParameters):
        raise TypeError(f"parameters must be ModelParameters, not {type(parameters).__name__}")


def encode(body: Mapping[str, object]) -> bytes:
    """The body as UTF-8 JSON text; ``ValueError`` when it cannot be written as JSON."""
    try:
        text = json.dumps(body, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        return text.encode("utf-8")
    except (TypeError, ValueError, RecursionError) as error:
        raise ValueError(f"the request cannot be written as JSON: {error}") from None
