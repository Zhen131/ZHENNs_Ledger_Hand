"""Tests of what is said when a cloud service reports an error of its own.

With the cloud or the deepseek plug, a server error with no sentence of its
own (500, 502, 503, a 422, or no status at all) is said in the service's
words: which service, the status when there is one, to try again in a
while, and that nothing was sent to the local model instead. It does not
mention Ollama or a server's own log, and it quotes nothing the service
answered. The statuses that have a sentence of their own (400, 401, 402,
403, 429) keep it, and the local plug's sentence is word for word as
before. Every value is invented; no address or model name holds the word
"ollama", so that a check for that word looks at the sentence itself.
"""

from __future__ import annotations

import dataclasses

import pytest

from ledger_hand.ports import ModelError, ModelErrorKind
from ledger_hand.settings import ModelSettings, Plug, Secret
from ledger_hand.ui.failure_words import (
    CLOUD_FAILURES,
    MODEL_FAILURES,
    model_kind_trouble,
    model_trouble,
)
from tests.llm.fake_deepseek import deepseek_settings

LOCAL = ModelSettings(base_url="http://127.0.0.1:59999", model="invented-model:3b")
CLOUD = dataclasses.replace(
    LOCAL,
    plug=Plug.CLOUD,
    base_url="https://api.example.com/v1",
    api_key=Secret("sk-invented-server-words-0123456789"),
)
PLUGS = {"cloud": CLOUD, "deepseek": deepseek_settings()}
SAID_BY_THE_SERVICE = "INVENTED-SERVICE-WORDS-5K2"
LOCAL_SENTENCE = (
    "The model server reported an error of its own (status 500). Try again; if it keeps "
    "failing, look at the server's own log."
)


def server_error(status: int | None) -> ModelError:
    return ModelError(
        ModelErrorKind.SERVER_ERROR,
        "the service failed",
        status=status,
        snippet=SAID_BY_THE_SERVICE,
    )


def assert_said_as_the_service(sentence: str, settings: ModelSettings) -> None:
    assert sentence.endswith("Nothing was sent to the local model instead.")
    assert "ollama" not in sentence.lower()
    assert "own log" not in sentence
    assert SAID_BY_THE_SERVICE not in sentence
    if settings.plug is Plug.DEEPSEEK:
        assert "DeepSeek" in sentence
    else:
        assert settings.base_url in sentence


@pytest.mark.parametrize("status", [500, 502, 503, 422, None])
@pytest.mark.parametrize("plug", list(PLUGS))
def test_a_server_error_with_no_sentence_of_its_own_is_said_by_the_service(
    plug: str, status: int | None
) -> None:
    settings = PLUGS[plug]

    sentence = model_trouble(server_error(status), settings)

    assert_said_as_the_service(sentence, settings)
    if status is not None:
        assert f"(status {status})" in sentence


@pytest.mark.parametrize("plug", list(PLUGS))
def test_a_server_error_known_only_by_its_kind_is_said_the_same_way(plug: str) -> None:
    settings = PLUGS[plug]

    sentence = model_kind_trouble(ModelErrorKind.SERVER_ERROR, settings)

    assert_said_as_the_service(sentence, settings)
    assert "(status" not in sentence


OWN_WORDS = {
    400: "turned the request down as it was sent",
    401: "did not take the key",
    402: "has no money left on it",
    403: "did not take the key",
}


@pytest.mark.parametrize("status", list(OWN_WORDS))
@pytest.mark.parametrize("plug", list(PLUGS))
def test_the_statuses_with_a_sentence_of_their_own_keep_it(plug: str, status: int) -> None:
    settings = PLUGS[plug]
    assert OWN_WORDS[status] in CLOUD_FAILURES[(ModelErrorKind.SERVER_ERROR, status)]

    sentence = model_trouble(server_error(status), settings)

    assert OWN_WORDS[status] in sentence
    assert "reported an error of its own" not in sentence


@pytest.mark.parametrize("plug", list(PLUGS))
def test_a_rate_limited_call_keeps_its_own_sentence(plug: str) -> None:
    settings = PLUGS[plug]
    error = ModelError(ModelErrorKind.RATE_LIMITED, "too often", status=429)

    sentence = model_trouble(error, settings)

    assert "called too often" in sentence


def test_the_local_plug_says_it_word_for_word_as_before() -> None:
    assert model_trouble(server_error(500), LOCAL) == LOCAL_SENTENCE
    assert model_kind_trouble(ModelErrorKind.SERVER_ERROR, LOCAL) == MODEL_FAILURES[
        ModelErrorKind.SERVER_ERROR
    ].format(status="")
