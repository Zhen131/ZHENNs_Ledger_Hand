"""The ledgers the tests of vague words for money are run against, each made here.

Every asset, trade and number is invented. The tests do not rest on the
invented book or the demo book, so either may change without touching
them. The codes follow the demo book: DOT (a coin) and PEP (a share)
have no trade at all.

- ``jia``: USDT and USD price trades; ETH was last bought for USDT, MSFT
  for USD, ADA for USDT; BTC for USD on one day and for USDT the next;
  no euro.
- ``yi``: ``jia`` with a euro that prices trades, and KO last bought for
  euros.
- ``bing``: ``jia`` with USD no longer pricing trades.
- ``ding``: ``jia``, but asking for trades always fails.
- ``wu``: ``jia`` with SOL bought for USDT and for USD on the same day.
- ``ji``: ``jia`` without USD, and without the trades that used it.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from ledger_hand.core.ledger_records import (
    Asset,
    AssetKind,
    Pricing,
    TradeFacts,
    TradeFilter,
    TradeList,
)
from ledger_hand.core.trade import Side
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ledger.invented_book import INVENTED_ZONE
from ledger_hand.ports import LedgerError, LedgerErrorKind

_BUDAPEST = ZoneInfo(INVENTED_ZONE)


def asset(code: str, kind: AssetKind, pricing: Pricing = Pricing.CANNOT_PRICE) -> Asset:
    return Asset(id=f"asset-{code.lower()}", code=code, name=code, kind=kind, pricing=pricing)


def bought(asset_code: str, quote: str, when: tuple[int, int, int, int, int]) -> TradeFacts:
    """A buy of one unit of ``asset_code`` at 10 ``quote``, no fee, at ``when``."""
    return TradeFacts(
        occurred=datetime(*when, tzinfo=_BUDAPEST),
        side=Side.BUY,
        asset=asset_code,
        quantity=Decimal(1),
        price=Decimal(10),
        total=Decimal(10),
        quote=quote,
        fee=Decimal(0),
        fee_asset=quote,
        platform="",
        note="",
        raw_text=None,
        zone=INVENTED_ZONE,
        date_only=False,
        cost_rate=None,
    )


USDT = asset("USDT", AssetKind.CASH, Pricing.CAN_PRICE)
USD = asset("USD", AssetKind.CASH, Pricing.CAN_PRICE)
EUR = asset("EUR", AssetKind.CASH, Pricing.CAN_PRICE)
JIA_ASSETS = (
    USDT,
    USD,
    asset("BTC", AssetKind.CRYPTO),
    asset("ETH", AssetKind.CRYPTO),
    asset("ADA", AssetKind.CRYPTO),
    asset("DOT", AssetKind.CRYPTO),
    asset("MSFT", AssetKind.STOCK),
    asset("PEP", AssetKind.STOCK),
)
JIA_TRADES = (
    ("t-btc-usd", bought("BTC", "USD", (2026, 8, 1, 10, 0))),
    ("t-btc-usdt", bought("BTC", "USDT", (2026, 8, 2, 10, 0))),
    ("t-eth", bought("ETH", "USDT", (2026, 8, 3, 10, 0))),
    ("t-ada", bought("ADA", "USDT", (2026, 8, 4, 10, 0))),
    ("t-msft", bought("MSFT", "USD", (2026, 8, 5, 16, 0))),
)


def jia() -> FakeLedger:
    return FakeLedger(assets=JIA_ASSETS, trades=JIA_TRADES)


def yi() -> FakeLedger:
    assets = (*JIA_ASSETS, EUR, asset("KO", AssetKind.STOCK))
    trades = (*JIA_TRADES, ("t-ko", bought("KO", "EUR", (2026, 8, 6, 16, 0))))
    return FakeLedger(assets=assets, trades=trades)


def bing() -> FakeLedger:
    assets = tuple(
        dataclasses.replace(one, pricing=Pricing.CANNOT_PRICE) if one.code == "USD" else one
        for one in JIA_ASSETS
    )
    return FakeLedger(assets=assets, trades=JIA_TRADES)


class FailingTrades(FakeLedger):
    """The ``jia`` ledger, whose list of trades can never be had."""

    def list_trades(self, trade_filter: TradeFilter) -> TradeList:
        self.calls.append("list_trades")
        raise LedgerError(LedgerErrorKind.UNREACHABLE, "unreachable", "No ledger answered.")


def ding() -> FakeLedger:
    return FailingTrades(assets=JIA_ASSETS, trades=JIA_TRADES)


def wu() -> FakeLedger:
    assets = (*JIA_ASSETS, asset("SOL", AssetKind.CRYPTO))
    trades = (
        *JIA_TRADES,
        ("t-sol-morning", bought("SOL", "USDT", (2026, 8, 7, 9, 0))),
        ("t-sol-afternoon", bought("SOL", "USD", (2026, 8, 7, 15, 0))),
    )
    return FakeLedger(assets=assets, trades=trades)


def ji() -> FakeLedger:
    assets = tuple(one for one in JIA_ASSETS if one.code != "USD")
    trades = tuple(pair for pair in JIA_TRADES if pair[1].quote != "USD")
    return FakeLedger(assets=assets, trades=trades)
