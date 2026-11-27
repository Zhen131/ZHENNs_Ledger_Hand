"""The cloud plug for the model port: an OpenAI-style chat endpoint.

``CloudModel`` sends each call to ``POST <address>/chat/completions`` of the
service named in the settings, with the key as a bearer token, waits for the
whole reply (no streaming), and returns it with a record of the call, or
raises ``ModelError`` with one of the six kinds. It tries once: trying
again is ``retry``'s job, and ``connect.connect_model`` puts the two
together. ``cloud_request`` writes what is sent and ``cloud_reply`` reads
what comes back.

The settings it is handed are the effective ones
(``settings.effective_settings``): the address and the model are those the
call goes to. The key sent is the one the plug reads (``key_in_use``):
DeepSeek's own for the deepseek plug, the general one otherwise. A service
with fixed settings (``settings.SERVICES``) also fixes how a reply in the
shape of a table is asked for and the fields added to every body.

When a service that is asked for a JSON object turns a call down because
the prompt does not hold the word "json" (status 400, the error saying
"json" in any case, and the call carried ``response_format``), that way of
asking is dropped for the rest of this process (``reply_format_now`` says
which way is in use), and the call is sent once more without it. Nothing is
added to the prompt instead: every plug sends the same words.

The default parameters come from the settings, as for the local plug
(``ollama.parameters_from``); a call can hand in others. The time spent is
measured on this side, from sending to having the whole answer.

What the local plug does with the connection is done here the same way,
because both go through ``exchange``: the cap on the answer's size, the time
allowed, no proxy taken from the environment, no redirect followed, and the
key hidden in every error. On top of that, with the cloud or the deepseek
plug, nothing of what the service answered goes into an error that is not
a reply (``snippet`` is left empty), and a failed connection is said
without its own words: a service may write the key back in a
form the hiding does not know (DeepSeek, measured 2026-11-27, writes the
last four characters of a key it refuses), and errors are shown, recorded
and written into results files.

Whether the settings fit a cloud service (an address of its own, https and a
key when it is not on this machine) is checked where the plug is chosen, in
``connect``; this class takes the settings it is given.

This plug sends no pictures. A call with pictures is refused before anything
is sent, with ``ValueError`` naming the plug setting: it is the caller's
mistake, not a failure of the model, so it is never tried again and never
sorted into one of the six kinds, none of which says "this plug does not
send pictures". Pictures are read through the local plug only.

It hands the model tools the OpenAI way (``cloud_request.tool_body``) and
reads the calls back (``cloud_reply.read_tool_completion``).

This module keeps nothing between calls but the ways of asking dropped as
above: each call opens its own connection and closes it. It writes nothing
to disk and records nothing that was said.

Names defined here: ``CloudModel``, ``NO_PICTURES``, ``reply_format_now`` and
``forget_dropped_formats``.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping, Sequence

import httpx

from ledger_hand.llm.cloud_reply import read_completion, read_tool_completion
from ledger_hand.llm.cloud_request import CHAT_PATH, chat_body, tool_body
from ledger_hand.llm.exchange import Answer, Endpoint, exchange
from ledger_hand.llm.ollama import parameters_from
from ledger_hand.llm.reply_json import json_object_or_none
from ledger_hand.llm.request_body import encode
from ledger_hand.ports import (
    ChatItem,
    JsonSchema,
    Message,
    ModelError,
    ModelErrorKind,
    ModelParameters,
    ModelReply,
    Picture,
    ToolReply,
    ToolSpec,
)
from ledger_hand.settings import (
    SERVICES,
    ModelSettings,
    Plug,
    ReplyFormat,
    Variable,
    key_in_use,
)

# Why a call with pictures is refused, naming the setting that chooses the plug.
NO_PICTURES = (
    "the cloud plug sends no pictures; pictures are read through the local plug only. "
    f"Set {Variable.PLUG.value} to {Plug.LOCAL.value} to read a picture."
)

# What a failed connection is said as with a cloud plug, in place of its own words.
_CONNECTION_WORDS = {
    ModelErrorKind.UNREACHABLE: "cannot reach the model server at {address}",
    ModelErrorKind.SERVER_ERROR: (
        "the exchange with the model server at {address} failed in a way no other kind fits"
    ),
}

# The plugs whose service turned ``response_format`` down for want of the word
# "json", in this process; their calls are sent without it from then on.
_DROPPED: set[Plug] = set()


def reply_format_now(plug: Plug) -> ReplyFormat:
    """How a reply in the shape of a table is asked for with ``plug``, in this process now."""
    service = SERVICES.get(plug)
    if service is None:
        return ReplyFormat.JSON_SCHEMA
    if plug in _DROPPED:
        return ReplyFormat.NOT_SENT
    return service.reply_format


def forget_dropped_formats() -> None:
    """Go back to every service's own way of asking; for tests."""
    _DROPPED.clear()


