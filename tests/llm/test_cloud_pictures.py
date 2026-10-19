"""Tests of the cloud plug's answer to a call with pictures: refused before anything is sent.

The refusal is the caller's mistake, not one of the six kinds of model
failure, so it is not tried again, even with the plug wrapped as the program
wraps it; and it names the setting that chooses the plug.
"""

from __future__ import annotations

import dataclasses

import pytest

from ledger_hand.llm.cloud import NO_PICTURES, CloudModel
from ledger_hand.llm.connect import connect_model
from ledger_hand.llm.retry import RetryingModel
from ledger_hand.ports import Message, ModelError, Picture, PictureKind, Role
from ledger_hand.settings import Plug, Variable
from tests.llm.fake_cloud import CLOUD_SETTINGS
from tests.llm.fake_server import FakeServer

PICTURE = Picture(b"\x89PNG\r\n\x1a\n invented", PictureKind.PNG)
ASKED = [Message(Role.USER, "Read the invented card.")]
CLOUD = dataclasses.replace(CLOUD_SETTINGS, plug=Plug.CLOUD, retries=3, retry_wait_seconds=1.0)


class Waits:
    def __init__(self) -> None:
        self.seconds: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.seconds.append(seconds)


def test_the_cloud_plug_refuses_pictures_before_sending_anything() -> None:
    server = FakeServer([])

    with pytest.raises(ValueError) as caught:
        CloudModel(CLOUD, transport=server.transport).chat_with_pictures(ASKED, [PICTURE])

    assert not isinstance(caught.value, ModelError)
    assert str(caught.value) == NO_PICTURES
    assert server.requests == []


def test_the_refusal_names_the_plug_setting_and_the_local_plug() -> None:
    assert Variable.PLUG.value in NO_PICTURES
    assert "LEDGER_HAND_MODEL_PLUG" in NO_PICTURES
    assert Plug.LOCAL.value in NO_PICTURES
    assert "sends no pictures" in NO_PICTURES


def test_wrapped_as_the_program_wraps_it_the_refusal_is_raised_once_with_no_wait() -> None:
    server = FakeServer([])
    waits = Waits()
    model = connect_model(CLOUD, transport=server.transport, sleep=waits)
    assert isinstance(model, RetryingModel)

    with pytest.raises(ValueError, match="sends no pictures"):
        model.chat_with_pictures(ASKED, [PICTURE])

    assert server.requests == []
    assert waits.seconds == []


@pytest.mark.parametrize(
    "pictures", [[], [PICTURE.data], "not pictures"], ids=["none", "bytes", "text"]
)
def test_the_refusal_comes_first_whatever_the_pictures(pictures: object) -> None:
    server = FakeServer([])

    with pytest.raises(ValueError, match="sends no pictures"):
        CloudModel(CLOUD, transport=server.transport).chat_with_pictures(
            ASKED,
            pictures,  # type: ignore[arg-type]
        )

    assert server.requests == []
