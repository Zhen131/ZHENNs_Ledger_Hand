"""Uploading a screenshot: the checks made before the vision model is shown it, then the reading.

``read_upload`` takes the bytes of a file the person uploaded, the settings
the parts were built from, the vision model, and a way to ask the model
server whether it has the vision model (``VisionModelCheck``). It goes step
by step, and stops at the first step that does not pass; each that does not
is an ``UploadProblem``:

1. the settings choose the cloud plug, which sends no pictures
   (``CLOUD_PLUG``);
2. the file is larger than the limit the settings name, in MB of
   ``BYTES_PER_MB`` bytes; a file of exactly the limit is taken
   (``TOO_LARGE``);
3. the file starts neither as a PNG nor as a JPEG, judged by its own first
   bytes (``ports.picture_kind``), never by its name or the type the browser
   gave; an empty file is neither (``NOT_A_PICTURE``);
4. the model server is asked whether it has the vision model: it does not
   (``VISION_MODEL_MISSING``), or it could not be asked
   (``VISION_MODEL_UNCHECKED``, with the ``ModelError`` that says how);
5. the picture is read (``screenshot.read_screenshot``): the vision model
   failed (``MODEL_FAILED``, with its ``ModelError``), read nothing
   (``EMPTY``), or reached the longest reply and was cut off (``CUT_OFF``).

The first three ask nothing of anyone, so a file that cannot be used, or a
plug that cannot send it, is said at once. The fourth sends no picture.

What was read comes back as ``UploadRead``, holding the reading itself
(``PictureRead``), so that the text can be shown to the person, changed,
and joined with a note (``screenshot.start_from_reading``). What was not
comes back as ``UploadNotRead``: the problem, the file's size and the limit,
and the model's error or the reading that was not made, when there is one.

An empty reading is told by the words the local plug's message holds for a
reply with blank text, ``EMPTY_REPLY_WORDS``, on a malformed reply: the plug
says an empty reply that way, the thinking of a model that spent the whole
reply on it among them, rather than with a kind of its own. A test ties the
words to the plug's and to those the model comparison counts by. A reading
that comes back as blank text is empty too.

The vision model and the check are handed in, as the model is for
``recording.start``; nothing here reads the clock, the machine's zone or the
environment, and the picture is not kept.

Names defined here: ``BYTES_PER_MB``, ``EMPTY_REPLY_WORDS``,
``VisionModelPresence``, ``VisionModelCheck``, ``UploadProblem``,
``UploadRead``, ``UploadNotRead``, ``UploadOutcome`` and ``read_upload``.
"""

from __future__ import annotations

import enum
from collections.abc import Callable
from dataclasses import dataclass

from ledger_hand.extraction.picture_reading import PictureNotRead, PictureRead, ReadingProblem
from ledger_hand.flows.screenshot import read_screenshot
from ledger_hand.ports import (
    ModelError,
    ModelErrorKind,
    ModelPort,
    Picture,
    PictureKind,
    picture_kind,
)
from ledger_hand.settings import ModelSettings, Plug

# One MB, as the settings count it, and as Streamlit counts its own upload limit.
BYTES_PER_MB = 1024 * 1024
# What the local plug's message says of a reply whose text is blank.
EMPTY_REPLY_WORDS = "has an empty reply"


class VisionModelPresence(enum.Enum):
    """Whether the model server has the vision model the settings name."""

    PRESENT = "the model server has the vision model"
    MISSING = "the model server does not have the vision model"


type VisionModelCheck = Callable[[], VisionModelPresence]
"""Asks the model server whether it has the vision model; raises ``ModelError`` when it cannot."""


