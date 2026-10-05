"""Tests of asking the Ollama server who it is: its version and the model's fingerprint."""

from __future__ import annotations

import httpx
import pytest

from ledger_hand.llm.ollama_identity import (
    MODELS_PATH,
    VERSION_PATH,
    BackendIdentity,
    ask_identity,
)
from ledger_hand.ports import ModelError, ModelErrorKind
from ledger_hand.settings import ModelSettings, Secret
from tests.llm.fake_server import SETTINGS, FakeServer, json_response

FINGERPRINT = "845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e"
OTHER_FINGERPRINT = "0" * 64


def models(*entries: object) -> httpx.Response:
    return json_response(200, {"models": list(entries)})


def entry(name: str, digest: object = FINGERPRINT) -> dict[str, object]:
    return {"name": name, "model": name, "size": 4683087332, "digest": digest}


def ask(server: FakeServer, settings: ModelSettings = SETTINGS) -> BackendIdentity:
    return ask_identity(settings, transport=server.transport)


def fails_as(server: FakeServer, settings: ModelSettings = SETTINGS) -> ModelError:
    with pytest.raises(ModelError) as caught:
        ask(server, settings)
    return caught.value


def test_the_version_and_the_fingerprint_of_the_named_model_come_back() -> None:
    server = FakeServer(
        [
            json_response(200, {"version": "0.34.3"}),
            models(entry("llama3:8b", OTHER_FINGERPRINT), entry(SETTINGS.model)),
        ]
    )

    identity = ask(server)

    assert identity == BackendIdentity(
        server_version="0.34.3", model=SETTINGS.model, fingerprint=FINGERPRINT
    )
    assert [request.url.path for request in server.requests] == [VERSION_PATH, MODELS_PATH]
    assert [request.method for request in server.requests] == ["GET", "GET"]


def test_a_name_without_a_tag_finds_the_latest_tag() -> None:
    server = FakeServer(
        [json_response(200, {"version": "0.5.0-rc1"}), models(entry("qwen2.5:latest"))]
    )

    identity = ask(server, ModelSettings(model="qwen2.5"))

    assert identity.fingerprint == FINGERPRINT
    assert identity.server_version == "0.5.0-rc1"


def test_a_fingerprint_with_its_algorithm_in_front_is_taken() -> None:
    digest = "sha256:" + FINGERPRINT
    server = FakeServer(
        [json_response(200, {"version": "0.34.3"}), models(entry(SETTINGS.model, digest))]
    )

    assert ask(server).fingerprint == digest


def test_a_model_the_server_does_not_have_is_model_not_found() -> None:
    server = FakeServer([json_response(200, {"version": "0.34.3"}), models(entry("llama3:8b"))])

    error = fails_as(server)

    assert error.kind is ModelErrorKind.MODEL_NOT_FOUND
    assert SETTINGS.model in error.message


def test_a_tagged_name_does_not_match_another_tag() -> None:
    server = FakeServer([json_response(200, {"version": "0.34.3"}), models(entry("qwen2.5:14b"))])

    assert fails_as(server).kind is ModelErrorKind.MODEL_NOT_FOUND


def test_an_unreachable_server_is_unreachable() -> None:
    server = FakeServer([httpx.ConnectError("[Errno 61] Connection refused")])

    assert fails_as(server).kind is ModelErrorKind.UNREACHABLE


def test_a_wrong_address_that_answers_404_is_a_server_error_with_the_status() -> None:
    server = FakeServer([httpx.Response(404, content=b"404 page not found")])

    error = fails_as(server)

    assert error.kind is ModelErrorKind.SERVER_ERROR
    assert error.status == 404


@pytest.mark.parametrize(
    "version_body",
    [
        b"",
        b"not json",
        b"[]",
        b"{}",
        b'{"version": 34}',
        b'{"version": ""}',
        b'{"version": "0.34.3; rm -rf"}',
        b'{"version": "' + b"9" * 65 + b'"}',
        b'{"version": ["0.34.3"]}',
    ],
)
def test_a_version_in_an_unknown_form_is_malformed(version_body: bytes) -> None:
    server = FakeServer([httpx.Response(200, content=version_body)])

    assert fails_as(server).kind is ModelErrorKind.MALFORMED_REPLY


@pytest.mark.parametrize(
    "models_body",
    [
        b"",
        b"{}",
        b'{"models": {}}',
        b'{"models": "qwen2.5:7b"}',
        b'{"models": [1]}',
        b'{"models": [null]}',
    ],
)
def test_a_model_list_in_an_unknown_form_is_malformed(models_body: bytes) -> None:
    server = FakeServer(
        [json_response(200, {"version": "0.34.3"}), httpx.Response(200, content=models_body)]
    )

    assert fails_as(server).kind is ModelErrorKind.MALFORMED_REPLY


@pytest.mark.parametrize(
    "digest", [None, "", 42, "abc", FINGERPRINT.upper(), FINGERPRINT + "0", "md5:" + FINGERPRINT]
)
def test_a_fingerprint_in_an_unknown_form_is_malformed(digest: object) -> None:
    server = FakeServer(
        [json_response(200, {"version": "0.34.3"}), models(entry(SETTINGS.model, digest))]
    )

    assert fails_as(server).kind is ModelErrorKind.MALFORMED_REPLY


@pytest.mark.parametrize("name", [["qwen2.5:7b"], {"n": 1}, 7, None])
def test_entries_whose_names_are_not_text_are_passed_over(name: object) -> None:
    odd = {"name": name, "model": name, "digest": OTHER_FINGERPRINT}
    server = FakeServer(
        [json_response(200, {"version": "0.34.3"}), models(odd, entry(SETTINGS.model))]
    )

    assert ask(server).fingerprint == FINGERPRINT


def test_a_key_is_sent_with_both_questions() -> None:
    settings = ModelSettings(api_key=Secret("invented-key-456"))
    server = FakeServer([json_response(200, {"version": "0.34.3"}), models(entry(settings.model))])

    ask(server, settings)

    assert all(
        request.headers["authorization"] == "Bearer invented-key-456" for request in server.requests
    )
