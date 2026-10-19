"""Tests of reading an upload through the real local plug, with a fake server behind it.

The vision model is the plug the program builds for it (``connect_vision_model``),
and only the transport is fake. An answer with blank text, with or without
the model's thinking beside it, comes back from the plug as a malformed
reply in its own words, and is told here as an empty reading; should the
plug's words change, these fail. An answer cut off at the longest reply is
told as cut off. Every answer here is invented.
"""

from __future__ import annotations

from ledger_hand.flows.uploading import (
    UploadNotRead,
    UploadProblem,
    UploadRead,
    VisionModelPresence,
    read_upload,
)
from ledger_hand.llm.connect import connect_vision_model
from tests.llm.fake_server import SETTINGS, FakeServer, chat_reply, json_response

PNG = b"\x89PNG\r\n\x1a\n" + b"invented picture bytes" * 3
THOUGHT = "The picture shows an order: a purchase of bitcoin, so"


def through_the_plug(answer: dict[str, object]) -> tuple[object, FakeServer]:
    server = FakeServer([json_response(200, answer)])
    model = connect_vision_model(SETTINGS, transport=server.transport, sleep=lambda _: None)
    outcome = read_upload(
        PNG, SETTINGS, vision_model=model, check=lambda: VisionModelPresence.PRESENT
    )
    return outcome, server


def test_an_answer_with_blank_text_is_an_empty_reading() -> None:
    for content in ("", "   ", "\n\t "):
        outcome, server = through_the_plug(chat_reply(content))

        assert isinstance(outcome, UploadNotRead), content
        assert outcome.problem is UploadProblem.EMPTY
        assert len(server.requests) == 1


def test_an_answer_of_only_thinking_is_an_empty_reading() -> None:
    for done_reason in ("stop", "length"):
        answer = chat_reply(
            message={"role": "assistant", "content": "", "thinking": THOUGHT},
            done_reason=done_reason,
        )

        outcome, _ = through_the_plug(answer)

        assert isinstance(outcome, UploadNotRead), done_reason
        assert outcome.problem is UploadProblem.EMPTY


def test_an_answer_cut_off_at_the_longest_reply_is_cut_off() -> None:
    outcome, _ = through_the_plug(chat_reply("Side: buy\nPair: BT", done_reason="length"))

    assert isinstance(outcome, UploadNotRead)
    assert outcome.problem is UploadProblem.CUT_OFF


def test_an_answer_with_text_is_read_and_the_picture_was_sent_once() -> None:
    outcome, server = through_the_plug(chat_reply("Side: buy\nPair: BTC/USDT\n"))

    assert isinstance(outcome, UploadRead)
    assert outcome.reading.text == "Side: buy\nPair: BTC/USDT\n"
    (request,) = server.requests
    assert request.url.path == "/api/chat"
    assert server.sent_json()["model"] == SETTINGS.vision_model  # type: ignore[index]
