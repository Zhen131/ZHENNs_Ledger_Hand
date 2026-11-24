"""Tests of checking a read tool's asset and side against what the user said."""

from __future__ import annotations

import pytest

from ledger_hand.assistant.narrowing import (
    AssetDropped,
    AssetUsed,
    NoSuchAsset,
    SideDropped,
    SideUsed,
    assets_named,
    check_asset,
    check_side,
)
from ledger_hand.core.trade import Side
from ledger_hand.ledger.invented_book import INVENTED_ASSETS

ASSETS = INVENTED_ASSETS  # USDT, USD, BTC, ETH, ADA, MSFT


@pytest.mark.parametrize(
    ("said", "named"),
    [
        ("我上个月买了多少比特币", {"BTC"}),
        ("大饼今年花了多少", {"BTC"}),
        ("以太坊10月的买入", {"ETH"}),
        ("How much ETH did I buy?", {"ETH"}),
        ("how much eth", {"ETH"}),
        ("Bitcoin and Cardano", {"BTC", "ADA"}),
        ("something method", set()),
        ("somethingETH", set()),
        ("比特币现金涨了吗", set()),
        ("Bitcoin Cash", set()),
        ("我10月一共买了多少钱的币？", set()),
    ],
)
def test_the_assets_named_are_found_by_whole_word_and_longest_name(
    said: str, named: set[str]
) -> None:
    assert assets_named(said, ASSETS) == named


def test_another_name_of_a_coin_counts_only_for_a_code_the_ledger_has() -> None:
    only_btc = [asset for asset in ASSETS if asset.code == "BTC"]

    assert assets_named("以太坊和比特币", only_btc) == {"BTC"}


def test_the_users_bitcoin_and_the_models_btc_are_the_same_asset() -> None:
    assert check_asset("BTC", ASSETS, "我上个月买了多少比特币", None) == AssetUsed(code="BTC")
    assert check_asset("比特币", ASSETS, "我上个月买了多少比特币", None) == AssetUsed(code="BTC")
    assert check_asset("btc", ASSETS, "BTC 10月", None) == AssetUsed(code="BTC")


def test_an_asset_the_user_did_not_name_is_dropped() -> None:
    checked = check_asset("BTC", ASSETS, "上个月哪几笔卖出最赚钱", None)

    assert isinstance(checked, AssetDropped)
    assert checked.why == "Not narrowed to BTC: you did not name it."


def test_an_asset_named_the_time_before_is_kept_when_nothing_is_named_now() -> None:
    assert check_asset("BTC", ASSETS, "那上个月呢", "我10月买了多少比特币") == AssetUsed(code="BTC")


def test_an_asset_named_the_time_before_is_dropped_when_another_is_named_now() -> None:
    checked = check_asset("BTC", ASSETS, "那ETH呢", "我10月买了多少比特币")

    assert isinstance(checked, AssetDropped)


def test_a_coin_the_ledger_lacks_named_now_also_stops_the_one_before() -> None:
    checked = check_asset("BTC", ASSETS, "那狗狗币呢", "我10月买了多少比特币")

    assert isinstance(checked, AssetDropped)


def test_a_general_word_for_coins_is_dropped_and_everything_is_looked_up() -> None:
    checked = check_asset("币", ASSETS, "我10月一共买了多少钱的币？", None)

    assert isinstance(checked, AssetDropped)
    assert "币" in checked.why


@pytest.mark.parametrize("word", ["coin", "crypto", "coins"])
def test_english_general_words_are_dropped_too(word: str) -> None:
    assert isinstance(check_asset(word, ASSETS, f"how much {word} did I buy", None), AssetDropped)


def test_a_code_the_ledger_lacks_that_the_user_said_is_no_such_asset() -> None:
    assert check_asset("DOGE", ASSETS, "10月我买了多少DOGE", None) == NoSuchAsset(word="DOGE")
    assert check_asset("doge", ASSETS, "how much DOGE do I hold", None) == NoSuchAsset(word="doge")


def test_a_code_the_ledger_lacks_that_the_user_never_said_is_dropped() -> None:
    assert isinstance(check_asset("DOGE", ASSETS, "10月我买了多少币", None), AssetDropped)
    assert isinstance(check_asset("X", ASSETS, "X 10月", None), AssetDropped)
    assert isinstance(check_asset("12345", ASSETS, "12345", None), AssetDropped)


@pytest.mark.parametrize(
    ("given", "said"),
    [
        ("buy", "我10月一共买了多少钱的币"),
        ("sell", "上个月哪几笔卖出最赚钱"),
        ("sell", "What did I sell last month?"),
        ("buy", "Show what I bought in October"),
        ("buy", "10月6号我买入了什么"),
    ],
)
def test_a_side_the_user_named_alone_is_used(given: str, said: str) -> None:
    assert check_side(given, said) == SideUsed(side=Side(given))


@pytest.mark.parametrize(
    ("given", "said"),
    [
        ("buy", "我10月的买卖赚了多少"),
        ("sell", "最近7天我有没有买卖过东西"),
        ("buy", "my buys and sells in October"),
        ("sell", "I bought and sold ETH"),
        ("buy", "我10月买了什么又卖了什么"),
        ("buy", "10月的交易"),
        ("sell", "我10月买了什么"),
        ("buy", "bestseller buyer"),
        ("sell", "我买的币赚了多少"),
    ],
)
def test_a_side_not_named_alone_is_dropped(given: str, said: str) -> None:
    checked = check_side(given, said)

    assert isinstance(checked, SideDropped)
    assert checked.why == (f"Not narrowed to {given}s: what you said does not name {given}s alone.")
