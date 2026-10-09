"""The local plug for the model port: Ollama's own chat endpoint.

``OllamaModel`` sends each call to ``POST /api/chat`` of the Ollama server
named in the settings, waits for the whole reply (no streaming), and returns
it with a record of the call, or raises ``ModelError`` with one of the six
kinds. It tries once: trying again is ``retry``'s job, and
``local.connect_local_model`` puts the two together.

The default parameters come from the settings; a call can hand in others.
The time spent is measured on this side, from sending to having the whole
answer, so it includes loading the model when it was not yet in memory.

Ollama's own chat endpoint is used rather than its OpenAI-style one because
only its own takes the length the model reads at once (``num_ctx``).

This module keeps nothing between calls: each call opens its own connection
and closes it. It writes nothing to disk and records nothing that was said.

Names defined here: ``OllamaModel``, ``parameters_from``.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence

import httpx

from ledger_hand.llm.exchange import Endpoint, exchange
from ledger_hand.llm.ollama_reply import read_chat_answer
from ledger_hand.llm.ollama_request import CHAT_PATH, chat_body, encode
from ledger_hand.ports import JsonSchema, Message, ModelParameters, ModelReply
from ledger_hand.settings import ModelSettings


def parameters_from(settings: ModelSettings) -> ModelParameters:
    """The default parameters the settings name."""
    return ModelParameters(
        temperature=settings.temperature,
        top_p=settings.top_p,
        max_reply_tokens=settings.max_reply_tokens,
        context_tokens=settings.context_tokens,
        timeout_seconds=settings.timeout_seconds,
    )


class OllamaModel:
    """A model port that talks to an Ollama server; one try per call.

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
        return read_chat_answer(
            answer,
            self._endpoint,
            requested_model=self._model,
            elapsed_seconds=clock() - started,
        )
