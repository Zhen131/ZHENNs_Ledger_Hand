"""Tests of saving a passage: final records kept in the book, with new identifiers and their coins.

The passages are recorded with fake models (``RoutedModel``) and saved into
the in-memory book or the real SQLite one. Every passage is invented.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from ledger_hand.core.book import ConfirmedCoin, EarlierSave, Listing
from ledger_hand.flows.fingerprint import passage_fingerprint
from ledger_hand.flows.identifiers import IDENTIFIER_PREFIX, new_identifier
from ledger_hand.flows.progress import Progress
from ledger_hand.flows.recording import answer, finish, remove
from ledger_hand.flows.saving import Saved, save
from ledger_hand.ports import StorageError, StorageErrorKind
from ledger_hand.storage.sqlite_store import SqliteStore
from tests.fakes.memory_store import MemoryStore
from tests.fakes.routed_model import RoutedModel
from tests.flows.scripted_flow import begin, row, screened, table, walk

SAVED_AT = datetime(2026, 10, 7, 19, 30, 5, 250000, tzinfo=timezone.utc)
SPOT = screened(("spot_trade", "买了 0.5 ETH"))
COMPLETE_TWO = "昨天买了 0.5 ETH，价格 3,420，手续费 0；卖了 2 SOL，价格 150，手续费 0.2 USDT"
COMPLETE_ROWS = table(
    row(side="buy", coin="ETH", quantity="0.5 ETH", price="3,420", fee="0", time="昨天"),
    row(side="sell", coin="SOL", quantity="2 SOL", price="150", fee="0.2 USDT", time="昨天"),
)
NEW_COINS = "昨天买了 100 PIKA，价格 0.5，手续费 0；卖了 3 ZORK，价格 2，手续费 0.1 ZORK"
NEW_COIN_ROWS = table(
    row(side="buy", coin="PIKA", quantity="100 PIKA", price="0.5", fee="0", time="昨天"),
    row(side="sell", coin="ZORK", quantity="3 ZORK", price="2", fee="0.1 ZORK", time="昨天"),
)


def done_two() -> tuple[Progress, RoutedModel]:
    model = RoutedModel(screen=[SPOT], extraction=[COMPLETE_ROWS])
    return finish(begin(COMPLETE_TWO, model)), model


def test_the_final_records_are_saved_as_new_trades_at_the_moment_given() -> None:
    done, _ = done_two()
    book = MemoryStore()

    saved = save(done, book, now=SAVED_AT)

    assert [trade.record for trade in saved.trades] == list(done.records)
    assert all(trade.created_at == trade.updated_at == SAVED_AT for trade in saved.trades)
    assert len({trade.id for trade in saved.trades}) == 2
    assert [entry.trade for entry in book.trades(Listing.ALL)] == list(saved.trades)
    assert saved.coins == ()


def test_the_passage_is_kept_by_its_fingerprint_with_the_count() -> None:
    done, _ = done_two()
    book = MemoryStore()

    save(done, book, now=SAVED_AT)

    assert book.earlier_saves(passage_fingerprint(COMPLETE_TWO)) == (
        EarlierSave(saved_at=SAVED_AT, trades=2),
    )


def test_a_removed_record_is_not_saved() -> None:
    model = RoutedModel(screen=[SPOT], extraction=[COMPLETE_ROWS])
    done = finish(remove(begin(COMPLETE_TWO, model), 1))
    book = MemoryStore()

    saved = save(done, book, now=SAVED_AT)

    assert [trade.record.coin for trade in saved.trades] == ["SOL"]
    assert [entry.trade.record.coin for entry in book.trades(Listing.ALL)] == ["SOL"]


def test_a_passage_with_no_record_left_saves_nothing_and_leaves_the_book_alone() -> None:
    model = RoutedModel(screen=[SPOT], extraction=[COMPLETE_ROWS])
    done = finish(remove(remove(begin(COMPLETE_TWO, model), 1), 2))
    book = MemoryStore()

    assert save(done, book, now=SAVED_AT) == Saved((), ())
    assert book.calls == []


def test_records_that_are_not_final_are_not_saved() -> None:
    model = RoutedModel(screen=[SPOT], extraction=[COMPLETE_ROWS])
    reviewing = begin(COMPLETE_TWO, model)
    book = MemoryStore()

    with pytest.raises(ValueError, match="final"):
        save(reviewing, book, now=SAVED_AT)
    assert book.calls == []


def test_the_moment_of_saving_must_carry_an_offset() -> None:
    done, _ = done_two()

    with pytest.raises(ValueError):
        save(done, MemoryStore(), now=datetime(2026, 10, 7, 19, 30))


def test_a_failure_of_the_book_is_raised_and_nothing_is_saved() -> None:
    done, _ = done_two()
    book = MemoryStore()
    book.fail_next("save", StorageErrorKind.INACCESSIBLE)

    with pytest.raises(StorageError) as raised:
        save(done, book, now=SAVED_AT)

    assert raised.value.kind is StorageErrorKind.INACCESSIBLE
    assert book.trades(Listing.ALL) == ()


def confirmed_both() -> tuple[Progress, RoutedModel]:
    model = RoutedModel(screen=[SPOT], extraction=[NEW_COIN_ROWS])
    asked = begin(NEW_COINS, model)
    *_, settled = walk(asked, model, "yes", "yes")
    assert [record.coin for record in settled.records] == ["PIKA", "ZORK"]
    return settled, model


def test_coins_confirmed_are_kept_with_the_trades_that_use_them() -> None:
    settled, _ = confirmed_both()
    book = MemoryStore()

    saved = save(finish(settled), book, now=SAVED_AT)

    expected = (
        ConfirmedCoin(symbol="PIKA", confirmed_at=SAVED_AT),
        ConfirmedCoin(symbol="ZORK", confirmed_at=SAVED_AT),
    )
    assert saved.coins == expected
    assert book.confirmed_coins() == expected


def test_a_coin_confirmed_for_a_trade_left_out_is_not_kept() -> None:
    settled, _ = confirmed_both()
    book = MemoryStore()

    save(finish(remove(settled, 2)), book, now=SAVED_AT)

    assert [coin.symbol for coin in book.confirmed_coins()] == ["PIKA"]


def test_saving_into_the_real_book_keeps_every_cell(tmp_path: Path) -> None:
    done, _ = done_two()
    book = SqliteStore(tmp_path / "book.sqlite3")

    saved = save(done, book, now=SAVED_AT)

    reopened = SqliteStore(tmp_path / "book.sqlite3").trades(Listing.ALL)
    assert [entry.trade for entry in reopened] == list(saved.trades)
    assert [entry.trade.record for entry in reopened] == list(done.records)


def test_a_new_identifier_is_the_prefix_and_a_random_uuid() -> None:
    made = {new_identifier() for _ in range(1000)}

    assert len(made) == 1000
    for identifier in made:
        assert identifier.startswith(IDENTIFIER_PREFIX)
        assert len(identifier) == 41
        assert identifier.strip() == identifier
        assert uuid.UUID(identifier.removeprefix(IDENTIFIER_PREFIX)).version == 4


def test_answers_given_before_saving_are_in_what_is_saved() -> None:
    passage = "昨天卖了 2 SOL，手续费 0.2 USDT"
    model = RoutedModel(
        screen=[SPOT],
        extraction=[
            table(row(side="sell", coin="SOL", quantity="2 SOL", fee="0.2 USDT", time="昨天"))
        ],
    )
    asked = begin(passage, model)
    done = finish(answer(asked, "150", model))
    book = MemoryStore()

    (trade,) = save(done, book, now=SAVED_AT).trades

    assert str(trade.record.price) == "150"
    assert trade.record.raw_text == passage
