"""Tests of the try-out script on cash: the balances printed one line a money, money moved named.

The script runs with a scripted model and the demo ledger with cash; no
model is called. Every figure is invented.
"""

from __future__ import annotations

import io

from ledger_hand.ledger.demo_cash import demo_ledger_with_cash
from ledger_hand.ledger.fake_ledger import FakeLedger
from scripts import try_assistant
from tests.fakes.routed_model import RoutedModel


def run(*sentences: str, ledger: FakeLedger) -> str:
    out = io.StringIO()
    try_assistant.main(list(sentences), model=RoutedModel(), max_steps=6, ledger=ledger, out=out)
    return out.getvalue()


def test_the_balances_are_printed_one_line_a_money_as_the_ledger_gave_them() -> None:
    printed = run("我还有多少USDT", ledger=demo_ledger_with_cash().taking_cards())

    assert "cash balances: counted up to 2026-11-24" in printed
    assert "  USDT (Tether): 140080.18724 USDT" in printed
    assert "  USD (US dollar): 17093.94 USD" in printed
    assert "sent to the ledger: nothing" in printed


def test_a_ledger_with_no_tool_is_said_to_have_none() -> None:
    printed = run("我还有多少USDT", ledger=FakeLedger())

    assert "cash balances: the ledger has no tool for them" in printed


def test_money_moved_is_named_and_nothing_is_sent() -> None:
    printed = run("我今天入金了500 USDT", ledger=demo_ledger_with_cash().taking_cards())

    assert "money moved, to record by hand: deposits" in printed
    assert "Please record it in the ledger yourself." in printed
    assert "sent to the ledger: nothing" in printed
