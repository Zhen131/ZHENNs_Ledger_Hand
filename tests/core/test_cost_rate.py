"""Tests of the rate between two moneys: how it is worked out, compared and marked.

Every figure is invented; the five rates of the exam's practice half are
those its gold answers hold.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from ledger_hand.core.cost_rate import (
    RATE_PLACES,
    RateNote,
    RateReference,
    far_from_reference,
    rate_mark,
    rate_of,
    reference_in,
    written,
)
from ledger_hand.core.ledger_records import LedgerTrade, MarketPrice, MoneyAmount, TradeFacts
from ledger_hand.core.marks import REASON_MOST, Field, MarkKind, reason_length
from ledger_hand.core.price_check import check_price
from ledger_hand.core.trade import InferredFrom, SaidPrice, Side

_BUDAPEST = ZoneInfo("Europe/Budapest")
NOW = datetime(2026, 11, 24, 23, 55, tzinfo=_BUDAPEST)


@pytest.mark.parametrize(
    ("quantity", "said", "total", "rate"),
    [
        ("2", "69.5", "128", "1.0859375"),
        ("3", "36.2", "100", "1.086"),
        ("2", "70", "130", "1.0769230769"),
        ("0.001", "98000", "95", "1.0315789474"),
        ("2", "6.95", "128", "0.10859375"),
        ("2", "69.5", "12.8", "10.859375"),
        ("1", "140", "1000", "0.14"),
        ("0.0061629", "81.13", "0.46", "1.0869479935"),
        ("3.1657591", "78.97", "210.6", "1.187084502"),
        ("1.0822979", "230.99", "223.67", "1.1177180307"),
        ("1.1283116", "221.57", "231.61", "1.079400722"),
        ("2.0408163", "73.5", "128.53", "1.1670426986"),
    ],
)
def test_the_rate_is_quantity_times_price_said_over_total_to_ten_places(
    quantity: str, said: str, total: str, rate: str
) -> None:
    found = rate_of(Decimal(quantity), Decimal(said), Decimal(total))

    assert written(found) == rate
    assert found == Decimal(rate)
    assert -found.as_tuple().exponent <= RATE_PLACES  # type: ignore[operator]


def test_a_rate_that_comes_out_whole_is_written_with_no_point() -> None:
    assert written(rate_of(Decimal(2), Decimal(50), Decimal(100))) == "1"


@pytest.mark.parametrize(("quantity", "said", "total"), [("0", "1", "1"), ("1", "0", "1")])
def test_a_rate_is_worked_out_only_from_figures_above_zero(
    quantity: str, said: str, total: str
) -> None:
    with pytest.raises(ValueError):
        rate_of(Decimal(quantity), Decimal(said), Decimal(total))


# 1.0859 × 1.1 = 1.19449; 1.0859 × 0.9 = 0.97731: exactly that share is not far.
@pytest.mark.parametrize("rate", ["1.0859375", "1.19449", "0.97731"])
def test_within_the_share_either_way_is_not_far(rate: str) -> None:
    assert not far_from_reference(Decimal(rate), Decimal("1.0859"), Decimal("0.1"))


@pytest.mark.parametrize("rate", ["1.19450", "0.97730"])
def test_beyond_the_share_either_way_is_far(rate: str) -> None:
    assert far_from_reference(Decimal(rate), Decimal("1.0859"), Decimal("0.1"))


def test_exactly_ten_in_a_hundred_below_is_not_far() -> None:
    assert not far_from_reference(Decimal("0.9"), Decimal("1"), Decimal("0.1"))
    assert far_from_reference(Decimal("0.8999"), Decimal("1"), Decimal("0.1"))


def _trade(key: str, asset: str, quote: str, day: int, rate: str | None) -> LedgerTrade:
    return LedgerTrade(
        id=key,
        facts=TradeFacts(
            occurred=datetime(2026, 11, day, 12, 0, tzinfo=_BUDAPEST),
            side=Side.BUY,
            asset=asset,
            quantity=Decimal(1),
            price=Decimal(100),
            total=Decimal(100),
            quote=quote,
            fee=Decimal(0),
            fee_asset=quote,
            platform="",
            note="",
            raw_text=None,
            zone="Europe/Budapest",
            date_only=False,
            cost_rate=Decimal(rate) if rate is not None else None,
        ),
        realized=None,
        realized_unreliable=None,
        dated_after_today=False,
    )


PRICED_IN = {"KO": "USD", "AAPL": "USD", "BTC": "USDT"}


def test_the_reference_is_the_latest_trade_paid_in_that_money_for_an_asset_in_the_same_money() -> (
    None
):
    trades = (
        _trade("t-1", "AAPL", "EUR", 1, "1.08"),
        _trade("t-2", "KO", "EUR", 3, "1.09"),
        _trade("t-3", "BTC", "EUR", 5, "1.2"),
        _trade("t-4", "KO", "USD", 6, None),
        _trade("t-5", "KO", "CNY", 7, "0.14"),
    )

    found = reference_in(trades, "EUR", "USD", PRICED_IN, NOW)

    assert found == RateReference(
        rate=Decimal("1.09"), trade_id="t-2", day=date(2026, 11, 3), asset="KO"
    )


def test_no_such_trade_gives_no_reference() -> None:
    trades = (_trade("t-3", "BTC", "EUR", 5, "1.2"), _trade("t-4", "KO", "USD", 6, None))

    assert reference_in(trades, "EUR", "USD", PRICED_IN, NOW) is None


def _note(**changed: object) -> RateNote:
    fields: dict[str, object] = {
        "rate": Decimal("1.0859375"),
        "said": SaidPrice(amount=Decimal("69.5"), money="USD", paid="EUR"),
        "quantity": Decimal(2),
        "total": Decimal(128),
        "each": "a share",
    }
    fields.update(changed)
    return RateNote(**fields)  # type: ignore[arg-type]


def test_a_rate_from_a_price_whose_money_was_named_is_worked_out() -> None:
    mark = rate_mark(_note(), "KO")

    assert (mark.field, mark.kind) == (Field.COST_RATE, MarkKind.COMPUTED)
    assert mark.reason == "worked out from the 69.5 USD a share you said: 2 × 69.5 ÷ 128"


def test_a_rate_from_a_price_whose_money_was_guessed_is_assumed_and_says_from_where() -> None:
    source = InferredFrom(
        trade_id="t-ko",
        occurred=datetime(2026, 8, 6, 16, tzinfo=_BUDAPEST),
        money="USD",
        asset="KO",
    )
    said = SaidPrice(amount=Decimal("69.5"), money="USD", paid="EUR", guessed_from=source)

    mark = rate_mark(_note(said=said), "KO")

    assert mark.kind is MarkKind.INFERRED
    assert mark.reason is not None
    assert mark.reason.startswith("the money of the price said was assumed from the last KO")
    assert "t-ko, 2026-08-06" in mark.reason


def test_both_guards_far_make_one_suspicious_mark_with_every_reason() -> None:
    reference = RateReference(
        rate=Decimal("1.0859"), trade_id="t-aapl", day=date(2026, 11, 3), asset="AAPL"
    )
    market = check_price(
        Decimal("6.95"),
        "USD",
        [MarketPrice(asset="KO", price=MoneyAmount(currency="USD", amount=Decimal(70)), day=None)],
        Decimal(5),
    )
    said = SaidPrice(amount=Decimal("6.95"), money="USD", paid="EUR")

    mark = rate_mark(
        _note(
            rate=Decimal("0.10859375"),
            said=said,
            reference=reference,
            reference_far=True,
            market=market,
        ),
        "KO",
    )

    assert mark.kind is MarkKind.SUSPICIOUS
    assert mark.reason is not None
    assert "6.95 USD" in mark.reason and "70 USD" in mark.reason and "1.0859" in mark.reason
    assert reason_length(mark.reason) <= REASON_MOST


def test_a_price_said_must_be_in_another_money_than_the_one_paid() -> None:
    with pytest.raises(ValueError):
        SaidPrice(amount=Decimal(1), money="EUR", paid="EUR")
    with pytest.raises(ValueError):
        SaidPrice(amount=Decimal(0), money="USD", paid="EUR")
