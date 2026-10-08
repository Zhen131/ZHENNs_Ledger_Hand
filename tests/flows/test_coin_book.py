"""Tests of the coins the user confirmed, between the book and the coin table."""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone

from ledger_hand.core.book import ConfirmedCoin
from ledger_hand.core.coins import BUILT_IN_TABLE, CoinOrigin
from ledger_hand.flows.coin_book import coins_to_keep, with_confirmed_coins
from tests.storage.invented import records

AT = datetime(2026, 10, 9, 6, 0, tzinfo=timezone.utc)


def confirmed(*symbols: str) -> list[ConfirmedCoin]:
    return [ConfirmedCoin(symbol=symbol, confirmed_at=AT) for symbol in symbols]


def test_kept_coins_join_the_table_as_coins_the_user_confirmed() -> None:
    table = with_confirmed_coins(BUILT_IN_TABLE, confirmed("PIKA", "ZORK"))

    for symbol in ("PIKA", "ZORK"):
        coin = table.find(symbol)
        assert coin is not None
        assert coin.origin is CoinOrigin.USER_CONFIRMED
    assert BUILT_IN_TABLE.find("PIKA") is None


def test_a_kept_coin_the_table_knows_already_changes_nothing() -> None:
    assert with_confirmed_coins(BUILT_IN_TABLE, confirmed("BTC", "XBT")) is BUILT_IN_TABLE
    assert with_confirmed_coins(BUILT_IN_TABLE, []) is BUILT_IN_TABLE


def test_only_the_confirmed_coins_the_records_use_are_kept() -> None:
    table = BUILT_IN_TABLE.with_confirmed("PIKA").with_confirmed("ZORK")
    every = records()

    assert coins_to_keep([every["minute"], every["day"]], table, AT) == ()
    assert coins_to_keep([every["second"]], table, AT) == tuple(confirmed("PIKA"))


def test_a_confirmed_coin_a_fee_was_paid_in_is_kept() -> None:
    table = BUILT_IN_TABLE.with_confirmed("ZORK")
    fee_in_zork = dataclasses.replace(records()["minute"], fee_coin="ZORK")

    assert coins_to_keep([fee_in_zork], table, AT) == tuple(confirmed("ZORK"))
