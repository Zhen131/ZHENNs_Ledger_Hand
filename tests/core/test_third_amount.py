"""Tests of working out the third amount of a trade already in the ledger."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ledger_hand.core.trade import Amount
from ledger_hand.core.validation import amounts_agree, third_amount

D = Decimal


def test_a_total_is_the_product_without_trailing_zeros() -> None:
    assert (
        str(third_amount(Amount.TOTAL, {Amount.QUANTITY: D("0.0081"), Amount.PRICE: D("61940")}))
        == "501.714"
    )


def test_a_price_that_does_not_come_out_even_is_rounded_half_up_to_eight_places() -> None:
    price = third_amount(Amount.PRICE, {Amount.QUANTITY: D("0.0081"), Amount.TOTAL: D("507.908")})
    assert str(price) == "62704.69135802"


def test_a_quantity_that_comes_out_even_is_kept_whole() -> None:
    quantity = third_amount(Amount.QUANTITY, {Amount.PRICE: D("2446"), Amount.TOTAL: D("244.6")})
    assert str(quantity) == "0.1"


def test_a_result_rounded_to_zero_is_not_offered() -> None:
    assert (
        third_amount(Amount.QUANTITY, {Amount.PRICE: D("3000000000000"), Amount.TOTAL: D("0.001")})
        is None
    )


def test_the_two_others_must_be_given() -> None:
    with pytest.raises(ValueError, match="two other amounts"):
        third_amount(Amount.TOTAL, {Amount.QUANTITY: D("1")})


def test_amounts_agree_within_the_ledgers_tolerance() -> None:
    assert amounts_agree(D("0.0082"), D("61940"), D("507.908"))
    assert amounts_agree(D("0.006"), D("66120"), D("396.7249"))
    assert not amounts_agree(D("0.0081"), D("61940"), D("507.908"))
