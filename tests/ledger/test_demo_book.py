"""Tests of the demo book: the invented book with seven more assets and nine buys in August.

The demo book takes the invented book whole and adds to it; what is held,
which assets are listed, that two assets have no trade, that every new buy
falls before the invented book's first trade, and that the next trade
proposed gets the next identifier. Nothing here touches a model.
"""

from __future__ import annotations

from decimal import Decimal

from ledger_hand.core.ledger_records import AssetKind, TradeFilter
from ledger_hand.ledger.demo_book import DEMO_ASSETS, DEMO_TRADES, demo_ledger
from ledger_hand.ledger.invented_book import INVENTED_ASSETS, INVENTED_TRADES


def test_the_demo_book_holds_the_invented_book_whole_and_then_its_own() -> None:
    assert DEMO_ASSETS[: len(INVENTED_ASSETS)] == INVENTED_ASSETS
    assert DEMO_TRADES[-len(INVENTED_TRADES) :] == INVENTED_TRADES
    assert [asset.code for asset in DEMO_ASSETS[len(INVENTED_ASSETS) :]] == [
        "SOL",
        "INTC",
        "KO",
        "AAPL",
        "NVDA",
        "PEP",
        "DOT",
    ]
    assert [key for key, _ in DEMO_TRADES[:9]] == [f"t-{number}" for number in range(12, 21)]


def test_the_new_assets_have_their_names_and_kinds() -> None:
    new = {asset.code: (asset.name, asset.kind) for asset in DEMO_ASSETS[len(INVENTED_ASSETS) :]}

    assert new == {
        "SOL": ("Solana", AssetKind.CRYPTO),
        "INTC": ("Intel", AssetKind.STOCK),
        "KO": ("Coca-Cola", AssetKind.STOCK),
        "AAPL": ("Apple", AssetKind.STOCK),
        "NVDA": ("NVIDIA", AssetKind.STOCK),
        "PEP": ("PepsiCo", AssetKind.STOCK),
        "DOT": ("Polkadot", AssetKind.CRYPTO),
    }


def test_every_new_buy_falls_before_the_invented_books_first_trade() -> None:
    first = min(facts.occurred for _, facts in INVENTED_TRADES)

    assert all(facts.occurred < first for _, facts in DEMO_TRADES[:9])


def test_pepsico_and_polkadot_have_no_trade() -> None:
    traded = {facts.asset for _, facts in DEMO_TRADES}

    assert "PEP" not in traded
    assert "DOT" not in traded


def test_the_holdings_are_the_nine_assets_traded() -> None:
    held = {position.asset: position.quantity for position in demo_ledger().positions()}

    assert held == {
        "AAPL": Decimal("50"),
        "ADA": Decimal("20939.06"),
        "BTC": Decimal("1.0174765"),
        "ETH": Decimal("10.41995"),
        "INTC": Decimal("50"),
        "KO": Decimal("50"),
        "MSFT": Decimal("52"),
        "NVDA": Decimal("50"),
        "SOL": Decimal("100"),
    }


def test_the_ledger_lists_thirteen_assets_and_twenty_trades() -> None:
    ledger = demo_ledger()

    assert len(ledger.list_assets()) == 13
    assert len(ledger.list_trades(TradeFilter()).trades) == 20
