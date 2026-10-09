"""Where a key stands in a text, in whatever known way a server wrote it back.

``key_spans`` gives the stretches of a text that are the key, as pairs of
offsets, for ``error_text`` to hide. A server that repeats the key does not
always repeat it as it was sent. It may write it inside a JSON string, where
a quote or a backslash gets a backslash in front (twice over, when that JSON
is itself put in a string), any character may become ``\\uXXXX`` and a
slash may become ``\\/``; in an address, where characters become ``%XX`` in
either case; or in an HTML page, where ``&``, ``<``, ``>`` and quotes become
entities, named or numbered.

How it is found. The key is looked for as it was sent. Then the text is read
once for each way of writing in ``WAYS``, in a single pass from left to
right that never goes back: each pass reads a run of backslashes as
nothing, and reads its own escapes (``\\uXXXX``, ``%XX``, or an entity) as
the character they stand for. The key, with its own backslashes left out,
is looked for in what the pass read, with an ordinary search, and each place
found is mapped back to the stretch of the text it was read from. A pass
runs only when the text holds what its escapes start with. So the time taken
grows in step with the length of the text, whatever the text holds: nothing
here tries the same characters over and over.

What that costs. The key's own backslashes are left out of the comparison,
so the key written with more backslashes, or with none, is hidden too; and
so are backslashes just before a key, and, for a key that ends in a
backslash, just after it. Within one pass the characters written as they are
and those written in that pass's escapes may be mixed; escapes of two
different passes within one key are not looked for. All of it errs on the
side of hiding more.

This module only finds; it changes no text.

Names defined here: ``Way``, ``WAYS``, ``key_spans``.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass

_BACKSLASH = "\\"
_NAMED = {"amp": "&", "lt": "<", "gt": ">", "quot": '"', "apos": "'"}
_LARGEST_CHARACTER = 0x10FFFF


@dataclass(frozen=True)
class Way:
    """One way of writing text: the units it writes some characters as, and how to read one.

    ``starts`` are the strings at least one of which a text must hold for the
    way to be worth reading. ``read`` gives the character a unit stands for,
    nothing for a backslash, or the unit itself when it stands for no
    character (then it is read as it is written).
    """

    name: str
    starts: tuple[str, ...]
    units: re.Pattern[str]
    read: Callable[[re.Match[str]], str]


def _backslash_or(character: str) -> str:
    """A character as a pass reads it: a backslash is left out, like the key's own."""
    return "" if character == _BACKSLASH else character


def _read_escaped(_unit: re.Match[str]) -> str:
    return ""


def _read_json(unit: re.Match[str]) -> str:
    code = unit.group(1)
    return "" if code is None else _backslash_or(chr(int(code, 16)))


def _read_percent(unit: re.Match[str]) -> str:
    code = unit.group(1)
    if code is None:
        return ""
    value = int(code, 16)
    # A byte above 127 is part of a longer character; a key holds none.
    return unit.group(0) if value > 0x7F else _backslash_or(chr(value))


def _read_html(unit: re.Match[str]) -> str:
    named, decimal, hexadecimal = unit.group(1, 2, 3)
    if named is not None:
        return _NAMED[named]
    if decimal is None and hexadecimal is None:
        return ""
    value = int(decimal, 10) if decimal is not None else int(hexadecimal, 16)
    return unit.group(0) if value > _LARGEST_CHARACTER else _backslash_or(chr(value))


# Each pattern matches a run of backslashes whole, so no unit is ever tried
# again from inside a run; every other unit has a fixed longest length.
WAYS = (
    Way("escaped", (_BACKSLASH,), re.compile(r"\\+"), _read_escaped),
    Way("json", ("\\u", "\\U"), re.compile(r"\\+(?:[uU]([0-9a-fA-F]{4}))?"), _read_json),
    Way("percent", ("%",), re.compile(r"\\+|%([0-9a-fA-F]{2})"), _read_percent),
    Way(
        "html",
        ("&",),
        re.compile(r"\\+|&(?:(amp|lt|gt|quot|apos)|#([0-9]{1,7})|#[xX]([0-9a-fA-F]{1,6}));"),
        _read_html,
    ),
)


def key_spans(text: str, key: str) -> list[tuple[int, int]]:
    """Every stretch of ``text`` that is ``key`` in a known way of writing, merged, in order."""
    if not key:
        return []
    spans = list(_as_sent(text, key))
    if key.replace(_BACKSLASH, ""):
        for way in WAYS:
            if any(start in text for start in way.starts):
                spans += _written(text, way, key)
    return _merged(spans)


def _as_sent(text: str, key: str) -> Iterator[tuple[int, int]]:
    at = text.find(key)
    while at != -1:
        yield at, at + len(key)
        at = text.find(key, at + len(key))


def _written(text: str, way: Way, key: str) -> list[tuple[int, int]]:
    """The stretches of ``text`` that ``way`` reads as ``key`` without its backslashes."""
    wanted = key.replace(_BACKSLASH, "")
    # A key that ends in backslashes takes the units read as nothing after it too.
    ends_in_backslash = key.endswith(_BACKSLASH)
    read = way.units.sub(way.read, text)
    found = list(_as_sent(read, wanted))
    if not found:
        return []
    last = len(wanted) - 1
    needed: set[int] = set()
    for start, _ in found:
        needed.update({start, start + last})
        if start > 0:
            needed.add(start - 1)
        if ends_in_backslash and start + last + 1 < len(read):
            needed.add(start + last + 1)
    places = _places(text, way, sorted(needed))
    spans = []
    for start, _ in found:
        end = start + last
        # The unit before the key ends where the backslashes in front of it begin.
        begin = places[start - 1][1] if start > 0 else 0
        if not ends_in_backslash:
            finish = places[end][1]
        else:
            finish = places[end + 1][0] if end + 1 < len(read) else len(text)
        spans.append((begin, finish))
    return spans


def _places(text: str, way: Way, indices: list[int]) -> dict[int, tuple[int, int]]:
    """For each index of what ``way`` reads, the stretch of ``text`` it was read from."""
    places: dict[int, tuple[int, int]] = {}
    pending = iter(indices)
    want = next(pending, None)
    count = 0
    after = 0
    for unit in way.units.finditer(text):
        if want is None:
            break
        want, count = _copied(places, pending, want, count, after, unit.start())
        character = way.read(unit)
        if character == unit.group(0):
            want, count = _copied(places, pending, want, count, unit.start(), unit.end())
        else:
            while want is not None and want < count + len(character):
                places[want] = (unit.start(), unit.end())
                want = next(pending, None)
            count += len(character)
        after = unit.end()
    _copied(places, pending, want, count, after, len(text))
    return places


def _copied(
    places: dict[int, tuple[int, int]],
    pending: Iterator[int],
    want: int | None,
    count: int,
    begin: int,
    end: int,
) -> tuple[int | None, int]:
    """Place the wanted indices that fall in a stretch read as it is written."""
    while want is not None and want < count + (end - begin):
        offset = begin + (want - count)
        places[want] = (offset, offset + 1)
        want = next(pending, None)
    return want, count + (end - begin)


def _merged(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for begin, end in sorted(spans):
        if merged and begin < merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((begin, end))
    return merged
