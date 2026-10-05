"""Attacks on the plug: odd, broken and hostile answers, fed through the whole plug.

Every case must end in one of two ways: a reply, or a ``ModelError`` with one
of the six kinds. Any other exception fails the test, and so would a case
that never ends (bodies that never stop are cut at the size cap, and
trickling ones at the deadline). The random cases use a fixed seed, so every
run feeds the same inputs.
"""

from __future__ import annotations

import gzip
import json
import random

import httpx
import pytest

from ledger_hand.llm.exchange import MAX_ANSWER_BYTES
from ledger_hand.llm.ollama import OllamaModel
from ledger_hand.ports import Message, ModelError, ModelErrorKind, ModelReply, Role
from ledger_hand.settings import ModelSettings
from tests.llm.fake_server import SETTINGS, Endless, FakeClock, Pieces, chat_reply, mock_transport

HELLO = [Message(Role.USER, "hello")]
GOOD = json.dumps(chat_reply('{"fruit": "pear"}')).encode("utf-8")
STATUSES = [200, 200, 200, 201, 204, 301, 400, 404, 418, 429, 500, 503, 599]


def outcome(
    response: httpx.Response, settings: ModelSettings = SETTINGS
) -> ModelReply | ModelError:
    plug = OllamaModel(settings, transport=mock_transport(lambda _: response))
    try:
        return plug.chat(HELLO)
    except ModelError as error:
        return error


def expect_error(response: httpx.Response) -> ModelError:
    result = outcome(response)
    assert isinstance(result, ModelError), f"expected a failure, got {result!r}"
    return result


def test_every_prefix_of_a_good_answer_is_malformed_and_only_the_whole_one_succeeds() -> None:
    for end in range(len(GOOD)):
        result = expect_error(httpx.Response(200, content=GOOD[:end]))
        assert result.kind is ModelErrorKind.MALFORMED_REPLY, end
    assert isinstance(outcome(httpx.Response(200, content=GOOD)), ModelReply)


def test_random_bytes_under_any_status_end_in_a_reply_or_a_known_failure() -> None:
    chance = random.Random(20261005)
    for _ in range(400):
        body = bytes(chance.randrange(256) for _ in range(chance.randrange(300)))
        status = chance.choice(STATUSES)
        result = outcome(httpx.Response(status, content=body))
        assert isinstance(result, ModelError)
        assert result.kind in set(ModelErrorKind)


ODD_VALUES: list[object] = [
    None,
    True,
    0,
    -1,
    1e308,
    "",
    " ",
    "\u0000",
    "\x1b[31m",
    "\ud800",
    [],
    {},
    [[[[[]]]]],
    {"content": {"content": "x"}},
    "x" * 10_000,
]
FIELDS = ["model", "message", "done", "done_reason", "prompt_eval_count", "eval_count", "content"]


@pytest.mark.parametrize("field", FIELDS)
def test_any_odd_value_in_any_field_ends_in_a_reply_or_a_known_failure(field: str) -> None:
    for value in ODD_VALUES:
        data = chat_reply("text")
        if field == "content":
            data["message"] = {"role": "assistant", "content": value}
        else:
            data[field] = value
        result = outcome(httpx.Response(200, content=json.dumps(data).encode("utf-8")))
        if isinstance(result, ModelError):
            assert result.kind is ModelErrorKind.MALFORMED_REPLY, (field, value)
        else:
            assert isinstance(result.text, str)
            result.text.encode("utf-8")


@pytest.mark.parametrize(
    ("status", "kind"),
    [
        (200, ModelErrorKind.MALFORMED_REPLY),
        (404, ModelErrorKind.SERVER_ERROR),
        (429, ModelErrorKind.RATE_LIMITED),
        (500, ModelErrorKind.SERVER_ERROR),
        (302, ModelErrorKind.SERVER_ERROR),
    ],
)
def test_a_body_that_never_ends_is_cut_under_any_status(status: int, kind: ModelErrorKind) -> None:
    endless = Endless(b"z" * 100_000)

    error = expect_error(httpx.Response(status, stream=endless))

    assert error.kind is kind
    assert endless.sent * 100_000 <= MAX_ANSWER_BYTES + 100_000


