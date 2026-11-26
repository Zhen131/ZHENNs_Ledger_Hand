"""Tests of a gold trade written with its day alone in the share set (K6 and K7).

A sentence said with its day only is sent with its day alone; its gold
time is that day, "YYYY-MM-DD". A trade sent with its day alone on that
day is right; one sent with a time of day, even 00:00 of that day, or on
another day, is silently wrong. Every figure is invented.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from evals.stock_set import SEND, Outcome, Verdict, judge, load_stock_set
from ledger_hand.core.ledger_records import TradeFacts
from ledger_hand.core.trade import Side

ZONE = ZoneInfo("Europe/Budapest")


def sent(day: int, *, date_only: bool, hour: int = 0) -> TradeFacts:
    return TradeFacts(
        occurred=datetime(2026, 11, day, hour, 0, tzinfo=ZONE),
        side=Side.BUY,
        asset="MSFT",
        quantity=Decimal("2"),
        price=Decimal("410"),
        total=Decimal("820"),
        quote="USD",
        fee=Decimal("1"),
        fee_asset="USD",
        platform="IBKR",
        note="",
        raw_text="invented",
        zone="Europe/Budapest",
        date_only=date_only,
        cost_rate=None,
    )


def gold_of(identifier: str):  # type: ignore[no-untyped-def]
    (sentence,) = [one for one in load_stock_set().sentences if one.id == identifier]
    return sentence.gold


def test_k6_and_k7_send_the_trade_with_its_day_alone() -> None:
    for identifier in ("K6", "K7"):
        gold = gold_of(identifier)
        assert gold.expect == SEND
        (trade,) = gold.trades
        assert trade.occurred == date(2026, 11, 23)
        assert not isinstance(trade.occurred, datetime)


def test_the_day_alone_on_that_day_is_right() -> None:
    outcome = Outcome(sent=(sent(23, date_only=True),))

    assert judge(gold_of("K6"), outcome) is Verdict.RIGHT


def test_a_time_of_day_sent_is_silently_wrong_even_midnight() -> None:
    for facts in (sent(23, date_only=False), sent(23, date_only=False, hour=15)):
        assert judge(gold_of("K6"), Outcome(sent=(facts,))) is Verdict.SILENTLY_WRONG


def test_another_day_is_silently_wrong() -> None:
    assert judge(gold_of("K7"), Outcome(sent=(sent(22, date_only=True),))) is Verdict.SILENTLY_WRONG


def test_a_gold_moment_still_needs_a_time_of_day() -> None:
    (first, *_) = load_stock_set().sentences
    (trade,) = first.gold.trades
    day_alone = sent(24, date_only=True)

    assert isinstance(trade.occurred, datetime)
    assert judge(first.gold, Outcome(sent=(day_alone,))) is Verdict.SILENTLY_WRONG
