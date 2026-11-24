"""What a version of the assistant's system prompt is, and the message it makes.

An ``AssistantPrompt`` is a name and the words of the system prompt, with
two marks where the program puts the current moment and the time zone in
(``NOW_MARK``, ``ZONE_MARK``). ``system_message`` fills them in: the moment
is written in the zone, with its weekday, to the minute, so that the model
reads "today" and "yesterday" from the user's point of view; it is never
asked to turn them into dates itself.

Names defined here: ``NOW_MARK``, ``ZONE_MARK``, ``AssistantPrompt`` and
``system_message``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from ledger_hand.ports import Message, Role

NOW_MARK = "<now>"
ZONE_MARK = "<zone>"


@dataclass(frozen=True, kw_only=True)
class AssistantPrompt:
    """One version of the system prompt: its name and its words, holding both marks once."""

    name: str
    words: str

    def __post_init__(self) -> None:
        for mark in (NOW_MARK, ZONE_MARK):
            if self.words.count(mark) != 1:
                raise ValueError(f"a prompt holds {mark} exactly once")


def system_message(prompt: AssistantPrompt, now: datetime, zone: str) -> Message:
    """The system message of ``prompt`` for the moment ``now`` in ``zone``."""
    if now.utcoffset() is None:
        raise ValueError("the current moment must carry an offset")
    local = now.astimezone(ZoneInfo(zone))
    written = local.strftime("%Y-%m-%d (%A) %H:%M")
    return Message(Role.SYSTEM, prompt.words.replace(NOW_MARK, written).replace(ZONE_MARK, zone))
