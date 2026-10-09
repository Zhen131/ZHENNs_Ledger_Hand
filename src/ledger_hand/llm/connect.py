"""The model, assembled from the settings: the plug they choose, with retries.

``connect_model`` builds the plug the settings choose (``Plug``): the local
Ollama plug, or the cloud plug for an OpenAI-style chat endpoint. Either is
wrapped so that the failures that may pass on their own are tried again,
with the number of retries and the first wait the settings name. The result
is all the rest of the program needs: something to ``chat`` with.

Before a cloud plug is built, ``check_plug`` checks that the settings fit
it, and raises ``SettingsError`` naming the variable when they do not:

- the address must be set, not left at the local Ollama's own address;
- an address off this machine (any host but ``LOOPBACK_HOSTS``) must use
  https, because the key and every passage typed are sent there;
- and an address off this machine needs a key.

A server on this machine that offers the same endpoint may go without https
and without a key. These checks are made here, where the plug is chosen,
and not where the settings are read, so that every variable is still read
on its own. The local plug takes the settings as they are, and a key or an
address set alone never switches to the cloud: only the plug setting does.

Building sends nothing; the first call is the first contact with the
server. ``local.connect_local_model`` still builds the local plug alone,
for the tools that only ever use it.

Names defined here: ``LOOPBACK_HOSTS``, ``check_plug``, ``connect_model``.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from urllib.parse import urlsplit

import httpx

from ledger_hand.llm.cloud import CloudModel
from ledger_hand.llm.local import connect_local_model
from ledger_hand.llm.retry import RetryingModel
from ledger_hand.ports import ModelPort
from ledger_hand.settings import DEFAULT_BASE_URL, ModelSettings, Plug, SettingsError, Variable

# The names of this machine an address may use: the only ones a cloud plug
# may reach without https and without a key.
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def check_plug(settings: ModelSettings) -> None:
    """Refuse settings that do not fit the plug they choose, naming the variable to set."""
    if not isinstance(settings, ModelSettings):
        raise TypeError(f"settings must be ModelSettings, not {type(settings).__name__}")
    if settings.plug is Plug.LOCAL:
        return
    address = Variable.URL.value
    if settings.base_url == DEFAULT_BASE_URL:
        raise SettingsError(
            f"{address}: the cloud plug needs the address of the service, such as "
            f"https://api.example.com/v1; {DEFAULT_BASE_URL} is the local Ollama's own"
        )
    parts = urlsplit(settings.base_url)
    if parts.hostname in LOOPBACK_HOSTS:
        return
    if parts.scheme != "https":
        raise SettingsError(
            f"{address}: an address off this machine must start with https:// for the cloud "
            "plug, because the key and every passage typed are sent there"
        )
    if settings.api_key is None:
        raise SettingsError(
            f"{Variable.KEY.value}: the cloud plug needs a key for an address off this "
            f"machine; set {Variable.KEY.value} in the environment"
        )


def connect_model(
    settings: ModelSettings,
    *,
    transport: httpx.BaseTransport | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> ModelPort:
    """The plug ``settings`` choose, retrying as they say; ``SettingsError`` when they do not fit.

    ``transport`` and ``sleep`` are for tests: no network, and no real waits.
    """
    check_plug(settings)
    if settings.plug is Plug.LOCAL:
        return connect_local_model(settings, transport=transport, sleep=sleep)
    return RetryingModel(
        CloudModel(settings, transport=transport),
        retries=settings.retries,
        first_wait_seconds=settings.retry_wait_seconds,
        sleep=sleep,
    )
