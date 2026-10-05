"""Time zone names: which names a time may be recorded in, and the zone each one names.

A name is taken only when it is, letter for letter, one of the names the
zone database lists, and is not one of the few listed names the ledger does
not know. Everything else is refused, whatever Python itself would load. On a
disk that does not tell capitals from small letters, "europe/budapest" or
"FACTORY" loads the same file as the listed name; the ledger knows zones only
by their exact names and refuses a trade recorded in any other spelling. A
name read from the machine is always spelled the listed way.

The list of names is read from the zone database once and then remembered.
It is the same database ``ZoneInfo`` reads a zone's rules from: reading it is
the one look outside the program the core allows itself, because the rules
of time zones are kept nowhere else. The clock and the machine's own zone are
still never read.

Names defined here: ``zone_named``, ``is_zone_name`` and ``NOT_ZONE_NAMES``.
"""

from __future__ import annotations

import functools
from zoneinfo import ZoneInfo, available_timezones

# Names that Python's zone database may list or load but that are not the
# time zone of any place, so a time is never recorded in one. On some systems
# "localtime" loads the machine's own zone, which the core must never read.
# "Factory" and "posixrules" are files of the zone database rather than
# zones; the ledger's runtime does not know them, and refuses a trade that
# names one.
NOT_ZONE_NAMES = frozenset({"localtime", "Factory", "posixrules"})


@functools.cache
def _taken_names() -> frozenset[str]:
    return frozenset(available_timezones()) - NOT_ZONE_NAMES


def is_zone_name(name: object) -> bool:
    """Whether ``name`` is exactly one of the zone names a time may be recorded in."""
    return isinstance(name, str) and name in _taken_names()


def zone_named(name: str) -> ZoneInfo:
    """The zone called exactly ``name``; ``ValueError`` for any other text."""
    if not is_zone_name(name):
        raise ValueError(f"not a time zone name: {name!r}")
    try:
        return ZoneInfo(name)
    except (KeyError, ValueError, OSError) as error:
        raise ValueError(f"not a time zone name: {name!r}") from error
