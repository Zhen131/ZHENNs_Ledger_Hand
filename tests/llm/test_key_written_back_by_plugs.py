"""The key never shows, even when a hostile server writes it back escaped: both plugs.

The key here holds a quote and a backslash, the two characters a JSON string
writes with a backslash in front. The fake server takes the Authorization
header it was sent and writes the key back in its answers and in the errors
it raises: as JSON (in the message of an error object, the way cloud
services word a refused key), as JSON inside JSON, percent-encoded and
HTML-escaped. Whatever kind of failure follows, no text of the error holds
the key in any of these forms. The first tests check that the key really
was sent, so the others cannot pass by never sending it. Every value is
invented.
"""

from __future__ import annotations

import dataclasses
import html
import json
import urllib.parse
from collections.abc import Callable

import httpx
import pytest

from ledger_hand.llm.cloud import CloudModel
from ledger_hand.llm.ollama import OllamaModel
from ledger_hand.ports import Message, ModelError, ModelErrorKind, ModelPort, Role
from ledger_hand.settings import ModelSettings, Secret
from tests.llm.fake_cloud import CLOUD_SETTINGS
from tests.llm.fake_server import mock_transport

KEY = 'sk-invented-"quote\\back-0123456789'
HELLO = [Message(Role.USER, "hello")]


def json_string(text: str) -> str:
    return json.dumps(text)[1:-1]


# Every way the key may come back, and the key itself.
FORMS = {
    "as sent": KEY,
    "json": json_string(KEY),
    "json in json": json_string(json_string(KEY)),
    "percent-encoded": urllib.parse.quote(KEY, safe=""),
    "html": html.escape(KEY),
}

Build = Callable[[httpx.BaseTransport], ModelPort]


def local(transport: httpx.BaseTransport) -> ModelPort:
    settings = ModelSettings(api_key=Secret(KEY), retries=0, retry_wait_seconds=0.0)
    return OllamaModel(settings, transport=transport)


def cloud(transport: httpx.BaseTransport) -> ModelPort:
    settings = dataclasses.replace(CLOUD_SETTINGS, api_key=Secret(KEY))
    return CloudModel(settings, transport=transport)


PLUGS = {"local": local, "cloud": cloud}


def sent_key(request: httpx.Request) -> str:
    return request.headers["authorization"].removeprefix("Bearer ")


def echoing(status: int, form: str) -> httpx.MockTransport:
    """A server that answers ``status`` with the sent key written back in ``form``, twice."""

    def answer(request: httpx.Request) -> httpx.Response:
        assert sent_key(request) == KEY
        written = FORMS[form]
        # Once whole, and once again near the point where a snippet is cut. The
        # form goes into the bytes as it is: for JSON forms the body is JSON.
        said = f"Incorrect API key provided: {written}. " + "x" * 120 + written
        body = '{"error": {"message": "' + said + '", "code": "invalid_api_key"}}'
        return httpx.Response(status, content=body.encode("utf-8"))

    return mock_transport(answer)


def raising(make: Callable[[str], Exception], form: str) -> httpx.MockTransport:
    def answer(request: httpx.Request) -> httpx.Response:
        assert sent_key(request) == KEY
        raise make(f"failed while sending Bearer {FORMS[form]}")

    return mock_transport(answer)


def every_text_of(error: ModelError) -> list[str]:
    return [str(error), repr(error), error.message, error.snippet or "", *map(str, error.args)]


def assert_no_form_of_the_key(error: ModelError) -> None:
    for text in every_text_of(error):
        for form, written in FORMS.items():
            assert written not in text, (form, text)


@pytest.mark.parametrize("plug", list(PLUGS))
def test_the_key_with_a_quote_and_a_backslash_is_really_sent(plug: str) -> None:
    seen: list[str] = []

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(sent_key(request))
        return httpx.Response(500)

    with pytest.raises(ModelError):
        PLUGS[plug](mock_transport(answer)).chat(HELLO)

    assert seen == [KEY]


@pytest.mark.parametrize("form", list(FORMS))
@pytest.mark.parametrize("status", [200, 400, 401, 403, 404, 429, 500])
@pytest.mark.parametrize("plug", list(PLUGS))
def test_no_answer_that_writes_the_key_back_shows_it(plug: str, status: int, form: str) -> None:
    with pytest.raises(ModelError) as caught:
        PLUGS[plug](echoing(status, form)).chat(HELLO)

    assert_no_form_of_the_key(caught.value)
    assert "<hidden>" in (caught.value.snippet or "")


@pytest.mark.parametrize("form", list(FORMS))
@pytest.mark.parametrize(
    ("make", "kind"),
    [
        (httpx.ConnectError, ModelErrorKind.UNREACHABLE),
        (httpx.ReadTimeout, ModelErrorKind.TIMED_OUT),
        (httpx.RemoteProtocolError, ModelErrorKind.SERVER_ERROR),
    ],
)
@pytest.mark.parametrize("plug", list(PLUGS))
def test_no_connection_error_that_writes_the_key_back_shows_it(
    plug: str, make: Callable[[str], Exception], kind: ModelErrorKind, form: str
) -> None:
    with pytest.raises(ModelError) as caught:
        PLUGS[plug](raising(make, form)).chat(HELLO)

    assert caught.value.kind is kind
    assert_no_form_of_the_key(caught.value)
