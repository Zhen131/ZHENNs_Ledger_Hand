"""The live checks of reading a picture: one picture in, words out; and thinking off taken.

Marked ``live_model``, so ordinary runs leave them out; ``scripts/check.sh
live`` runs them, with the settings read from the environment as the program
reads them, and the vision model the settings name
(``LEDGER_HAND_MODEL_VISION_NAME``). They need the model server running and
that model there: without it, they fail, and are not skipped. Both build the
plug with thinking set to off, whatever the default, and say so.

The picture is one plain colour, 64 by 64 pixels, drawn here in memory with
the standard library and never written anywhere: no screenshot, and no
picture file. The first check asks the model what colour it is and checks
only that a reply came back from the vision model; whether it named the
colour is printed, not judged. The second extracts one invented passage
with the vision model and thinking off, and checks only that the server did
not turn the request down (a server error with a status from 400 to 499):
what the model gave, an empty reply among them, is printed and not judged;
that is what the experiments measure.
"""

from __future__ import annotations

import binascii
import dataclasses
import struct
import sys
import time
import zlib
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from ledger_hand.extraction.extractor import ModelFailed, extract
from ledger_hand.llm.connect import connect_vision_model
from ledger_hand.ports import Message, ModelErrorKind, Picture, PictureKind, Role
from ledger_hand.settings import ModelSettings, Thinking, load_model_settings
from scripts.try_extraction import show_result
from tests.live.test_live_extraction import PASSAGES

pytestmark = pytest.mark.live_model

ZONE = "Europe/Budapest"
NOW = datetime(2026, 10, 5, 18, 30, tzinfo=ZoneInfo(ZONE))
SIDE = 64
RED = (220, 30, 30)
ASKED = "What colour is this picture? Answer with one word."


def plain_png(side: int, colour: tuple[int, int, int]) -> bytes:
    """A PNG of one colour, ``side`` pixels square, made in memory."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        checksum = binascii.crc32(kind + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum)

    rows = b"".join(b"\x00" + bytes(colour) * side for _ in range(side))
    header = struct.pack(">IIBBBBB", side, side, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


def thinking_off() -> ModelSettings:
    return dataclasses.replace(load_model_settings(), think=Thinking.OFF)


def test_a_picture_goes_in_and_words_come_back_from_the_vision_model() -> None:
    settings = thinking_off()
    picture = Picture(plain_png(SIDE, RED), PictureKind.PNG)
    assert struct.unpack(">II", picture.data[16:24]) == (SIDE, SIDE)
    model = connect_vision_model(settings)

    started = time.monotonic()
    reply = model.chat_with_pictures([Message(Role.USER, ASKED)], [picture])
    took = time.monotonic() - started

    print()
    print(f"vision model: {settings.vision_model}, thinking: {settings.think.value}")
    print(f"picture: {SIDE} by {SIDE} pixels, one colour, rgb {RED}, {len(picture.data)} bytes")
    print(f"reply: {reply.text!r}")
    print(f"named the colour red: {'red' in reply.text.lower()}")
    record = reply.record
    print(
        f"call: {record.model}, {record.elapsed_seconds:.2f} s, {record.prompt_tokens} tokens "
        f"read, {record.reply_tokens} written, {record.finish.value}; took {took:.2f} s"
    )
    assert reply.text.strip()
    assert record.model == settings.vision_model


def test_the_server_takes_thinking_off_from_the_vision_model() -> None:
    settings = thinking_off()
    passage = str(PASSAGES[0].values[0])
    model = connect_vision_model(settings)

    started = time.monotonic()
    result = extract(passage, model, now=NOW, zone=ZONE)
    took = time.monotonic() - started

    print()
    print(f"vision model: {settings.vision_model}, thinking: {settings.think.value}")
    show_result(result, passage, ZONE, sys.stdout)
    print(f"whole passage took {took:.2f} s")
    if isinstance(result, ModelFailed):
        error = result.error
        refused = (
            error.kind is ModelErrorKind.SERVER_ERROR
            and error.status is not None
            and 400 <= error.status <= 499
        )
        assert not refused, f"the server turned the request down: {error}"
