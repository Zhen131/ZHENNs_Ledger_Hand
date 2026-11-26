"""Tests of ``scripts/try_assistant.py``'s two lines under each trade sent: its marks, its price.

"marks: ..." lists every mark of the trade, cell by cell, with its reason,
or says "marks: none"; "price check: ..." says what came of comparing the
price with the ledger's market price. Both follow the money line, and
nothing the script printed before changes. A scripted model and the demo
ledger stand in; every sentence and figure is invented.
"""

from __future__ import annotations

import io
from decimal import Decimal

from ledger_hand.ledger.demo_book import DEMO_ASSETS, DEMO_TRADES, demo_ledger
from ledger_hand.ledger.fake_ledger import FakeLedger
from scripts import try_assistant
from tests.fakes.routed_model import RoutedModel
from tests.flows.scripted_flow import row, screened, table
from tests.flows.test_marks_examples import RECORD, ROW_1_CELLS, ROW_1_WORDS


def run(words: str, cells: dict[str, str], ledger: FakeLedger, gap: str = "5") -> list[str]:
    model = RoutedModel(
        tools=[RECORD],
        screen=[screened(("spot_trade", cells["coin"]))],
        extraction=[table(row(**cells))],
    )
    out = io.StringIO()
    status = try_assistant.main(
        [words], out=out, model=model, ledger=ledger, max_steps=6, price_gap=Decimal(gap)
    )
    assert status == 0
    return out.getvalue().splitlines()


def under_the_trade(lines: list[str]) -> list[str]:
    """The two lines after the money line of the one trade sent."""
    at = next(index for index, line in enumerate(lines) if line.startswith("    money:"))
    return lines[at + 1 : at + 3]


def test_the_fourth_sentence_prints_the_price_suspicious_and_the_total_worked_out() -> None:
    marks, price = under_the_trade(run(ROW_1_WORDS, ROW_1_CELLS, demo_ledger()))

    assert marks.startswith(
        "    marks: price: suspicious (far from the market price of BTC in the ledger, 64880 USDT"
    )
    assert marks.endswith("; totalValue: computed (worked out as quantity × price)")
    assert price == (
        "    price check: far from the market price: 64880 USDT on 2026-11-24, about 68 times lower"
    )


def test_a_trade_with_no_mark_and_no_market_price_says_so() -> None:
    cells = {
        "side": "buy",
        "coin": "ADA",
        "quantity": "100个ADA",
        "price": "5 USDT",
        "total": "500 USDT",
        "fee": "0",
        "time": "今天上午10点",
    }
    lines = run("今天上午10点买了100个ADA，价格5 USDT，共500 USDT，手续费0", cells, demo_ledger())

    assert under_the_trade(lines) == [
        "    marks: none",
        "    price check: no market price in the ledger",
    ]


def test_a_market_price_in_another_money_prints_not_compared() -> None:
    ledger = FakeLedger(
        assets=DEMO_ASSETS, trades=DEMO_TRADES, prices={("ETH", "USD"): Decimal("2700")}
    )
    cells = {
        "side": "buy",
        "coin": "ETH",
        "quantity": "0.1个ETH",
        "price": "2600 USDT",
        "fee": "0",
        "time": "今天上午10点",
    }
    lines = run("今天上午10点买了0.1个ETH，成交价2600 USDT，手续费0", cells, ledger)

    assert under_the_trade(lines)[1] == (
        "    price check: not compared: the market price is in USD and the trade in USDT, "
        "never taken as one money"
    )
