"""Every mark made for a row of the table of examples passes the ledger's own rules for marks.

The ledger's rules (``assistant-link/README.md`` in the ledger, "Unfinished
trades and field marks"): a mark is exactly ``field``, ``kind`` and
``reason``; the field and the kind are names it knows; one mark a field;
a suspicious mark has a reason; a reason is at most 256 UTF-16 units; an
empty field carries only a suspicious mark. Each row is said with a
scripted model against the demo book, and its marks are put through the
guard before sending (``as_sent``). For now the marks are not sent to the
ledger; this keeps them ready to be. Every sentence is invented.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from ledger_hand.core.marks import Field, MarkKind, as_sent, fields_sent, reason_length
from ledger_hand.ledger.demo_book import DEMO_ASSETS, DEMO_MARKET_PRICES, DEMO_TRADES
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ports import LedgerError, LedgerErrorKind
from tests.flows.test_marks_examples import ETH_2600, ETH_2600_CELLS, ROW_1_CELLS, ROW_1_WORDS, send


def ledger(**prices: Any) -> FakeLedger:
    return FakeLedger(assets=DEMO_ASSETS, trades=DEMO_TRADES, **prices)


def btc(price: str) -> tuple[str, dict[str, str]]:
    cells = {
        "side": "buy",
        "coin": "BTC",
        "quantity": "0.01个BTC",
        "price": price,
        "fee": "0",
        "time": "今天上午10点",
    }
    return f"今天上午10点买了0.01个BTC，价格{price}，手续费0", cells


def eth30(price: str) -> tuple[str, dict[str, str]]:
    cells = {
        "side": "buy",
        "coin": "ETH",
        "total": "30美金",
        "price": price,
        "fee": "0",
        "time": "今天上午10点",
    }
    return f"今天上午10点花了30美金买了ETH，均价{price}，手续费0", cells


FAILING = LedgerError(LedgerErrorKind.TIMED_OUT, "timed_out", "No answer.")
ROWS = {
    "01": (ROW_1_WORDS, ROW_1_CELLS, None),
    "02": (*btc("12976 USDT"), None),
    "03": (*btc("12977 USDT"), None),
    "04": (*btc("324400 USDT"), None),
    "05": (*btc("324399 USDT"), None),
    "07": (ETH_2600, ETH_2600_CELLS, ledger(prices={("ETH", "USD"): Decimal("2700")})),
    "07c": (*btc("950 USDT"), ledger(prices={("BTC", "USDT"): Decimal("0")})),
    "08": (*eth30("2400"), None),
    "09": (*eth30("240"), None),
    "12": (ROW_1_WORDS, ROW_1_CELLS, ledger(prices=DEMO_MARKET_PRICES, market_failure=FAILING)),
    "16": (
        "今天10点花了950U买了10个BTC，手续费0",
        {
            "side": "buy",
            "coin": "BTC",
            "quantity": "10个BTC",
            "total": "950U",
            "fee": "0",
            "time": "今天10点",
        },
        None,
    ),
    "17": (
        "11月20号买了0.1个ETH，价格2600 USDT，手续费0",
        {
            "side": "buy",
            "coin": "ETH",
            "quantity": "0.1个ETH",
            "price": "2600 USDT",
            "fee": "0",
            "time": "11月20号",
        },
        None,
    ),
}


def ledger_problems(wire: tuple[dict[str, Any], ...], empty: frozenset[Field]) -> list[str]:
    """What the ledger would refuse in ``wire``, the marks of one trade as sent."""
    problems: list[str] = []
    names = {field.value for field in Field}
    kinds = {kind.value for kind in MarkKind}
    seen = [mark.get("field") for mark in wire]
    if len(set(seen)) != len(seen):
        problems.append("two marks on one field")
    for mark in wire:
        if set(mark) != {"field", "kind", "reason"}:
            problems.append(f"keys {sorted(mark)}")
        if mark["field"] not in names or mark["kind"] not in kinds:
            problems.append(f"unknown {mark}")
        reason = mark["reason"]
        if mark["kind"] == "suspicious" and (not isinstance(reason, str) or not reason.strip()):
            problems.append("suspicious without a reason")
        if isinstance(reason, str) and reason_length(reason) > 256:
            problems.append("reason too long")
        if mark["field"] in {field.value for field in empty} and mark["kind"] != "suspicious":
            problems.append("an empty field marked other than suspicious")
    return problems


@pytest.mark.parametrize("row", sorted(ROWS))
def test_the_marks_of_every_row_pass_the_ledgers_rules(row: str) -> None:
    words, cells, book = ROWS[row]
    said, _ = send(words, cells, ledger=book)

    recorded = said.recorded
    assert recorded is not None and recorded.trades, said.reply
    for facts, marked in zip(recorded.trades, recorded.marked, strict=True):
        sent = fields_sent(facts)
        wire = as_sent(marked.marks, sent)
        assert ledger_problems(wire, frozenset(Field) - sent) == []
        assert len(wire) == len(marked.marks.marks)


def test_a_day_alone_sends_no_time_of_day() -> None:
    words, cells, _ = ROWS["17"]
    said, _ = send(words, cells)

    assert said.recorded is not None
    (facts,) = said.recorded.trades
    assert not {Field.OCCURRED_TIME, Field.OCCURRED_TIME_ZONE} & fields_sent(facts)