class CloudModel:
    """A model port that talks to an OpenAI-style chat endpoint; one try per call.

    ``transport``, ``clock`` and ``wall_clock`` are for tests: a fake
    transport instead of the network, a clock that does not have to tick,
    and the date a Retry-After date is counted from.
    """

    def __init__(
        self,
        settings: ModelSettings,
        *,
        transport: httpx.BaseTransport | None = None,
        clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], float] = time.time,
    ) -> None:
        if not isinstance(settings, ModelSettings):
            raise TypeError(f"settings must be ModelSettings, not {type(settings).__name__}")
        self._model = settings.model
        self._plug = settings.plug
        service = SERVICES.get(settings.plug)
        self._fields: Mapping[str, object] = {} if service is None else service.fields
        self._defaults = parameters_from(settings)
        self._endpoint = Endpoint(
            base_url=settings.base_url,
            api_key=key_in_use(settings),
            transport=transport,
            clock=clock,
            wall_clock=wall_clock,
        )

    @property
    def defaults(self) -> ModelParameters:
        """The parameters a call uses when it hands in none."""
        return self._defaults

    def chat(
        self,
        messages: Sequence[Message],
        *,
        reply_schema: JsonSchema | None = None,
        parameters: ModelParameters | None = None,
    ) -> ModelReply:
        chosen = self._defaults if parameters is None else parameters
        asked = reply_format_now(self._plug)

        def body(way: ReplyFormat) -> dict[str, object]:
            return chat_body(
                self._model, messages, reply_schema, chosen, reply_format=way, fields=self._fields
            )

        started = self._endpoint.clock()
        answer = self._send(body(asked), chosen)
        if reply_schema is not None and asked is ReplyFormat.JSON_OBJECT and _wants_json(answer):
            _DROPPED.add(self._plug)
            answer = self._send(body(ReplyFormat.NOT_SENT), chosen)
        elapsed = self._endpoint.clock() - started
        try:
            return read_completion(
                answer, self._endpoint, requested_model=self._model, elapsed_seconds=elapsed
            )
        except ModelError as error:
            raise self._quiet(error) from None

    def chat_with_pictures(
        self,
        messages: Sequence[Message],
        pictures: Sequence[Picture],
        *,
        parameters: ModelParameters | None = None,
    ) -> ModelReply:
        """Refused before anything is sent: this plug sends no pictures."""
        raise ValueError(NO_PICTURES)

    def chat_with_tools(
        self,
        items: Sequence[ChatItem],
        tools: Sequence[ToolSpec],
        *,
        parameters: ModelParameters | None = None,
    ) -> ToolReply:
        chosen = self._defaults if parameters is None else parameters
        body = tool_body(self._model, items, tools, chosen, fields=self._fields)
        started = self._endpoint.clock()
        answer = self._send(body, chosen)
        elapsed = self._endpoint.clock() - started
        try:
            return read_tool_completion(
                answer, self._endpoint, requested_model=self._model, elapsed_seconds=elapsed
            )
        except ModelError as error:
            raise self._quiet(error) from None

    def _send(self, body: Mapping[str, object], chosen: ModelParameters) -> Answer:
        try:
            return exchange(
                self._endpoint,
                "POST",
                CHAT_PATH,
                content=encode(body),
                timeout_seconds=chosen.timeout_seconds,
            )
        except ModelError as error:
            raise self._quiet(error) from None

    def _quiet(self, error: ModelError) -> ModelError:
        """``error`` without what the service answered, unless it was a reply (status 200).

        A failed connection's own words are left out too: they may repeat
        what was sent, and they are not needed to say what happened.
        """
        if self._plug is Plug.LOCAL or error.status == 200:
            return error
        message = error.message
        if error.status is None and error.kind in _CONNECTION_WORDS:
            message = _CONNECTION_WORDS[error.kind].format(address=self._endpoint.base_url)
        if message == error.message and error.snippet is None:
            return error
        return ModelError(
            error.kind,
            message,
            status=error.status,
            retry_after_seconds=error.retry_after_seconds,
        )


def _wants_json(answer: Answer) -> bool:
    """Whether a call was turned down for want of the word json in the prompt."""
    if answer.status != 400:
        return False
    data = json_object_or_none(answer)
    error = None if data is None else data.get("error")
    said = error.get("message") if isinstance(error, dict) else None
    text = said if isinstance(said, str) else answer.body.decode("utf-8", errors="replace")
    return "json" in text.lower()
