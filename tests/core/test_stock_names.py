"""Tests of the program's table of company names, the words cut off a name, and matching.

The table holds only names a person says for one company, never a coin's
name, a word for money or a word for a kind of asset; every code can be a
ledger code; no two rows read the same once looked up. A name is matched
only whole, its trailing words for "share" or "company" cut off, at most
twice; the eight ways of saying a name that must not be matched are not.
The user's answers come before the table. Every figure is invented.
"""

from __future__ import annotations

from datetime import date

import pytest

from ledger_hand.core.coins import BUILT_IN_COINS, USDT_WORDS, spoken_key
from ledger_hand.core.ledger_limits import is_symbol
from ledger_hand.core.ledger_records import Asset, AssetKind, Pricing
from ledger_hand.core.ledger_table import MONEY_WORDS, VAGUE_MONEY_WORDS, table_of
from ledger_hand.core.stock_names import (
    COMPANY_NAMES,
    GENERAL_WORDS,
    LEAST_NAME_LENGTH,
    TAIL_WORDS,
    NameAbsent,
    NameMatched,
    NameSeveral,
    RememberedName,
    bare_name,
    can_remember,
    codes_named,
    find_name,
    worth_remembering,
)
from ledger_hand.core.trade import PickedBy, PickedFrom
from ledger_hand.ledger.demo_book import DEMO_ASSETS
from ledger_hand.ledger.invented_book import INVENTED_ASSETS

DEMO = table_of(DEMO_ASSETS)
NAMES = [name for name, _ in COMPANY_NAMES]


def demo():  # type: ignore[no-untyped-def]
    assert DEMO is not None
    return DEMO


def stock(code: str, name: str) -> Asset:
    return Asset(
        id=f"asset-{code.lower()}",
        code=code,
        name=name,
        kind=AssetKind.STOCK,
        pricing=Pricing.CANNOT_PRICE,
    )


def ledger_with(*codes: str):  # type: ignore[no-untyped-def]
    table = table_of((*INVENTED_ASSETS[:2], *(stock(code, code.title()) for code in codes)))
    assert table is not None
    return table


# --- the table ---------------------------------------------------------------------------


def test_the_table_holds_forty_to_eighty_rows_and_every_code_can_be_a_ledger_code() -> None:
    assert 40 <= len(COMPANY_NAMES) <= 80
    for name, codes in COMPANY_NAMES:
        assert codes, name
        assert all(is_symbol(code) for code in codes), name


def test_no_two_rows_read_the_same_once_looked_up() -> None:
    keys = [spoken_key(name) for name in NAMES]
    assert len(keys) == len(set(keys))


def test_no_name_is_a_coins_name_a_word_for_money_or_a_word_for_a_kind_of_asset() -> None:
    coins = {
        spoken_key(form)
        for coin in BUILT_IN_COINS
        for form in (coin.symbol, coin.name, *coin.aliases)
    }
    money = {spoken_key(word) for word, _ in MONEY_WORDS} | {
        spoken_key(word) for word in VAGUE_MONEY_WORDS
    }
    general = {spoken_key(word) for word in GENERAL_WORDS}
    for name in NAMES:
        key = spoken_key(name)
        assert key not in coins, name
        assert key not in money and key not in USDT_WORDS, name
        assert key not in general, name


def test_no_name_is_a_product_rather_than_a_company() -> None:
    for product in ("雪碧", "IPHONE", "百事可乐", "可乐", "WINDOWS", "芬达"):
        assert codes_named(product) == ()


def test_every_name_is_matched_whole_and_ends_in_no_tail_word() -> None:
    for name, codes in COMPANY_NAMES:
        assert bare_name(name) == spoken_key(name), name
        assert codes_named(name) == codes


# --- the words cut off the end -----------------------------------------------------------


@pytest.mark.parametrize(
    ("said", "bare"),
    [
        ("微软的股票", "微软"),
        ("苹果股票", "苹果"),
        ("英特尔的股份", "英特尔"),
        ("英特尔股份", "英特尔"),
        ("苹果的公司", "苹果"),
        ("百事公司", "百事"),
        ("阿里巴巴集团", "阿里巴巴"),
        ("微软公司的股票", "微软"),
        ("  微软的股票 ", "微软"),
    ],
)
def test_each_tail_word_is_cut_off_the_end(said: str, bare: str) -> None:
    assert bare_name(said) == bare


def test_every_tail_word_is_tested_above() -> None:
    assert set(TAIL_WORDS) == {"的股票", "股票", "的股份", "股份", "的公司", "公司", "集团"}


