"""Tests of the storage port, run against every plug: the SQLite book and the in-memory stand-in.

Whatever is behind the port, a saved trade comes back exactly as it went in,
every cell of it; a save and a marking are whole or not at all; a coin the
user confirmed is kept with the trades that use it; and an earlier save of
the same passage is found by its fingerprint. Each test starts from an empty
book. Every trade is invented.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from ledger_hand.core.book import ConfirmedCoin, EarlierSave, ExportMark, Listing
from ledger_hand.ports import StorageError, StorageErrorKind, StoragePort
from tests.fakes.memory_store import MemoryStore
from tests.storage.invented import SAVED_AT, passage, records, stored

LATER = SAVED_AT + timedelta(minutes=5)
EXPORTED_AT = datetime(2026, 10, 9, 7, 0, 0, 654321, tzinfo=timezone.utc)
PLUGS = ["memory"]


def build(plug: str, where: Path) -> StoragePort:
    if plug == "memory":
        return MemoryStore()
    raise AssertionError(f"no such plug: {plug}")


@pytest.fixture(params=PLUGS)
def store(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[StoragePort]:
    yield build(request.param, tmp_path / "data")


def four_trades() -> list:
    return [stored(f"hand-{name}", record) for name, record in records().items()]


def test_an_empty_book_holds_nothing(store: StoragePort) -> None:
    assert store.trades(Listing.ALL) == ()
    assert store.trades(Listing.NOT_EXPORTED) == ()
    assert store.confirmed_coins() == ()
    assert store.earlier_saves("never") == ()


def test_saved_trades_come_back_equal_in_every_cell(store: StoragePort) -> None:
    trades = four_trades()

    given_back = store.save(passage("p1", *trades, coins=("PIKA",)))
    listed = store.trades(Listing.ALL)

    assert list(given_back) == trades
    assert [entry.trade for entry in listed] == trades
    for entry, original in zip(listed, trades, strict=True):
        assert entry.exported_at is None
        assert not entry.exported
        kept, record = entry.trade.record, original.record
        assert kept.derived is record.derived
        assert kept.occurred.precision is record.occurred.precision
        assert kept.occurred.time_zone == record.occurred.time_zone
        assert kept.occurred.value == record.occurred.value
        assert type(kept.occurred.value) is type(record.occurred.value)
        for name in ("quantity", "price", "total", "fee"):
            assert str(getattr(kept, name)) == str(getattr(record, name)), name
        assert (kept.platform, kept.note, kept.raw_text) == (
            record.platform,
            record.note,
            record.raw_text,
        )


def test_moments_come_back_in_utc_as_the_same_instants(store: StoragePort) -> None:
    budapest = SAVED_AT.astimezone(timezone(timedelta(hours=2)))
    trade = stored("hand-1", records()["minute"], at=budapest)

    (kept,) = store.save(passage("p1", trade, at=budapest))

    assert kept.created_at == budapest
    assert kept.created_at.utcoffset() == timedelta(0)
    assert kept.created_at.microsecond == 123456
    assert store.trades(Listing.ALL)[0].trade.updated_at == budapest


def test_trades_are_listed_in_the_order_they_were_saved(store: StoragePort) -> None:
    first, second, third, fourth = four_trades()
    store.save(passage("p1", second, first))
    store.save(passage("p2", fourth, third, at=LATER))

    assert [entry.trade.id for entry in store.trades(Listing.ALL)] == [
        second.id,
        first.id,
        fourth.id,
        third.id,
    ]


def test_marked_trades_carry_their_export_moment_and_leave_the_not_exported_list(
    store: StoragePort,
) -> None:
    first, second, third, _ = four_trades()
    store.save(passage("p1", first, second, third))

    store.mark_exported(ExportMark(identifiers=(first.id, third.id), exported_at=EXPORTED_AT))

    listed = {entry.trade.id: entry for entry in store.trades(Listing.ALL)}
    assert listed[first.id].exported_at == EXPORTED_AT
    assert listed[third.id].exported_at == EXPORTED_AT
    assert listed[second.id].exported_at is None
    assert [entry.trade.id for entry in store.trades(Listing.NOT_EXPORTED)] == [second.id]


def test_marking_is_all_or_nothing(store: StoragePort) -> None:
    first, second, _, _ = four_trades()
    store.save(passage("p1", first, second))

    with pytest.raises(StorageError) as raised:
        store.mark_exported(ExportMark(identifiers=(first.id, "hand-none"), exported_at=LATER))

    assert raised.value.kind is StorageErrorKind.CONFLICT
    assert all(entry.exported_at is None for entry in store.trades(Listing.ALL))


def test_a_trade_is_never_marked_twice(store: StoragePort) -> None:
    first, second, _, _ = four_trades()
    store.save(passage("p1", first, second))
    store.mark_exported(ExportMark(identifiers=(first.id,), exported_at=EXPORTED_AT))

    with pytest.raises(StorageError) as raised:
        store.mark_exported(ExportMark(identifiers=(second.id, first.id), exported_at=LATER))

    assert raised.value.kind is StorageErrorKind.CONFLICT
    listed = {entry.trade.id: entry.exported_at for entry in store.trades(Listing.ALL)}
    assert listed == {first.id: EXPORTED_AT, second.id: None}


def test_an_identifier_already_saved_is_a_conflict_and_nothing_of_that_save_is_kept(
    store: StoragePort,
) -> None:
    first, second, third, _ = four_trades()
    store.save(passage("p1", first))

    with pytest.raises(StorageError) as raised:
        store.save(passage("p2", third, first, second, at=LATER, coins=("PIKA",)))

    assert raised.value.kind is StorageErrorKind.CONFLICT
    assert [entry.trade.id for entry in store.trades(Listing.ALL)] == [first.id]
    assert store.confirmed_coins() == ()
    assert store.earlier_saves("p2") == ()


def test_confirmed_coins_are_kept_with_the_save_and_keep_their_first_moment(
    store: StoragePort,
) -> None:
    first, second, _, _ = four_trades()
    store.save(passage("p1", first, coins=("PIKA", "ZORK")))
    store.save(passage("p2", second, at=LATER, coins=("PIKA", "ABC1")))

    assert store.confirmed_coins() == (
        ConfirmedCoin(symbol="ABC1", confirmed_at=LATER),
        ConfirmedCoin(symbol="PIKA", confirmed_at=SAVED_AT),
        ConfirmedCoin(symbol="ZORK", confirmed_at=SAVED_AT),
    )
    assert all(coin.confirmed_at.utcoffset() == timedelta(0) for coin in store.confirmed_coins())


def test_earlier_saves_are_found_by_fingerprint_with_their_moment_and_count(
    store: StoragePort,
) -> None:
    first, second, third, fourth = four_trades()
    store.save(passage("same", first, second))
    store.save(passage("other", third, at=LATER))
    store.save(passage("same", fourth, at=LATER))

    assert store.earlier_saves("same") == (
        EarlierSave(saved_at=SAVED_AT, trades=2),
        EarlierSave(saved_at=LATER, trades=1),
    )
    assert store.earlier_saves("other") == (EarlierSave(saved_at=LATER, trades=1),)
    assert store.earlier_saves("none") == ()
    assert store.earlier_saves("same")[0].saved_at.utcoffset() == timedelta(0)
