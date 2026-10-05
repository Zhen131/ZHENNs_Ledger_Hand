"""Tests of working out what a sentence covers, and of checking its hand-given labels."""

from __future__ import annotations

import pytest

from evals.coverage import Item, feature_holds, items_of
from evals.gold import Feature, Split, sentences_from_json
from tests.evals.builders import sentence


def test_items_are_read_off_the_gold_answer() -> None:
    text = "昨天花了 500 刀买大饼，手续费 0.002 BNB，感觉还行"
    items = items_of(
        sentence(
            text,
            {
                "side": "buy",
                "coin": ["大饼", "BTC"],
                "total": ["500 刀", "500"],
                "price_currency": ["刀", "USDT"],
                "fee": ["0.002 BNB", "0.002"],
                "fee_currency": ["BNB", "BNB"],
                "time": ["昨天", "2026-10-04", "day"],
                "opinion": ["感觉还行", "感觉还行"],
            },
        )
    )

    assert items == {
        Item.CHINESE,
        Item.ONE_TRADE,
        Item.NO_PRICE,
        Item.ONE_AMOUNT,
        Item.FEE_THIRD_COIN,
        Item.BUY,
        Item.OPINION,
    }


def test_a_field_the_rules_leave_empty_and_a_missing_time() -> None:
    text = "卖了 0.1 BTC，价格 94 900，手续费 0"
    items = items_of(
        sentence(
            text,
            {
                "side": "sell",
                "coin": ["BTC", "BTC"],
                "quantity": ["0.1 BTC", "0.1"],
                "price": ["94 900", None],
                "fee": ["0", "0"],
            },
        )
    )

    assert {Item.RULES_LEAVE_EMPTY, Item.NO_TIME, Item.TIME_NOT_SAID, Item.FEE_ZERO} <= items
    assert Item.QUANTITY_AND_PRICE in items
    assert Item.SELL in items


def test_a_passage_not_to_record_counts_only_for_its_language_and_kind() -> None:
    data = {
        "id": "n1",
        "text": "打算明天买 1 个 ETH",
        "now": "2026-10-05T21:30:00+02:00",
        "zone": "Europe/Budapest",
        "language": "zh",
        "group": "not_to_record",
        "kind": "plan",
        "features": ["shared_detail"],
        "trades": [],
    }
    (plan,) = sentences_from_json([data], Split.DEBUG)

    assert items_of(plan) == {Item.CHINESE, Item.PLAN}


def test_talk_is_a_passage_with_no_trade() -> None:
    assert items_of(sentence("今天没交易")) == {Item.CHINESE, Item.NO_TRADE}


ETH_TWO = {"quantity": ["2 个 ETH", "2"]}


@pytest.mark.parametrize(
    ("feature", "text", "cells"),
    [
        (Feature.PER_PIECE, "买了 2 个 ETH，3000 一个", ETH_TWO),
        (Feature.GAP_BEFORE_MULTIPLIER, "买了 3w DOGE", {"quantity": ["3w DOGE", "30000"]}),
        (Feature.SPACE_THOUSANDS, "买了 2 个 ETH，3000 一个", ETH_TWO),
        (Feature.THOUSANDS_COMMA, "买了 2 个 ETH，3000 一个", ETH_TWO),
        (Feature.CHINESE_NUMERALS, "买了 2 个 ETH，3000 一个", ETH_TWO),
        (Feature.UNRELATED_NUMBER, "买了 2 个 ETH", ETH_TWO),
        (Feature.SHARED_DETAIL, "买了 2 个 ETH", ETH_TWO),
        (Feature.ADJACENT_NUMBERS, "买了 2 个 ETH", ETH_TWO),
        (Feature.SPAN_BACK, "买了 2 个 ETH", ETH_TWO),
    ],
)
def test_a_label_the_sentence_does_not_bear_out_is_caught(
    feature: Feature, text: str, cells: dict[str, object]
) -> None:
    assert not feature_holds(sentence(text, {"side": "buy", **cells}), feature)


@pytest.mark.parametrize(
    ("feature", "text", "cells"),
    [
        (Feature.PER_PIECE, "买了 2 个 ETH，3000一个", {"price": ["3000", "3000"]}),
        (
            Feature.GAP_BEFORE_MULTIPLIER,
            "买了 100 万 SHIB",
            {"quantity": ["100 万 SHIB", "1000000"]},
        ),
        (Feature.SPACE_THOUSANDS, "价格 94 900", {"price": ["94 900", None]}),
        (Feature.UNRELATED_NUMBER, "买了 2 个 ETH，第 3 次了", {"quantity": ["2 个 ETH", "2"]}),
        (
            Feature.SPAN_BACK,
            "3 小时前买的",
            {"time": ["3 小时前", "2026-10-05T18:30:00+02:00", "minute"]},
        ),
    ],
)
def test_a_label_the_sentence_bears_out_holds(
    feature: Feature, text: str, cells: dict[str, object]
) -> None:
    assert feature_holds(sentence(text, {"side": "buy", **cells}), feature)
