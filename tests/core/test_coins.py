"""Tests of the coin table: its data, its lookup, and coins the user confirms."""

from __future__ import annotations

import pytest

from ledger_hand.core.coins import (
    BUILT_IN_COINS,
    BUILT_IN_TABLE,
    USDT_WORDS,
    Coin,
    CoinOrigin,
    CoinTable,
    means_usdt,
    spoken_key,
)
from ledger_hand.core.ledger_limits import (
    COIN_NAME_MAX_LENGTH,
    MARKET_PAIR_MAX_LENGTH,
    is_symbol,
    text_length,
)


def spoken_forms(coin: Coin) -> list[str]:
    """Everything a coin can be called: its symbol, its name and its aliases."""
    return [coin.symbol, coin.name, *coin.aliases]


# --- the built-in data ------------------------------------------------------


def test_built_in_table_is_not_empty_and_knows_the_two_largest_coins() -> None:
    assert len(BUILT_IN_COINS) >= 20
    assert {"BTC", "ETH"} <= {coin.symbol for coin in BUILT_IN_COINS}


def test_every_built_in_symbol_is_written_the_way_the_ledger_requires() -> None:
    assert [coin.symbol for coin in BUILT_IN_COINS if not is_symbol(coin.symbol)] == []


def test_built_in_symbols_are_unique() -> None:
    symbols = [coin.symbol for coin in BUILT_IN_COINS]

    assert len(symbols) == len(set(symbols))


def test_usdt_is_not_in_the_built_in_table() -> None:
    assert "USDT" not in {coin.symbol for coin in BUILT_IN_COINS}
    assert BUILT_IN_TABLE.find("USDT") is None


def test_every_spoken_form_points_to_exactly_one_coin() -> None:
    owners: dict[str, set[str]] = {}
    for coin in BUILT_IN_COINS:
        for form in spoken_forms(coin):
            owners.setdefault(spoken_key(form), set()).add(coin.symbol)

    assert {key: symbols for key, symbols in owners.items() if len(symbols) > 1} == {}


def test_every_spoken_form_finds_its_own_coin() -> None:
    for coin in BUILT_IN_COINS:
        for form in spoken_forms(coin):
            assert BUILT_IN_TABLE.find(form) is coin, form


def test_no_usdt_word_is_also_a_way_to_say_a_coin() -> None:
    coin_keys = {spoken_key(form) for coin in BUILT_IN_COINS for form in spoken_forms(coin)}

    assert coin_keys & USDT_WORDS == set()
    assert [word for word in USDT_WORDS if BUILT_IN_TABLE.find(word) is not None] == []


def test_every_built_in_name_fits_the_ledger() -> None:
    for coin in BUILT_IN_COINS:
        assert coin.name, coin.symbol
        assert text_length(coin.name) <= COIN_NAME_MAX_LENGTH, coin.symbol


def test_every_built_in_market_pair_is_the_symbol_quoted_in_usdt() -> None:
    for coin in BUILT_IN_COINS:
        if coin.binance_pair is not None:
            assert coin.binance_pair == f"{coin.symbol}USDT"
            assert text_length(coin.binance_pair) <= MARKET_PAIR_MAX_LENGTH


def test_some_built_in_coins_have_no_market_pair() -> None:
    assert [coin.symbol for coin in BUILT_IN_COINS if coin.binance_pair is None] != []


def test_every_built_in_coin_is_marked_built_in() -> None:
    assert {coin.origin for coin in BUILT_IN_COINS} == {CoinOrigin.BUILT_IN}


def test_usdt_words_are_stored_in_their_lookup_form() -> None:
    assert {spoken_key(word) for word in USDT_WORDS} == USDT_WORDS
    assert "USDT" in USDT_WORDS


# --- lookup -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("spoken", "symbol"),
    [
        ("BTC", "BTC"),
        ("btc", "BTC"),
        ("Btc", "BTC"),
        ("  BTC\t", "BTC"),
        ("ＢＴＣ", "BTC"),
        ("ｂｔｃ", "BTC"),
        ("\N{IDEOGRAPHIC SPACE}比特币\N{IDEOGRAPHIC SPACE}", "BTC"),
        ("Bitcoin", "BTC"),
        ("bitcoin", "BTC"),
        ("比特币", "BTC"),
        ("大饼", "BTC"),
        ("以太坊", "ETH"),
        ("以太", "ETH"),
        ("ETHEREUM", "ETH"),
        ("以太经典", "ETC"),
        ("bitcoin cash", "BCH"),
        ("Bitcoin   Cash", "BCH"),
        ("狗狗币", "DOGE"),
        ("usdc", "USDC"),
    ],
)
def test_lookup_ignores_case_width_and_surrounding_whitespace(spoken: str, symbol: str) -> None:
    found = BUILT_IN_TABLE.find(spoken)

    assert found is not None
    assert found.symbol == symbol


