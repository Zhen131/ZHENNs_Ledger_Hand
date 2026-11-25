"""Recording from a screenshot: the order read off the picture, with the note typed beside it.

A screenshot shows the facts of an order; the note the person types beside
it may say more (a fee the screen leaves out, why they traded). The two are
kept apart until they are joined into one passage, which then goes the way
a typed passage goes (``recording.start``): judged, extracted, checked and
asked about. Four things are offered, so that a caller may show the text
read before going on, or go on at once:

- ``read_screenshot`` shows the vision model the picture and hands back what
  it read, or why nothing was (``extraction.picture_reading``). It makes no
  ``Progress``.
- ``joined_passage`` joins the text read and the note: the text first, then
  ``NOTE_SEPARATOR``, then the note, each with the blanks around it dropped
  and its own words unchanged; a blank note leaves the text alone.
- ``start_from_reading`` takes a reading that was made, the text to use (the
  text read, unless the person changed it) and the note, joins them, and
  starts the passage with the model that extracts. The call that read the
  picture comes first among the calls, and ``read-1`` first among the
  prompts, for the step ``Step.READING``. A reading that was not made is the
  caller's mistake, and is refused.
- ``start_from_screenshot`` does all of it: it checks the moment and the
  zone, reads the picture and, when it was read, starts from the reading
  with the text as read. When it was not, the passage ends there, failed at
  the reading step: its passage is the note, the calls and the prompt are
  the reading's, the model that extracts is never called and the book is
  never read.

The passage the trades are drafted from, and so each draft's raw text, is
the joined passage. The current moment and the zone are handed in, as for
``recording.start``; nothing here reads the clock or the machine's zone.
Nothing is written anywhere, and the picture is not kept.

Names defined here: ``NOTE_SEPARATOR``, ``read_screenshot``,
``joined_passage``, ``start_from_reading`` and ``start_from_screenshot``.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime

from ledger_hand.core.assets import BUILT_IN_ASSETS, AssetTable
from ledger_hand.core.zones import is_zone_name
from ledger_hand.extraction.picture_reading import (
    PictureNotRead,
    PictureRead,
    PictureReading,
    read_picture,
)
from ledger_hand.flows.progress import (
    DEFAULT_TUNING,
    Call,
    Failure,
    Progress,
    Setting,
    Stage,
    Step,
    Tuning,
)
from ledger_hand.flows.recording import start
from ledger_hand.ports import ModelPort, Picture, StoragePort

# Between the text read off the picture and the note: an empty line.
NOTE_SEPARATOR = "\n\n"


def read_screenshot(picture: Picture, vision_model: ModelPort) -> PictureReading:
    """What ``vision_model`` reads on ``picture``, or why it read nothing."""
    return read_picture(picture, vision_model)


def joined_passage(text: str, note: str) -> str:
    """The text read, then the note; each without the blanks around it."""
    for name, value in (("text", text), ("note", note)):
        if not isinstance(value, str):
            raise TypeError(f"the {name} is text, not {type(value).__name__}")
    read, typed = text.strip(), note.strip()
    if not typed:
        return read
    if not read:
        return typed
    return f"{read}{NOTE_SEPARATOR}{typed}"


def start_from_reading(
    reading: PictureRead,
    model: ModelPort,
    *,
    now: datetime,
    zone: str,
    text: str | None = None,
    note: str = "",
    assets: AssetTable = BUILT_IN_ASSETS,
    tuning: Tuning = DEFAULT_TUNING,
    book: StoragePort | None = None,
) -> Progress:
    """Start the passage joined from ``reading`` (or ``text``) and ``note``, with ``model``.

    ``text`` is the text to use, when the person changed what was read.
    Raises ``ValueError`` for a reading that was not made, and as
    ``recording.start`` does for the moment and the zone.
    """
    if isinstance(reading, PictureNotRead):
        raise ValueError("the picture was not read, so there is no text to start from")
    if not isinstance(reading, PictureRead):
        raise TypeError(f"a reading is a PictureRead, not {type(reading).__name__}")
    passage = joined_passage(reading.text if text is None else text, note)
    progress = start(passage, model, now=now, zone=zone, assets=assets, tuning=tuning, book=book)
    return dataclasses.replace(
        progress,
        calls=(*_reading_calls(reading), *progress.calls),
        prompts=((Step.READING, reading.version), *progress.prompts),
    )


def start_from_screenshot(
    picture: Picture,
    vision_model: ModelPort,
    model: ModelPort,
    *,
    now: datetime,
    zone: str,
    note: str = "",
    assets: AssetTable = BUILT_IN_ASSETS,
    tuning: Tuning = DEFAULT_TUNING,
    book: StoragePort | None = None,
) -> Progress:
    """Read ``picture`` with ``vision_model``, then start the passage with ``model``.

    When the picture is not read, the passage ends there, failed at the
    reading step, and ``model`` and ``book`` are never used.
    """
    _check_moment(now, zone)
    if not isinstance(note, str):
        raise TypeError(f"the note is text, not {type(note).__name__}")
    reading = read_screenshot(picture, vision_model)
    if isinstance(reading, PictureRead):
        return start_from_reading(
            reading, model, now=now, zone=zone, note=note, assets=assets, tuning=tuning, book=book
        )
    problems = tuple(problem.value for problem in reading.problems)
    return Progress(
        Stage.FAILED,
        note.strip(),
        Setting(now, zone, assets, tuning),
        failure=Failure(Step.READING, reading.error, problems),
        prompts=((Step.READING, reading.version),),
        calls=_reading_calls(reading),
    )


def _reading_calls(reading: PictureReading) -> tuple[Call, ...]:
    return tuple(Call(Step.READING, record) for record in reading.calls)


def _check_moment(now: object, zone: object) -> None:
    """Refuse a moment or a zone as ``recording.start`` does, before the picture is sent."""
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ValueError("the current moment must be a datetime that carries an offset")
    if not is_zone_name(zone):
        raise ValueError(f"not a time zone name: {zone!r}")
