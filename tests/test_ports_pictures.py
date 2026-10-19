"""Tests of the picture shape and of the model port's call with pictures.

A picture is the bytes of a PNG or JPEG file and which of the two it is; it
is refused when the bytes are not bytes, are empty, or do not start the way
a file of the kind declared does. The bytes here are only the first bytes of
such files, made up in the test; no picture file is read or kept.
"""

from __future__ import annotations

import inspect

import pytest

from ledger_hand.ports import ModelPort, Picture, PictureKind, picture_kind

PNG_START = b"\x89PNG\r\n\x1a\n"
JPEG_START = b"\xff\xd8\xff"
PNG = PNG_START + b"\x00\x00\x00\rIHDR invented"
JPEG = JPEG_START + b"\xe0\x00\x10JFIF invented"


def test_the_kinds_are_png_and_jpeg_named_by_their_media_types() -> None:
    assert {kind.name: kind.value for kind in PictureKind} == {
        "PNG": "image/png",
        "JPEG": "image/jpeg",
    }


@pytest.mark.parametrize(("data", "kind"), [(PNG, PictureKind.PNG), (JPEG, PictureKind.JPEG)])
def test_a_picture_keeps_its_bytes_and_its_kind(data: bytes, kind: PictureKind) -> None:
    picture = Picture(data, kind)

    assert picture.data == data
    assert picture.kind is kind


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (PNG, PictureKind.PNG),
        (JPEG, PictureKind.JPEG),
        (PNG_START, PictureKind.PNG),
        (JPEG_START, PictureKind.JPEG),
        (b"GIF89a invented", None),
        (b"\x89PNG\r\n", None),
        (b"\xff\xd8", None),
        (b"", None),
        (b"plain text", None),
    ],
)
def test_the_kind_is_told_by_the_first_bytes(data: bytes, expected: PictureKind | None) -> None:
    assert picture_kind(data) is expected


@pytest.mark.parametrize("data", ["\x89PNG\r\n\x1a\n", bytearray(PNG), memoryview(PNG), None, 7])
def test_the_kind_of_anything_but_bytes_is_not_told(data: object) -> None:
    with pytest.raises(TypeError):
        picture_kind(data)  # type: ignore[arg-type]


@pytest.mark.parametrize("data", ["\x89PNG\r\n\x1a\n", bytearray(PNG), memoryview(PNG), None, 7])
def test_a_picture_is_bytes(data: object) -> None:
    with pytest.raises(TypeError, match="a picture is bytes"):
        Picture(data, PictureKind.PNG)  # type: ignore[arg-type]


@pytest.mark.parametrize("kind", ["image/png", "PNG", None])
def test_a_pictures_kind_is_a_picture_kind(kind: object) -> None:
    with pytest.raises(TypeError, match="PictureKind"):
        Picture(PNG, kind)  # type: ignore[arg-type]


def test_an_empty_picture_is_refused() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        Picture(b"", PictureKind.PNG)


@pytest.mark.parametrize(
    ("data", "kind"),
    [
        (JPEG, PictureKind.PNG),
        (PNG, PictureKind.JPEG),
        (b"GIF89a invented", PictureKind.PNG),
        (b"plain text", PictureKind.JPEG),
        (b" " + PNG, PictureKind.PNG),
    ],
)
def test_bytes_that_do_not_start_as_the_kind_declared_are_refused(
    data: bytes, kind: PictureKind
) -> None:
    with pytest.raises(ValueError, match="do not start as a file of"):
        Picture(data, kind)


def test_a_picture_is_shown_by_its_kind_and_size_not_its_bytes() -> None:
    shown = repr(Picture(PNG, PictureKind.PNG))

    assert shown == f"Picture(PNG, {len(PNG)} bytes)"
    assert "IHDR" not in shown


def test_a_picture_cannot_be_changed() -> None:
    picture = Picture(PNG, PictureKind.PNG)

    with pytest.raises(AttributeError):
        picture.data = JPEG  # type: ignore[misc]


def test_the_model_port_has_exactly_two_calls() -> None:
    calls = {
        name
        for name, member in vars(ModelPort).items()
        if inspect.isfunction(member) and not name.startswith("_")
    }

    assert calls == {"chat", "chat_with_pictures"}


def test_the_call_with_pictures_takes_messages_pictures_and_parameters_but_no_schema() -> None:
    signature = inspect.signature(ModelPort.chat_with_pictures)

    assert list(signature.parameters) == ["self", "messages", "pictures", "parameters"]
    assert signature.parameters["parameters"].kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["parameters"].default is None
