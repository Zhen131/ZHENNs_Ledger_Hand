"""Tests of the asset table: the built-in one, a table with two moneys, and what a table refuses.

The built-in table must answer every question exactly as the fixed USDT
rules did: one money, USDT, named by every word for USDT and by nothing
else. A table made in the tests shows the other answers. Every coin and
word below is invented or taken from the built-in table.
"""

from __future__ import annotations

import pytest

from ledger_hand.core.assets import (
    BUILT_IN_ASSETS,
    AssetTable,
    Money,
    MoneyFound,
    MoneyReading,
    MoneyUse,
    UnknownAssets,
)
from ledger_hand.core.coins import (
    BUILT_IN_COINS,
    BUILT_IN_TABLE,
    USDT_WORDS,
    Coin,
    CoinTable,
    means_usdt,
)
from tests.core.two_moneys import TWO_MONEYS, USD, USDT

OTHER_WORDS = [
    "EUR",
    "欧元",
    "BTC",
    "比特币",
    "PIKA",
    "某某币",
    "",
    "   ",
    "u",
    "ｕｓｄ",
    " 刀 ",
    "dollar",
]


# --- the built-in table -------------------------------------------------------


def test_the_built_in_table_is_the_built_in_coins_priced_in_usdt_alone() -> None:
    assert BUILT_IN_ASSETS.coins is BUILT_IN_TABLE
    assert BUILT_IN_ASSETS.pricing_codes == ("USDT",)
    assert BUILT_IN_ASSETS.sole_pricing_code == "USDT"
    assert BUILT_IN_ASSETS.prices_only_in_usdt()
    assert BUILT_IN_ASSETS.unknown is UnknownAssets.CONFIRM_ON_THE_SPOT
    assert BUILT_IN_ASSETS.extra_units == ()


@pytest.mark.parametrize("word", sorted(USDT_WORDS))
def test_every_word_for_usdt_names_usdt_in_the_built_in_table(word: str) -> None:
    assert BUILT_IN_ASSETS.money(word) == MoneyFound(MoneyReading.ONE, "USDT")


@pytest.mark.parametrize(
    "word",
    OTHER_WORDS
    + [form for coin in BUILT_IN_COINS for form in (coin.symbol, coin.name, *coin.aliases)],
)
def test_the_built_in_table_reads_money_exactly_as_the_words_for_usdt_did(word: str) -> None:
    found = BUILT_IN_ASSETS.money(word)

    assert found.reading in (MoneyReading.ONE, MoneyReading.NOT_MONEY)
    assert (found.reading is MoneyReading.ONE) is means_usdt(word)


def test_the_built_in_table_finds_a_coin_as_the_coin_table_does() -> None:
    for coin in BUILT_IN_COINS:
        assert BUILT_IN_ASSETS.find(coin.name) is BUILT_IN_TABLE.find(coin.name)
    assert BUILT_IN_ASSETS.find("PIKA") is None


def test_confirming_a_coin_in_the_built_in_table_is_confirming_it_in_the_coin_table() -> None:
    confirmed = BUILT_IN_ASSETS.with_confirmed("pika")

    assert confirmed.coins == BUILT_IN_TABLE.with_confirmed("pika")
    assert confirmed.moneys == BUILT_IN_ASSETS.moneys
    assert BUILT_IN_ASSETS.find("PIKA") is None
    assert BUILT_IN_ASSETS.with_confirmed("比特币") is BUILT_IN_ASSETS


@pytest.mark.parametrize("word", ["U", "美元", "USDT"])
def test_a_word_for_usdt_is_never_confirmed_as_a_coin(word: str) -> None:
    with pytest.raises(ValueError):
        BUILT_IN_ASSETS.with_confirmed(word)


# --- a table with two moneys to price in --------------------------------------


@pytest.mark.parametrize(
    ("word", "found"),
    [
        ("USD", MoneyFound(MoneyReading.ONE, "USD")),
        ("美元", MoneyFound(MoneyReading.ONE, "USD")),
        ("$", MoneyFound(MoneyReading.ONE, "USD")),
        ("u", MoneyFound(MoneyReading.ONE, "USDT")),
        ("泰达币", MoneyFound(MoneyReading.ONE, "USDT")),
        ("刀", MoneyFound(MoneyReading.SEVERAL)),
        ("欧元", MoneyFound(MoneyReading.CANNOT_PRICE, "EUR")),
        ("EUR", MoneyFound(MoneyReading.CANNOT_PRICE, "EUR")),
        ("BTC", MoneyFound(MoneyReading.NOT_MONEY)),
        ("股", MoneyFound(MoneyReading.NOT_MONEY)),
        ("", MoneyFound(MoneyReading.NOT_MONEY)),
    ],
)
def test_a_word_is_one_of_four_things_as_money(word: str, found: MoneyFound) -> None:
    assert TWO_MONEYS.money(word) == found


def test_a_table_with_two_moneys_has_no_sole_one_and_names_no_usdt_alone() -> None:
    assert TWO_MONEYS.pricing_codes == ("USDT", "USD")
    assert TWO_MONEYS.sole_pricing_code is None
    assert not TWO_MONEYS.prices_only_in_usdt()


def test_a_table_priced_in_usd_alone_does_not_count_as_usdt_alone() -> None:
    usd_only = AssetTable(
        coins=CoinTable(()), moneys=(USD,), unknown=UnknownAssets.REFUSE, extra_units=()
    )

    assert usd_only.sole_pricing_code == "USD"
    assert not usd_only.prices_only_in_usdt()


def test_a_table_that_refuses_unseen_assets_takes_none_confirmed() -> None:
    with pytest.raises(ValueError, match="does not take"):
        TWO_MONEYS.with_confirmed("SOL")


def test_a_share_is_found_by_its_symbol_and_its_names() -> None:
    for spoken in ("MSFT", "msft", "Microsoft", "微软"):
        found = TWO_MONEYS.find(spoken)
        assert found is not None and found.symbol == "MSFT", spoken


# --- what a table refuses -----------------------------------------------------


def test_a_table_with_no_money_to_price_in_is_refused() -> None:
    cannot = Money("EUR", (), MoneyUse.CANNOT_PRICE)
    with pytest.raises(ValueError, match="at least one"):
        AssetTable(
            coins=CoinTable(()), moneys=(cannot,), unknown=UnknownAssets.REFUSE, extra_units=()
        )


def test_a_money_code_used_twice_is_refused() -> None:
    with pytest.raises(ValueError, match="twice"):
        AssetTable(
            coins=CoinTable(()), moneys=(USD, USD), unknown=UnknownAssets.REFUSE, extra_units=()
        )


def test_a_word_naming_both_an_asset_and_a_money_is_refused() -> None:
    coins = CoinTable((Coin("ABC", "Abc", None, ("币甲",)),))
    money = Money("XYZ", ("币甲",), MoneyUse.CAN_PRICE)
    with pytest.raises(ValueError, match="both an asset and a money"):
        AssetTable(coins=coins, moneys=(money,), unknown=UnknownAssets.REFUSE, extra_units=())


def test_a_unit_word_that_is_a_word_for_money_is_refused() -> None:
    with pytest.raises(ValueError, match="word for money"):
        AssetTable(
            coins=CoinTable(()), moneys=(USDT,), unknown=UnknownAssets.REFUSE, extra_units=("刀",)
        )


@pytest.mark.parametrize("code", ["usd", " USD", ""])
def test_a_money_code_is_written_in_capitals_and_trimmed(code: str) -> None:
    with pytest.raises(ValueError, match="capitals"):
        Money(code, (), MoneyUse.CAN_PRICE)
