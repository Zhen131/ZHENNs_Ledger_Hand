"""Tests of the fake ledger's exchange rates, as the real ledger lists them since its dev 1b016ec.

Every rate, day and identifier is invented.
"""

from __future__ import annotations

from datetime import date

import pytest

from ledger_hand.core.ledger_rate import RateRequest, RateRow
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ports import LedgerError


def rate(base: str, quote: str, value: str, day: str) -> RateRow:
    return RateRow(
        base_id=f"asset-{base.lower()}",
        base_code=base,
        quote_id=f"asset-{quote.lower()}",
        quote_code=quote,
        rate=value,
        rate_date=day,
        source="manual",
        online_source=None,
    )


ROWS = (
    rate("USD", "USDT", "1.0", "2026-11-20"),
    rate("EUR", "USD", "1.08", "2026-11-18"),
    rate("USD", "EUR", "0.93", "2026-11-21"),
    rate("EUR", "USD", "1.07", "2026-11-21"),
    rate("EUR", "USD", "1.5", "2026-11-26"),
)


def ask(currency: str = "asset-usd", other: str = "asset-usdt", last: int = 30) -> RateRequest:
    return RateRequest(
        currency_id=currency,
        other_id=other,
        last_day=date(2026, 11, last),
        enough_day=date(2026, 11, 1),
    )


def ledger_with_euro() -> FakeLedger:
    from tests.flows.paid_apart_books import JIA_ASSETS  # noqa: PLC0415

    return FakeLedger(assets=JIA_ASSETS).listing_rates(ROWS)


def test_with_no_tool_it_says_so_and_names_no_call() -> None:
    ledger = FakeLedger()

    with pytest.raises(LedgerError) as caught:
        ledger.exchange_rates(ask())

    assert caught.value.code == "NO_RATE_TOOL"
    assert ledger.calls == []


def test_rows_between_the_two_moneys_both_ways_newest_first_none_after_today() -> None:
    ledger = ledger_with_euro()

    listed = ledger.exchange_rates(ask("asset-eur", "asset-usd"))

    assert [(one.rate, one.rate_date) for one in listed.rows] == [
        ("0.93", "2026-11-21"),
        ("1.07", "2026-11-21"),
        ("1.08", "2026-11-18"),
    ]
    assert listed.today == date(2026, 11, 24)
    assert ledger.calls == ["exchange_rates"]


def test_no_row_after_the_last_day_asked_for() -> None:
    listed = ledger_with_euro().exchange_rates(ask("asset-eur", "asset-usd", last=20))

    assert [one.rate for one in listed.rows] == ["1.08"]


@pytest.mark.parametrize(
    ("other", "code"),
    [("asset-gbp", "ASSET_NOT_FOUND"), ("asset-btc", "ASSET_IS_NOT_CURRENCY")],
)
def test_a_money_it_lacks_or_one_that_is_not_cash_is_refused(other: str, code: str) -> None:
    with pytest.raises(LedgerError) as caught:
        ledger_with_euro().exchange_rates(ask("asset-eur", other))

    assert caught.value.code == code
    assert "otherCurrencyAssetId" in caught.value.message
