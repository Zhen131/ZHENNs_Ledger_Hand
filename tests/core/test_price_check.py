"""Tests of comparing a trade's price with the ledger's market price.

The line of five times is checked from both sides, with the demo book's
figures (BTC 64880 USDT: far at 12976 and below, and at 324400 and
above); a market price of 0 or below is none; another money is never
compared; and with the trade's money not known nothing stands in for it.
All figures are invented.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ledger_hand.core.ledger_records import MarketPrice, MoneyAmount
from ledger_hand.core.price_check import PriceVerdict, check_price, not_asked

FIVE = Decimal(5)


def market(amount: str, money: str = "USDT", asset: str = "BTC") -> MarketPrice:
    return MarketPrice(
        asset=asset,
        price=MoneyAmount(currency=money, amount=Decimal(amount)),
        day=date(2026, 11, 24),
    )


BTC = market("64880")


@pytest.mark.parametrize(
    ("price", "verdict"),
    [
        ("12976", PriceVerdict.FAR),
        ("12977", PriceVerdict.WITHIN),
        ("324400", PriceVerdict.FAR),
        ("324399", PriceVerdict.WITHIN),
        ("950", PriceVerdict.FAR),
        ("64880", PriceVerdict.WITHIN),
    ],
)
def test_the_line_of_five_times_counts_exactly_five(price: str, verdict: PriceVerdict) -> None:
    assert check_price(Decimal(price), "USDT", [BTC], FIVE).verdict is verdict


def test_times_apart_are_shown_whole_from_ten_and_to_one_place_below() -> None:
    lower = check_price(Decimal("950"), "USDT", [BTC], FIVE)
    near = check_price(Decimal("20000"), "USDT", [BTC], Decimal(3))

    assert (lower.times, lower.higher) == (Decimal("68"), False)
    assert (near.verdict, near.times) == (PriceVerdict.FAR, Decimal("3.2"))


def test_a_higher_price_says_so() -> None:
    check = check_price(Decimal("324400"), "USDT", [BTC], FIVE)

    assert (check.times, check.higher) == (Decimal("5.0"), True)


@pytest.mark.parametrize("amount", ["0", "-3"])
def test_a_market_price_of_zero_or_below_is_no_market_price(amount: str) -> None:
    check = check_price(Decimal("950"), "USDT", [market(amount)], FIVE)

    assert check.verdict is PriceVerdict.NO_MARKET_PRICE
    assert check.times is None


def test_no_market_price_is_not_compared() -> None:
    assert check_price(Decimal("5"), "USDT", [], FIVE).verdict is PriceVerdict.NO_MARKET_PRICE


def test_a_market_price_in_another_money_is_never_compared() -> None:
    check = check_price(Decimal("2600"), "USDT", [market("2700", "USD", "ETH")], FIVE)

    assert check.verdict is PriceVerdict.OTHER_MONEY
    assert check.market is not None and check.market.price.currency == "USD"
    assert check.times is None


def test_of_two_market_prices_the_one_in_the_trades_money_is_compared() -> None:
    both = [market("9999999", "USD"), BTC]

    check = check_price(Decimal("950"), "USDT", both, FIVE)

    assert check.verdict is PriceVerdict.FAR
    assert check.market == BTC


def test_with_the_money_not_known_nothing_stands_in_for_it() -> None:
    check = check_price(Decimal("950"), None, [BTC, market("64000", "USD")], FIVE)

    assert check.verdict is PriceVerdict.NO_MONEY
    assert check.market is None


def test_a_ledger_not_asked_carries_its_sentence() -> None:
    check = not_asked(Decimal("950"), "USDT", "The ledger did not answer.")

    assert check.verdict is PriceVerdict.NOT_ASKED
    assert check.failure == "The ledger did not answer."
    assert not check.verdict.compared


@pytest.mark.parametrize(("price", "gap"), [("0", "5"), ("950", "1"), ("950", "0.5")])
def test_a_price_not_above_zero_or_a_gap_not_above_one_is_refused(price: str, gap: str) -> None:
    with pytest.raises(ValueError):
        check_price(Decimal(price), "USDT", [BTC], Decimal(gap))
