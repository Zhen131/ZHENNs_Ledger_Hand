"""The two ends of time: the export answers for every trade the check accepts, and never fails.

A trade the check accepts is either exported or refused with a reason; the
export raises for none of them. These tests go to the edges of what a
``datetime`` can hold: 1 January of the year 1 and 31 December 9999, in every
time zone, at day, minute and second precision, and bookkeeping moments at
the same edges.
"""

from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from ledger_hand.core.coins import BUILT_IN_TABLE
from ledger_hand.core.stored import StoredTrade
from ledger_hand.core.trade import OccurredTime, Side, TimePrecision, TradeDraft, TradeRecord
from ledger_hand.core.validation import check_draft
from ledger_hand.export.backup import ExportProblem, ExportRefused, export_backup
from ledger_hand.export.file_name import backup_file_name
from tests.export.samples import APP_NAME, APP_VERSION, EXPORTED_AT, zones_taken

ZONES = zones_taken()
CREATED = datetime(2026, 10, 4, 7, 41, tzinfo=timezone.utc)
# Late enough that 31 December 9999 has begun in every zone from UTC-09:59 to
# UTC+14, and early enough that no zone's wall clock has passed the year 9999.
LATE_NOW = datetime(9999, 12, 31, 9, 59, tzinfo=timezone.utc)
EARLY_NOW = datetime(2026, 10, 4, 10, 0, tzinfo=timezone.utc)


def accepted(occurred: OccurredTime, now: datetime) -> TradeRecord | None:
    """The record the check makes of a plain buy at ``occurred``, or ``None``."""
    draft = TradeDraft(
        side=Side.BUY,
        coin="BTC",
        quantity=Decimal("1"),
        price=Decimal("1"),
        fee=Decimal("0"),
        occurred=occurred,
        raw_text=f"1 BTC at {occurred.value} in {occurred.time_zone}",
    )
    result = check_draft(draft, BUILT_IN_TABLE, now)
    return result if isinstance(result, TradeRecord) else None


def saved(records: list[TradeRecord]) -> list[StoredTrade]:
    return [
        StoredTrade(id=f"t{place:04d}", record=record, created_at=CREATED, updated_at=CREATED)
        for place, record in enumerate(records)
    ]


def export(trades: list[StoredTrade], **changes: Any) -> str | ExportRefused:
    arguments: dict[str, Any] = {
        "exported_at": EXPORTED_AT,
        "app_name": APP_NAME,
        "app_version": APP_VERSION,
    }
    arguments.update(changes)
    return export_backup(trades, BUILT_IN_TABLE, **arguments)


def instant(occurred: OccurredTime) -> timedelta:
    """When a trade happened as the ledger orders it, worked out on its own."""
    if isinstance(occurred.value, datetime):
        wall, offset = occurred.value.replace(tzinfo=None), occurred.value.utcoffset()
    else:
        wall = datetime.combine(occurred.value, time())
        offset = ZoneInfo(occurred.time_zone).utcoffset(wall)
    assert offset is not None
    return wall - datetime.min - offset


def assert_exported_in_order(trades: list[StoredTrade], text: str | ExportRefused) -> None:
    assert isinstance(text, str), text
    written = [entry["id"] for entry in json.loads(text)["ledgerData"]["trades"]]
    by_id = {trade.id: trade for trade in trades}
    assert sorted(written) == sorted(by_id)
    keys = [(instant(by_id[identifier].record.occurred), identifier) for identifier in written]
    assert keys == sorted(keys)


# --- the first day ----------------------------------------------------------


def test_the_first_day_there_is_exports_in_every_zone() -> None:
    records = [
        accepted(OccurredTime(date(1, 1, 1), TimePrecision.DAY, zone), EARLY_NOW) for zone in ZONES
    ]
    assert all(record is not None for record in records)
    trades = saved([record for record in records if record is not None])

    assert_exported_in_order(trades, export(trades))


@pytest.mark.parametrize(
    "zone", ["Asia/Tokyo", "Europe/Budapest", "Etc/GMT-14", "Pacific/Kiritimati"]
)
def test_the_first_day_east_of_utc_exports_alone(zone: str) -> None:
    record = accepted(OccurredTime(date(1, 1, 1), TimePrecision.DAY, zone), EARLY_NOW)
    assert record is not None

    text = export(saved([record]))

    assert isinstance(text, str)
    assert json.loads(text)["ledgerData"]["trades"][0]["occurredAt"] == "0001-01-01"


