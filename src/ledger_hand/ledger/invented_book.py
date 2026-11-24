"""The invented book the fake ledger starts with: assets, trades and market prices.

Every number here is made up for this book and copies no real trade and no
test sentence. The trades fall between September and November 2026, and
are written against one fixed moment, ``INVENTED_NOW`` (24 November 2026,
23:55 in Budapest), which the try-out script and the tests use as "now".

What the book is built to show:

- two assets that can be the money a trade is priced in, USDT and USD, and
  a stock bought with USD beside coins bought with USDT;
- on 6 October 2026 exactly two trades, a BTC buy and an ETH buy, and on
  25 September 2026 exactly one, an ADA buy: a question about "that trade
  on 6 October" finds more than one;
- two sells of coins and one of the stock, each with its profit or loss;
- fees taken in the asset bought and fees taken in the money paid;
- a market price for every asset held but ADA, whose profit or loss on
  paper is therefore not worked out.

Names defined here: ``INVENTED_ZONE``, ``INVENTED_NOW``, ``INVENTED_ASSETS``,
``INVENTED_TRADES`` and ``INVENTED_MARKET_PRICES``.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from ledger_hand.core.ledger_records import Asset, AssetKind, Pricing, TradeFacts
from ledger_hand.core.trade import Side

INVENTED_ZONE = "Europe/Budapest"
_BUDAPEST = ZoneInfo(INVENTED_ZONE)
INVENTED_NOW = datetime(2026, 11, 24, 23, 55, tzinfo=_BUDAPEST)

INVENTED_ASSETS = (
    Asset(
        id="asset-usdt", code="USDT", name="Tether", kind=AssetKind.CASH, pricing=Pricing.CAN_PRICE
    ),
    Asset(
        id="asset-usd", code="USD", name="US dollar", kind=AssetKind.CASH, pricing=Pricing.CAN_PRICE
    ),
    Asset(
        id="asset-btc",
        code="BTC",
        name="Bitcoin",
        kind=AssetKind.CRYPTO,
        pricing=Pricing.CANNOT_PRICE,
    ),
    Asset(
        id="asset-eth",
        code="ETH",
        name="Ethereum",
        kind=AssetKind.CRYPTO,
        pricing=Pricing.CANNOT_PRICE,
    ),
    Asset(
        id="asset-ada",
        code="ADA",
        name="Cardano",
        kind=AssetKind.CRYPTO,
        pricing=Pricing.CANNOT_PRICE,
    ),
    Asset(
        id="asset-msft",
        code="MSFT",
        name="Microsoft",
        kind=AssetKind.STOCK,
        pricing=Pricing.CANNOT_PRICE,
    ),
)


def _trade(
    when: tuple[int, int, int, int, int],
    side: Side,
    asset: str,
    amounts: tuple[str, str, str],
    quote: str,
    fee: tuple[str, str],
    platform: str,
    note: str,
) -> TradeFacts:
    """One invented trade: ``amounts`` are quantity, price, total; ``fee`` its amount, asset."""
    quantity, price, total = (Decimal(amount) for amount in amounts)
    return TradeFacts(
        occurred=datetime(*when, tzinfo=_BUDAPEST),
        side=side,
        asset=asset,
        quantity=quantity,
        price=price,
        total=total,
        quote=quote,
        fee=Decimal(fee[0]),
        fee_asset=fee[1],
        platform=platform,
        note=note,
    )


_B, _S = Side.BUY, Side.SELL

# Identifiers and trades, oldest first.
INVENTED_TRADES = (
    (
        "t-01",
        _trade(
            (2026, 9, 12, 10, 15),
            _B,
            "BTC",
            ("0.0153", "57310", "876.843"),
            "USDT",
            ("0.0000153", "BTC"),
            "OKX",
            "first buy after the summer",
        ),
    ),
    (
        "t-02",
        _trade(
            (2026, 9, 18, 14, 2),
            _B,
            "ETH",
            ("0.42", "2287", "960.54"),
            "USDT",
            ("0.96054", "USDT"),
            "Binance",
            "",
        ),
    ),
    (
        "t-03",
        _trade(
            (2026, 9, 25, 20, 37),
            _B,
            "ADA",
            ("640", "0.2931", "187.584"),
            "USDT",
            ("0.64", "ADA"),
            "OKX",
            "small bet",
        ),
    ),
    (
        "t-04",
        _trade(
            (2026, 10, 2, 9, 20),
            _B,
            "MSFT",
            ("3", "412.37", "1237.11"),
            "USD",
            ("1.05", "USD"),
            "Broker",
            "",
        ),
    ),
    (
        "t-05",
        _trade(
            (2026, 10, 6, 11, 48),
            _B,
            "BTC",
            ("0.0082", "61940", "507.908"),
            "USDT",
            ("0.0000082", "BTC"),
            "OKX",
            "",
        ),
    ),
    (
        "t-06",
        _trade(
            (2026, 10, 6, 16, 25),
            _B,
            "ETH",
            ("0.15", "2446", "366.9"),
            "USDT",
            ("0.3669", "USDT"),
            "Binance",
            "",
        ),
    ),
    (
        "t-07",
        _trade(
            (2026, 10, 14, 13, 11),
            _S,
            "ETH",
            ("0.2", "2618", "523.6"),
            "USDT",
            ("0.5236", "USDT"),
            "Binance",
            "took some profit",
        ),
    ),
    (
        "t-08",
        _trade(
            (2026, 10, 21, 8, 54),
            _S,
            "BTC",
            ("0.006", "66120", "396.72"),
            "USDT",
            ("0.39672", "USDT"),
            "OKX",
            "",
        ),
    ),
    (
        "t-09",
        _trade(
            (2026, 11, 3, 19, 30),
            _B,
            "ADA",
            ("300", "0.3127", "93.81"),
            "USDT",
            ("0.3", "ADA"),
            "OKX",
            "",
        ),
    ),
    (
        "t-10",
        _trade(
            (2026, 11, 12, 15, 40),
            _S,
            "MSFT",
            ("1", "438.15", "438.15"),
            "USD",
            ("1.05", "USD"),
            "Broker",
            "",
        ),
    ),
    (
        "t-11",
        _trade(
            (2026, 11, 19, 10, 5),
            _B,
            "ETH",
            ("0.05", "2734", "136.7"),
            "USDT",
            ("0.00005", "ETH"),
            "Binance",
            "",
        ),
    ),
)

# The market price of one unit of an asset in a money, at ``INVENTED_NOW``.
# ADA has none on purpose: its profit or loss on paper is not worked out.
INVENTED_MARKET_PRICES = {
    ("BTC", "USDT"): Decimal("64880"),
    ("ETH", "USDT"): Decimal("2701"),
    ("MSFT", "USD"): Decimal("441.62"),
}
