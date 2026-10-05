"""Tests of a stored trade: a finished record with its identifier and two moments."""

from __future__ import annotations

import dataclasses
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from ledger_hand.core.stored import StoredTrade
from ledger_hand.core.trade import OccurredTime, Side, TimePrecision, TradeRecord

BUDAPEST_ZONE = ZoneInfo("Europe/Budapest")

RECORD = TradeRecord(
    side=Side.BUY,
    coin="BTC",
    quantity=Decimal("0.02"),
    price=Decimal("94900"),
    total=Decimal("1898"),
    derived=None,
    fee=Decimal("2"),
    fee_coin="USDT",
    occurred=OccurredTime(date(2026, 10, 3), TimePrecision.DAY, "Europe/Budapest"),
    raw_text="昨天买了 0.02 BTC，94900，手续费 2 USDT",
)

CREATED = datetime(2026, 10, 4, 7, 41, tzinfo=timezone.utc)


def stored(**changes: Any) -> StoredTrade:
    values: dict[str, Any] = {
        "id": "trade-0001",
        "record": RECORD,
        "created_at": CREATED,
        "updated_at": CREATED,
    }
    values.update(changes)
    return StoredTrade(**values)


def test_a_stored_trade_keeps_what_it_was_given() -> None:
    later = CREATED + timedelta(minutes=5)

    trade = stored(updated_at=later)

    assert trade.id == "trade-0001"
    assert trade.record is RECORD
    assert trade.created_at == CREATED
    assert trade.updated_at == later


def test_a_stored_trade_cannot_be_changed() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        stored().id = "other"  # type: ignore[misc]


def test_creation_and_change_may_be_the_same_moment() -> None:
    assert stored(updated_at=CREATED).updated_at == CREATED


def test_moments_in_different_zones_are_compared_as_instants() -> None:
    # 09:41 in Budapest is 07:41 in UTC: the same instant, not two hours later.
    same_instant = datetime(2026, 10, 4, 9, 41, tzinfo=BUDAPEST_ZONE)

    assert stored(updated_at=same_instant).updated_at == same_instant
    with pytest.raises(ValueError, match="changed before it was created"):
        stored(updated_at=same_instant - timedelta(seconds=1))


def test_a_change_before_the_creation_is_refused() -> None:
    with pytest.raises(ValueError, match="changed before it was created"):
        stored(updated_at=CREATED - timedelta(microseconds=1))


def test_the_hour_shown_twice_is_told_apart_by_its_instant() -> None:
    # 02:30 on 2025-10-26 happened twice in Budapest: first at +02:00, then
    # an hour later at +01:00. Compared by the wall clock alone they are equal.
    first = datetime(2025, 10, 26, 2, 30, tzinfo=BUDAPEST_ZONE, fold=0)
    second = datetime(2025, 10, 26, 2, 30, tzinfo=BUDAPEST_ZONE, fold=1)

    assert stored(created_at=first, updated_at=second).updated_at == second
    with pytest.raises(ValueError, match="changed before it was created"):
        stored(created_at=second, updated_at=first)


@pytest.mark.parametrize("name", ["created_at", "updated_at"])
def test_a_moment_without_an_offset_is_refused(name: str) -> None:
    naive = datetime(2026, 10, 4, 7, 41)

    with pytest.raises(ValueError, match=f"{name} must carry a time zone offset"):
        stored(**{name: naive})


@pytest.mark.parametrize(
    ("changes", "complaint"),
    [
        ({"id": 1}, "an identifier is text"),
        ({"record": None}, "holds a TradeRecord"),
        ({"created_at": "2026-10-04T07:41:00Z"}, "created_at must be a datetime"),
        ({"updated_at": date(2026, 10, 4)}, "updated_at must be a datetime"),
    ],
)
def test_values_of_the_wrong_kind_are_refused(changes: dict[str, Any], complaint: str) -> None:
    with pytest.raises(TypeError, match=complaint):
        stored(**changes)