def test_a_body_that_trickles_forever_is_abandoned_at_the_deadline() -> None:
    endless = Endless(b" ")
    clock = FakeClock(step=0.5)
    plug = OllamaModel(
        ModelSettings(timeout_seconds=3, retries=0),
        transport=mock_transport(lambda _: httpx.Response(200, stream=endless)),
        clock=clock,
    )

    with pytest.raises(ModelError) as caught:
        plug.chat(HELLO)

    assert caught.value.kind is ModelErrorKind.TIMED_OUT
    assert endless.sent < 20


def test_a_character_split_across_two_pieces_is_put_back_together() -> None:
    body = json.dumps(chat_reply("中文"), ensure_ascii=False).encode("utf-8")
    cut = body.index("中".encode()) + 1

    result = outcome(httpx.Response(200, stream=Pieces([body[:cut], body[cut:]])))

    assert isinstance(result, ModelReply)
    assert result.text == "中文"


def test_a_compressed_bomb_is_malformed_without_being_expanded() -> None:
    bomb = gzip.compress(json.dumps(chat_reply("0" * (MAX_ANSWER_BYTES * 8))).encode())
    response = httpx.Response(200, stream=Pieces([bomb]), headers={"Content-Encoding": "gzip"})

    assert expect_error(response).kind is ModelErrorKind.MALFORMED_REPLY


def test_an_answer_in_utf16_is_malformed() -> None:
    body = json.dumps(chat_reply("text")).encode("utf-16")

    assert expect_error(httpx.Response(200, content=body)).kind is ModelErrorKind.MALFORMED_REPLY


def test_terminal_control_codes_in_a_connection_error_are_made_harmless() -> None:
    plug = OllamaModel(
        SETTINGS,
        transport=mock_transport(_raise(httpx.ConnectError("refused\x1b[2J\x1b[H\x07"))),
    )

    with pytest.raises(ModelError) as caught:
        plug.chat(HELLO)

    assert "\x1b" not in str(caught.value)
    assert "\x07" not in str(caught.value)
    assert "\\x1b[2J" in str(caught.value)


def test_a_huge_server_message_is_cut_short_in_the_error() -> None:
    plug = OllamaModel(
        SETTINGS, transport=mock_transport(_raise(httpx.ConnectError("e" * 1_000_000)))
    )

    with pytest.raises(ModelError) as caught:
        plug.chat(HELLO)

    assert len(str(caught.value)) < 1000


def test_a_long_reply_under_the_cap_comes_back_whole() -> None:
    text = "w" * (MAX_ANSWER_BYTES // 2)

    result = outcome(httpx.Response(200, content=json.dumps(chat_reply(text)).encode()))

    assert isinstance(result, ModelReply)
    assert result.text == text


def test_an_address_with_a_path_keeps_its_path() -> None:
    seen: list[str] = []

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, content=GOOD)

    settings = ModelSettings(base_url="https://models.example/ollama", retries=0)
    OllamaModel(settings, transport=mock_transport(answer)).chat(HELLO)

    assert seen == ["https://models.example/ollama/api/chat"]


def test_an_ipv6_address_is_used_as_given() -> None:
    seen: list[str] = []

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.host)
        return httpx.Response(200, content=GOOD)

    OllamaModel(
        ModelSettings(base_url="http://[::1]:11434"), transport=mock_transport(answer)
    ).chat(HELLO)

    assert seen == ["::1"]


def test_a_reply_made_only_of_invisible_characters_still_counts_as_text() -> None:
    # Only blanks count as empty; anything else is the caller's to judge.
    result = outcome(httpx.Response(200, content=json.dumps(chat_reply("​")).encode()))

    assert isinstance(result, ModelReply)


def _raise(error: Exception) -> object:
    def answer(_: httpx.Request) -> httpx.Response:
        raise error

    return answer
