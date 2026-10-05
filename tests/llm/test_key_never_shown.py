"""The key never shows: not in the settings when printed, not in any kind of failure.

The fake server here is hostile on purpose: it repeats the Authorization
header it was sent in its bodies and in the errors it raises, so a key that
leaks anywhere into an error's text is caught. The first test checks that the
key really was sent, so the others cannot pass by never sending it.
"""

from __future__ import annotations

import httpx
import pytest

from ledger_hand.llm.local import connect_local_model
from ledger_hand.llm.ollama import OllamaModel
from ledger_hand.llm.ollama_identity import ask_identity
from ledger_hand.ports import Message, ModelError, ModelErrorKind, Role
from ledger_hand.settings import ModelSettings, Secret, Variable, load_model_settings
from tests.llm.fake_server import Pieces

KEY = "sk-invented-9f8e7d6c5b4a39281706"
SETTINGS = ModelSettings(api_key=Secret(KEY), retries=0, retry_wait_seconds=0.0)
HELLO = [Message(Role.USER, "hello")]


def echoing(kind: ModelErrorKind) -> httpx.MockTransport:
    """A server that fails as ``kind`` and repeats the sent Authorization header while at it."""

    def answer(request: httpx.Request) -> httpx.Response:
        sent = request.headers.get("authorization", "")
        # Once at the start, and once straddling the point where a snippet is cut.
        long_echo = (sent + "x" * 150 + sent + "y" * 50).encode()
        if kind is ModelErrorKind.UNREACHABLE:
            raise httpx.ConnectError(f"refused while sending {sent}")
        if kind is ModelErrorKind.TIMED_OUT:
            raise httpx.ReadTimeout(f"timed out holding {sent}")
        statuses = {
            ModelErrorKind.MODEL_NOT_FOUND: 404,
            ModelErrorKind.RATE_LIMITED: 429,
            ModelErrorKind.SERVER_ERROR: 500,
            ModelErrorKind.MALFORMED_REPLY: 200,
        }
        if kind is ModelErrorKind.MODEL_NOT_FOUND:
            body = f'{{"error": "model not found for {sent}"}}'.encode()
            return httpx.Response(404, content=body)
        return httpx.Response(statuses[kind], content=long_echo)

    return httpx.MockTransport(answer)


def every_text_of(error: ModelError) -> list[str]:
    return [str(error), repr(error), error.message, error.snippet or "", *map(str, error.args)]


def test_the_key_is_really_sent() -> None:
    seen: list[str] = []

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers["authorization"])
        return httpx.Response(500)

    with pytest.raises(ModelError):
        OllamaModel(SETTINGS, transport=httpx.MockTransport(answer)).chat(HELLO)
    assert seen == [f"Bearer {KEY}"]


@pytest.mark.parametrize("kind", list(ModelErrorKind))
def test_no_kind_of_failure_shows_the_key(
    kind: ModelErrorKind, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(ModelError) as caught:
        OllamaModel(SETTINGS, transport=echoing(kind)).chat(HELLO)
    error = caught.value
    print(error)
    print(repr(error))

    assert error.kind is kind
    for text in every_text_of(error):
        assert KEY not in text
        assert KEY[:12] not in text
    printed = capsys.readouterr()
    assert KEY not in printed.out + printed.err


def test_a_connection_that_breaks_off_while_echoing_the_key_does_not_show_it() -> None:
    def answer(request: httpx.Request) -> httpx.Response:
        sent = request.headers["authorization"]
        broken = Pieces([b"{"], then=httpx.RemoteProtocolError(f"peer closed after {sent}"))
        return httpx.Response(200, stream=broken)

    with pytest.raises(ModelError) as caught:
        OllamaModel(SETTINGS, transport=httpx.MockTransport(answer)).chat(HELLO)

    assert all(KEY not in text for text in every_text_of(caught.value))


def test_the_retrying_model_does_not_show_the_key_either() -> None:
    settings = ModelSettings(api_key=Secret(KEY), retries=2, retry_wait_seconds=0.0)
    model = connect_local_model(
        settings, transport=echoing(ModelErrorKind.SERVER_ERROR), sleep=lambda _: None
    )

    with pytest.raises(ModelError) as caught:
        model.chat(HELLO)

    assert all(KEY not in text for text in every_text_of(caught.value))


def test_asking_who_the_server_is_does_not_show_the_key() -> None:
    with pytest.raises(ModelError) as caught:
        ask_identity(SETTINGS, transport=echoing(ModelErrorKind.SERVER_ERROR))

    assert all(KEY not in text for text in every_text_of(caught.value))


def test_printing_the_settings_does_not_show_the_key(capsys: pytest.CaptureFixture[str]) -> None:
    loaded = load_model_settings({Variable.KEY.value: KEY})

    print(loaded)
    print(repr(loaded))
    print(loaded.api_key)
    print(f"{loaded.api_key!r} {loaded.api_key!s}")

    printed = capsys.readouterr()
    assert KEY not in printed.out + printed.err
    assert "<hidden>" in printed.out


def test_the_plug_itself_does_not_show_the_key() -> None:
    plug = OllamaModel(SETTINGS)

    assert KEY not in repr(plug)
    assert KEY not in repr(vars(plug))
