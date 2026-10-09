"""Tests of whether the ledger counts a trade's fee in the cost.

The ledger takes a fee into the cost only when it is paid in USDT or in the
coin traded; a fee above 0 paid in a third coin is left out, and that is
what the person is reminded of. Every trade below is invented.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ledger_hand.core.fee_cost import fee_left_out_of_cost
from ledger_hand.core.trade import OccurredTime, Side, TimePrecision, TradeRecord

DAY = OccurredTime(date(2026, 10, 6), TimePrecision.DAY, "Europe/Budapest")


def record(*, coin: str, fee: str, fee_coin: str) -> TradeRecord:
    return TradeRecord(
        side=Side.BUY,
        coin=coin,
        quantity=Decimal("0.5"),
        price=Decimal("3420"),
        total=Decimal("1710"),
        derived=None,
        fee=Decimal(fee),
        fee_coin=fee_coin,
        occurred=DAY,
        raw_text="invented",
    )


@pytest.mark.parametrize(
    ("coin", "fee", "fee_coin"),
    [("ETH", "0.001", "BNB"), ("BTC", "0.3", "ETH")],
)
def test_a_fee_above_0_in_a_third_coin_is_left_out(coin: str, fee: str, fee_coin: str) -> None:
    assert fee_left_out_of_cost(record(coin=coin, fee=fee, fee_coin=fee_coin))


@pytest.mark.parametrize(
    ("coin", "fee", "fee_coin"),
    [
        ("ETH", "1", "USDT"),
        ("ETH", "0.0005", "ETH"),
        ("SOL", "0.01", "SOL"),
        ("ETH", "0", "BNB"),
        ("ETH", "0", "USDT"),
    ],
)
def test_a_fee_in_usdt_in_the_coin_traded_or_of_0_is_counted(
    coin: str, fee: str, fee_coin: str
) -> None:
    assert not fee_left_out_of_cost(record(coin=coin, fee=fee, fee_coin=fee_coin))
