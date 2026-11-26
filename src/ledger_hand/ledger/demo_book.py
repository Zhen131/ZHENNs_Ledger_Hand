"""The demo book: the invented book, with seven more assets and nine buys in August 2026.

The assistant page and the try-out script start the fake ledger with this
book; the tests and the measures written before it keep the invented book
(``invented_book``), which stays as it is. This book takes the invented
book's assets, trades and market prices as they are, and adds:

- seven assets: SOL and DOT (crypto), and Intel, Coca-Cola, Apple, NVIDIA
  and PepsiCo (stocks), none of which can price a trade;
- nine buys between 3 and 24 August 2026 (``t-12`` to ``t-20``), one each
  of BTC, ETH, SOL, ADA, MSFT, INTC, KO, AAPL and NVDA, large enough that
  a sale said later in the autumn is never turned down for want of a
  holding: coins priced in USDT, shares in USD.

PepsiCo and DOT have no trade at all, so that an asset the ledger lists
but was never traded can be tried. The nine buys all fall before the
invented book's first trade (12 September 2026), so every trade of the
invented book keeps its place in time; only what is held, the costs and
the profits of the later sells come out otherwise. SOL, Intel, Coca-Cola,
Apple and NVIDIA have a market price near their August buy; ADA, PepsiCo
and DOT have none, so ADA's profit on paper is not worked out.

Every number here is made up, as in the invented book, and copies no real
trade and no test sentence. Why it exists: the assistant is shown on
stocks with Chinese names, and on sells said months later, which the
invented book could not hold (decided on 2026-11-25).

``demo_ledger`` gives a new fake ledger holding this book.

Names defined here: ``DEMO_ASSETS``, ``DEMO_TRADES``,
``DEMO_MARKET_PRICES`` and ``demo_ledger``.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from ledger_hand.core.ledger_records import Asset, AssetKind, Pricing, TradeFacts
from ledger_hand.core.trade import Side
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ledger.invented_book import (
    INVENTED_ASSETS,
    INVENTED_MARKET_PRICES,
    INVENTED_TRADES,
    INVENTED_ZONE,
)

_BUDAPEST = ZoneInfo(INVENTED_ZONE)


def _asset(code: str, name: str, kind: AssetKind) -> Asset:
    return Asset(
        id=f"asset-{code.lower()}", code=code, name=name, kind=kind, pricing=Pricing.CANNOT_PRICE
    )


DEMO_ASSETS = (
    *INVENTED_ASSETS,
    _asset("SOL", "Solana", AssetKind.CRYPTO),
    _asset("INTC", "Intel", AssetKind.STOCK),
    _asset("KO", "Coca-Cola", AssetKind.STOCK),
    _asset("AAPL", "Apple", AssetKind.STOCK),
    _asset("NVDA", "NVIDIA", AssetKind.STOCK),
    _asset("PEP", "PepsiCo", AssetKind.STOCK),
    _asset("DOT", "Polkadot", AssetKind.CRYPTO),
)


def _buy(
    day: int,
    clock: tuple[int, int],
    asset: str,
    amounts: tuple[str, str, str],
    quote: str,
    fee: str,
    platform: str,
    raw_text: str,
) -> TradeFacts:
    """One invented buy in August 2026: ``amounts`` are quantity, price, total; fee in ``quote``."""
    quantity, price, total = (Decimal(amount) for amount in amounts)
    return TradeFacts(
        occurred=datetime(2026, 8, day, *clock, tzinfo=_BUDAPEST),
        side=Side.BUY,
        asset=asset,
        quantity=quantity,
        price=price,
        total=total,
        quote=quote,
        fee=Decimal(fee),
        fee_asset=quote,
        platform=platform,
        note="",
        raw_text=raw_text,
        zone=INVENTED_ZONE,
        date_only=False,
        cost_rate=None,
    )


# The nine buys, oldest first, then the invented book's trades, oldest first.
DEMO_TRADES = (
    (
        "t-12",
        _buy(
            3,
            (10, 0),
            "BTC",
            ("1", "58000", "58000"),
            "USDT",
            "58",
            "OKX",
            "8月3号10:00在OKX买了1个BTC，58000 USDT一个，手续费58 USDT",
        ),
    ),
    (
        "t-13",
        _buy(
            5,
            (11, 0),
            "ETH",
            ("10", "2600", "26000"),
            "USDT",
            "26",
            "Binance",
            "Bought 10 ETH at 2600 USDT on Binance, 5 August 11:00, fee 26 USDT.",
        ),
    ),
    (
        "t-14",
        _buy(
            7,
            (12, 0),
            "SOL",
            ("100", "160", "16000"),
            "USDT",
            "16",
            "Binance",
            "8月7号12:00在币安买了100个SOL，160 USDT一个，手续费16 USDT",
        ),
    ),
    (
        "t-15",
        _buy(
            10,
            (13, 0),
            "ADA",
            ("20000", "0.38", "7600"),
            "USDT",
            "7.6",
            "OKX",
            "8月10号13:00在OKX买了20000个ADA，均价0.38，手续费7.6 USDT",
        ),
    ),
    (
        "t-16",
        _buy(
            12,
            (15, 40),
            "MSFT",
            ("50", "405", "20250"),
            "USD",
            "1",
            "Broker",
            "Bought 50 MSFT at 405 USD a share, 12 August 15:40, fee 1 USD.",
        ),
    ),
    (
        "t-17",
        _buy(
            14,
            (16, 0),
            "INTC",
            ("50", "22", "1100"),
            "USD",
            "1",
            "Broker",
            "8月14号16:00买了50股INTC，22美元一股，手续费1美元",
        ),
    ),
    (
        "t-18",
        _buy(
            18,
            (16, 10),
            "KO",
            ("50", "70", "3500"),
            "USD",
            "1",
            "Broker",
            "8月18号16:10买了50股KO，70美元一股，手续费1美元",
        ),
    ),
    (
        "t-19",
        _buy(
            20,
            (16, 20),
            "AAPL",
            ("50", "225", "11250"),
            "USD",
            "1",
            "Broker",
            "Bought 50 AAPL at 225 USD a share, 20 August 16:20, fee 1 USD.",
        ),
    ),
    (
        "t-20",
        _buy(
            24,
            (16, 30),
            "NVDA",
            ("50", "120", "6000"),
            "USD",
            "1",
            "Broker",
            "8月24号16:30买了50股NVDA，120美元一股，手续费1美元",
        ),
    ),
    *INVENTED_TRADES,
)

# The invented book's market prices, and five more near each asset's August
# buy, so that a price said at about that level is never far from it. ADA,
# PepsiCo and DOT have none on purpose: an asset held with no market price,
# and two never traded (decided on 2026-11-25; every figure made up).
DEMO_MARKET_PRICES = {
    **INVENTED_MARKET_PRICES,
    ("SOL", "USDT"): Decimal("150"),
    ("INTC", "USD"): Decimal("24"),
    ("KO", "USD"): Decimal("70"),
    ("AAPL", "USD"): Decimal("230"),
    ("NVDA", "USD"): Decimal("130"),
}


def demo_ledger() -> FakeLedger:
    """A new fake ledger holding the demo book: its assets, its trades and its market prices."""
    return FakeLedger(assets=DEMO_ASSETS, trades=DEMO_TRADES, prices=DEMO_MARKET_PRICES)
