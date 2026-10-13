"""Tests of the sentence for a missing model, said for the plug the settings choose.

With the local plug, a model the server does not have is one to install with
Ollama, and the sentence says how, word for word as before. A cloud service
keeps its own list of models, so with the cloud plug the sentence names the
address and the model and sends the person to the Settings page and to the
service's list, and never mentions Ollama. The sentence for a failure known
only by its kind is looked up the same way. Every value below is invented,
and no address or model name holds the word "ollama", so that a check for
that word looks at the sentence itself.
"""

from __future__ import annotations

import dataclasses

import pytest

from ledger_hand.ports import ModelError, ModelErrorKind
from ledger_hand.settings import ModelSettings, Plug, Secret
from ledger_hand.ui import failure_words
from ledger_hand.ui.failure_words import (
    MODEL_FAILURES,
    MODEL_FAILURES_BY_PLUG,
    model_kind_trouble,
    model_trouble,
)

LOCAL = ModelSettings(base_url="http://127.0.0.1:59999", model="invented-model:3b")
CLOUD = dataclasses.replace(
    LOCAL,
    plug=Plug.CLOUD,
    base_url="http://127.0.0.1:59999/v1",
    api_key=Secret("sk-invented-plug-words-0123456789"),
)
# Written out by hand: the local plug's sentence as it always was.
LOCAL_SENTENCE = (
    "The server at http://127.0.0.1:59999 has no model named invented-model:3b. Check the "
    "name on the Settings page, or install the model with Ollama (ollama pull invented-model:3b)."
)
NOT_FOUND = ModelError(ModelErrorKind.MODEL_NOT_FOUND, "no such model", status=404)


def test_the_values_hold_no_word_ollama() -> None:
    for settings in (LOCAL, CLOUD):
        assert "ollama" not in settings.base_url.lower()
        assert "ollama" not in settings.model.lower()


@pytest.mark.parametrize("status", [None, 404])
def test_the_local_plug_says_it_word_for_word_as_before(status: int | None) -> None:
    error = ModelError(ModelErrorKind.MODEL_NOT_FOUND, "no such model", status=status)

    assert model_trouble(error, LOCAL) == LOCAL_SENTENCE


@pytest.mark.parametrize("status", [None, 404])
def test_the_cloud_plug_names_the_address_and_the_model_but_not_ollama(
    status: int | None,
) -> None:
    error = ModelError(ModelErrorKind.MODEL_NOT_FOUND, "no such model", status=status)

    sentence = model_trouble(error, CLOUD)

    assert "http://127.0.0.1:59999/v1" in sentence
    assert "invented-model:3b" in sentence
    assert "ollama" not in sentence.lower()
    assert "Settings page" in sentence
    assert "list of models" in sentence
    assert sentence.endswith(".")
    assert "{" not in sentence and "}" not in sentence


def test_the_cloud_template_itself_never_mentions_ollama() -> None:
    template = MODEL_FAILURES_BY_PLUG[(ModelErrorKind.MODEL_NOT_FOUND, Plug.CLOUD)]

    assert "ollama" not in template.lower()


def test_the_cloud_sentence_is_unlike_the_local_one_and_every_other_kind() -> None:
    cloud = model_trouble(NOT_FOUND, CLOUD)
    others = [
        model_trouble(ModelError(kind, "invented"), CLOUD)
        for kind in ModelErrorKind
        if kind is not ModelErrorKind.MODEL_NOT_FOUND
    ]

    assert cloud != model_trouble(NOT_FOUND, LOCAL)
    assert cloud not in others
    assert len(set(others)) == len(others)


def test_the_plugs_table_leaves_the_kinds_table_as_it_was() -> None:
    assert "ollama pull {model}" in MODEL_FAILURES[ModelErrorKind.MODEL_NOT_FOUND]
    assert set(MODEL_FAILURES_BY_PLUG) == {(ModelErrorKind.MODEL_NOT_FOUND, Plug.CLOUD)}


@pytest.mark.parametrize("status", [401, 403, 400])
def test_the_statuses_sentences_do_not_depend_on_the_plug(status: int) -> None:
    error = ModelError(ModelErrorKind.SERVER_ERROR, "refused", status=status)

    assert model_trouble(error, CLOUD) == model_trouble(
        error, dataclasses.replace(CLOUD, plug=Plug.LOCAL)
    )


def test_a_status_with_its_own_sentence_comes_before_the_plug(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    by_status = {**failure_words.MODEL_FAILURES_BY_STATUS}
    by_status[(ModelErrorKind.MODEL_NOT_FOUND, 404)] = "Said for the status {status}."
    monkeypatch.setattr(failure_words, "MODEL_FAILURES_BY_STATUS", by_status)

    assert model_trouble(NOT_FOUND, CLOUD) == "Said for the status  (status 404)."
    assert "ollama" not in model_kind_trouble(ModelErrorKind.MODEL_NOT_FOUND, CLOUD).lower()


def test_a_rate_limited_wait_is_said_for_either_plug() -> None:
    error = ModelError(ModelErrorKind.RATE_LIMITED, "slow down", status=429, retry_after_seconds=3)

    for settings in (LOCAL, CLOUD):
        assert "wait 3 seconds" in model_trouble(error, settings)


@pytest.mark.parametrize("kind", list(ModelErrorKind))
@pytest.mark.parametrize("settings", [LOCAL, CLOUD], ids=["local", "cloud"])
def test_a_kind_alone_is_looked_up_as_a_failure_of_that_kind(
    kind: ModelErrorKind, settings: ModelSettings
) -> None:
    assert model_kind_trouble(kind, settings) == model_trouble(ModelError(kind, "x"), settings)


def test_a_kind_alone_with_the_cloud_plug_uses_the_cloud_sentence() -> None:
    sentence = model_kind_trouble(ModelErrorKind.MODEL_NOT_FOUND, CLOUD)

    assert sentence == model_trouble(NOT_FOUND, CLOUD)
    assert "ollama" not in sentence.lower()
    assert model_kind_trouble(ModelErrorKind.MODEL_NOT_FOUND, LOCAL) == LOCAL_SENTENCE
