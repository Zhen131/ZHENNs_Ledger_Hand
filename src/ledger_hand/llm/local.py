"""The local model, assembled from the settings.

``connect_local_model`` builds the Ollama plug from the settings and wraps
it so that the failures that may pass on their own are tried again, with the
number of retries and the first wait the settings name. The result is all
the rest of the program needs: something to ``chat`` with.

Building it sends nothing; the first call is the first contact with the
server.

Names defined here: ``connect_local_model``.
"""

from __future__ import annotations

import time
from collections.abc import Callable

import httpx

from ledger_hand.llm.ollama import OllamaModel
from ledger_hand.llm.retry import RetryingModel
from ledger_hand.ports import ModelPort
from ledger_hand.settings import ModelSettings


def connect_local_model(
    settings: ModelSettings,
    *,
    transport: httpx.BaseTransport | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> ModelPort:
    """The Ollama plug for ``settings``, retrying as the settings say.

    ``transport`` and ``sleep`` are for tests: no network, and no real waits.
    """
    return RetryingModel(
        OllamaModel(settings, transport=transport),
        retries=settings.retries,
        first_wait_seconds=settings.retry_wait_seconds,
        sleep=sleep,
    )