def test_at_most_two_words_are_cut() -> None:
    assert bare_name("微软公司的股份的股票") == "微软公司"


@pytest.mark.parametrize("said", ["公司", "股票", "的股票", "微的股票", "币"])
def test_what_is_left_must_be_two_characters_or_more(said: str) -> None:
    assert LEAST_NAME_LENGTH == 2
    assert bare_name(said) is None


def test_gu_and_de_alone_are_never_cut() -> None:
    assert bare_name("微软股") == "微软股"
    assert bare_name("微软的") == "微软的"


# --- what is matched ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "said",
    [
        "可口可乐装瓶公司",
        "雪碧的股票",
        "微软的期权",
        "微软A股",
        "英伟达两倍做多ETF",
        "以太坊经典",
        "微软和英特尔",
        "可乐",
    ],
)
def test_the_ways_of_saying_that_must_not_be_matched_are_not(said: str) -> None:
    assert find_name(said, demo(), (), table=True) is None


def test_a_name_the_table_holds_and_the_ledger_has_is_matched_from_the_table() -> None:
    found = find_name("微软的股票", demo(), (), table=True)

    assert found is not None
    assert found.word == "微软的股票"
    assert found.name == "微软"
    assert found.found == NameMatched("MSFT", PickedFrom(by=PickedBy.TABLE))


def test_a_name_whose_codes_the_ledger_lacks_is_absent() -> None:
    found = find_name("特斯拉", demo(), (), table=True)

    assert found is not None and found.found == NameAbsent(("TSLA",))


def test_one_name_with_two_codes_is_matched_only_when_the_ledger_has_exactly_one() -> None:
    one = find_name("谷歌", ledger_with("GOOGL"), (), table=True)
    both = find_name("谷歌", ledger_with("GOOGL", "GOOG"), (), table=True)
    neither = find_name("谷歌", ledger_with("KO"), (), table=True)

    assert one is not None and one.found == NameMatched("GOOGL", PickedFrom(by=PickedBy.TABLE))
    assert both is not None and both.found == NameSeveral(("GOOGL", "GOOG"))
    assert neither is not None and neither.found == NameAbsent(("GOOGL", "GOOG"))


def test_the_table_off_matches_nothing_from_the_table() -> None:
    assert find_name("微软", demo(), (), table=False) is None


def test_an_answer_comes_before_the_table_and_the_latest_answer_wins() -> None:
    answers = (
        RememberedName("微软", "KO", date(2026, 11, 1)),
        RememberedName("微软", "INTC", date(2026, 11, 2)),
    )

    found = find_name("微软", demo(), answers, table=True)

    assert found is not None
    assert found.found == NameMatched("INTC", PickedFrom(by=PickedBy.ANSWER, day=date(2026, 11, 2)))


def test_an_answer_whose_code_the_ledger_no_longer_has_counts_for_nothing() -> None:
    answers = (RememberedName("小可", "TSLA", date(2026, 11, 1)),)

    assert find_name("小可", demo(), answers, table=True) is None


def test_a_name_the_ledger_finds_money_and_a_coin_it_lacks_are_never_looked_up() -> None:
    answers = (RememberedName("比特币现金", "KO", date(2026, 11, 1)),)

    assert find_name("MSFT", demo(), (), table=True) is None
    assert find_name("美元", demo(), (), table=True) is None
    assert find_name("比特币现金", demo(), answers, table=True) is None


# --- what may be remembered --------------------------------------------------------------


@pytest.mark.parametrize(
    "name", ["股票", "这只", "COIN", "美股", "ETF", "可", "美元", "比特币", "MSFT", "期权"]
)
def test_a_general_word_money_a_coins_name_a_code_or_one_character_is_never_remembered(
    name: str,
) -> None:
    assert not can_remember(name)


def test_a_name_said_and_answered_with_a_code_of_the_ledger_is_worth_remembering() -> None:
    passage = "2026年11月20号14:30在IBKR买了2股小可，100美元一股"

    assert worth_remembering("小可", "ko", passage, demo()) == ("小可", "KO")
    assert worth_remembering("小可的股票", "KO", passage, demo()) == ("小可", "KO")
    assert worth_remembering("大可", "KO", passage, demo()) is None
    assert worth_remembering("小可", "TSLA", passage, demo()) is None
    assert worth_remembering("小可", "USD", passage, demo()) is None
    assert worth_remembering("股票", "KO", passage, demo()) is None
