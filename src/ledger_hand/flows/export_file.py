"""Writing an export file without ever replacing a file that is already there.

The text is first written to a hidden temporary file in the same folder and
flushed to the disk; then the file is given its real name by a hard link,
which fails when that name is taken, and the temporary file is removed. So
the real name only ever holds a whole file, and a file of that name already
there (two exports within the same second are given the same name) is left
exactly as it was. Whatever fails, the temporary file is removed.

The folder is made when it is missing.

Names defined here: ``write_new_file``, ``NotWritten`` and ``WriteProblem``.
"""

from __future__ import annotations

import enum
import os
import uuid
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path


class WriteProblem(enum.Enum):
    """Why an export file was not written."""

    NAME_TAKEN = "a file of that name is already there; it was left as it is"
    CANNOT_WRITE = "the file could not be written"


@dataclass(frozen=True)
class NotWritten:
    """Why the file was not written, and what the system said."""

    problem: WriteProblem
    detail: str


def write_new_file(folder: Path, name: str, text: str) -> Path | NotWritten:
    """Write ``text`` as UTF-8 to a new file ``name`` in ``folder``; its path, or why not."""
    target = folder / name
    temporary = folder / f".{name}.{uuid.uuid4().hex}.partial"
    try:
        folder.mkdir(parents=True, exist_ok=True)
        _write_whole(temporary, text)
        try:
            os.link(temporary, target)
        except FileExistsError:
            return NotWritten(WriteProblem.NAME_TAKEN, str(target))
    except OSError as error:
        return NotWritten(WriteProblem.CANNOT_WRITE, str(error))
    finally:
        with suppress(OSError):
            temporary.unlink(missing_ok=True)
    return target


def _write_whole(path: Path, text: str) -> None:
    """A new file at ``path`` holding ``text``, on the disk before this returns."""
    with path.open("xb") as file:
        file.write(text.encode("utf-8"))
        file.flush()
        os.fsync(file.fileno())
