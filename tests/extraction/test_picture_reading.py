"""Tests of the step that reads a screenshot, with a scripted model and no real picture.

The model is shown the picture on one user message, the version's ask,
after the version's instructions as the system message; what it writes comes
back as it is, with the record of the call and the version's name. A model
failure comes back with its error, and a reply cut off at the longest reply
comes back as not read, with its call. The picture bytes are only the first
bytes of a PNG file, made up here; the replies are invented text.
"""

from __future__ import annotations

import pytest

from ledger_hand.extraction.picture_prompt import PicturePromptVersion
from ledger_hand.extraction.picture_reading import (
    PictureNotRead,
    PictureRead,
    ReadingProblem,
    read_picture,
)
from ledger_hand.extraction.prompts.read import READ_PROMPT
from ledger_hand.ports import (
    FinishReason,
    Message,
    ModelError,
    ModelErrorKind,
    ModelReply,
    Picture,
    PictureKind,
    ReplyRecord,
    Role,
)
from tests.fakes.routed_model import RoutedModel
from tests.fakes.scripted_model import ScriptedModel

PICTURE = Picture(b"\x89PNG\r\n\x1a\n invented", PictureKind.PNG)
READ = "Side: Buy\nPair: SOL/USDT\nFilled: 2 SOL\nPrice: 150 USDT\n"


def record(finish: FinishReason) -> ReplyRecord:
    return ReplyRecord(
        model="invented-vl",
        elapsed_seconds=3.5,
        prompt_tokens=1100,
        reply_tokens=40,
        finish=finish,
    )


def test_the_picture_goes_with_the_ask_after_the_instructions() -> None:
    model = ScriptedModel([READ])

    read_picture(PICTURE, model)

    (call,) = model.calls
    assert call.messages == (
        Message(Role.SYSTEM, READ_PROMPT.instructions),
        Message(Role.USER, READ_PROMPT.ask),
    )
    assert call.pictures == (PICTURE,)
    assert call.reply_schema is None
    assert call.parameters is None


def test_what_was_read_comes_back_as_written_with_its_call_and_version() -> None:
    reply = ModelReply(text=READ, record=record(FinishReason.STOPPED))

    reading = read_picture(PICTURE, ScriptedModel([reply]))

    assert reading == PictureRead(READ, (reply.record,), "read-1")


@pytest.mark.parametrize("finish", [FinishReason.STOPPED, FinishReason.NOT_REPORTED])
def test_a_reply_not_marked_cut_off_is_a_reading(finish: FinishReason) -> None:
    reply = ModelReply(text=READ, record=record(finish))

    assert isinstance(read_picture(PICTURE, ScriptedModel([reply])), PictureRead)


def test_a_reply_cut_off_is_not_passed_on_and_keeps_its_call() -> None:
    cut = ModelReply(text="Side: Buy\nPair: SO", record=record(FinishReason.LENGTH_LIMIT))

    reading = read_picture(PICTURE, ScriptedModel([cut]))

    assert reading == PictureNotRead(None, (ReadingProblem.CUT_OFF,), (cut.record,), "read-1")
    assert ReadingProblem.CUT_OFF.value == "the reading reached the longest reply and was cut off"


@pytest.mark.parametrize(
    "kind",
    [ModelErrorKind.MALFORMED_REPLY, ModelErrorKind.SERVER_ERROR, ModelErrorKind.UNREACHABLE],
)
def test_a_model_failure_comes_back_with_its_error(kind: ModelErrorKind) -> None:
    error = ModelError(kind, "invented failure")

    reading = read_picture(PICTURE, ScriptedModel([error]))

    assert isinstance(reading, PictureNotRead)
    assert reading.error is error
    assert reading.problems == ()
    assert reading.calls == ()
    assert reading.version == "read-1"


def test_one_call_is_made_whatever_the_reply() -> None:
    model = ScriptedModel([ModelError(ModelErrorKind.MALFORMED_REPLY, "empty"), READ])

    read_picture(PICTURE, model)

    assert model.steps_left == 1


def test_another_version_may_be_handed_in() -> None:
    other = PicturePromptVersion(name="read-x", instructions="Read it all.", ask="Go on.")
    model = ScriptedModel([READ])

    reading = read_picture(PICTURE, model, version=other)

    assert isinstance(reading, PictureRead)
    assert reading.version == "read-x"
    assert model.calls[0].messages[1] == Message(Role.USER, "Go on.")


def test_the_routed_model_reads_from_its_pictures_script() -> None:
    model = RoutedModel(pictures=[READ])

    reading = read_picture(PICTURE, model)

    assert isinstance(reading, PictureRead)
    assert reading.text == READ
    assert model.extraction.calls == []


@pytest.mark.parametrize("picture", [PICTURE.data, None, "picture"])
def test_a_picture_must_be_a_picture(picture: object) -> None:
    model = ScriptedModel([READ])

    with pytest.raises(TypeError):
        read_picture(picture, model)  # type: ignore[arg-type]

    assert model.calls == []


def test_a_version_must_be_a_reading_prompt() -> None:
    with pytest.raises(TypeError):
        read_picture(PICTURE, ScriptedModel([READ]), version="read-1")  # type: ignore[arg-type]