@pytest.mark.parametrize("spoken", ["PEPE2", "NOSUCHCOIN", "不存在币", "", "   ", "BT", "比特"])
def test_unknown_text_finds_nothing(spoken: str) -> None:
    assert BUILT_IN_TABLE.find(spoken) is None


@pytest.mark.parametrize(
    "spoken",
    [
        "USDT",
        "usdt",
        "U",
        "u",
        "ＵＳＤＴ",
        " USDT ",
        "USD",
        "$",
        "＄",
        "刀",
        "美刀",
        "美元",
        "美金",
    ],
)
def test_word_for_usdt_is_recognised(spoken: str) -> None:
    assert means_usdt(spoken)


@pytest.mark.parametrize("spoken", ["BTC", "USDC", "CNY", "EUR", "元", "块", "人民币", "", "US"])
def test_other_word_does_not_mean_usdt(spoken: str) -> None:
    assert not means_usdt(spoken)


# --- coins the user confirmed -----------------------------------------------


def test_confirmed_coin_joins_a_new_table() -> None:
    table = BUILT_IN_TABLE.with_confirmed("pepe2")

    coin = table.find("PEPE2")
    assert coin == Coin(
        symbol="PEPE2",
        name="PEPE2",
        binance_pair=None,
        aliases=(),
        origin=CoinOrigin.USER_CONFIRMED,
    )
    assert table.find(" pepe2 ") is coin
    assert table.coins[:-1] == BUILT_IN_TABLE.coins


def test_confirming_a_coin_leaves_the_original_table_alone() -> None:
    BUILT_IN_TABLE.with_confirmed("PEPE2")

    assert BUILT_IN_TABLE.find("PEPE2") is None
    assert BUILT_IN_TABLE.coins == BUILT_IN_COINS


def test_confirming_a_coin_that_is_already_known_changes_nothing() -> None:
    assert BUILT_IN_TABLE.with_confirmed("比特币") is BUILT_IN_TABLE


def test_several_coins_can_be_confirmed_one_after_another() -> None:
    table = BUILT_IN_TABLE.with_confirmed("PEPE2").with_confirmed("WIF")

    confirmed = [coin.symbol for coin in table.coins if coin.origin is CoinOrigin.USER_CONFIRMED]
    assert confirmed == ["PEPE2", "WIF"]


@pytest.mark.parametrize("spoken", ["", "狗狗币2号", "BT-C", "X" * 33, "USDT", "刀", "U"])
def test_text_that_cannot_be_a_coin_symbol_cannot_be_confirmed(spoken: str) -> None:
    with pytest.raises(ValueError, match="cannot be a coin symbol"):
        BUILT_IN_TABLE.with_confirmed(spoken)


# --- a table that contradicts itself is refused -----------------------------


@pytest.mark.parametrize("symbol", ["btc", "", "BT-C", "USDT", "X" * 33])
def test_coin_with_a_malformed_symbol_is_refused(symbol: str) -> None:
    with pytest.raises(ValueError, match="symbol"):
        Coin(symbol=symbol, name="Some Coin")


@pytest.mark.parametrize("name", ["", "N" * 129])
def test_coin_with_a_name_the_ledger_would_refuse_is_refused(name: str) -> None:
    with pytest.raises(ValueError, match="name"):
        Coin(symbol="ABC", name=name)


@pytest.mark.parametrize("pair", ["", " ABCUSDT", "ABCUSDT ", "P" * 33])
def test_coin_with_a_market_pair_the_ledger_would_refuse_is_refused(pair: str) -> None:
    with pytest.raises(ValueError, match="market pair"):
        Coin(symbol="ABC", name="Some Coin", binance_pair=pair)


def test_table_with_one_spoken_form_for_two_coins_is_refused() -> None:
    first = Coin(symbol="ABC", name="First Coin", aliases=("shared",))
    second = Coin(symbol="XYZ", name="Second Coin", aliases=("Shared",))

    with pytest.raises(ValueError, match="SHARED"):
        CoinTable((first, second))


def test_table_with_the_same_symbol_twice_is_refused() -> None:
    with pytest.raises(ValueError, match="ABC"):
        CoinTable((Coin(symbol="ABC", name="First"), Coin(symbol="ABC", name="Second")))


@pytest.mark.parametrize("alias", ["刀", "usd", "U"])
def test_table_with_a_usdt_word_as_a_coin_alias_is_refused(alias: str) -> None:
    with pytest.raises(ValueError, match="USDT"):
        CoinTable((Coin(symbol="ABC", name="Some Coin", aliases=(alias,)),))


def test_empty_table_knows_no_coin() -> None:
    assert CoinTable(()).find("BTC") is None
