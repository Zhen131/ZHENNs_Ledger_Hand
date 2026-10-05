"""Tests of the bookkeeping moments: UTC, a ``T``, to the second, a ``Z``."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from ledger_hand.export.moments import write_moment


@pytest.mark.parametrize(
    ("moment", "written"),
    [
        (datetime(2026, 10, 4, 7, 41, tzinfo=timezone.utc), "2026-10-04T07:41:00Z"),
        (datetime(2026, 10, 4, 9, 41, tzinfo=ZoneInfo("Europe/Budapest")), "2026-10-04T07:41:00Z"),
        (datetime(2026, 10, 4, 3, 41, tzinfo=ZoneInfo("America/New_York")), "2026-10-04T07:41:00Z"),
        (datetime(2026, 1, 1, 5, 0, tzinfo=ZoneInfo("Asia/Shanghai")), "2025-12-31T21:00:00Z"),
        (
            datetime(2026, 10, 4, 7, 41, tzinfo=timezone(timedelta(hours=5, minutes=45))),
            "2026-10-04T01:56:00Z",
        ),
        (datetime(999, 3, 1, 0, 0, tzinfo=timezone.utc), "0999-03-01T00:00:00Z"),
    ],
)
def test_a_moment_is_written_in_utc_to_the_second(moment: datetime, written: str) -> None:
    assert write_moment(moment) == written


def test_a_part_of_a_second_is_dropped_not_rounded() -> None:
    moment = datetime(2026, 10, 4, 7, 41, 59, 999_999, tzinfo=timezone.utc)

    assert write_moment(moment) == "2026-10-04T07:41:59Z"


def test_a_moment_without_an_offset_is_refused() -> None:
    with pytest.raises(ValueError, match="needs a time zone offset"):
        write_moment(datetime(2026, 10, 4, 7, 41))
