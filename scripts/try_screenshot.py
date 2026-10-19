"""Try a screenshot by hand: see the text the vision model reads off it, then the drafts.

    .venv/bin/python scripts/try_screenshot.py <picture> [--note "a sentence"]
    .venv/bin/python scripts/try_screenshot.py --help

The picture is a PNG or JPEG file, told apart by its first bytes, not by its
name. It is shown to the vision model the settings name
(``LEDGER_HAND_MODEL_VISION_NAME``; by default ``qwen3-vl:8b`` on this
machine's Ollama) with the reading prompt ``read-1``, through the local plug
only: settings that choose the cloud plug stop the script before anything is
sent. The text the model reads is printed, then the note, if one is given
with ``--note``. The two are joined into one passage
(``flows.screenshot.joined_passage``: the text read, then the note), which is
extracted as a typed passage is, with the model the settings name for
extraction (``LEDGER_HAND_MODEL_NAME``; by default ``qwen2.5:7b``) and the
prompt the product uses, and printed as ``try_extraction.py`` prints it: the
passage, the drafts field by field, the issues, and one line for each call
to the model. The call that read the picture has its line last. Each line
says which model answered, how long it took, how many tokens it read and
wrote, and why it stopped; the two models take turns in memory, so the time
of loading one shows in its line.

``--help`` or ``-h``, given alone, prints this text instead and reads
nothing else (no picture, no setting, no clock, no zone, no model).

The current moment is read from the machine's clock and the time zone is the
machine's own, read with ``tzlocal``, as ``try_extraction.py`` does. A zone
name the program does not take as it stands stops the script.

Only the one picture file named is read. Nothing is written to disk: the
picture, the text read and the passage are not kept anywhere.

Exit status: 0 the picture was read and its passage extracted (even when it
holds no trade), or this text was printed; 1 the picture was not read (the
model failed, or its reading was cut off at the longest reply), or the
passage was refused, every reply missed the table, or the model failed; 2
the script could not start: the arguments are wrong, the file cannot be read
or is not a PNG or JPEG file, a setting is wrong or the settings choose the
cloud plug, or the machine's zone is not a zone name the program takes.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO

from ledger_hand.extraction.extractor import Extracted, extract
from ledger_hand.extraction.picture_reading import PictureRead
from ledger_hand.flows.screenshot import joined_passage, read_screenshot
from ledger_hand.llm.connect import connect_model, connect_vision_model
from ledger_hand.ports import ModelPort, Picture, ReplyRecord, picture_kind
from ledger_hand.settings import SettingsError, load_model_settings

# The machine's zone is read, and a result printed, as by try_extraction.py.
try:
    from scripts.try_extraction import _machine_zone, show_result
except ModuleNotFoundError:  # run as a file: this script's own folder is on the path
    from try_extraction import _machine_zone, show_result  # type: ignore[import-not-found,no-redef]

_ASKING_FOR_HELP = frozenset({"--help", "-h"})
_NOTE = "--note"
_USAGE = 'usage: scripts/try_screenshot.py <picture> [--note "a sentence"]'
_INDENT = "  "


def main(
    arguments: Sequence[str],
    *,
    out: TextIO = sys.stdout,
    vision_model: ModelPort | None = None,
    model: ModelPort | None = None,
    now: datetime | None = None,
    zone: str | None = None,
) -> int:
    """Run the script; the keyword arguments stand in for the outside world in tests."""
    if len(arguments) == 1 and arguments[0] in _ASKING_FOR_HELP:
        print((__doc__ or _USAGE).strip(), file=out)
        return 0
    given = _arguments(arguments)
    if given is None:
        print(_USAGE, file=out)
        return 2
    path, note = given
    picture = _picture(path, out)
    if picture is None:
        return 2
    if zone is None:
        zone = _machine_zone()
        if zone is None:
            print("cannot tell the machine's time zone by a name the program takes", file=out)
            return 2
    if vision_model is None or model is None:
        models = _models(out)
        if models is None:
            return 2
        vision_model, model = models
    return _tried(picture, note, vision_model, model, now or datetime.now(timezone.utc), zone, out)


def _arguments(arguments: Sequence[str]) -> tuple[str, str] | None:
    """The picture's path and the note, or ``None`` when the arguments are not of that form."""
    paths: list[str] = []
    notes: list[str] = []
    words = list(arguments)
    while words:
        word = words.pop(0)
        if word == _NOTE:
            if not words:
                return None
            notes.append(words.pop(0))
        elif word.startswith(_NOTE + "="):
            notes.append(word.removeprefix(_NOTE + "="))
        else:
            paths.append(word)
    if len(paths) != 1 or len(notes) > 1:
        return None
    return paths[0], notes[0] if notes else ""


def _picture(path: str, out: TextIO) -> Picture | None:
    """The picture in the file at ``path``, or ``None``, said why, when there is none."""
    try:
        data = Path(path).read_bytes()
    except OSError as error:
        print(f"cannot read the picture: {error.strerror or error}", file=out)
        return None
    kind = picture_kind(data)
    if kind is None:
        print("not a picture this script reads: the file is neither PNG nor JPEG", file=out)
        return None
    return Picture(data, kind)


def _models(out: TextIO) -> tuple[ModelPort, ModelPort] | None:
    """The plug that reads the picture and the one that extracts, from the settings."""
    try:
        settings = load_model_settings()
        return connect_vision_model(settings), connect_model(settings)
    except SettingsError as error:
        print(f"setting refused: {error}", file=out)
        return None


def _tried(
    picture: Picture,
    note: str,
    vision_model: ModelPort,
    model: ModelPort,
    now: datetime,
    zone: str,
    out: TextIO,
) -> int:
    reading = read_screenshot(picture, vision_model)
    if not isinstance(reading, PictureRead):
        if reading.error is not None:
            print(f"picture not read: the model failed: {reading.error}", file=out)
        else:
            problems = "; ".join(problem.value for problem in reading.problems)
            print(f"picture not read: {problems}", file=out)
        _show_reading_calls(reading.calls, out)
        return 1
    print(f"text read ({reading.version}):", file=out)
    for line in reading.text.strip().splitlines():
        print(f"{_INDENT}{line}", file=out)
    print(f"note: {note.strip()!r}" if note.strip() else "note: none", file=out)
    passage = joined_passage(reading.text, note)
    result = extract(passage, model, now=now, zone=zone)
    show_result(result, passage, zone, out)
    _show_reading_calls(reading.calls, out)
    return 0 if isinstance(result, Extracted) else 1


def _show_reading_calls(calls: tuple[ReplyRecord, ...], out: TextIO) -> None:
    for call in calls:
        print(
            f"reading call: {call.model}, {call.elapsed_seconds:.2f} s, "
            f"{call.prompt_tokens} tokens read, {call.reply_tokens} written, {call.finish.value}",
            file=out,
        )


if __name__ == "__main__":
    # Text read with characters the terminal cannot show is still shown, escaped.
    sys.stdout.reconfigure(errors="backslashreplace")  # type: ignore[union-attr]
    sys.exit(main(sys.argv[1:]))
