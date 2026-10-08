"""Tests of recording a passage with a book handed in: the reminder of an earlier save, and coins.

With a book, the passage is looked up before anything else: an earlier save
of it, or of one that differs only in spacing or character width, is kept
as a reminder with its date and number of trades, and holds nothing back.
The coins the user confirmed and saved before are known. Without a book,
recording is as it always was, and nothing is looked up. Every passage is
invented.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from ledger_hand.core.book import EarlierSave, Listing
from ledger_hand.core.followup import ConfirmCoin
from ledger_hand.flows.exporting import ExportResult, export
from ledger_hand.flows.progress import Stage
from ledger_hand.flows.recording import finish, remove, start
from ledger_hand.flows.saving import save
from ledger_hand.ports import StorageError, StorageErrorKind
from ledger_hand.storage.sqlite_store import SqliteStore
from tests.fakes.memory_store import MemoryStore
from tests.fakes.routed_model import RoutedModel
from tests.flows.scripted_flow import NOW, ZONE, begin, row, screened, table, walk

SPOT = screened(("spot_trade", "买了 0.5 ETH"))
PASSAGE = "昨天买了 0.5 ETH，价格 3,420，手续费 0；卖了 2 SOL，价格 150，手续费 0.2 USDT"
ROWS = table(
    row(side="buy", coin="ETH", quantity="0.5 ETH", price="3,420", fee="0", time="昨天"),
    row(side="sell", coin="SOL", quantity="2 SOL", price="150", fee="0.2 USDT", time="昨天"),
)
SAVED_AT = NOW - timedelta(hours=2)


def model() -> RoutedModel:
    return RoutedModel(screen=[SPOT], extraction=[ROWS])


def book_with_the_passage_saved() -> MemoryStore:
    book = MemoryStore()
    save(finish(begin(PASSAGE, model())), book, now=SAVED_AT)
    book.calls.clear()
    return book


# --- the reminder ---------------------------------------------------------------


@pytest.mark.parametrize(
    "again",
    [
        PASSAGE,
        f"  {PASSAGE}  ",
        PASSAGE.replace(" ", "   "),
        PASSAGE.replace("，", ",").replace("0.5", "０.５"),
        PASSAGE.replace(" ", "　", 1),
    ],
)
def test_the_same_passage_again_is_reminded_with_the_day_and_count_and_not_held_back(
    again: str,
) -> None:
    book = book_with_the_passage_saved()
    fake = model()

    progress = start(again, fake, now=NOW, zone=ZONE, book=book)

    assert progress.seen_before == (EarlierSave(saved_at=SAVED_AT, trades=2),)
    assert progress.seen_before[0].saved_at.astimezone(timezone.utc).date().isoformat() == (
        "2026-10-07"
    )
    assert progress.stage is Stage.REVIEWING
    assert len(progress.records) == 2
    assert len(fake.screen.calls) == 1
    assert len(fake.extraction.calls) == 1


@pytest.mark.parametrize(
    "other",
    [
        PASSAGE.replace("0.5", "0.6"),
        PASSAGE.replace("ETH", "eth"),
        PASSAGE.replace("买了 0.5", "买了0.5"),
        "前天" + PASSAGE.removeprefix("昨天"),
    ],
)
def test_another_passage_is_not_reminded(other: str) -> None:
    book = book_with_the_passage_saved()

    progress = start(other, model(), now=NOW, zone=ZONE, book=book)

    assert progress.seen_before == ()


def test_every_earlier_save_is_reminded_oldest_first() -> None:
    book = book_with_the_passage_saved()
    save(finish(remove(begin(PASSAGE, model()), 1)), book, now=SAVED_AT + timedelta(hours=1))

    progress = start(PASSAGE, model(), now=NOW, zone=ZONE, book=book)

    assert progress.seen_before == (
        EarlierSave(saved_at=SAVED_AT, trades=2),
        EarlierSave(saved_at=SAVED_AT + timedelta(hours=1), trades=1),
    )


def test_the_book_is_looked_up_before_the_model_is_asked_anything() -> None:
    book = MemoryStore()
    fake = model()

    start(PASSAGE, fake, now=NOW, zone=ZONE, book=book)

    assert book.calls == ["earlier_saves", "confirmed_coins"]


def test_a_failing_book_is_raised_before_the_model_is_asked_anything() -> None:
    book = MemoryStore()
    book.fail_next("earlier_saves", StorageErrorKind.NEWER_VERSION)
    fake = model()

    with pytest.raises(StorageError) as raised:
        start(PASSAGE, fake, now=NOW, zone=ZONE, book=book)

    assert raised.value.kind is StorageErrorKind.NEWER_VERSION
    assert fake.screen.calls == []


def test_without_a_book_nothing_is_looked_up_and_nothing_is_reminded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    progress = start(PASSAGE, model(), now=NOW, zone=ZONE)

    assert progress.seen_before == ()
    assert progress.stage is Stage.REVIEWING
    assert list(tmp_path.iterdir()) == []


# --- coins confirmed and saved ------------------------------------------------------

NEW_COIN = "昨天买了 100 PIKA，价格 0.5，手续费 0；又买了 2 ZORK，价格 3，手续费 0"
NEW_COIN_ROWS = table(
    row(side="buy", coin="PIKA", quantity="100 PIKA", price="0.5", fee="0", time="昨天"),
    row(side="buy", coin="ZORK", quantity="2 ZORK", price="3", fee="0", time="昨天"),
)
PIKA_AGAIN = "今天又买了 50 PIKA，价格 0.6，手续费 0"
PIKA_ROW = table(
    row(side="buy", coin="PIKA", quantity="50 PIKA", price="0.6", fee="0", time="今天")
)
ZORK_AGAIN = "今天又买了 1 ZORK，价格 3，手续费 0"
ZORK_ROW = table(row(side="buy", coin="ZORK", quantity="1 ZORK", price="3", fee="0", time="今天"))


def saved_pika_but_not_zork(book: SqliteStore) -> None:
    """PIKA and ZORK both confirmed; the ZORK trade then left out; the PIKA one saved."""
    fake = RoutedModel(screen=[SPOT], extraction=[NEW_COIN_ROWS])
    *_, settled = walk(begin(NEW_COIN, fake), fake, "yes", "yes")
    assert [record.coin for record in settled.records] == ["PIKA", "ZORK"]
    save(finish(remove(settled, 2)), book, now=SAVED_AT)


def test_a_coin_confirmed_and_saved_is_known_after_the_book_is_opened_again(
    tmp_path: Path,
) -> None:
    saved_pika_but_not_zork(SqliteStore(tmp_path / "book.sqlite3"))
    reopened = SqliteStore(tmp_path / "book.sqlite3")
    fake = RoutedModel(screen=[SPOT], extraction=[PIKA_ROW])

    progress = start(PIKA_AGAIN, fake, now=NOW, zone=ZONE, book=reopened)

    assert progress.stage is Stage.REVIEWING
    assert [record.coin for record in progress.records] == ["PIKA"]


def test_a_coin_confirmed_but_not_saved_is_not_known_after_the_book_is_opened_again(
    tmp_path: Path,
) -> None:
    saved_pika_but_not_zork(SqliteStore(tmp_path / "book.sqlite3"))
    reopened = SqliteStore(tmp_path / "book.sqlite3")
    fake = RoutedModel(screen=[SPOT], extraction=[ZORK_ROW])

    progress = start(ZORK_AGAIN, fake, now=NOW, zone=ZONE, book=reopened)

    assert progress.question is not None
    assert isinstance(progress.question.asked, ConfirmCoin)
    assert [coin.symbol for coin in reopened.confirmed_coins()] == ["PIKA"]


def test_the_export_after_the_book_is_opened_again_carries_the_saved_coins_card(
    tmp_path: Path,
) -> None:
    saved_pika_but_not_zork(SqliteStore(tmp_path / "book.sqlite3"))
    reopened = SqliteStore(tmp_path / "book.sqlite3")
    when = datetime(2026, 10, 8, 6, 0, tzinfo=timezone.utc)

    outcome = export(reopened, tmp_path / "exports", now=when, zone=ZONE)

    assert outcome.result is ExportResult.EXPORTED
    assert outcome.path is not None
    data = json.loads(outcome.path.read_text(encoding="utf-8"))["ledgerData"]
    assert [card["symbol"] for card in data["assets"]] == ["PIKA"]
    assert [trade["assetSymbol"] for trade in data["trades"]] == ["PIKA"]
    assert reopened.trades(Listing.NOT_EXPORTED) == ()
