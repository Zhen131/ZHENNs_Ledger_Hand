"""The model port: what the rest of the program may ask of a language model.

The rest of the program only ever talks to a ``ModelPort``. Behind it sits a
plug: the local model server today, perhaps a cloud service later, or a
scripted stand-in in the tests. One call sends a list of messages, optionally
a JSON schema the reply has to follow, and the sampling parameters; it gets
back the reply's text and a short record of the call. Every failure, whatever
the plug, is one ``ModelError`` carrying one of six kinds.

This module only declares shapes. It sends nothing, reads no settings and
holds no prompt. Whether the text of a reply is valid JSON that follows the
schema is for the caller to check: a model reply is untrusted input. Which
plug is used, and with which default parameters, is decided where the plug is
built from the settings.

The storage port joins this file when storage is built.

Names defined here: ``Role``, ``Message``, ``JsonSchema``,
``ModelParameters``, ``FinishReason``, ``ReplyRecord``, ``ModelReply``,
``ModelErrorKind``, ``ModelError``, ``ModelPort``.
"""

from __future__ import annotations

import enum
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol


class Role(enum.Enum):
    """Who speaks in a message; the values are the names model servers use."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True)
class Message:
    """One message of a conversation."""

    role: Role
    content: str

    def __post_init__(self) -> None:
        if not isinstance(self.role, Role):
            raise TypeError(f"a message role is a Role, not {type(self.role).__name__}")
        if not isinstance(self.content, str):
            raise TypeError(f"a message's content is text, not {type(self.content).__name__}")


type JsonSchema = Mapping[str, object]
"""A JSON schema, as plain JSON values, that a reply's text has to follow."""


@dataclass(frozen=True, kw_only=True)
class ModelParameters:
    """How the model samples its reply, and how long the caller waits for it.

    ``temperature`` is how adventurous the model is (0 is the same answer to
    the same text). ``top_p`` keeps only the likeliest words whose chances add
    up to it (1 keeps them all). ``max_reply_tokens`` caps the length of the
    reply and ``context_tokens`` the length the model reads at once, both in
    tokens, the pieces of words a model counts in. ``timeout_seconds`` is how
    long the caller waits for the whole reply; it is not sent to the model.
    """

    temperature: float
    top_p: float
    max_reply_tokens: int
    context_tokens: int
    timeout_seconds: float

    def __post_init__(self) -> None:
        _require_number("temperature", self.temperature)
        _require_number("top_p", self.top_p)
        _require_number("timeout_seconds", self.timeout_seconds)
        _require_whole_number("max_reply_tokens", self.max_reply_tokens)
        _require_whole_number("context_tokens", self.context_tokens)
        if self.temperature < 0:
            raise ValueError("temperature must be 0 or more")
        if not 0 < self.top_p <= 1:
            raise ValueError("top_p must be more than 0 and at most 1")
        if self.max_reply_tokens < 1 or self.context_tokens < 1:
            raise ValueError("max_reply_tokens and context_tokens must be 1 or more")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be more than 0")


def _require_number(name: str, value: object) -> None:
    """Refuse anything but a finite int or float; a bool is not a number here."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"{name} must be a number, not {type(value).__name__}")
    # Infinity minus itself, and NaN minus anything, are NaN, which is not 0.
    if value - value != 0:
        raise ValueError(f"{name} must be a finite number")


def _require_whole_number(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be a whole number, not {type(value).__name__}")


class FinishReason(enum.Enum):
    """Why the model stopped writing."""

    STOPPED = "stopped"
    """The model ended the reply itself."""
    LENGTH_LIMIT = "length_limit"
    """The reply reached ``max_reply_tokens`` and was cut off; its text is incomplete."""
    NOT_REPORTED = "not_reported"
    """The server gave no reason, or one this program does not know."""


@dataclass(frozen=True, kw_only=True)
class ReplyRecord:
    """A short record of one call.

    ``model`` is the model that answered, as the server names it.
    ``elapsed_seconds`` is measured by the caller's side, from sending to
    having the whole reply. The two token counts are what the model read and
    wrote, and are ``None`` when the server does not say.
    """

    model: str
    elapsed_seconds: float
    prompt_tokens: int | None
    reply_tokens: int | None
    finish: FinishReason


@dataclass(frozen=True, kw_only=True)
class ModelReply:
    """The text the model wrote, and the record of the call."""

    text: str
    record: ReplyRecord


class ModelErrorKind(enum.Enum):
    """The six kinds of failure. Every plug sorts every failure into one of them."""

    UNREACHABLE = "unreachable"
    """Nothing answered at the address: the server is not running, refused the
    connection, or the address cannot be resolved."""
    TIMED_OUT = "timed_out"
    """No complete reply within the time allowed."""
    MODEL_NOT_FOUND = "model_not_found"
    """The server answered that it does not have the model asked for."""
    RATE_LIMITED = "rate_limited"
    """The server refused because it was called too often."""
    SERVER_ERROR = "server_error"
    """The server reported an internal error, or failed in a way that fits no
    other kind; then the error carries the raw status and the start of the reply."""
    MALFORMED_REPLY = "malformed_reply"
    """An answer came back but not in the agreed shape: not JSON, a field
    missing, empty text, too long, or not valid text."""


class ModelError(Exception):
    """A call to the model failed; ``kind`` says how.

    ``message`` says what happened in words. ``status`` is the HTTP status
    when the server answered with one, and ``snippet`` the start of what it
    sent, made printable, when that helps to see what went wrong. None of
    these ever holds a key.
    """

    def __init__(
        self,
        kind: ModelErrorKind,
        message: str,
        *,
        status: int | None = None,
        snippet: str | None = None,
    ) -> None:
        super().__init__(kind, message)
        self.kind = kind
        self.message = message
        self.status = status
        self.snippet = snippet

    def __str__(self) -> str:
        text = f"{self.kind.value}: {self.message}"
        if self.status is not None:
            text += f" (status {self.status})"
        if self.snippet is not None:
            text += f"; the reply began {self.snippet!r}"
        return text

    def __repr__(self) -> str:
        return f"ModelError({self.kind.name}, {self.message!r}, status={self.status!r})"


class ModelPort(Protocol):
    """Anything the program can ask for a reply."""

    def chat(
        self,
        messages: Sequence[Message],
        *,
        reply_schema: JsonSchema | None = None,
        parameters: ModelParameters | None = None,
    ) -> ModelReply:
        """Send ``messages`` and return the reply, or raise ``ModelError``.

        With ``reply_schema`` the model is asked to write JSON that follows
        it. Without ``parameters`` the plug uses the defaults it was built with.
        """
        ...