@pytest.mark.parametrize("precision", [TimePrecision.MINUTE, TimePrecision.SECOND])
def test_the_earliest_moments_in_every_zone_are_exported_or_refused_never_failed_on(
    precision: TimePrecision,
) -> None:
    second = 1 if precision is TimePrecision.SECOND else 0
    records = []
    for zone in ZONES:
        # Noon of 2 January of the year 1 on the zone's own wall clock; most
        # zones then had an offset with seconds in it.
        local = datetime(1, 1, 2, 12, 0, second, tzinfo=ZoneInfo(zone))
        record = accepted(OccurredTime(local, precision, zone), EARLY_NOW)
        assert record is not None, zone
        records.append(record)
    trades = saved(records)
    whole = [
        trade
        for trade in trades
        if not trade.record.occurred.value.utcoffset() % timedelta(minutes=1)  # type: ignore[union-attr]
    ]
    unwritable = {trade.id for trade in trades} - {trade.id for trade in whole}

    refused = export(trades)
    assert isinstance(refused, ExportRefused)
    assert {issue.problem for issue in refused.issues} == {ExportProblem.OFFSET_NOT_WHOLE_MINUTES}
    assert {issue.subject for issue in refused.issues} == unwritable
    assert_exported_in_order(whole, export(whole))


# --- the last day -----------------------------------------------------------


def test_the_last_day_there_is_exports_in_every_zone_the_check_accepts_it_in() -> None:
    records = [
        accepted(OccurredTime(date(9999, 12, 31), TimePrecision.DAY, zone), LATE_NOW)
        for zone in ZONES
    ]
    taken = [record for record in records if record is not None]
    assert len(taken) > len(ZONES) // 2
    trades = saved(taken)

    assert_exported_in_order(trades, export(trades))


@pytest.mark.parametrize("precision", [TimePrecision.MINUTE, TimePrecision.SECOND])
def test_the_latest_moments_in_every_zone_are_exported(precision: TimePrecision) -> None:
    second = 59 if precision is TimePrecision.SECOND else 0
    records = []
    for zone in ZONES:
        local = datetime(9999, 12, 30, 12, 0, second, tzinfo=ZoneInfo(zone))
        record = accepted(OccurredTime(local, precision, zone), LATE_NOW)
        assert record is not None, zone
        records.append(record)
    trades = saved(records)

    assert_exported_in_order(trades, export(trades))


# --- bookkeeping moments at the edges ---------------------------------------


def test_bookkeeping_moments_at_both_ends_of_utc_are_written() -> None:
    record = accepted(OccurredTime(date(2026, 10, 1), TimePrecision.DAY, "UTC"), EARLY_NOW)
    assert record is not None
    first = datetime(1, 1, 1, tzinfo=timezone.utc)
    last = datetime(9999, 12, 31, 23, 59, 59, 999_999, tzinfo=timezone.utc)
    trade = StoredTrade(id="t", record=record, created_at=first, updated_at=last)

    text = export([trade], exported_at=last)

    assert isinstance(text, str)
    document = json.loads(text)
    assert document["exportedAt"] == "9999-12-31T23:59:59Z"
    entry = document["ledgerData"]["trades"][0]
    assert (entry["createdAt"], entry["updatedAt"]) == (
        "0001-01-01T00:00:00Z",
        "9999-12-31T23:59:59Z",
    )


@pytest.mark.parametrize(
    "moment",
    [
        datetime(1, 1, 1, 0, 30, tzinfo=timezone(timedelta(hours=1))),
        datetime(9999, 12, 31, 23, 30, tzinfo=timezone(timedelta(hours=-1))),
    ],
)
def test_a_moment_outside_the_years_utc_can_hold_is_refused_where_it_comes_in(
    moment: datetime,
) -> None:
    record = accepted(OccurredTime(date(2026, 10, 1), TimePrecision.DAY, "UTC"), EARLY_NOW)
    assert record is not None
    fine = datetime(2026, 10, 4, tzinfo=timezone.utc)

    with pytest.raises(ValueError, match="outside the years UTC can hold"):
        StoredTrade(id="t", record=record, created_at=moment, updated_at=moment)
    with pytest.raises(ValueError, match="cannot be written in UTC"):
        export(saved([record]), exported_at=moment)
    with pytest.raises(ValueError, match="cannot be written in UTC"):
        backup_file_name(moment)
    assert isinstance(export(saved([record]), exported_at=fine), str)
