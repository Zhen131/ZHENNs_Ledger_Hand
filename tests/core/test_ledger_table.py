"""Tests of the asset table made from the ledger's own list of assets.

What may be traded and which money a trade may be priced in come from the
list; the built-in coin table only lends its other names to the ledger's
own codes, and covers with the names of the coins the ledger lacks. Every
asset below is invented.
"""

from __future__ import annotations

import dataclasses

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
from ledger_hand.core.coins import BUILT_IN_TABLE
from ledger_hand.core.ledger_records import Asset, AssetKind, Pricing
from ledger_hand.core.ledger_table import (
    MONEY_WORDS,
    SHARE_UNITS,
    VAGUE_MONEY_WORDS,
    names_of,
    table_of,
)
from ledger_hand.ledger.invented_book import INVENTED_ASSETS
from tests.fakes.usdt_only import USDT_ONLY_ASSETS


def asset(code: str, name: str, kind: AssetKind, pricing: Pricing = Pricing.CANNOT_PRICE) -> Asset:
    return Asset(id=f"asset-{code.lower()}", code=code, name=name, kind=kind, pricing=pricing)


def made(assets: tuple[Asset, ...]) -> AssetTable:
    table = table_of(assets)
    assert table is not None
    return table


def test_the_invented_book_prices_in_usdt_and_usd_and_trades_its_other_assets() -> None:
    table = made(INVENTED_ASSETS)

    assert table.pricing_codes == ("USDT", "USD")
    assert {coin.symbol for coin in table.coins.coins} == {"BTC", "ETH", "ADA", "MSFT"}
    assert table.unknown is UnknownAssets.REFUSE
    assert table.extra_units == SHARE_UNITS
    assert table.from_ledger
    assert not table.speaks_of_usdt_only()


@pytest.mark.parametrize(
    ("word", "found"),
    [
        ("U", MoneyFound(MoneyReading.ONE, "USDT")),
        ("usdt", MoneyFound(MoneyReading.ONE, "USDT")),
        ("Tether", MoneyFound(MoneyReading.ONE, "USDT")),
        ("泰达币", MoneyFound(MoneyReading.ONE, "USDT")),
        ("USD", MoneyFound(MoneyReading.ONE, "USD")),
        ("$", MoneyFound(MoneyReading.VAGUE)),
        ("dollars", MoneyFound(MoneyReading.ONE, "USD")),
        ("美元", MoneyFound(MoneyReading.ONE, "USD")),
        ("美金", MoneyFound(MoneyReading.VAGUE)),
        ("US dollar", MoneyFound(MoneyReading.ONE, "USD")),
        ("刀", MoneyFound(MoneyReading.VAGUE)),
        ("美刀", MoneyFound(MoneyReading.VAGUE)),
        ("BTC", MoneyFound(MoneyReading.NOT_MONEY)),
    ],
)
def test_each_word_for_money_names_the_money_the_ledger_has(word: str, found: MoneyFound) -> None:
    assert made(INVENTED_ASSETS).money(word) == found


def test_with_usd_pricing_nothing_dollars_name_no_money_to_price_in_and_dao_is_usdt() -> None:
    table = made(USDT_ONLY_ASSETS)

    assert table.pricing_codes == ("USDT",)
    assert table.money("美元") == MoneyFound(MoneyReading.CANNOT_PRICE, "USD")
    assert table.money("$") == MoneyFound(MoneyReading.VAGUE)
    assert table.money("刀") == MoneyFound(MoneyReading.VAGUE)
    assert table.money("U") == MoneyFound(MoneyReading.ONE, "USDT")
    assert not table.speaks_of_usdt_only()


def test_a_word_for_a_money_the_ledger_lacks_names_no_money() -> None:
    table = made(tuple(one for one in INVENTED_ASSETS if one.code != "USD"))

    assert table.money("美元").reading is MoneyReading.NOT_MONEY
    assert table.money("刀") == MoneyFound(MoneyReading.VAGUE)


def test_usd_is_never_usdt_and_usdt_never_usd() -> None:
    table = made(INVENTED_ASSETS)
    usdt_words = {word for word, code in MONEY_WORDS if code == "USDT"}
    usd_words = {word for word, code in MONEY_WORDS if code == "USD"}

    assert all(table.money(word).code == "USDT" for word in usdt_words)
    assert all(table.money(word).code == "USD" for word in usd_words)


# Every kind of ledger a vague word is read against: both moneys pricing,
# only USDT, only USD, no USD at all, and with a euro that prices trades.
_LEDGERS = {
    "both": INVENTED_ASSETS,
    "usdt only": USDT_ONLY_ASSETS,
    "usd only": tuple(
        dataclasses.replace(one, pricing=Pricing.CANNOT_PRICE) if one.code == "USDT" else one
        for one in INVENTED_ASSETS
    ),
    "no usd": tuple(one for one in INVENTED_ASSETS if one.code != "USD"),
    "with euro": (
        *INVENTED_ASSETS,
        asset("EUR", "Euro", AssetKind.CASH, Pricing.CAN_PRICE),
    ),
}


@pytest.mark.parametrize("ledger", sorted(_LEDGERS))
@pytest.mark.parametrize("word", [*VAGUE_MONEY_WORDS, " 美金 ", "BUCKS", "＄"])
def test_a_vague_word_is_never_read_as_one_money_whatever_the_ledger_has(
    word: str, ledger: str
) -> None:
    table = made(_LEDGERS[ledger])

    assert table.money(word) == MoneyFound(MoneyReading.VAGUE)
    assert table.money(word).code is None
    assert table.missing_money(word) is None


