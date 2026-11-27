"""The names of assets the user answered, kept in a plain file in the data folder.

When the assistant asked which asset a trade was, and the user answered a
code of the ledger, the name said and that code are kept here, so that
the same name is matched at once next time (``core.stock_names``). This
module reads and writes the file; it decides nothing about what is kept.

The file (``settings.DataPlaces.asset_names``) is JSON a person can read
and change by hand: a version, then one list for each kind of ledger,
each entry a name, a code and the day it was answered::

    {
      "version": 1,
      "demo": [{"name": "小可", "code": "KO", "day": "2026-11-20"}],
      "page": []
    }

The answers given on the demo ledger are used only there, and those given
on the ledger page only there: a name answered in a demonstration never
reaches the real ledger. Deleting the file forgets every answer.

- ``read_names`` gives the answers of one kind of ledger. A file that is
  not there gives none. A file that cannot be read, is not such JSON, is
  of a newer version, or holds an entry with a field missing, a code that
  cannot be written as a ledger code or a day that is not one, is used as
  far as it can be (a bad entry is passed over) and is never written to,
  so a file changed by hand is not overwritten. An entry whose name may
  not be remembered (``stock_names.can_remember``: "股票" written by hand)
  is passed over and kept as it is.
- ``remember`` keeps one answer: it reads the whole file first, takes out
  an earlier answer for the same name on the same kind of ledger (the
  later one wins), and writes a new file beside it, which then takes its
  name (``os.replace``); the file is never rewritten in place.

Why a plain file and not the book: the product owner asked for a small
plain file the user can open (decided on 2026-11-27).

Names defined here: ``NAMES_VERSION``, ``NamesFile``, ``NamesRead``,
``read_names`` and ``remember``.
"""

from __future__ import annotations

import json
import os
import uuid
from contextlib import suppress
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from ledger_hand.core.coins import spoken_key
from ledger_hand.core.ledger_limits import is_symbol
from ledger_hand.core.stock_names import RememberedName, can_remember
from ledger_hand.flows.standing import LedgerKind

# The file's own version; it is none of the ledger's four version numbers.
NAMES_VERSION = 1

# The key each kind of ledger's answers are kept under.
_KIND_KEYS = {LedgerKind.DEMO: "demo", LedgerKind.PAGE: "page"}


@dataclass(frozen=True)
class NamesFile:
    """The file of answers, and the kind of ledger whose answers are read and kept."""

    place: Path
    kind: LedgerKind


@dataclass(frozen=True)
class NamesRead:
    """The answers usable for one kind of ledger, and whether the file may be written."""

    names: tuple[RememberedName, ...]
    writable: bool


@dataclass(frozen=True)
class _Whole:
    """The file as read: its object (``None`` when there is no file) and its answers."""

    data: dict[str, Any] | None
    read: NamesRead


def read_names(names: NamesFile) -> NamesRead:
    """The answers kept for ``names.kind``, and whether the file may be written; never raises."""
    return _read(names).read


def remember(names: NamesFile, name: str, code: str, day: date) -> bool:
    """Keep ``name`` as ``code``, answered on ``day``; whether it was written.

    Nothing is written when the file may not be (``read_names``) or the
    folder cannot be written to.
    """
    whole = _read(names)
    if not whole.read.writable:
        return False
    data: dict[str, Any] = whole.data if whole.data is not None else {"version": NAMES_VERSION}
    for kind_key in _KIND_KEYS.values():
        data.setdefault(kind_key, [])
    key = _KIND_KEYS[names.kind]
    kept = [
        entry
        for entry in data[key]
        if not (isinstance(entry.get("name"), str) and spoken_key(entry["name"]) == name)
    ]
    kept.append({"name": name, "code": code, "day": day.isoformat()})
    data[key] = kept
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    try:
        _replace_with(names.place, text.encode("utf-8"))
    except OSError:
        return False
    return True


def _read(names: NamesFile) -> _Whole:
    try:
        raw = names.place.read_bytes()
    except FileNotFoundError:
        return _Whole(None, NamesRead((), writable=True))
    except OSError:
        return _Whole(None, NamesRead((), writable=False))
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return _Whole(None, NamesRead((), writable=False))
    version = data.get("version") if isinstance(data, dict) else None
    if not isinstance(data, dict) or type(version) is not int or version != NAMES_VERSION:
        return _Whole(None, NamesRead((), writable=False))
    lists = [data.get(key, []) for key in _KIND_KEYS.values()]
    if not all(isinstance(entries, list) for entries in lists):
        return _Whole(None, NamesRead((), writable=False))
    whole = all(_entry(entry) is not None for entries in lists for entry in entries)
    found = (_entry(entry) for entry in data.get(_KIND_KEYS[names.kind], []))
    usable = tuple(entry for entry in found if entry is not None and can_remember(entry.name))
    return _Whole(data, NamesRead(usable, writable=whole))


def _entry(entry: object) -> RememberedName | None:
    """One entry as an answer; ``None`` when a field is missing or not of its shape."""
    if not isinstance(entry, dict):
        return None
    name, code, day = entry.get("name"), entry.get("code"), entry.get("day")
    if not isinstance(name, str) or not isinstance(code, str) or not isinstance(day, str):
        return None
    if not is_symbol(code):
        return None
    try:
        answered = date.fromisoformat(day)
    except ValueError:
        return None
    return RememberedName(name=spoken_key(name), code=code, day=answered)


def _replace_with(place: Path, data: bytes) -> None:
    """Write ``data`` to a new file beside ``place``, which then takes its name."""
    place.parent.mkdir(parents=True, exist_ok=True)
    temporary = place.with_name(f".{place.name}.{uuid.uuid4().hex}.partial")
    try:
        with temporary.open("xb") as file:
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, place)
    finally:
        with suppress(OSError):
            temporary.unlink(missing_ok=True)
