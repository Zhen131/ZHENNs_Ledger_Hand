"""The demo ledger with a euro: cash, a euro, and the money each of its own assets is priced in.

The assistant page and the try-out script start the fake ledger with this
one (decided on 2026-11-26), so that "花了128欧元买了2股KO，一股69.5美元" can
be shown as the ledger takes it: paid in euros for a share priced in US
dollars, with the rate between the two. It is the demo ledger with cash
(``demo_cash``), its trades and market prices as they are, and:

- a euro (``asset-eur``, EUR, "Euro"), a cash money trades may be paid in,
  after every asset of the demo book, as a money the user added in the
  ledger comes last;
- the money each of the demo book's seven own assets is itself priced in,
  as the real ledger names it: USDT for SOL and DOT, the US dollar for
  INTC, KO, AAPL, NVDA and PEP. The four assets it takes from the invented
  book (BTC, ETH, ADA, MSFT) say none, as there, so "花欧元买微软" is
  asked about as before;
- 5000 euros of opening cash, made up.

The demo book's own file is left byte for byte as it is (a test of the
exam pins it), and ``demo_ledger`` and ``demo_ledger_with_cash`` still make
the ledgers every test written before uses. The demo book has no trade paid
in euros, so a rate worked out on ``demo_ledger_with_euro`` alone is never
compared with an earlier one: the reply says so.

The assistant page and the try-out script also turn on the ledger's tool
for exchange rates (``FakeLedger.listing_rates``, 2026-11-27), with two
made-up rates between the euro and the US dollar, one each way round, as
the real ledger may hold them (``DEMO_EURO_RATES``): then that rate is
compared with the ledger's instead. ``demo_ledger_with_euro`` alone has no
such tool, so every test written before keeps the ledger it was written
against.

Names defined here: ``EURO``, ``DEMO_PRICED_IN``, ``DEMO_EURO_ASSETS``,
``DEMO_EURO_OPENING_CASH``, ``DEMO_EURO_RATES``, ``demo_ledger_with_euro``
and ``demo_ledger_with_euro_rates``.
"""

from __future__ import annotations

import dataclasses
from decimal import Decimal

from ledger_hand.core.ledger_rate import RateRow
from ledger_hand.core.ledger_records import Asset, AssetKind, Pricing
from ledger_hand.ledger.demo_book import DEMO_ASSETS, DEMO_MARKET_PRICES, DEMO_TRADES
from ledger_hand.ledger.demo_cash import DEMO_OPENING_CASH
from ledger_hand.ledger.fake_ledger import FakeLedger

# A money the user added in the ledger, as the ledger names one it adds (73C1).
EURO = Asset(
    id="asset-eur",
    code="EUR",
    name="Euro",
    kind=AssetKind.CASH,
    pricing=Pricing.CAN_PRICE,
)

# The money each of the demo book's own seven assets is itself priced in.
DEMO_PRICED_IN = {
    "SOL": "USDT",
    "DOT": "USDT",
    "INTC": "USD",
    "KO": "USD",
    "AAPL": "USD",
    "NVDA": "USD",
    "PEP": "USD",
}

DEMO_EURO_ASSETS = (
    *(
        dataclasses.replace(asset, price_currency=DEMO_PRICED_IN[asset.code])
        if asset.code in DEMO_PRICED_IN
        else asset
        for asset in DEMO_ASSETS
    ),
    EURO,
)

# The demo ledger's opening cash, and 5000 euros, made up.
DEMO_EURO_OPENING_CASH = {**DEMO_OPENING_CASH, "EUR": Decimal("5000")}


# Two exchange rates between the euro and the US dollar, both made up, neither
# after the demo book's "now" (24 November 2026): one typed in by hand, "1 EUR =
# 1.08 USD", and one as the ledger fetches the euro's rate, the other way round,
# "1 USD = 0.93 EUR" from frankfurter. "花了128欧元买了2股KO，一股69.5美元"
# works out 1.0859375, about 1% from either, so it is not marked.
DEMO_EURO_RATES = (
    RateRow(
        base_id="asset-usd",
        base_code="USD",
        quote_id="asset-eur",
        quote_code="EUR",
        rate="0.93",
        rate_date="2026-11-21",
        source="online",
        online_source="frankfurter",
    ),
    RateRow(
        base_id="asset-eur",
        base_code="EUR",
        quote_id="asset-usd",
        quote_code="USD",
        rate="1.08",
        rate_date="2026-11-20",
        source="manual",
        online_source=None,
    ),
)


def demo_ledger_with_euro_rates() -> FakeLedger:
    """The demo ledger with a euro that takes cards and lists its made-up exchange rates,
    for the assistant page and the try-out script."""
    return demo_ledger_with_euro().taking_cards().listing_rates(DEMO_EURO_RATES)


def demo_ledger_with_euro() -> FakeLedger:
    """A new fake ledger holding the demo book, a euro and its assets' own moneys, with cash."""
    return FakeLedger(
        assets=DEMO_EURO_ASSETS,
        trades=DEMO_TRADES,
        prices=DEMO_MARKET_PRICES,
        opening_cash=DEMO_EURO_OPENING_CASH,
    )
