"""Trying a call again when its failure may pass on its own.

``RetryingModel`` wraps any model port. A call that fails as timed out, rate
limited or server error is tried again, a limited number of times, after a
wait that doubles each time: the first wait, then twice it, then four times
it. When the tries run out, the error of the last try is raised as it is.
A failure that waiting cannot mend (unreachable, model not found, malformed
reply) is raised at once.

"Unreachable" is not tried again on purpose: on this machine it means the
model server is not running, and the person at the keyboard should hear that
at once rather than after a round of waits.

The wait is a function handed in, so that tests record the waits instead of
sleeping through them.

Names defined here: ``RETRYABLE``, ``RetryingModel``.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable, Sequence

from ledger_hand.ports import (
    JsonSchema,
    Message,
    ModelError,
    ModelErrorKind,
    ModelParameters,
    ModelPort,
    ModelReply,
)

RETRYABLE = frozenset(
    {ModelErrorKind.TIMED_OUT, ModelErrorKind.RATE_LIMITED, ModelErrorKind.SERVER_ERROR}
)


class RetryingModel:
    """A model port that tries ``inner`` again after the failures in ``RETRYABLE``."""

    def __init__(
        self,
        inner: ModelPort,
        *,
        retries: int,
        first_wait_seconds: float,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if isinstance(retries, bool) or not isinstance(retries, int) or retries < 0:
            raise ValueError("retries must be a whole number, 0 or more")
        if isinstance(first_wait_seconds, bool) or not isinstance(first_wait_seconds, int | float):
            raise ValueError("first_wait_seconds must be a number")
        if not math.isfinite(first_wait_seconds) or first_wait_seconds < 0:
            raise ValueError("first_wait_seconds must be a finite number, 0 or more")
        self._inner = inner
        self._retries = retries
        self._first_wait = first_wait_seconds
        self._sleep = sleep

    def chat(
        self,
        messages: Sequence[Message],
        *,
        reply_schema: JsonSchema | None = None,
        parameters: ModelParameters | None = None,
    ) -> ModelReply:
        attempt = 0
        while True:
            try:
                return self._inner.chat(messages, reply_schema=reply_schema, parameters=parameters)
            except ModelError as error:
                if error.kind not in RETRYABLE or attempt >= self._retries:
                    raise
            self._sleep(self._first_wait * 2**attempt)
            attempt += 1
