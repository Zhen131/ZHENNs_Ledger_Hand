"""The demo ledger with cash: the demo book, and opening amounts of USDT and US dollars.

The assistant page and the try-out script start the fake ledger with this
one, so that asked "我还有多少USDT" the assistant has the ledger's cash
balances to lay out (decided on 2026-11-26). It is the demo book
(``demo_book``) as it is, its assets, trades and market prices, with a
tool for cash balances: each opening amount here is moved by every trade
of the book, the ledger's way (``FakeLedger``, ``opening_cash``), so a
trade saved in the demo shows in the balances next asked for.

The demo book's own file is left byte for byte as it is (a test of the
exam pins it), and ``demo_ledger`` there still makes a ledger with no tool
for cash, which every test written before keeps.

The opening amounts are made up, and large enough that no balance goes
below 0: the demo book's August buys alone take about 107708 USDT and
42105 US dollars. With every trade of the book, about 140080.19 USDT and
17093.94 US dollars are left.

Names defined here: ``DEMO_OPENING_CASH`` and ``demo_ledger_with_cash``.
"""

from __future__ import annotations

from decimal import Decimal

from ledger_hand.ledger.demo_book import DEMO_ASSETS, DEMO_MARKET_PRICES, DEMO_TRADES
from ledger_hand.ledger.fake_ledger import FakeLedger

# The cash the demo book starts with, before its first trade.
DEMO_OPENING_CASH = {
    "USDT": Decimal("250000"),
    "USD": Decimal("60000"),
}


def demo_ledger_with_cash() -> FakeLedger:
    """A new fake ledger holding the demo book, with a tool for its cash balances."""
    return FakeLedger(
        assets=DEMO_ASSETS,
        trades=DEMO_TRADES,
        prices=DEMO_MARKET_PRICES,
        opening_cash=DEMO_OPENING_CASH,
    )
