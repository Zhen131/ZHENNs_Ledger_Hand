"""Tests of what is handed back to the model: amounts as exact text, money always named.

A figure that was not worked out is handed back as its reason, never as a
number; each sell carries its profit; the program's own answers carry a
status word.
"""

from __future__ import annotations

import json

from ledger_hand.assistant.results import (
    not_connected_text,
    positions_text,
    summary_text,
    trades_text,
)
from ledger_hand.core.ledger_records import PeriodRequest, TradeFilter
from ledger_hand.core.trade import Side
from ledger_hand.ledger.fake_ledger import FakeLedger


def test_holdings_name_their_money_and_give_a_reason_where_there_is_no_figure() -> None:
    held = {
        entry["asset"]: entry
        for entry in json.loads(positions_text(FakeLedger().positions()))["positions"]
    }

    assert held["MSFT"]["bought_with"] == "USD"
    assert held["MSFT"]["cost"]["currency"] == "USD"
    assert isinstance(held["BTC"]["quantity"], str)
    assert "market price" in held["ADA"]["unrealized_profit"]["not_worked_out"]


def test_a_sell_carries_its_profit_and_every_amount_is_text() -> None:
    (sell,) = json.loads(
        trades_text(FakeLedger().list_trades(TradeFilter(asset="ETH", side=Side.SELL)).trades)
    )["trades"]

    assert sell["realized_profit"] == {"amount": "56.84221053", "currency": "USDT"}
    assert (sell["priced_in"], sell["fee_in"]) == ("USDT", "USDT")
    assert all(isinstance(sell[name], str) for name in ("quantity", "price", "total", "fee"))


def test_sums_are_given_for_each_money_apart() -> None:
    summary = json.loads(summary_text(FakeLedger().period_summary(PeriodRequest())))

    assert [entry["currency"] for entry in summary["by_currency"]] == ["USD", "USDT"]
    assert summary["trade_count"] == 11


def test_a_tool_not_built_yet_says_so() -> None:
    assert json.loads(not_connected_text())["status"] == "not_connected"
