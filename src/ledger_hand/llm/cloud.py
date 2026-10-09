"""The cloud plug for the model port: an OpenAI-style chat endpoint.

``CloudModel`` sends each call to ``POST <address>/chat/completions`` of the
service named in the settings, with the key as a bearer token, waits for the
whole reply (no streaming), and returns it with a record of the call, or
raises ``ModelError`` with one of the six kinds. It tries once: trying
again is ``retry``'s job, and ``connect.connect_model`` puts the two
together. ``cloud_request`` writes what is sent and ``cloud_reply`` reads
what comes back.

The default parameters come from the settings, as for the local plug
(``ollama.parameters_from``); a call can hand in others. The time spent is
measured on this side, from sending to having the whole answer.

What the local plug does with the connection is done here the same way,
because both go through ``exchange``: the cap on the answer's size, the time
allowed, no proxy taken from the environment, no redirect followed, and the
key hidden in every error.

Whether the settings fit a cloud service (an address of its own, https and a
key when it is not on this machine) is checked where the plug is chosen, in
``connect``; this class takes the settings it is given.

This module keeps nothing between calls: each call opens its own connection
and closes it. It writes nothing to disk and records nothing that was said.

Names defined here: ``CloudModel``.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence

import httpx

from ledger_hand.llm.cloud_reply import read_completion
from ledger_hand.llm.cloud_request import CHAT_PATH, chat_body
from ledger_hand.llm.exchange import Endpoint, exchange
from ledger_hand.llm.ollama import parameters_from
from ledger_hand.llm.request_body import encode
from ledger_hand.ports import JsonSchema, Message, ModelParameters, ModelReply
from ledger_hand.settings import ModelSettings


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
        self._defaults = parameters_from(settings)
        self._endpoint = Endpoint(
            base_url=settings.base_url,
            api_key=settings.api_key,
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
        content = encode(chat_body(self._model, messages, reply_schema, chosen))
        clock = self._endpoint.clock
        started = clock()
        answer = exchange(
            self._endpoint,
            "POST",
            CHAT_PATH,
            content=content,
            timeout_seconds=chosen.timeout_seconds,
        )
        return read_completion(
            answer,
            self._endpoint,
            requested_model=self._model,
            elapsed_seconds=clock() - started,
        )
