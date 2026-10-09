"""Who is behind the plug: the Ollama version and the model's fingerprint.

An experiment's results only mean something together with what produced
them. ``ask_identity`` asks the Ollama server named in the settings for its
version (``GET /api/version``) and for the list of models it has
(``GET /api/tags``), and returns the version together with the fingerprint
(the ``digest``) of the model the settings name. The same model name can
stand for different weights over time; the fingerprint cannot.

It is not part of the model port: only this plug has such a thing to tell.

Recognised answers: a version made of letters, digits, dots, plus and minus
signs; a model list holding an entry whose ``name`` or ``model`` is the
model asked for (a name given without a tag also matches the same name with
the tag ``latest``, as Ollama reads it); a fingerprint of 64 hexadecimal
digits, with or without ``sha256:`` in front. A model that is not in the
list is ``MODEL_NOT_FOUND``; any other shape is ``MALFORMED_REPLY``; failed
connections and statuses are sorted as for a chat call.

Names defined here: ``VERSION_PATH``, ``MODELS_PATH``, ``BackendIdentity``,
``ask_identity``.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from dataclasses import dataclass

import httpx

from ledger_hand.llm.exchange import Answer, Endpoint, exchange, failure_for_status, malformed
from ledger_hand.llm.reply_json import read_json_object
from ledger_hand.ports import ModelError, ModelErrorKind
from ledger_hand.settings import ModelSettings

VERSION_PATH = "/api/version"
MODELS_PATH = "/api/tags"

_VERSION = re.compile(r"[0-9A-Za-z.+-]{1,64}")
_FINGERPRINT = re.compile(r"(?:sha256:)?[0-9a-f]{64}")


@dataclass(frozen=True)
class BackendIdentity:
    """The server's version, the model asked for, and that model's fingerprint."""

    server_version: str
    model: str
    fingerprint: str


def ask_identity(
    settings: ModelSettings,
    *,
    transport: httpx.BaseTransport | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> BackendIdentity:
    """Ask the server named in ``settings`` who it is; ``ModelError`` when it cannot say."""
    endpoint = Endpoint(
        base_url=settings.base_url, api_key=settings.api_key, transport=transport, clock=clock
    )
    version_answer = _get(endpoint, VERSION_PATH, settings.timeout_seconds)
    version = read_json_object(version_answer, endpoint).get("version")
    if not isinstance(version, str) or _VERSION.fullmatch(version) is None:
        raise malformed("has no version in a known form", version_answer, endpoint)
    models_answer = _get(endpoint, MODELS_PATH, settings.timeout_seconds)
    entry = _entry_for(settings.model, models_answer, endpoint)
    fingerprint = entry.get("digest")
    if not isinstance(fingerprint, str) or _FINGERPRINT.fullmatch(fingerprint) is None:
        raise malformed("has no fingerprint in a known form for the model", models_answer, endpoint)
    return BackendIdentity(server_version=version, model=settings.model, fingerprint=fingerprint)


def _get(endpoint: Endpoint, path: str, timeout_seconds: float) -> Answer:
    answer = exchange(endpoint, "GET", path, content=None, timeout_seconds=timeout_seconds)
    if answer.status != 200:
        raise failure_for_status(answer, endpoint)
    return answer


def _entry_for(model: str, answer: Answer, endpoint: Endpoint) -> dict[str, object]:
    models = read_json_object(answer, endpoint).get("models")
    if not isinstance(models, list):
        raise malformed("has no list of models", answer, endpoint)
    wanted = {model} if ":" in model else {model, f"{model}:latest"}
    for entry in models:
        if not isinstance(entry, dict):
            raise malformed("has a model entry that is not an object", answer, endpoint)
        names = {entry.get("name"), entry.get("model")} if _plain(entry) else set()
        if names & wanted:
            return entry
    message = f"the model server at {endpoint.base_url} does not have the model {model!r}"
    raise ModelError(ModelErrorKind.MODEL_NOT_FOUND, message, status=answer.status)


def _plain(entry: dict[str, object]) -> bool:
    """Whether the entry's two names are text or absent, so that they can be compared."""
    return all(isinstance(entry.get(key), str | None) for key in ("name", "model"))
