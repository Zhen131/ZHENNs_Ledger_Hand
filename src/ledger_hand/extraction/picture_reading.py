"""Reading a screenshot: the text of the order on it, as the model reads it out.

``read_picture`` shows the model one picture, with a version of the reading
prompt (``read-1``, in ``prompts.read``, unless another is handed in): its
instructions as the system message, and one user message, the version's
ask, with the picture on it. It hands back what was read (``PictureRead``):
the text as the model wrote it, the record of the call and the version's
name. Or it hands back why nothing was read (``PictureNotRead``): the model
failed, and its ``ModelError`` is kept as it was raised; or the reply
reached the longest reply and was cut off (``ReadingProblem.CUT_OFF``), and
a reading cut short is never passed on as if it were whole. Either way the
records of the calls made are kept, the one cut off among them.

What was read is the model's reply, untrusted like any other, and nothing
here can check it against the picture: there are no words of the person's
own to compare it with. It is handed on as text, to be shown to the person
and extracted as a typed passage is. One call is made; a reading is not
asked for again.

Nothing here reads the clock, and only the standard library, the core and
the ports are imported: the plug that sends the picture is handed in, and
the prompt's words reach it as messages.

Names defined here: ``ReadingProblem``, ``PictureRead``, ``PictureNotRead``,
``PictureReading`` and ``read_picture``.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

from ledger_hand.extraction.picture_prompt import PicturePromptVersion
from ledger_hand.extraction.prompts.read import READ_PROMPT
from ledger_hand.ports import (
    FinishReason,
    Message,
    ModelError,
    ModelPort,
    Picture,
    ReplyRecord,
    Role,
)


class ReadingProblem(enum.Enum):
    """Why a reply that came back is not a reading; the value says it in words."""

    CUT_OFF = "the reading reached the longest reply and was cut off"


@dataclass(frozen=True)
class PictureRead:
    """What the model read on the picture, the record of each call, and the version used."""

    text: str
    calls: tuple[ReplyRecord, ...]
    version: str


@dataclass(frozen=True)
class PictureNotRead:
    """Why nothing was read: the model's error, or the problems of its reply; and the calls."""

    error: ModelError | None
    problems: tuple[ReadingProblem, ...]
    calls: tuple[ReplyRecord, ...]
    version: str


PictureReading = PictureRead | PictureNotRead


def read_picture(
    picture: Picture, model: ModelPort, *, version: PicturePromptVersion = READ_PROMPT
) -> PictureReading:
    """Show ``model`` the picture and hand back the text it reads, or why there is none."""
    if not isinstance(picture, Picture):
        raise TypeError(f"a picture is a Picture, not {type(picture).__name__}")
    if not isinstance(version, PicturePromptVersion):
        raise TypeError(f"a version is a PicturePromptVersion, not {type(version).__name__}")
    messages = (Message(Role.SYSTEM, version.instructions), Message(Role.USER, version.ask))
    try:
        reply = model.chat_with_pictures(messages, (picture,))
    except ModelError as error:
        return PictureNotRead(error, (), (), version.name)
    if reply.record.finish is FinishReason.LENGTH_LIMIT:
        return PictureNotRead(None, (ReadingProblem.CUT_OFF,), (reply.record,), version.name)
    return PictureRead(reply.text, (reply.record,), version.name)
