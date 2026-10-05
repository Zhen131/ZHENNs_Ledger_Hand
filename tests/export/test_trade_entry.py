"""Tests of a trade's entry: the ledger's fields, in its order, written its way."""

from __future__ import annotations

import dataclasses
from datetime import date, datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from ledger_hand.core.numbers import write_number
from ledger_hand.core.stored import StoredTrade
from ledger_hand.core.trade import OccurredTime, Side, TimePrecision, TradeRecord
from ledger_hand.export.trade_entry import trade_entry

BUDAPEST = "Europe/Budapest"

# The ledger's fields of a trade, in its order, without the three this program
# never writes (two sort keys and a fee rule).
LEDGER_TRADE_FIELDS = [
    "id",
    "occurredAt",
    "occurredTimeZone",
    "timePrecision",
    "type",
    "assetSymbol",
    "quantity",
    "price",
    "totalValue",
    "currency",
    "fee",
    "feeCurrency",
    "platform",
    "note",
    "rawText",
    "createdAt",
    "updatedAt",
]

RECORD = TradeRecord(
    side=Side.BUY,
    coin="BTC",
    quantity=Decimal("0.02"),
    price=Decimal("94900"),
    total=Decimal("1898"),
    derived=None,
    fee=Decimal("2"),
    fee_coin="USDT",
    occurred=OccurredTime(
        datetime(2026, 10, 3, 21, 40, tzinfo=ZoneInfo(BUDAPEST)), TimePrecision.MINUTE, BUDAPEST
    ),
    raw_text="昨天晚上 9 点 40 买了 0.02 BTC，94900，手续费 2 USDT，我觉得要涨",
    platform="Binance",
    note="我觉得要涨",
)

CREATED = datetime(2026, 10, 4, 7, 41, tzinfo=timezone.utc)


def entry(**changes: object) -> dict[str, object]:
    record = dataclasses.replace(RECORD, **changes)  # type: ignore[arg-type]
    return trade_entry(
        StoredTrade(id="hand-trade-0001", record=record, created_at=CREATED, updated_at=CREATED)
    )


def test_a_full_trade_has_every_field_the_ledger_takes_in_its_order() -> None:
    assert list(entry()) == LEDGER_TRADE_FIELDS


def test_a_full_trade_is_written_field_by_field() -> None:
    assert entry() == {
        "id": "hand-trade-0001",
        "occurredAt": "2026-10-03T21:40:00+02:00",
        "occurredTimeZone": BUDAPEST,
        "timePrecision": "minute",
        "type": "buy",
        "assetSymbol": "BTC",
        "quantity": "0.02",
        "price": "94900",
        "totalValue": "1898",
        "currency": "USDT",
        "fee": "2",
        "feeCurrency": "USDT",
        "platform": "Binance",
        "note": "我觉得要涨",
        "rawText": "昨天晚上 9 点 40 买了 0.02 BTC，94900，手续费 2 USDT，我觉得要涨",
        "createdAt": "2026-10-04T07:41:00Z",
        "updatedAt": "2026-10-04T07:41:00Z",
    }


@pytest.mark.parametrize(
    ("changes", "left_out"),
    [
        ({"platform": None}, {"platform"}),
        ({"note": None}, {"note"}),
        ({"platform": None, "note": None}, {"platform", "note"}),
        ({"platform": "", "note": ""}, {"platform", "note"}),
    ],
)
def test_a_platform_or_note_that_is_not_there_is_left_out_altogether(
    changes: dict[str, object], left_out: set[str]
) -> None:
    written = entry(**changes)

    assert list(written) == [name for name in LEDGER_TRADE_FIELDS if name not in left_out]


def test_a_sale_is_written_as_a_sale() -> None:
    assert entry(side=Side.SELL)["type"] == "sell"


@pytest.mark.parametrize(
    ("occurred", "at", "precision"),
    [
        (OccurredTime(date(2026, 10, 2), TimePrecision.DAY, BUDAPEST), "2026-10-02", "day"),
        (
            OccurredTime(
                datetime(2026, 10, 4, 9, 15, 30, tzinfo=ZoneInfo(BUDAPEST)),
                TimePrecision.SECOND,
                BUDAPEST,
            ),
            "2026-10-04T09:15:30+02:00",
            "second",
        ),
        (
            OccurredTime(
                datetime(2026, 1, 15, 9, 15, tzinfo=ZoneInfo(BUDAPEST)),
                TimePrecision.MINUTE,
                BUDAPEST,
            ),
            "2026-01-15T09:15:00+01:00",
            "minute",
        ),
        (
            OccurredTime(
                datetime(2026, 10, 1, 14, 5, tzinfo=ZoneInfo("Asia/Shanghai")),
                TimePrecision.MINUTE,
                "Asia/Shanghai",
            ),
            "2026-10-01T14:05:00+08:00",
            "minute",
        ),
    ],
)
def test_the_time_keeps_its_own_offset_zone_and_precision(
    occurred: OccurredTime, at: str, precision: str
) -> None:
    written = entry(occurred=occurred)

    assert written["occurredAt"] == at
    assert written["occurredTimeZone"] == occurred.time_zone
    assert written["timePrecision"] == precision


@pytest.mark.parametrize(
    ("field", "name", "value"),
    [
        ("quantity", "quantity", "0.000000033"),
        ("quantity", "quantity", "12345678901234567890.123456789012345678"),
        ("price", "price", "1E+3"),
        ("price", "price", "94900.00"),
        ("total", "totalValue", "0.000000000000000001"),
        ("fee", "fee", "0"),
        ("fee", "fee", "0.00001"),
    ],
)
def test_numbers_are_written_as_the_ledger_takes_them(field: str, name: str, value: str) -> None:
    written = entry(**{field: Decimal(value)})[name]

    assert written == write_number(Decimal(value))
    assert isinstance(written, str)
    assert "E" not in written


def test_a_fee_in_a_coin_names_that_coin() -> None:
    written = entry(fee=Decimal("0.0001"), fee_coin="BTC")

    assert written["fee"] == "0.0001"
    assert written["feeCurrency"] == "BTC"


def test_the_bookkeeping_moments_are_written_in_utc_to_the_second() -> None:
    created = datetime(2026, 10, 4, 9, 41, 7, 500_000, tzinfo=ZoneInfo(BUDAPEST))
    updated = datetime(2026, 10, 5, 1, 0, tzinfo=ZoneInfo("Asia/Shanghai"))

    written = trade_entry(
        StoredTrade(id="t", record=RECORD, created_at=created, updated_at=updated)
    )

    assert written["createdAt"] == "2026-10-04T07:41:07Z"
    assert written["updatedAt"] == "2026-10-04T17:00:00Z"


def test_the_original_text_is_written_exactly_as_it_was() -> None:
    raw = "  买了\t0.02 BTC \N{GRINNING FACE}\n第二行  "

    assert entry(raw_text=raw)["rawText"] == raw
