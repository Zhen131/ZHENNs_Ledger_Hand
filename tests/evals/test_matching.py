"""Tests of pairing drafts with gold trades: how many pairs, what is left over."""

from __future__ import annotations

import pytest

from evals.matching import MAX_GOLD_TRADES, agreement, pair_trades
from tests.evals.builders import draft, sentence

TEXT = "买了 1 SOL，150 一个，又买了 2 ETH，3,000 一个"
GOLD = sentence(
    TEXT,
    {"side": "buy", "coin": ["SOL", "SOL"], "quantity": ["1 SOL", "1"], "price": ["150", "150"]},
    {"side": "buy", "coin": ["ETH", "ETH"], "quantity": ["2 ETH", "2"], "price": ["3,000", "3000"]},
)
SOL = draft(TEXT, side="buy", coin="SOL", quantity="1", price="150")
ETH = draft(TEXT, side="buy", coin="ETH", quantity="2", price="3000")
JUNK = draft(TEXT, side="sell", coin="DOGE", quantity="7", price="0.2", opinion="x")


def test_agreement_counts_the_fields_that_hold_the_gold_value() -> None:
    assert agreement(GOLD.trades[0], SOL) == 11
    # side, coin, quantity and price differ, and the opinion is made up.
    assert agreement(GOLD.trades[0], JUNK) == 6


def test_as_many_pairs_as_the_smaller_side() -> None:
    fewer = pair_trades(GOLD.trades, [ETH])
    more = pair_trades(GOLD.trades, [JUNK, ETH, SOL])
    none = pair_trades(GOLD.trades, [])

    assert (fewer.pairs, fewer.missed, fewer.extra) == (((1, 0),), (0,), ())
    assert (more.pairs, more.missed, more.extra) == (((0, 2), (1, 1)), (), (0,))
    assert (none.pairs, none.missed, none.extra) == ((), (0, 1), ())


def test_a_poor_draft_is_still_paired_when_it_is_the_only_one() -> None:
    pairing = pair_trades(GOLD.trades[:1], [JUNK])

    assert pairing.pairs == ((0, 0),)


def test_too_many_gold_trades_are_refused() -> None:
    with pytest.raises(ValueError, match="at most"):
        pair_trades(GOLD.trades * (MAX_GOLD_TRADES // 2 + 1), [])
