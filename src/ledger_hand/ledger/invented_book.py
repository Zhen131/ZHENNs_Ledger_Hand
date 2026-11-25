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
  paper is therefore not worked out;
- for each trade, the words it was recorded from, made up too, whose
  figures agree with the trade.

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
    raw_text: str,
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
        raw_text=raw_text,
        zone=INVENTED_ZONE,
        date_only=False,
        cost_rate=None,
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
            "9月12号10:15在OKX买了0.0153 BTC，均价57310，花了876.843U，手续费0.0000153 BTC",
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
            "Bought 0.42 ETH at 2287 on Binance, 18 September 14:02, fee 0.96054 USDT.",
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
            "9月25号20:37在OKX买了640个ADA，0.2931一个，共187.584 USDT，手续费0.64 ADA，小试一下",
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
            "Bought 3 MSFT at 412.37 USD on 2 October at 9:20, fee 1.05 USD.",
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
            "10月6号11:48在OKX买了0.0082 BTC，均价61940，花了507.908 USDT，手续费0.0000082 BTC",
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
            "10月6号16:25在币安买了0.15 ETH，2446一个，共366.9 USDT，手续费0.3669 USDT",
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
            "Sold 0.2 ETH at 2618 on Binance, 14 October 13:11, fee 0.5236 USDT.",
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
            "10月21号8:54在OKX卖了0.006 BTC，66120一个，收到396.72 USDT，手续费0.39672 USDT",
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
            "11月3号19:30在OKX买了300个ADA，0.3127一个，共93.81 USDT，手续费0.3 ADA",
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
            "Sold 1 MSFT at 438.15 USD on 12 November at 15:40 through the broker, fee 1.05 USD.",
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
            "11月19号10:05在币安买了0.05 ETH，2734一个，共136.7 USDT，手续费0.00005 ETH",
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