class UploadProblem(enum.Enum):
    """Why an uploaded screenshot was not read; the value says it in words."""

    CLOUD_PLUG = "the cloud plug sends no pictures"
    TOO_LARGE = "the file is larger than the limit"
    NOT_A_PICTURE = "the file is neither a PNG nor a JPEG"
    VISION_MODEL_MISSING = "the model server does not have the vision model"
    VISION_MODEL_UNCHECKED = "the model server could not be asked for the vision model"
    MODEL_FAILED = "the vision model failed while reading"
    EMPTY = "the vision model read nothing"
    CUT_OFF = "the reading reached the longest reply and was cut off"


@dataclass(frozen=True)
class UploadRead:
    """The screenshot was read: what the vision model read on it."""

    reading: PictureRead


@dataclass(frozen=True)
class UploadNotRead:
    """Why the screenshot was not read, and what saying so needs.

    ``size_bytes`` is the size of the file and ``limit_mb`` the limit the
    settings name. ``error`` is the model's error, when the server could not
    be asked or the vision model failed; ``reading`` the reading that was not
    made, when the picture was sent.
    """

    problem: UploadProblem
    size_bytes: int
    limit_mb: int
    error: ModelError | None = None
    reading: PictureNotRead | None = None


UploadOutcome = UploadRead | UploadNotRead

# How each problem of a reply that came back is said here.
_READING_PROBLEMS = {ReadingProblem.CUT_OFF: UploadProblem.CUT_OFF}


def read_upload(
    data: bytes,
    settings: ModelSettings,
    *,
    vision_model: ModelPort | None,
    check: VisionModelCheck | None,
) -> UploadOutcome:
    """Check the uploaded ``data`` step by step and, when every step passes, read it.

    ``vision_model`` and ``check`` are ``None`` only for the cloud plug;
    for the local plug, a ``None`` is the caller's mistake and is refused.
    """
    if not isinstance(data, bytes):
        raise TypeError(f"an upload is bytes, not {type(data).__name__}")
    if not isinstance(settings, ModelSettings):
        raise TypeError(f"settings must be ModelSettings, not {type(settings).__name__}")
    size, limit = len(data), settings.screenshot_max_mb
    kind = picture_kind(data)
    problem = _before_asking(size, kind, settings)
    if problem is not None:
        return UploadNotRead(problem, size, limit)
    if vision_model is None or check is None or kind is None:
        raise ValueError("the local plug reads a screenshot with the vision model and its check")
    try:
        presence = check()
    except ModelError as error:
        return UploadNotRead(UploadProblem.VISION_MODEL_UNCHECKED, size, limit, error=error)
    if presence is not VisionModelPresence.PRESENT:
        return UploadNotRead(UploadProblem.VISION_MODEL_MISSING, size, limit)
    reading = read_screenshot(Picture(data, kind), vision_model)
    if isinstance(reading, PictureNotRead):
        return UploadNotRead(_not_read(reading), size, limit, error=reading.error, reading=reading)
    if not reading.text.strip():
        return UploadNotRead(UploadProblem.EMPTY, size, limit)
    return UploadRead(reading)


def _before_asking(
    size: int, kind: PictureKind | None, settings: ModelSettings
) -> UploadProblem | None:
    """The first of the steps that ask nothing of anyone not to pass; ``None`` when all do."""
    if settings.plug is not Plug.LOCAL:
        return UploadProblem.CLOUD_PLUG
    if size > settings.screenshot_max_mb * BYTES_PER_MB:
        return UploadProblem.TOO_LARGE
    if kind is None:
        return UploadProblem.NOT_A_PICTURE
    return None


def _not_read(reading: PictureNotRead) -> UploadProblem:
    """The problem of a reading that was not made: the model's error, else its first problem."""
    if reading.error is not None:
        return UploadProblem.EMPTY if _is_empty_reply(reading.error) else UploadProblem.MODEL_FAILED
    first, *_ = reading.problems
    return _READING_PROBLEMS[first]


def _is_empty_reply(error: ModelError) -> bool:
    """Whether ``error`` is the local plug's way of saying the reply was blank."""
    return error.kind is ModelErrorKind.MALFORMED_REPLY and EMPTY_REPLY_WORDS in error.message
