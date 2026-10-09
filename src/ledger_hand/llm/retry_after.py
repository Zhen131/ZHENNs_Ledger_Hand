"""How long a server asks to wait before the next call: its Retry-After header.

``seconds_to_wait`` reads the header's value in either of the two ways HTTP
allows: a number of seconds (``Retry-After: 2``), or a date
(``Retry-After: Wed, 21 Oct 2026 07:28:00 GMT``), counted from the moment
handed in, in seconds since the epoch. A date already past is no wait at
all. A value in neither form, or no header, gives ``None``: the server did
not say, and the caller waits as it would anyway.

HTTP writes whole seconds, but a number with a point (``1.5``) is taken
too: some services send one, and nothing is lost by reading it. A number
with more than nine digits before the point (over 31 years) is read as
``LONGEST_READ_SECONDS``: no one means it, but it surely means "not soon".

This module only reads the header. Whether to wait that long is for
``retry`` to decide.

Names defined here: ``RETRY_AFTER_HEADER``, ``LONGEST_READ_SECONDS``,
``seconds_to_wait``.
"""

from __future__ import annotations

import re
from datetime import UTC
from email.utils import parsedate_to_datetime

RETRY_AFTER_HEADER = "retry-after"
LONGEST_READ_SECONDS = 999_999_999.0

_SECONDS = re.compile(r"0*([0-9]+)(?:\.[0-9]+)?")


def seconds_to_wait(value: str | None, now: float) -> float | None:
    """The wait ``value`` asks for, in seconds from ``now``; ``None`` when it says none."""
    if value is None:
        return None
    text = value.strip()
    number = _SECONDS.fullmatch(text)
    if number is not None:
        return LONGEST_READ_SECONDS if len(number.group(1)) > 9 else float(text)
    try:
        when = parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError, OverflowError):
        return None
    if when.tzinfo is None:
        # HTTP dates are always in GMT; the old asctime form does not say so.
        when = when.replace(tzinfo=UTC)
    return max(0.0, when.timestamp() - now)
