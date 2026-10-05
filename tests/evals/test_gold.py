"""Tests of reading a set file: what it accepts, what it refuses, and writing a trade back."""

from __future__ import annotations

from decimal import Decimal

import pytest

from evals.gold import (
    DEBUG_SET,
    FINAL_SET,
    Split,
    gold_draft,
    load_set,
    sentences_from_json,
    trade_from_json,
    trade_to_json,
)
from ledger_hand.core.trade import Side, TimePrecision
from ledger_hand.core.validation import Missing
from ledger_hand.extraction.reply_table import Field

TEXT = "昨天在 OKX 买了 0.5 ETH，价格 3,200，手续费 1U"
TRADE = {
    "side": "buy",
    "coin": ["ETH", "ETH"],
    "quantity": ["0.5 ETH", "0.5"],
    "price": ["3,200", "3200"],
    "fee": ["1U", "1"],
    "fee_currency": ["U", "USDT"],
    "time": ["昨天", "2026-10-04", "day"],
    "platform": ["OKX", "OKX"],
    "missing": [],
}


def sentence_data(**changes: object) -> dict[str, object]:
    data: dict[str, object] = {
        "id": "x1",
        "text": TEXT,
        "now": "2026-10-05T21:30:00+02:00",
        "zone": "Europe/Budapest",
        "language": "zh",
        "group": "scored",
        "features": [],
        "trades": [TRADE],
    }
    data.update(changes)
    return data


def test_a_trade_is_read_field_by_field() -> None:
    trade = trade_from_json(TRADE, TEXT, "Europe/Budapest")

    assert trade.value(Field.SIDE) is Side.BUY
    assert trade.value(Field.PRICE) == Decimal("3200")
    assert trade.cell(Field.FEE_CURRENCY).phrase == "U"
    assert trade.value(Field.TIME).precision is TimePrecision.DAY  # type: ignore[union-attr]
    assert trade.cell(Field.TOTAL).phrase is None
    assert trade.missing == ()


def test_a_trade_written_back_reads_the_same() -> None:
    trade = trade_from_json(TRADE, TEXT, "Europe/Budapest")
    with_time = trade_from_json(
        {**TRADE, "time": ["昨天", "2026-10-04T09:00:00+02:00", "minute"], "missing": ["FEE"]},
        TEXT,
        "Europe/Budapest",
    )

    for original in (trade, with_time):
        again = trade_from_json(trade_to_json(original), TEXT, "Europe/Budapest")
        assert again == original
    assert with_time.missing == (Missing.FEE,)


def test_an_empty_value_means_said_but_left_empty() -> None:
    trade = trade_from_json({**TRADE, "price": ["3,200", None]}, TEXT, "Europe/Budapest")

    assert trade.cell(Field.PRICE).phrase == "3,200"
    assert trade.value(Field.PRICE) is None


@pytest.mark.parametrize(
    "changes",
    [
        {"price": ["3,300", "3300"]},
        {"price": ["3,200", "three"]},
        {"price": ["3,200"]},
        {"time": ["昨天", "2026-10-04"]},
        {"time": ["昨天", "2026-10-04T09:00:00+00:00", "minute"]},
        {"coin": ["ETH", ""]},
        {"side": "hold"},
        {"amount": ["0.5 ETH", "0.5"]},
        {"missing": ["NOTHING"]},
        {"price": ["3,200", "3200", "minute"]},
    ],
)
def test_a_malformed_trade_is_refused(changes: dict[str, object]) -> None:
    with pytest.raises((ValueError, KeyError)):
        sentences_from_json([sentence_data(trades=[{**TRADE, **changes}])], Split.DEBUG)


@pytest.mark.parametrize(
    "changes",
    [
        {"zone": "Mars/Base"},
        {"now": "2026-10-05T21:30:00"},
        {"group": "not_to_record"},
        {"kind": "plan"},
        {"language": "fr"},
        {"features": ["pretty"]},
        {"extra": 1},
    ],
)
def test_a_malformed_sentence_is_refused(changes: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        sentences_from_json([sentence_data(**changes)], Split.DEBUG)


def test_two_sentences_with_one_id_are_refused() -> None:
    with pytest.raises(ValueError, match="share an id"):
        sentences_from_json([sentence_data(), sentence_data()], Split.DEBUG)


def test_the_gold_draft_holds_the_gold_values() -> None:
    (sentence,) = sentences_from_json([sentence_data()], Split.DEBUG)

    draft = gold_draft(sentence.trades[0], sentence.text)

    assert (draft.coin, draft.quote, draft.fee_coin, draft.platform) == ("ETH", None, "USDT", "OKX")
    assert (draft.quantity, draft.price, draft.total) == (Decimal("0.5"), Decimal("3200"), None)
    assert draft.raw_text == TEXT


def test_both_set_files_are_read() -> None:
    assert load_set(DEBUG_SET, Split.DEBUG)
    assert load_set(FINAL_SET, Split.FINAL)
