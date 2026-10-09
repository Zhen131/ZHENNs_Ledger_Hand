"""Trying a call again when its failure may pass on its own.

``RetryingModel`` wraps any model port. A call that fails as timed out, rate
limited or server error is tried again, a limited number of times, after a
wait that doubles each time: the first wait, then twice it, then four times
it. When the tries run out, the error of the last try is raised as it is.
A failure that waiting cannot mend (unreachable, model not found, malformed
reply) is raised at once.

A server error whose status is 400 to 499 is raised at once too: the
server said the request itself is wrong (a key refused, a model it does not
offer, a field it does not take), and the same request will be wrong again.
429, "called too often", is the one such status worth waiting for, and it is
its own kind.

A rate-limited call whose server said how long to wait (``ModelError``'s
``retry_after_seconds``) waits that long instead of the doubling wait, as
long as it is not more than ``LONGEST_ASKED_WAIT_SECONDS``. A server that
asks for longer is not waited for: its error is raised at once, still
carrying the wait, so that the person can be told when to try again. Every
wait, either kind, counts as one retry.

"Unreachable" is not tried again on purpose: on this machine it means the
model server is not running, and the person at the keyboard should hear that
at once rather than after a round of waits.

The wait is a function handed in, so that tests record the waits instead of
sleeping through them.

Names defined here: ``RETRYABLE``, ``LONGEST_ASKED_WAIT_SECONDS``,
``worth_retrying``, ``RetryingModel``.
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

# The longest wait a server may ask for that is sat through. Limits per
# minute, the most common kind, clear within a minute, so a wait up to that
# is worth the person watching the program wait; a longer one (an hourly or
# daily quota) is handed back at once, with the wait, rather than leaving
# the page busy for minutes.
LONGEST_ASKED_WAIT_SECONDS = 60.0


def worth_retrying(error: ModelError) -> bool:
    """Whether waiting may mend ``error``: its kind may pass, and it is no 400 to 499 status."""
    if error.kind not in RETRYABLE:
        return False
    request_refused = error.status is not None and 400 <= error.status <= 499
    return not (error.kind is ModelErrorKind.SERVER_ERROR and request_refused)


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
                wait = self._wait_before_retry(error, attempt)
                if wait is None:
                    raise
            self._sleep(wait)
            attempt += 1

    def _wait_before_retry(self, error: ModelError, attempt: int) -> float | None:
        """How long to wait before trying again after ``error``; ``None`` for not trying again."""
        if not worth_retrying(error) or attempt >= self._retries:
            return None
        asked = error.retry_after_seconds
        if asked is None:
            return self._first_wait * 2**attempt
        return asked if asked <= LONGEST_ASKED_WAIT_SECONDS else None
