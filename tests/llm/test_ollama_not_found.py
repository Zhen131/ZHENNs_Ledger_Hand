"""Tests of telling Ollama's "no such model" apart from a 404 of something else at the address.

Ollama says it does not have a model with a 404 whose JSON ``error`` says
"not found" and names a model. An address that points at another service
may answer 404 with ``{"error": "Not Found"}``: that is not a missing model,
and is a server error that keeps the raw status. Every value is invented.
"""

from __future__ import annotations

import json

import pytest

from ledger_hand.llm.exchange import Answer, Endpoint
from ledger_hand.llm.ollama import OllamaModel
from ledger_hand.llm.ollama_reply import read_chat_answer
from ledger_hand.ports import Message, ModelError, ModelErrorKind, Role
from tests.llm.fake_server import SETTINGS, FakeServer, json_response

ENDPOINT = Endpoint(base_url="http://127.0.0.1:11434", api_key=None)
ASKED = "qwen2.5:7b"
HELLO = [Message(Role.USER, "hello")]


def fails_as(status: int, data: object) -> ModelError:
    answer = Answer(status, json.dumps(data).encode("utf-8"))
    with pytest.raises(ModelError) as caught:
        read_chat_answer(answer, ENDPOINT, requested_model=ASKED, elapsed_seconds=0.1)
    return caught.value


@pytest.mark.parametrize(
    "said",
    [
        # Ollama's own two ways of saying it.
        'model "qwen9:1b" not found, try pulling it first',
        "model 'qwen9:1b' not found",
        # The same words in other cases.
        "MODEL qwen9:1b NOT FOUND",
    ],
)
def test_a_404_that_names_a_model_not_found_is_model_not_found(said: str) -> None:
    error = fails_as(404, {"error": said})

    assert error.kind is ModelErrorKind.MODEL_NOT_FOUND
    assert error.status == 404


@pytest.mark.parametrize(
    "said",
    ["Not Found", "not found", "404 Not Found", "page not found", "route /api/chat not found"],
)
def test_a_404_that_does_not_name_a_model_is_a_server_error_with_its_status(said: str) -> None:
    error = fails_as(404, {"error": said})

    assert error.kind is ModelErrorKind.SERVER_ERROR
    assert error.status == 404
    assert error.snippet is not None and said in error.snippet


def test_the_whole_plug_sorts_another_services_404_as_a_server_error() -> None:
    server = FakeServer([json_response(404, {"error": "Not Found"})])

    with pytest.raises(ModelError) as caught:
        OllamaModel(SETTINGS, transport=server.transport).chat(HELLO)

    assert caught.value.kind is ModelErrorKind.SERVER_ERROR
    assert caught.value.status == 404