def test_the_vague_words_are_the_ones_the_rule_names() -> None:
    assert set(VAGUE_MONEY_WORDS) == {"美金", "刀", "美刀", "$", "buck", "bucks"}
    assert not {word for word, _ in MONEY_WORDS} & set(VAGUE_MONEY_WORDS)


@pytest.mark.parametrize("word", ["EUR", "euro", "Euros", "€", "欧元", "欧"])
def test_a_word_for_the_euro_names_a_money_the_ledger_lacks_until_it_has_one(word: str) -> None:
    lacking = made(INVENTED_ASSETS)
    having = made(_LEDGERS["with euro"])

    assert lacking.money(word).reading is MoneyReading.NOT_MONEY
    assert lacking.missing_money(word) == "EUR"
    assert having.money(word) == MoneyFound(MoneyReading.ONE, "EUR")
    assert having.missing_money(word) is None


@pytest.mark.parametrize(
    ("word", "code"),
    [("人民币", "CNY"), ("RMB", "CNY"), ("福林", "HUF"), ("forints", "HUF"), ("美元", "USD")],
)
def test_other_words_name_a_money_the_ledger_lacks(word: str, code: str) -> None:
    table = made(_LEDGERS["no usd"])

    assert table.money(word).reading is MoneyReading.NOT_MONEY
    assert table.missing_money(word) == code


@pytest.mark.parametrize("word", ["块", "元", "¥", "Ft", "镑", "欧易", "BTC"])
def test_words_left_off_the_lists_name_no_money(word: str) -> None:
    table = made(INVENTED_ASSETS)

    assert table.money(word).reading is MoneyReading.NOT_MONEY
    assert table.missing_money(word) is None


def test_the_number_reader_is_given_every_word_for_money_and_the_built_in_table_none() -> None:
    table = made(INVENTED_ASSETS)

    assert set(table.money_units) == {word for word, _ in MONEY_WORDS} | set(VAGUE_MONEY_WORDS)
    assert BUILT_IN_ASSETS.money_units == ()
    assert BUILT_IN_ASSETS.vague_words == frozenset()


def test_the_built_in_names_count_only_for_a_code_the_ledger_has() -> None:
    table = made(INVENTED_ASSETS)

    assert table.find("比特币") is not None and table.find("比特币").symbol == "BTC"  # type: ignore[union-attr]
    assert table.find("大饼").symbol == "BTC"  # type: ignore[union-attr]
    assert table.find("msft").symbol == "MSFT"  # type: ignore[union-attr]
    assert table.find("Microsoft").symbol == "MSFT"  # type: ignore[union-attr]
    for lacked in ("狗狗币", "DOGE", "比特币现金", "SOL", "索拉纳"):
        assert table.find(lacked) is None
        assert table.is_shielded(lacked)
    assert not table.is_shielded("比特币")
    assert not table.is_shielded("AAPL")


def test_the_names_split_into_the_ledger_s_sayings_and_the_names_that_only_cover() -> None:
    names = names_of(INVENTED_ASSETS)

    sayings = dict(names.sayings())
    shields = dict(names.shields())
    assert sayings["比特币"] == "BTC"
    assert sayings["Microsoft"] == "MSFT"
    assert sayings["US dollar"] == "USD"
    assert "狗狗币" not in sayings and shields["狗狗币"] == "DOGE"
    assert "比特币现金" in shields
    assert "U" not in sayings and "刀" not in sayings
    assert set(names.in_lookup_order()) == set(names.sayings()) | set(names.shields())


def test_a_stock_whose_code_is_a_word_for_money_is_left_out_and_the_rest_kept() -> None:
    listed = (*INVENTED_ASSETS, asset("U", "Unity Software", AssetKind.STOCK))

    table = made(listed)

    assert table.find("U") is None
    assert table.find("Unity Software") is None
    assert table.money("U") == MoneyFound(MoneyReading.ONE, "USDT")
    assert {coin.symbol for coin in table.coins.coins} == {"BTC", "ETH", "ADA", "MSFT"}


def test_a_code_with_a_dot_cannot_be_a_symbol_and_is_left_out() -> None:
    table = made((*INVENTED_ASSETS, asset("BRK.B", "Berkshire Hathaway B", AssetKind.STOCK)))

    assert table.find("BRK.B") is None
    assert table.find("MSFT") is not None


def test_a_ledger_that_prices_in_no_money_makes_no_table() -> None:
    unpriced = tuple(
        dataclasses.replace(one, pricing=Pricing.CANNOT_PRICE) for one in INVENTED_ASSETS
    )

    assert table_of(unpriced) is None
    assert table_of(()) is None


def test_without_a_stock_no_share_word_is_read() -> None:
    table = made(tuple(one for one in INVENTED_ASSETS if one.kind is not AssetKind.STOCK))

    assert table.extra_units == ()


def test_money_the_ledger_prices_nothing_in_is_money_not_an_asset() -> None:
    euro = asset("EUR", "Euro", AssetKind.CASH)
    table = made((*INVENTED_ASSETS, euro))

    assert table.money("EUR") == MoneyFound(MoneyReading.CANNOT_PRICE, "EUR")
    assert table.find("EUR") is None
    assert table.pricing_codes == ("USDT", "USD")


def test_a_table_that_confirms_assets_holds_no_money_it_cannot_price_in() -> None:
    with pytest.raises(ValueError, match="could never be confirmed"):
        AssetTable(
            coins=BUILT_IN_TABLE,
            moneys=(
                Money("USDT", ("U",), MoneyUse.CAN_PRICE),
                Money("EUR", ("Euro",), MoneyUse.CANNOT_PRICE),
            ),
            unknown=UnknownAssets.CONFIRM_ON_THE_SPOT,
            extra_units=(),
        )
