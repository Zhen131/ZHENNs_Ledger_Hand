"""Tests of recording a passage with the asset table made for the tests, through scripted models.

The table prices trades in USDT or USD, knows Bitcoin, Ether and one share,
reads "股" after a number, and refuses an asset it does not hold. Each test
walks one passage from the judging step to its records, the way the record
page does, with only the table changed. Every passage and reply is invented.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from ledger_hand.core.book import ConfirmedCoin
from ledger_hand.core.followup import AskCell, Cell
from ledger_hand.core.stored import StoredTrade
from ledger_hand.core.validation import Missing, Violation
from ledger_hand.export.backup import ExportIssue, ExportProblem, ExportRefused, export_backup
from ledger_hand.extraction.answer_phrase import AnswerProblem
from ledger_hand.flows.progress import Progress, Stage, TradeStatus
from ledger_hand.flows.recording import answer, finish, start
from ledger_hand.flows.saving import save
from ledger_hand.ports import StorageError, StorageErrorKind, StoragePort
from ledger_hand.storage.sqlite_store import SqliteStore
from tests.core.two_moneys import TWO_MONEYS
from tests.fakes.memory_store import MemoryStore
from tests.fakes.routed_model import RoutedModel
from tests.flows.scripted_flow import NOW, ZONE, row, screened, table

SHARES = "昨天买了 2 股微软，每股 400 美元，手续费 0"
SHARE_ROW = row(side="buy", coin="微软", quantity="2 股", price="400 美元", fee="0", time="昨天")
BITCOIN = "昨天买了 0.1 BTC，价格 60000，手续费 0"
BITCOIN_ROW = row(side="buy", coin="BTC", quantity="0.1 BTC", price="60000", fee="0", time="昨天")


def model_for(passage: str, *rows: dict[str, str]) -> RoutedModel:
    evidence = passage.split("，")[0]
    return RoutedModel(screen=[screened(("spot_trade", evidence))], extraction=[table(*rows)])


def begin(passage: str, model: RoutedModel, book: StoragePort | None = None) -> Progress:
    return start(passage, model, now=NOW, zone=ZONE, assets=TWO_MONEYS, book=book)


def asked(progress: Progress) -> object:
    assert progress.question is not None, progress.stage
    return progress.question.asked


# --- a share bought in USD ----------------------------------------------------


def test_a_share_bought_in_usd_is_recorded_priced_in_usd_with_its_quantity_read() -> None:
    model = model_for(SHARES, SHARE_ROW)

    settled = begin(SHARES, model)

    assert settled.stage is Stage.REVIEWING
    (record,) = settled.records
    assert (record.coin, record.quantity, record.price) == ("MSFT", Decimal("2"), Decimal("400"))
    assert (record.quote, record.fee_coin, record.total) == ("USD", "USD", Decimal("800"))


# --- the money not said, or not clear ------------------------------------------


def test_no_money_said_asks_which_and_the_answer_is_the_money_recorded() -> None:
    model = model_for(BITCOIN, BITCOIN_ROW)

    first = begin(BITCOIN, model)

    assert asked(first) == AskCell(Cell.QUOTE, Missing.QUOTE)
    assert first.question is not None
    assert first.question.label == "[Trade 1 of 1: pricing currency]"
    assert "Answer with one of: USDT, USD." in first.question.notes
    settled = answer(first, "USD", model)
    assert settled.stage is Stage.REVIEWING
    assert [(r.quote, r.fee_coin) for r in settled.records] == [("USD", "USD")]


def test_a_word_both_moneys_go_by_asks_which_and_is_not_taken_as_an_answer() -> None:
    passage = "昨天买了 0.1 BTC，价格 60000 刀，手续费 0"
    model = model_for(
        passage,
        row(side="buy", coin="BTC", quantity="0.1 BTC", price="60000 刀", fee="0", time="昨天"),
    )

    first = begin(passage, model)
    assert asked(first) == AskCell(Cell.QUOTE, Missing.QUOTE)

    again = answer(first, "刀", model)
    assert again.question is not None
    assert again.question.again == AnswerProblem.MONEY_NAMES_SEVERAL.value

    settled = answer(again, "泰达币", model)
    assert [r.quote for r in settled.records] == ["USDT"]


def test_a_fee_in_a_word_both_moneys_go_by_asks_the_fee_s_coin() -> None:
    passage = "昨天买了 0.1 BTC，价格 60000 美元，手续费 3 刀"
    model = model_for(
        passage,
        row(
            side="buy", coin="BTC", quantity="0.1 BTC", price="60000 美元", fee="3 刀", time="昨天"
        ),
    )

    first = begin(passage, model)
    assert asked(first) == AskCell(Cell.FEE_COIN, Missing.FEE_COIN)

    settled = answer(first, "U", model)
    assert [(r.quote, r.fee, r.fee_coin) for r in settled.records] == [
        ("USD", Decimal("3"), "USDT")
    ]


# --- what cannot be recorded with this table ---------------------------------------


def _cannot_record(passage: str, trade_row: dict[str, str]) -> Progress:
    settled = begin(passage, model_for(passage, trade_row))
    assert settled.stage is Stage.REVIEWING
    assert settled.question is None
    (trade,) = settled.trades
    assert trade.status is TradeStatus.CANNOT_RECORD
    return settled


def test_money_the_table_does_not_price_in_cannot_be_recorded() -> None:
    passage = "昨天买了 0.1 BTC，价格 60000，用欧元付的，手续费 0"
    trade_row = row(
        side="buy",
        coin="BTC",
        quantity="0.1 BTC",
        price="60000",
        price_currency="欧元",
        fee="0",
        time="昨天",
    )

    settled = _cannot_record(passage, trade_row)

    assert settled.trades[0].reason is Violation.QUOTE_CANNOT_PRICE


def test_an_asset_not_in_the_table_cannot_be_recorded_and_is_never_offered() -> None:
    passage = "昨天买了 2 SOL，价格 150 美元，手续费 0"
    trade_row = row(
        side="buy", coin="SOL", quantity="2 SOL", price="150 美元", fee="0", time="昨天"
    )

    settled = _cannot_record(passage, trade_row)

    assert settled.trades[0].reason is Violation.ASSET_NOT_IN_LEDGER


def test_a_money_trades_are_priced_in_cannot_be_the_asset_traded() -> None:
    passage = "昨天买了 100 USD，价格 1 U，手续费 0"
    trade_row = row(side="buy", coin="USD", quantity="100 USD", price="1 U", fee="0", time="昨天")

    settled = _cannot_record(passage, trade_row)

    assert settled.trades[0].reason is Violation.COIN_IS_PRICING_MONEY


def test_an_answer_naming_an_asset_not_in_the_table_is_not_taken() -> None:
    passage = "昨天买了一些，数量 0.1，价格 60000 U，手续费 0"
    model = model_for(
        passage, row(side="buy", quantity="0.1", price="60000 U", fee="0", time="昨天")
    )

    first = begin(passage, model)
    assert asked(first) == AskCell(Cell.COIN, Missing.COIN)

    again = answer(first, "SOL", model)
    assert again.question is not None
    assert again.question.asked == AskCell(Cell.COIN, Missing.COIN)
    assert again.question.again == AnswerProblem.ASSET_NOT_IN_LEDGER.value

    settled = answer(again, "比特币", model)
    assert [(r.coin, r.quote) for r in settled.records] == [("BTC", "USDT")]


# --- coins confirmed before are not used, and none are kept ------------------------


def test_coins_confirmed_before_are_not_joined_and_none_are_kept() -> None:
    book = MemoryStore()
    book.coins["PIKA"] = ConfirmedCoin(symbol="PIKA", confirmed_at=NOW)
    passage = "昨天买了 0.1 BTC，价格 60000 U，手续费 0"
    model = model_for(
        passage,
        row(side="buy", coin="BTC", quantity="0.1 BTC", price="60000 U", fee="0", time="昨天"),
    )

    settled = begin(passage, model, book)
    assert settled.setting.assets.find("PIKA") is None

    saved = save(finish(settled), book, now=NOW)
    assert saved.coins == ()
    assert [trade.record.quote for trade in saved.trades] == ["USDT"]


# --- the book and the export refuse a trade priced in USD --------------------------


def _bought_in_usd() -> Progress:
    return finish(begin(SHARES, model_for(SHARES, SHARE_ROW)))


@pytest.mark.parametrize("plug", ["memory", "sqlite"])
def test_the_book_refuses_a_trade_priced_in_usd(plug: str, tmp_path: Path) -> None:
    book: StoragePort = MemoryStore() if plug == "memory" else SqliteStore(tmp_path / "b.sqlite3")

    with pytest.raises(StorageError) as raised:
        save(_bought_in_usd(), book, now=NOW)

    assert raised.value.kind is StorageErrorKind.CONFLICT


def test_the_export_refuses_a_trade_priced_in_usd_and_names_it() -> None:
    (record,) = _bought_in_usd().records
    trade = StoredTrade(id="share-1", record=record, created_at=NOW, updated_at=NOW)

    refused = export_backup(
        [trade],
        TWO_MONEYS.coins,
        exported_at=NOW,
        today=datetime(2026, 10, 7, tzinfo=ZoneInfo(ZONE)).date(),
        app_name="ledger-hand",
        app_version="0.1.0",
    )

    assert isinstance(refused, ExportRefused)
    assert ExportIssue(ExportProblem.NOT_PRICED_IN_USDT, "share-1") in refused.issues
