"""Tests of the two stand-ins for the model port answering calls with pictures.

The scripted model takes the next step of its one script for a call with
pictures too, and records the pictures; the routed model answers every
call with pictures from a script of its own, and a call after the last one
scripted fails the test. Calls without pictures are as before.
"""

from __future__ import annotations

import pytest

from ledger_hand.extraction.reply_table import REPLY_TABLE
from ledger_hand.ports import (
    Message,
    ModelError,
    ModelErrorKind,
    ModelParameters,
    ModelPort,
    Picture,
    PictureKind,
    Role,
)
from tests.fakes.routed_model import RoutedModel
from tests.fakes.scripted_model import RecordedCall, ScriptedModel, ScriptExhaustedError

PNG = Picture(b"\x89PNG\r\n\x1a\n invented", PictureKind.PNG)
JPEG = Picture(b"\xff\xd8\xff\xe0 invented", PictureKind.JPEG)
ASKED = [Message(Role.SYSTEM, "Read the invented card."), Message(Role.USER, "Read it.")]
PARAMETERS = ModelParameters(
    temperature=0.0, top_p=1.0, max_reply_tokens=32, context_tokens=512, timeout_seconds=3
)


def read(model: ModelPort, *pictures: Picture) -> str:
    """Code under test only knows the port; this checks the fakes fit it."""
    return model.chat_with_pictures(ASKED, list(pictures)).text


def test_the_scripted_model_records_the_pictures_and_takes_the_same_script() -> None:
    model = ScriptedModel(["read", "chatted"])

    assert model.chat_with_pictures(ASKED, [PNG, JPEG], parameters=PARAMETERS).text == "read"
    assert model.chat([Message(Role.USER, "hello")]).text == "chatted"

    assert model.calls == [
        RecordedCall(tuple(ASKED), None, PARAMETERS, (PNG, JPEG)),
        RecordedCall((Message(Role.USER, "hello"),), None, None),
    ]
    assert model.calls[1].pictures == ()
    assert model.steps_left == 0


def test_the_scripted_model_raises_a_scripted_error_for_a_call_with_pictures() -> None:
    error = ModelError(ModelErrorKind.TIMED_OUT, "slow")
    model = ScriptedModel([error])

    with pytest.raises(ModelError) as caught:
        read(model, PNG)

    assert caught.value is error


def test_a_call_with_pictures_past_the_script_fails_the_test() -> None:
    model = ScriptedModel(["one"])
    read(model, PNG)

    with pytest.raises(ScriptExhaustedError, match="with pictures"):
        read(model, PNG)


def test_the_scripted_model_refuses_a_call_in_the_wrong_shape_without_taking_a_step() -> None:
    model = ScriptedModel(["kept"])

    with pytest.raises(ValueError):
        model.chat_with_pictures([Message(Role.SYSTEM, "Read it.")], [PNG])
    with pytest.raises(ValueError):
        model.chat_with_pictures(ASKED, [])

    assert model.calls == []
    assert model.steps_left == 1


def test_the_routed_model_answers_calls_with_pictures_from_their_own_script() -> None:
    model = RoutedModel(pictures=["read one", "read two"], extraction=["[]"])

    assert read(model, PNG) == "read one"
    assert model.chat(ASKED, reply_schema=REPLY_TABLE).text == "[]"
    assert read(model, JPEG) == "read two"

    assert [call.pictures for call in model.pictures.calls] == [(PNG,), (JPEG,)]
    assert len(model.extraction.calls) == 1
    assert model.screen.calls == []


def test_the_routed_model_with_no_pictures_scripted_fails_a_call_with_pictures() -> None:
    model = RoutedModel()

    with pytest.raises(ScriptExhaustedError):
        read(model, PNG)
