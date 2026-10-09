"""Tests of the table's cells: read off the progress, numbers as the ledger writes them.

A complete trade shows its record and marks the amount the program worked
out; any other trade shows its draft, with blanks, and no mark. Numbers are
written from exact decimals, never through floating-point numbers; a time
shows the wall clock of the trade's own zone and the zone's name. Every
trade below is invented.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from ledger_hand.core.coins import BUILT_IN_TABLE
from ledger_hand.core.trade import (
    Amount,
    OccurredTime,
    Side,
    TimePrecision,
    TradeDraft,
    TradeRecord,
)
from ledger_hand.core.validation import Violation
from ledger_hand.flows.progress import Progress, Setting, Stage, TradeState, TradeStatus
from ledger_hand.ui.preview import CALCULATED_MARK, COLUMNS, rows

ZONE = "Europe/Budapest"
NOW = datetime(2026, 10, 7, 21, 0, tzinfo=ZoneInfo(ZONE))
DAY = OccurredTime(date(2026, 10, 6), TimePrecision.DAY, ZONE)


def progress(*trades: TradeState) -> Progress:
    return Progress(Stage.REVIEWING, "invented", Setting(NOW, ZONE, BUILT_IN_TABLE), trades=trades)


def record(*, derived: Amount | None, occurred: OccurredTime = DAY) -> TradeRecord:
    return TradeRecord(
        side=Side.BUY,
        coin="BTC",
        quantity=Decimal("0.02"),
        price=Decimal("94900"),
        total=Decimal("1898"),
        derived=derived,
        fee=Decimal("0.1"),
        fee_coin="USDT",
        occurred=occurred,
        raw_text="买了 0.02 个比特币",
        platform="OKX",
        note="我觉得要涨",
    )


def complete(trade: TradeRecord) -> TradeState:
    draft = TradeDraft(coin="比特币", quantity=Decimal("0.02"), raw_text=trade.raw_text)
    return TradeState(draft, TradeStatus.RECORDED, trade)


def test_nothing_being_recorded_is_no_row() -> None:
    assert rows(None) == []


def test_a_row_has_every_column_and_numbers_its_trade() -> None:
    (only,) = rows(progress(complete(record(derived=None))))

    assert tuple(only) == COLUMNS
    assert only == {
        "#": "1",
        "Time": "2026-10-06 (Europe/Budapest)",
        "Coin": "BTC",
        "Side": "buy",
        "Quantity": "0.02",
        "Price": "94900",
        "Total": "1898",
        "Fee": "0.1",
        "Fee coin": "USDT",
        "Platform": "OKX",
        "Note": "我觉得要涨",
        "Status": "complete",
    }


@pytest.mark.parametrize(
    ("derived", "column"),
    [(Amount.QUANTITY, "Quantity"), (Amount.PRICE, "Price"), (Amount.TOTAL, "Total")],
)
def test_only_the_amount_the_record_says_was_worked_out_is_marked(
    derived: Amount, column: str
) -> None:
    (only,) = rows(progress(complete(record(derived=derived))))

    marked = [name for name, cell in only.items() if cell.endswith(CALCULATED_MARK)]
    assert marked == [column]


def test_a_draft_is_shown_as_it_stands_with_blanks_and_no_mark() -> None:
    draft = TradeDraft(
        side=Side.SELL,
        coin="以太坊",
        quantity=Decimal("1.5"),
        price=Decimal("3180"),
        total=Decimal("4770"),
        derived=frozenset({Amount.TOTAL}),
    )

    (only,) = rows(progress(TradeState(draft, TradeStatus.OPEN)))

    assert only["Coin"] == "以太坊"
    assert (only["Quantity"], only["Price"], only["Total"]) == ("1.5", "3180", "4770")
    assert (only["Time"], only["Fee"], only["Fee coin"], only["Platform"]) == ("", "", "", "")
    assert only["Status"] == "asking"


@pytest.mark.parametrize(
    ("value", "shown"),
    [
        (Decimal("0.1"), "0.1"),
        (Decimal("1E-7"), "0.0000001"),
        (Decimal("2.50"), "2.50"),
        (Decimal("94900"), "94900"),
    ],
)
def test_numbers_are_written_from_exact_decimals(value: Decimal, shown: str) -> None:
    (only,) = rows(progress(TradeState(TradeDraft(price=value), TradeStatus.OPEN)))

    assert only["Price"] == shown


@pytest.mark.parametrize(
    ("value", "shown"),
    [(Decimal("-5"), "-5"), (Decimal("1" * 40), "1" * 40)],
)
def test_a_draft_value_the_ledger_cannot_hold_is_still_shown_exactly(
    value: Decimal, shown: str
) -> None:
    (only,) = rows(progress(TradeState(TradeDraft(quantity=value), TradeStatus.OPEN)))

    assert only["Quantity"] == shown


@pytest.mark.parametrize(
    ("precision", "moment", "shown"),
    [
        (TimePrecision.MINUTE, datetime(2026, 10, 6, 21, 40), "2026-10-06 21:40"),
        (TimePrecision.SECOND, datetime(2026, 10, 6, 21, 40, 30), "2026-10-06 21:40:30"),
    ],
)
def test_a_time_shows_the_wall_clock_of_its_own_zone(
    precision: TimePrecision, moment: datetime, shown: str
) -> None:
    for zone in ("Europe/Budapest", "Asia/Shanghai"):
        occurred = OccurredTime(moment.replace(tzinfo=ZoneInfo(zone)), precision, zone)

        (only,) = rows(progress(complete(record(derived=None, occurred=occurred))))

        assert only["Time"] == f"{shown} ({zone})"


def test_each_status_is_named_and_a_trade_that_cannot_be_recorded_says_why() -> None:
    draft = TradeDraft(coin="ETH")
    shown = rows(
        progress(
            TradeState(draft, TradeStatus.OPEN),
            complete(record(derived=None)),
            TradeState(draft, TradeStatus.SKIPPED),
            TradeState(draft, TradeStatus.CANNOT_RECORD, reason=Violation.UNSUPPORTED_QUOTE),
        )
    )

    assert [row["Status"] for row in shown] == [
        "asking",
        "complete",
        "left out",
        f"cannot record: {Violation.UNSUPPORTED_QUOTE.value}",
    ]
    assert [row["#"] for row in shown] == ["1", "2", "3", "4"]
