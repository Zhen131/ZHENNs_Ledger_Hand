"""The live check of a missing model, said for each plug. By hand only.

Marked ``live_model``, so ordinary runs leave it out and the network guard
lets it through; ``scripts/check.sh live`` runs it. A model name the server
does not have (made sure of first, from its list of models) is asked for
twice: through the local plug, at the address the settings name, and through
the cloud plug, at Ollama's OpenAI-style endpoint under ``/v1`` of the same
address, with an invented key that Ollama does not check. Each plug's answer
is printed with its kind, status code and the start of what the server said,
and so is the sentence the interface would show: through the local plug it
names ``ollama pull``; through the cloud plug, when the kind is a missing
model, it never mentions Ollama.

When the address is not on this machine (127.0.0.1, localhost or ::1),
nothing is sent and the check is skipped, saying why: it must never carry its
invented key to a cloud service. No retries, so each plug asks once. The
server's list of models is read before and after (``GET /api/tags``, which
only reads) and must be the same: the check downloads and deletes nothing.
"""

from __future__ import annotations

import dataclasses
from urllib.parse import urlsplit

import httpx
import pytest

from ledger_hand.llm.connect import LOOPBACK_HOSTS, connect_model
from ledger_hand.llm.ollama_identity import MODELS_PATH
from ledger_hand.ports import ModelError, ModelErrorKind
from ledger_hand.settings import ModelSettings, Plug, Secret, load_model_settings
from ledger_hand.ui.failure_words import model_trouble
from tests.live.small_table import QUESTION

pytestmark = pytest.mark.live_model

# A name no model server is expected to have; the check makes sure of it first.
ABSENT = "no-such-model-for-the-check:0.1b"
# Plainly invented: the local server takes any key, and none is ever real here.
INVENTED_KEY = "sk-invented-live-missing-model-not-a-real-key"
# Where Ollama answers the OpenAI-style endpoints, under its own address.
OPENAI_STYLE_PATH = "/v1"


def model_names(settings: ModelSettings) -> list[str]:
    answer = httpx.get(settings.base_url + MODELS_PATH, timeout=settings.timeout_seconds)
    answer.raise_for_status()
    return sorted(str(entry.get("name")) for entry in answer.json().get("models", []))


def asked_for_the_absent_model(settings: ModelSettings) -> ModelError:
    try:
        reply = connect_model(settings).chat(QUESTION)
    except ModelError as error:
        print(f"  kind:     {error.kind.value}")
        print(f"  status:   {error.status}")
        print(f"  answered: {error.snippet!r}")
        print(f"  said:     {model_trouble(error, settings)}")
        return error
    pytest.fail(f"the server answered for a model it does not have: {reply.text!r}")


def test_a_missing_model_is_said_for_the_plug_that_asked_for_it() -> None:
    local = load_model_settings()
    if urlsplit(local.base_url).hostname not in LOOPBACK_HOSTS:
        pytest.skip(
            f"the address the settings name, {local.base_url}, is not on this machine; this "
            "check sends only to a server on this machine, never to a cloud service"
        )
    local = dataclasses.replace(local, plug=Plug.LOCAL, model=ABSENT, retries=0)
    before = model_names(local)
    assert ABSENT not in before
    cloud = dataclasses.replace(
        local,
        plug=Plug.CLOUD,
        base_url=local.base_url + OPENAI_STYLE_PATH,
        api_key=Secret(INVENTED_KEY),
    )

    print(f"\nmodels before: {before}")
    print(f"local plug at {local.base_url}:")
    through_local = asked_for_the_absent_model(local)
    print(f"cloud plug at {cloud.base_url}:")
    through_cloud = asked_for_the_absent_model(cloud)

    assert model_names(local) == before
    assert through_local.kind is ModelErrorKind.MODEL_NOT_FOUND
    assert f"ollama pull {ABSENT}" in model_trouble(through_local, local)
    if through_cloud.kind is not ModelErrorKind.MODEL_NOT_FOUND:
        pytest.fail(
            "the cloud plug did not report a missing model: "
            f"{through_cloud.kind.value}, status {through_cloud.status}, "
            f"answered {through_cloud.snippet!r}",
            pytrace=False,
        )
    assert "ollama" not in model_trouble(through_cloud, cloud).lower()
