"""Tests of reading a change's new value and putting it into the trade found."""

from __future__ import annotations

import dataclasses
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from ledger_hand.assistant.new_values import (
    AssetValue,
    Fix,
    Fixes,
    NotTaken,
    NumberValue,
    SideValue,
    TextValue,
    TimeValue,
    Unchanged,
    changed_trade,
    read_new_value,
)
from ledger_hand.core.ledger_limits import PLATFORM_MAX_LENGTH
from ledger_hand.core.trade import Amount, Side
from ledger_hand.ledger.invented_book import (
    INVENTED_ASSETS,
    INVENTED_NOW,
    INVENTED_TRADES,
    INVENTED_ZONE,
)

BOOK = dict(INVENTED_TRADES)
BTC_BUY = BOOK["t-05"]  # 0.0082 BTC at 61940 USDT, 507.908 USDT, fee 0.0000082 BTC
ETH_BUY = BOOK["t-06"]  # fee 0.3669 USDT
D = Decimal


def read(field: str, words: str) -> object:
    return read_new_value(field, words, INVENTED_ASSETS, now=INVENTED_NOW, zone=INVENTED_ZONE)


@pytest.mark.parametrize(
    ("field", "words", "value"),
    [
        ("quantity", "0.0081", NumberValue(D("0.0081"))),
        ("fee", "0", NumberValue(D("0"))),
        ("fee", "0.3U", NumberValue(D("0.3"), "U")),
        ("price", "6万", NumberValue(D("60000"))),
        ("side", "卖出", SideValue(Side.SELL)),
        ("side", "buy", SideValue(Side.BUY)),
        ("asset", "以太坊", AssetValue("ETH")),
        ("quote_currency", "USD", AssetValue("USD")),
        ("fee_currency", "ada", AssetValue("ADA")),
        ("platform", "Binance", TextValue("Binance")),
        ("note", "  keep  ", TextValue("  keep  ")),
    ],
)
def test_values_read(field: str, words: str, value: object) -> None:
    assert read(field, words) == value


def test_a_time_with_the_clock_is_a_moment() -> None:
    assert read("time", "10月5号14:30") == TimeValue(
        datetime(2026, 10, 5, 14, 30, tzinfo=ZoneInfo(INVENTED_ZONE))
    )


@pytest.mark.parametrize(
    ("field", "words"),
    [
        ("quantity", "0"),
        ("quantity", "1.500"),
        ("quantity", "大概0.1"),
        ("quantity", "abc"),
        ("price", "0.0000000000000000001"),
        ("time", "10月5号"),
        ("time", "昨天3点"),
        ("time", "12月25号10:00"),
        ("time", "某天"),
        ("side", "换一下"),
        ("asset", "DOGE"),
        ("quote_currency", "BTC"),
        ("platform", "x" * (PLATFORM_MAX_LENGTH + 1)),
    ],
)
def test_values_not_taken(field: str, words: str) -> None:
    assert isinstance(read(field, words), NotTaken)


def test_a_fee_with_the_fees_own_asset_is_taken() -> None:
    changed = changed_trade("fee", NumberValue(D("0.000009"), "BTC"), BTC_BUY, INVENTED_ASSETS)
    assert changed == dataclasses.replace(BTC_BUY, fee=D("0.000009"))


@pytest.mark.parametrize("unit", ["U", "USDT", "ETH", "刀"])
def test_a_unit_that_is_not_what_the_fee_is_in_changes_nothing(unit: str) -> None:
    changed = changed_trade("fee", NumberValue(D("0.3"), unit), BTC_BUY, INVENTED_ASSETS)
    assert isinstance(changed, NotTaken)
    assert "one at a time" in changed.words


def test_usdt_written_out_is_what_a_usdt_fee_is_in() -> None:
    changed = changed_trade("fee", NumberValue(D("0.3"), "USDT"), ETH_BUY, INVENTED_ASSETS)
    assert changed == dataclasses.replace(ETH_BUY, fee=D("0.3"))


def test_u_is_not_taken_for_usdt_until_that_is_settled() -> None:
    changed = changed_trade("fee", NumberValue(D("0.3"), "U"), ETH_BUY, INVENTED_ASSETS)
    assert isinstance(changed, NotTaken)


@pytest.mark.parametrize("unit", ["个", "BTC", "比特币", "个BTC"])
def test_a_quantity_with_a_counter_or_its_own_asset_is_taken(unit: str) -> None:
    changed = changed_trade("quantity", NumberValue(D("0.0082"), unit), BTC_BUY, INVENTED_ASSETS)
    assert isinstance(changed, Unchanged)


def test_a_fee_of_zero_keeps_what_it_is_taken_in() -> None:
    changed = changed_trade("fee", NumberValue(D("0")), BTC_BUY, INVENTED_ASSETS)
    assert changed == dataclasses.replace(BTC_BUY, fee=D("0"))


def test_a_new_quantity_out_of_step_gives_both_ways_total_first() -> None:
    changed = changed_trade("quantity", NumberValue(D("0.0081")), BTC_BUY, INVENTED_ASSETS)
    assert changed == Fixes(
        changed=Amount.QUANTITY,
        fixes=(
            Fix(follows=Amount.TOTAL, quantity=D("0.0081"), price=D("61940"), total=D("501.714")),
            Fix(
                follows=Amount.PRICE,
                quantity=D("0.0081"),
                price=D("62704.69135802"),
                total=D("507.908"),
            ),
        ),
    )


def test_a_new_total_out_of_step_gives_price_then_quantity() -> None:
    changed = changed_trade("total", NumberValue(D("500")), BTC_BUY, INVENTED_ASSETS)
    assert isinstance(changed, Fixes)
    assert [str(fix.price) for fix in changed.fixes] == ["60975.6097561", "61940"]
    assert [str(fix.quantity) for fix in changed.fixes] == ["0.0082", "0.00807233"]


def test_the_same_value_is_unchanged() -> None:
    assert isinstance(
        changed_trade("price", NumberValue(D("61940.0")), BTC_BUY, INVENTED_ASSETS), Unchanged
    )
    assert isinstance(
        changed_trade("platform", TextValue("OKX"), BTC_BUY, INVENTED_ASSETS), Unchanged
    )


def test_every_other_part_and_the_words_said_stay_as_they_were() -> None:
    changed = changed_trade("note", TextValue("fixed"), BTC_BUY, INVENTED_ASSETS)
    assert changed == dataclasses.replace(BTC_BUY, note="fixed")
