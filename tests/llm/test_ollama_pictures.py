"""Tests of the local plug's call with pictures, against a fake Ollama server.

The pictures go only on the last message, the user's, as the standard
base64 of their bytes, with no prefix; there is no schema; the options are
those of a call without pictures; the answer is read as any other. A call in
the wrong shape is refused before anything is sent. The picture bytes are
only the first bytes of a PNG or JPEG file, made up here.
"""

from __future__ import annotations

import base64

import pytest

from ledger_hand.llm.ollama import OllamaModel
from ledger_hand.llm.ollama_request import chat_body, picture_body
from ledger_hand.ports import (
    FinishReason,
    Message,
    ModelError,
    ModelErrorKind,
    ModelParameters,
    ModelPort,
    Picture,
    PictureKind,
    Role,
)
from ledger_hand.settings import DEFAULT_MODEL
from tests.llm.fake_server import SETTINGS, FakeClock, FakeServer, chat_reply, json_response

# The last bytes hold a "/" in the standard alphabet, which the URL-safe one writes "_".
PNG = Picture(b"\x89PNG\r\n\x1a\n invented\xfb\xff", PictureKind.PNG)
JPEG = Picture(b"\xff\xd8\xff\xe0 invented", PictureKind.JPEG)
ASKED = [
    Message(Role.SYSTEM, "You read the text on an invented card, as it stands."),
    Message(Role.USER, "Read the card."),
]
UNUSUAL = ModelParameters(
    temperature=0.7, top_p=0.8, max_reply_tokens=77, context_tokens=3333, timeout_seconds=9.5
)


def plug(server: FakeServer, clock: FakeClock | None = None) -> OllamaModel:
    if clock is None:
        return OllamaModel(SETTINGS, transport=server.transport)
    return OllamaModel(SETTINGS, transport=server.transport, clock=clock)


def answered(content: str = "Card: invented", **fields: object) -> FakeServer:
    return FakeServer([json_response(200, chat_reply(content, **fields))])


def sent_body(server: FakeServer) -> dict[str, object]:
    sent = server.sent_json()
    assert isinstance(sent, dict)
    return sent


# --- what is sent ------------------------------------------------------------


def test_the_pictures_go_on_the_last_message_as_standard_base64_with_no_prefix() -> None:
    server = answered()

    plug(server).chat_with_pictures(ASKED, [PNG, JPEG])

    messages = sent_body(server)["messages"]
    assert messages == [
        {"role": "system", "content": ASKED[0].content},
        {
            "role": "user",
            "content": ASKED[1].content,
            "images": [
                base64.b64encode(PNG.data).decode("ascii"),
                base64.b64encode(JPEG.data).decode("ascii"),
            ],
        },
    ]
    first = messages[1]["images"][0]  # type: ignore[index]
    assert "/" in first
    assert first != base64.urlsafe_b64encode(PNG.data).decode("ascii")
    assert not first.startswith("data:")
    assert base64.b64decode(first, validate=True) == PNG.data


def test_the_media_type_is_not_sent() -> None:
    server = answered()

    plug(server).chat_with_pictures(ASKED, [PNG])

    text = server.requests[0].content.decode("utf-8")
    assert "image/png" not in text
    assert "mime" not in text.lower()


def test_there_is_no_schema_and_the_options_are_those_of_a_call_without_pictures() -> None:
    server = FakeServer([json_response(200, chat_reply()), json_response(200, chat_reply())])

    plug(server).chat_with_pictures(ASKED, [PNG], parameters=UNUSUAL)
    plug(server).chat(ASKED, parameters=UNUSUAL)

    with_pictures, without = server.sent_json(0), server.sent_json(1)
    assert isinstance(with_pictures, dict) and isinstance(without, dict)
    assert set(with_pictures) == {"model", "messages", "stream", "options"}
    assert "format" not in with_pictures
    assert with_pictures["options"] == without["options"]
    assert with_pictures["options"] == {
        "temperature": 0.7,
        "top_p": 0.8,
        "num_predict": 77,
        "num_ctx": 3333,
    }
    assert with_pictures["model"] == DEFAULT_MODEL
    assert with_pictures["stream"] is False


def test_the_body_with_pictures_is_the_body_without_them_but_for_the_images() -> None:
    with_pictures = picture_body("m", ASKED, [PNG], UNUSUAL)
    without = chat_body("m", ASKED, None, UNUSUAL)

    messages = with_pictures["messages"]
    assert isinstance(messages, list)
    images = messages[-1].pop("images")
    assert images == [base64.b64encode(PNG.data).decode("ascii")]
    assert with_pictures == without
    assert list(with_pictures) == list(without)


