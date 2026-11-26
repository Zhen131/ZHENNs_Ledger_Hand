"""The ledgers the tests of trades paid in another money are run against, each made here.

Every asset, trade and number is invented. The ledgers follow the
contract's table (87B, part 4, item 8), and all take cards, as the real
ledger does now:

- ``jia``: USDT, USD, EUR and CNY price trades. KO (a share, priced in
  USD) was bought for USD in August, its market price 70 USD; AAPL (USD)
  was last bought for EUR on 2026-11-03 at a rate of 1.0859; BTC and ETH
  (coins, priced in USDT) were last bought for USDT; PEP (USD) has no
  trade at all.
- ``yi``: ``jia`` without the euro; that AAPL buy was for USD.
- ``bing``: ``jia`` with the euro no longer pricing trades.
- ``ding``: ``jia``, but no asset says which money it is priced in.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from ledger_hand.core.ledger_records import Asset, AssetKind, Pricing, TradeFacts
from ledger_hand.core.trade import Side
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ledger.invented_book import INVENTED_ZONE

_BUDAPEST = ZoneInfo(INVENTED_ZONE)


def money(code: str) -> Asset:
    return Asset(
        id=f"asset-{code.lower()}",
        code=code,
        name=code,
        kind=AssetKind.CASH,
        pricing=Pricing.CAN_PRICE,
    )


def held(code: str, kind: AssetKind, own: str) -> Asset:
    return Asset(
        id=f"asset-{code.lower()}",
        code=code,
        name=code,
        kind=kind,
        pricing=Pricing.CANNOT_PRICE,
        price_currency=own,
    )


def bought(
    asset: str,
    quote: str,
    when: tuple[int, int, int, int, int],
    price: str,
    rate: str | None = None,
) -> TradeFacts:
    """A buy of one unit of ``asset`` at ``price`` in ``quote``, no fee, at ``when``."""
    return TradeFacts(
        occurred=datetime(*when, tzinfo=_BUDAPEST),
        side=Side.BUY,
        asset=asset,
        quantity=Decimal(1),
        price=Decimal(price),
        total=Decimal(price),
        quote=quote,
        fee=Decimal(0),
        fee_asset=quote,
        platform="",
        note="",
        raw_text=None,
        zone=INVENTED_ZONE,
        date_only=False,
        cost_rate=Decimal(rate) if rate is not None else None,
    )


USDT, USD, EUR, CNY = money("USDT"), money("USD"), money("EUR"), money("CNY")
JIA_ASSETS = (
    USDT,
    USD,
    EUR,
    CNY,
    held("KO", AssetKind.STOCK, "USD"),
    held("AAPL", AssetKind.STOCK, "USD"),
    held("BTC", AssetKind.CRYPTO, "USDT"),
    held("ETH", AssetKind.CRYPTO, "USDT"),
    held("PEP", AssetKind.STOCK, "USD"),
)
KO_AUGUST = ("t-ko", bought("KO", "USD", (2026, 8, 6, 16, 0), "62"))
AAPL_EUR = ("t-aapl-eur", bought("AAPL", "EUR", (2026, 11, 3, 16, 0), "200", rate="1.0859"))
JIA_TRADES = (
    KO_AUGUST,
    ("t-btc", bought("BTC", "USDT", (2026, 8, 2, 10, 0), "95000")),
    ("t-eth", bought("ETH", "USDT", (2026, 8, 3, 10, 0), "2500")),
    AAPL_EUR,
)
JIA_PRICES = {
    ("KO", "USD"): Decimal(70),
    ("AAPL", "USD"): Decimal(230),
    ("BTC", "USDT"): Decimal(98000),
    ("ETH", "USDT"): Decimal(2400),
}


def _ledger(assets: tuple[Asset, ...], trades: tuple[tuple[str, TradeFacts], ...]) -> FakeLedger:
    return FakeLedger(assets=assets, trades=trades, prices=JIA_PRICES).taking_cards()


def jia(trades: tuple[tuple[str, TradeFacts], ...] = JIA_TRADES) -> FakeLedger:
    return _ledger(JIA_ASSETS, trades)


def yi() -> FakeLedger:
    assets = tuple(one for one in JIA_ASSETS if one.code != "EUR")
    trades = tuple(
        ("t-aapl-usd", bought("AAPL", "USD", (2026, 11, 3, 16, 0), "217"))
        if key == AAPL_EUR[0]
        else (key, facts)
        for key, facts in JIA_TRADES
    )
    return _ledger(assets, trades)


def bing() -> FakeLedger:
    assets = tuple(
        dataclasses.replace(one, pricing=Pricing.CANNOT_PRICE) if one.code == "EUR" else one
        for one in JIA_ASSETS
    )
    return _ledger(assets, JIA_TRADES)


def ding() -> FakeLedger:
    assets = tuple(dataclasses.replace(one, price_currency=None) for one in JIA_ASSETS)
    return _ledger(assets, JIA_TRADES)
