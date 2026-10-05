"""Tests of a coin's card: everything from the coin table, the same in every export."""

from __future__ import annotations

import pytest

from ledger_hand.core.coins import BUILT_IN_TABLE, Coin, CoinOrigin
from ledger_hand.export.coin_card import COIN_CARD_MOMENT, coin_card, coin_card_id

# The ledger's fields of a coin, in its order, without the one this program
# never writes (``decimals``).
LEDGER_ASSET_FIELDS = [
    "id",
    "symbol",
    "name",
    "quoteCurrency",
    "binanceMapping",
    "createdAt",
    "updatedAt",
]


def built_in(symbol: str) -> Coin:
    coin = BUILT_IN_TABLE.find(symbol)
    assert coin is not None
    return coin


def test_a_coin_with_a_binance_market_gets_a_full_card() -> None:
    assert coin_card(built_in("BTC")) == {
        "id": "asset-hand-btc",
        "symbol": "BTC",
        "name": "Bitcoin",
        "quoteCurrency": "USDT",
        "binanceMapping": {
            "provider": "binance",
            "symbol": "BTCUSDT",
            "baseAsset": "BTC",
            "quoteAsset": "USDT",
        },
        "createdAt": "2026-10-04T00:00:00Z",
        "updatedAt": "2026-10-04T00:00:00Z",
    }


def test_the_fields_come_in_the_ledger_s_order() -> None:
    assert list(coin_card(built_in("ETH"))) == LEDGER_ASSET_FIELDS


def test_a_built_in_coin_without_a_known_market_has_its_market_empty() -> None:
    card = coin_card(built_in("XMR"))

    assert card["name"] == "Monero"
    assert card["binanceMapping"] is None


def test_a_confirmed_coin_is_named_by_its_symbol_and_has_no_market() -> None:
    table = BUILT_IN_TABLE.with_confirmed("newcoin")
    coin = table.find("NEWCOIN")
    assert coin is not None

    card = coin_card(coin)

    assert card["id"] == "asset-hand-newcoin"
    assert card["symbol"] == "NEWCOIN"
    assert card["name"] == "NEWCOIN"
    assert card["binanceMapping"] is None


def test_a_confirmed_coin_never_carries_a_name_or_market_from_elsewhere() -> None:
    coin = Coin("ZZZ", "Some Name", "ZZZUSDT", origin=CoinOrigin.USER_CONFIRMED)

    card = coin_card(coin)

    assert card["name"] == "ZZZ"
    assert card["binanceMapping"] is None


@pytest.mark.parametrize("coin", BUILT_IN_TABLE.coins, ids=lambda coin: coin.symbol)
def test_every_built_in_coin_gets_the_same_card_every_time(coin: Coin) -> None:
    first = coin_card(coin)

    assert coin_card(coin) == first
    assert first["id"] == coin_card_id(coin.symbol)
    assert first["createdAt"] == first["updatedAt"] == "2026-10-04T00:00:00Z"
    mapping = first["binanceMapping"]
    if mapping is not None:
        assert isinstance(mapping, dict)
        assert mapping["baseAsset"] == coin.symbol


def test_the_card_moment_is_fixed() -> None:
    assert COIN_CARD_MOMENT.isoformat() == "2026-10-04T00:00:00+00:00"


def test_different_symbols_give_different_identifiers() -> None:
    symbols = [coin.symbol for coin in BUILT_IN_TABLE.coins] + ["A1", "A", "1"]

    identifiers = {coin_card_id(symbol) for symbol in symbols}

    assert len(identifiers) == len(symbols)
