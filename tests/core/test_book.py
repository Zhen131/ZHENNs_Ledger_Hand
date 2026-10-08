"""Tests of the shapes the local book keeps and is asked for: what each refuses to be."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

import pytest

from ledger_hand.core.book import (
    ConfirmedCoin,
    EarlierSave,
    ExportMark,
    ListedTrade,
    Listing,
    PassageSave,
)
from tests.storage.invented import SAVED_AT, records, stored

NAIVE = datetime(2026, 10, 8, 18, 30)
EARLIEST_EAST = datetime(1, 1, 1, 0, 30, tzinfo=timezone(timedelta(hours=1)))


def trade(identifier: str = "hand-1") -> Any:
    return stored(identifier, records()["minute"])


def test_the_listings_are_these_two() -> None:
    assert [listing.name for listing in Listing] == ["ALL", "NOT_EXPORTED"]


def test_a_listed_trade_says_whether_it_was_exported() -> None:
    assert not ListedTrade(trade=trade()).exported
    assert ListedTrade(trade=trade(), exported_at=SAVED_AT).exported


@pytest.mark.parametrize("moment", [NAIVE, EARLIEST_EAST, date(2026, 10, 8), "2026-10-08"])
def test_every_moment_must_carry_an_offset_that_utc_can_hold(moment: object) -> None:
    for build in (
        lambda: ListedTrade(trade=trade(), exported_at=moment),  # type: ignore[arg-type]
        lambda: ConfirmedCoin(symbol="PIKA", confirmed_at=moment),  # type: ignore[arg-type]
        lambda: PassageSave(fingerprint="f", saved_at=moment, trades=(trade(),)),  # type: ignore[arg-type]
        lambda: EarlierSave(saved_at=moment, trades=1),  # type: ignore[arg-type]
        lambda: ExportMark(identifiers=("a",), exported_at=moment),  # type: ignore[arg-type]
    ):
        with pytest.raises((TypeError, ValueError)):
            build()


def test_a_listed_trade_holds_a_stored_trade() -> None:
    with pytest.raises(TypeError):
        ListedTrade(trade=records()["minute"])  # type: ignore[arg-type]


@pytest.mark.parametrize("symbol", ["pika", "", "PI KA", "USDT", "U", "USD", "A" * 33, 7])
def test_a_confirmed_coin_is_a_ledger_symbol_and_never_usdt(symbol: object) -> None:
    with pytest.raises(ValueError):
        ConfirmedCoin(symbol=symbol, confirmed_at=SAVED_AT)  # type: ignore[arg-type]


def test_a_confirmed_coin_keeps_its_symbol_and_moment() -> None:
    coin = ConfirmedCoin(symbol="PIKA2", confirmed_at=SAVED_AT)

    assert (coin.symbol, coin.confirmed_at) == ("PIKA2", SAVED_AT)


@pytest.mark.parametrize(
    ("changes", "error"),
    [
        ({"fingerprint": ""}, ValueError),
        ({"fingerprint": None}, ValueError),
        ({"trades": ()}, ValueError),
        ({"trades": [trade()]}, ValueError),
        ({"trades": (records()["minute"],)}, TypeError),
        ({"trades": (trade("a"), trade("a"))}, ValueError),
        ({"coins": [ConfirmedCoin(symbol="PIKA", confirmed_at=SAVED_AT)]}, TypeError),
        ({"coins": ("PIKA",)}, TypeError),
        (
            {
                "coins": (
                    ConfirmedCoin(symbol="PIKA", confirmed_at=SAVED_AT),
                    ConfirmedCoin(symbol="PIKA", confirmed_at=SAVED_AT),
                )
            },
            ValueError,
        ),
    ],
)
def test_a_save_holds_one_trade_or_more_each_once(
    changes: dict[str, object], error: type[Exception]
) -> None:
    values: dict[str, Any] = {"fingerprint": "f", "saved_at": SAVED_AT, "trades": (trade(),)}
    with pytest.raises(error):
        PassageSave(**{**values, **changes})


@pytest.mark.parametrize("count", [0, -1, True, 1.0, "2"])
def test_an_earlier_save_saved_at_least_one_trade(count: object) -> None:
    with pytest.raises(ValueError):
        EarlierSave(saved_at=SAVED_AT, trades=count)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("identifiers", "error"),
    [((), ValueError), (["a"], ValueError), (("a", "a"), ValueError), (("a", 1), TypeError)],
)
def test_an_export_mark_names_each_trade_once(identifiers: object, error: type[Exception]) -> None:
    with pytest.raises(error):
        ExportMark(identifiers=identifiers, exported_at=SAVED_AT)  # type: ignore[arg-type]