def test_without_parameters_the_defaults_are_sent_and_the_time_allowed_is_used() -> None:
    server = answered()

    plug(server).chat_with_pictures(ASKED, [PNG])

    assert sent_body(server)["options"] == {
        "temperature": SETTINGS.temperature,
        "top_p": SETTINGS.top_p,
        "num_predict": SETTINGS.max_reply_tokens,
        "num_ctx": SETTINGS.context_tokens,
    }
    assert server.requests[0].extensions["timeout"]["read"] == SETTINGS.timeout_seconds


# --- what comes back ------------------------------------------------------------


def test_the_reply_comes_back_with_its_record_as_any_other() -> None:
    server = answered("Side: Buy")

    reply = plug(server, FakeClock(step=0.5)).chat_with_pictures(ASKED, [PNG])

    assert reply.text == "Side: Buy"
    assert reply.record.model == DEFAULT_MODEL
    assert reply.record.prompt_tokens == 44
    assert reply.record.reply_tokens == 14
    assert reply.record.finish is FinishReason.STOPPED
    assert reply.record.elapsed_seconds > 0


def test_a_reply_cut_off_says_so() -> None:
    server = answered("Side: Bu", done_reason="length")

    reply = plug(server).chat_with_pictures(ASKED, [PNG])

    assert reply.record.finish is FinishReason.LENGTH_LIMIT


@pytest.mark.parametrize(
    "fields",
    [{"content": ""}, {"content": "  \n"}, {"content": "Side: Buy", "done": False}],
    ids=["empty", "blank", "unfinished"],
)
def test_an_empty_or_unfinished_reply_is_malformed(fields: dict[str, object]) -> None:
    rest = dict(fields)
    content = str(rest.pop("content"))
    server = answered(content, **rest)

    with pytest.raises(ModelError) as caught:
        plug(server).chat_with_pictures(ASKED, [PNG])

    assert caught.value.kind is ModelErrorKind.MALFORMED_REPLY


def test_a_model_that_cannot_see_pictures_is_a_refused_request() -> None:
    # What Ollama answered when it was sent a picture for a model with no vision.
    said = {
        "error": {
            "code": 400,
            "message": "Multimodal data provided, but model does not support multimodal requests.",
            "type": "invalid_request_error",
        }
    }
    server = FakeServer([json_response(400, said)])

    with pytest.raises(ModelError) as caught:
        plug(server).chat_with_pictures(ASKED, [PNG])

    assert caught.value.kind is ModelErrorKind.SERVER_ERROR
    assert caught.value.status == 400


def test_a_missing_model_is_said_as_for_any_other_call() -> None:
    server = FakeServer([json_response(404, {"error": "model 'invented' not found"})])

    with pytest.raises(ModelError) as caught:
        plug(server).chat_with_pictures(ASKED, [PNG])

    assert caught.value.kind is ModelErrorKind.MODEL_NOT_FOUND


def test_the_plug_fits_the_model_port() -> None:
    model: ModelPort = plug(answered("red"))

    assert model.chat_with_pictures([Message(Role.USER, "Which colour?")], [PNG]).text == "red"


# --- calls in the wrong shape --------------------------------------------------------


@pytest.mark.parametrize(
    ("messages", "pictures", "error"),
    [
        ([Message(Role.SYSTEM, "Read it.")], [PNG], ValueError),
        ([Message(Role.USER, "Read it."), Message(Role.ASSISTANT, "Yes.")], [PNG], ValueError),
        (ASKED, [], ValueError),
        (ASKED, (), ValueError),
        (ASKED, [PNG.data], TypeError),
        (ASKED, PNG.data, TypeError),
        (ASKED, PNG, TypeError),
        (ASKED, [PNG, "picture"], TypeError),
        ([], [PNG], ValueError),
        ("Read it.", [PNG], TypeError),
    ],
)
def test_a_call_in_the_wrong_shape_is_refused_before_anything_is_sent(
    messages: object, pictures: object, error: type[Exception]
) -> None:
    server = FakeServer([])

    with pytest.raises(error):
        plug(server).chat_with_pictures(messages, pictures)  # type: ignore[arg-type]

    assert server.requests == []


def test_a_last_message_that_is_not_the_users_is_named_in_the_refusal() -> None:
    server = FakeServer([])

    with pytest.raises(ValueError, match="must be the user's, not the assistant's"):
        plug(server).chat_with_pictures(
            [Message(Role.USER, "Read it."), Message(Role.ASSISTANT, "Yes.")], [PNG]
        )
