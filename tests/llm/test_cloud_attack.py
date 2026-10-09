"""Attacks on the cloud plug: odd, broken and hostile answers, fed through the whole plug.

Every case must end in one of two ways: a reply, or a ``ModelError`` with one
of the six kinds. Any other exception fails the test, and so would a case
that never ends (bodies that never stop are cut at the size cap, and
trickling ones at the deadline). The random cases use a fixed seed, so every
run feeds the same inputs. Every value is invented.
"""

from __future__ import annotations

import dataclasses
import json
import random

import httpx
import pytest

from ledger_hand.llm.cloud import CloudModel
from ledger_hand.llm.exchange import MAX_ANSWER_BYTES
from ledger_hand.ports import Message, ModelError, ModelErrorKind, ModelReply, Role
from tests.llm.fake_cloud import CLOUD_SETTINGS, completion
from tests.llm.fake_server import Endless, FakeClock, mock_transport

HELLO = [Message(Role.USER, "hello")]
GOOD = json.dumps(completion('{"fruit": "pear"}')).encode("utf-8")
STATUSES = [200, 200, 200, 201, 204, 301, 400, 401, 403, 404, 418, 429, 500, 503, 599]


def outcome(response: httpx.Response) -> ModelReply | ModelError:
    plug = CloudModel(CLOUD_SETTINGS, transport=mock_transport(lambda _: response))
    try:
        return plug.chat(HELLO)
    except ModelError as error:
        return error


def test_every_prefix_of_a_good_answer_is_malformed_and_only_the_whole_one_succeeds() -> None:
    for end in range(len(GOOD)):
        result = outcome(httpx.Response(200, content=GOOD[:end]))
        assert isinstance(result, ModelError), end
        assert result.kind is ModelErrorKind.MALFORMED_REPLY, end
    assert isinstance(outcome(httpx.Response(200, content=GOOD)), ModelReply)


def test_random_bytes_under_any_status_end_in_a_known_failure() -> None:
    chance = random.Random(20261009)
    for _ in range(400):
        body = bytes(chance.randrange(256) for _ in range(chance.randrange(300)))
        status = chance.choice(STATUSES)
        headers = {"Retry-After": chance.choice(["2", "soon", "-1", "9" * 30, ""])}
        result = outcome(httpx.Response(status, headers=headers, content=body))
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
PLACES = ["model", "choices", "usage", "choice", "message", "content", "finish_reason"]


def with_odd_value(place: str, value: object) -> dict[str, object]:
    body = completion("text")
    choices = body["choices"]
    assert isinstance(choices, list)
    if place in ("model", "choices", "usage"):
        body[place] = value
    elif place == "choice":
        choices[0] = value
    elif place == "message":
        choices[0]["message"] = value
    elif place == "content":
        choices[0]["message"] = {"role": "assistant", "content": value}
    else:
        choices[0]["finish_reason"] = value
    return body


@pytest.mark.parametrize("place", PLACES)
def test_any_odd_value_in_any_place_ends_in_a_reply_or_a_malformed_reply(place: str) -> None:
    for value in ODD_VALUES:
        result = outcome(httpx.Response(200, content=json.dumps(with_odd_value(place, value))))
        if isinstance(result, ModelError):
            assert result.kind is ModelErrorKind.MALFORMED_REPLY, (place, value)
        else:
            assert isinstance(result.text, str)
            result.text.encode("utf-8")


@pytest.mark.parametrize(
    ("status", "kind"),
    [
        (200, ModelErrorKind.MALFORMED_REPLY),
        (404, ModelErrorKind.SERVER_ERROR),
        (401, ModelErrorKind.SERVER_ERROR),
        (429, ModelErrorKind.RATE_LIMITED),
        (500, ModelErrorKind.SERVER_ERROR),
    ],
)
def test_a_body_that_never_ends_is_cut_under_any_status(status: int, kind: ModelErrorKind) -> None:
    endless = Endless(b"z" * 100_000)

    result = outcome(httpx.Response(status, stream=endless))

    assert isinstance(result, ModelError)
    assert result.kind is kind
    assert endless.sent * 100_000 <= MAX_ANSWER_BYTES + 100_000


def test_a_body_that_trickles_forever_is_abandoned_at_the_deadline() -> None:
    endless = Endless(b" ")
    plug = CloudModel(
        dataclasses.replace(CLOUD_SETTINGS, timeout_seconds=3),
        transport=mock_transport(lambda _: httpx.Response(200, stream=endless)),
        clock=FakeClock(step=0.5),
    )

    with pytest.raises(ModelError) as caught:
        plug.chat(HELLO)

    assert caught.value.kind is ModelErrorKind.TIMED_OUT
    assert endless.sent < 20


def test_a_redirect_is_not_followed() -> None:
    seen: list[str] = []

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(307, headers={"Location": "https://elsewhere.example/v1"})

    plug = CloudModel(CLOUD_SETTINGS, transport=mock_transport(answer))

    with pytest.raises(ModelError) as caught:
        plug.chat(HELLO)

    assert caught.value.kind is ModelErrorKind.SERVER_ERROR
    assert caught.value.status == 307
    assert len(seen) == 1
