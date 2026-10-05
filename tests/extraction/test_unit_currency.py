"""Tests of telling which currency a word, or a unit word, names."""

from __future__ import annotations

import pytest

from ledger_hand.core.coins import BUILT_IN_TABLE
from ledger_hand.extraction.unit_currency import (
    CurrencyWord,
    currencies_in_unit,
    identity_of,
    word_identity,
)


@pytest.mark.parametrize(
    ("word", "identity"),
    [
        ("USDT", "USDT"),
        ("u", "USDT"),
        ("刀", "USDT"),
        ("美元", "USDT"),
        ("$", "USDT"),
        ("ＵＳＤＴ", "USDT"),
        ("BTC", "BTC"),
        ("btc", "BTC"),
        ("比特币", "BTC"),
        ("大饼", "BTC"),
        ("𝐁𝐓𝐂", "BTC"),
        ("Bitcoin Cash", "BCH"),
        ("以太经典", "ETC"),
    ],
)
def test_words_the_program_knows_name_their_currency(word: str, identity: str) -> None:
    assert identity_of(word, BUILT_IN_TABLE) == identity


@pytest.mark.parametrize("word", ["", "个", "coin", "BONK", "sats", "元", "¥", "BTCUSDT"])
def test_other_words_name_nothing(word: str) -> None:
    assert identity_of(word, BUILT_IN_TABLE) is None


def test_a_word_allowed_for_the_call_names_itself_in_lookup_form() -> None:
    assert identity_of("bonk", BUILT_IN_TABLE, ("BONK",)) == "BONK"
    assert identity_of("ＢＯＮＫ", BUILT_IN_TABLE, ("bonk",)) == "BONK"
    assert identity_of("BONK", BUILT_IN_TABLE, ("PEPE2",)) is None


def test_the_identity_of_a_users_word_is_itself_when_nothing_else() -> None:
    assert word_identity("比特币", BUILT_IN_TABLE) == "BTC"
    assert word_identity("bonk", BUILT_IN_TABLE) == "BONK"
    assert word_identity("U", BUILT_IN_TABLE) == "USDT"


@pytest.mark.parametrize(
    ("unit", "expected"),
    [
        ("刀", [("刀", "USDT")]),
        ("USDT", [("USDT", "USDT")]),
        ("BTC", [("BTC", "BTC")]),
        ("个", []),
        ("coins", []),
        ("个 BTC", [("BTC", "BTC")]),
        ("个比特币", [("比特币", "BTC")]),
        ("枚以太坊", [("以太坊", "ETH")]),
        ("个以太经典", [("以太经典", "ETC")]),
        ("BTC USDT", [("BTC", "BTC"), ("USDT", "USDT")]),
        ("BTC 比特币", [("BTC", "BTC")]),
        ("Bitcoin Cash", [("Bitcoin Cash", "BCH")]),
        ("个BTC", [("BTC", "BTC")]),
    ],
)
def test_a_unit_names_each_of_its_currencies_once(
    unit: str, expected: list[tuple[str, str]]
) -> None:
    found = currencies_in_unit(unit, BUILT_IN_TABLE)

    assert found == tuple(CurrencyWord(text, identity) for text, identity in expected)


def test_a_unit_may_name_a_coin_allowed_for_the_call() -> None:
    assert currencies_in_unit("个邦克", BUILT_IN_TABLE, ("邦克",)) == (
        CurrencyWord("邦克", "邦克"),
    )
    assert currencies_in_unit("BONK", BUILT_IN_TABLE, ("BONK",)) == (CurrencyWord("BONK", "BONK"),)
    assert currencies_in_unit("BONK", BUILT_IN_TABLE) == ()
