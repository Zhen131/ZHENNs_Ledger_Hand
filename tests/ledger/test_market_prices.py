"""Tests of reading the ledger's market prices: the fake ledger's, and the real ledger's plug.

The real ledger's answers are the captured sample of ``get_positions``
(``tests/ledger/samples/positions.json``), in which no holding has a market
price; the rows with one are written from the ledger's
``assistant-link/README.md`` ("### get_positions", ``marketPrice``), as the
capture did not reach one and the real ledger page is not connected in
tests. A trade known only to its day is sent with the day alone, as the
captured sample ``propose-add-date-only`` shows the ledger takes it. Every
figure is invented.
"""

from __future__ import annotations

import copy
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

import pytest

from ledger_hand.core.ledger_records import MarketPrice, MoneyAmount
from ledger_hand.core.proposals import CheckOutcome
from ledger_hand.ledger.demo_book import demo_ledger
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ledger.link_client import AnswerKind, ToolAnswer
from ledger_hand.ports import LedgerError, LedgerErrorKind
from tests.ledger.test_link_ledger import ASSETS, SAID, facts, plug, sample, twin_assets


def priced(price: str, money: str, day: str) -> dict[str, Any]:
    """A market price as the ledger's README writes one (the capture had none)."""
    return {
        "price": price,
        "priceCurrencyAssetId": f"asset-{money.lower()}",
        "priceCurrencyCode": money,
        "source": "manual",
        "onlineSourceId": None,
        "priceDate": day,
        "adjustedForSplit": False,
    }


def positions_with(prices: dict[str, dict[str, Any] | None]) -> ToolAnswer:
    """The captured holdings, each asset named given the market price beside it."""
    answer = sample("positions")
    content = copy.deepcopy(dict(answer.content))
    for row in content["positions"]:
        if row["assetCode"] in prices:
            row["marketPrice"] = prices[row["assetCode"]]
    return ToolAnswer(kind=AnswerKind.RESULT, content=content)


# --- the fake ledger --------------------------------------------------------------------


def test_the_demo_ledger_has_eight_market_prices_none_for_ada_pep_or_dot() -> None:
    found = {
        (one.asset, one.price.currency): one.price.amount for one in demo_ledger().market_prices()
    }

    assert found[("SOL", "USDT")] == Decimal("150")
    assert found[("KO", "USD")] == Decimal("70")
    assert found[("BTC", "USDT")] == Decimal("64880")
    assert len(found) == 8
    assert not {asset for asset, _ in found} & {"ADA", "PEP", "DOT"}
    assert {one.day for one in demo_ledger().market_prices()} == {date(2026, 11, 24)}


def test_an_asset_with_a_price_in_two_moneys_has_both() -> None:
    ledger = FakeLedger(prices={("ETH", "USDT"): Decimal("2701"), ("ETH", "USD"): Decimal("2700")})

    assert {one.price.currency for one in ledger.market_prices()} == {"USDT", "USD"}
    assert ledger.calls == ["market_prices"]


def test_the_fake_ledger_can_fail_to_give_its_market_prices_alone() -> None:
    failure = LedgerError(LedgerErrorKind.TIMED_OUT, "timed_out", "No answer.")
    ledger = FakeLedger(market_failure=failure)

    with pytest.raises(LedgerError):
        ledger.market_prices()
    assert ledger.list_assets()


# --- the real ledger's plug ---------------------------------------------------------------


def test_a_holding_with_a_market_price_gives_it_with_its_money_and_day() -> None:
    answer = positions_with({"BTC": priced("64880", "USDT", "2026-11-24")})
    ledger, link = plug(("get_positions", answer), ASSETS)

    (found,) = ledger.market_prices()

    assert found == MarketPrice(
        asset="BTC",
        price=MoneyAmount(currency="USDT", amount=Decimal("64880")),
        day=date(2026, 11, 24),
    )
    assert link.names() == ["get_positions", "list_assets"]


def test_a_holding_whose_market_price_is_null_gives_none() -> None:
    ledger, _ = plug(("get_positions", sample("positions")), ASSETS)

    assert ledger.market_prices() == ()


def test_a_sold_out_holding_still_gives_its_market_price() -> None:
    # AAPL's row in the sample has a quantity of 0: sold out.
    answer = positions_with({"AAPL": priced("230", "USD", "2026-11-24T21:00:00.000Z")})
    ledger, _ = plug(("get_positions", answer), ASSETS)

    (found,) = ledger.market_prices()

    assert (found.asset, found.price.amount, found.day) == (
        "AAPL",
        Decimal("230"),
        date(2026, 11, 24),
    )


def test_two_assets_sharing_a_code_give_no_market_price_for_either() -> None:
    answer = positions_with({"BTC": priced("64880", "USDT", "2026-11-24")})
    content = copy.deepcopy(dict(answer.content))
    twin = copy.deepcopy(next(row for row in content["positions"] if row["assetCode"] == "BTC"))
    twin.update(assetId="asset-stock-btc", marketPrice=priced("12", "USD", "2026-11-24"))
    content["positions"].append(twin)
    both = ToolAnswer(kind=AnswerKind.RESULT, content=content)
    ledger, _ = plug(("get_positions", both), ("list_assets", twin_assets()))

    assert ledger.market_prices() == ()


@pytest.mark.parametrize("odd", ["NaN", "Infinity", "-Infinity", "not a number"])
def test_a_market_price_that_is_not_a_number_is_no_market_price(odd: str) -> None:
    answer = positions_with(
        {"BTC": priced(odd, "USDT", "2026-11-24"), "ETH": priced("2701", "USDT", "2026-11-24")}
    )
    ledger, _ = plug(("get_positions", answer), ASSETS)

    assert [found.asset for found in ledger.market_prices()] == ["ETH"]


def test_a_ledger_that_cannot_be_asked_is_a_ledger_failure() -> None:
    ledger, _ = plug(("get_positions", sample("page-not-connected")))

    with pytest.raises(LedgerError) as caught:
        ledger.market_prices()

    assert caught.value.kind is LedgerErrorKind.UNREACHABLE


def test_a_trade_known_only_to_its_day_is_sent_with_the_day_alone() -> None:
    day_only = facts(
        occurred=datetime(2026, 11, 19, 0, 0, tzinfo=timezone.utc),
        asset="ADA",
        quantity=Decimal("10"),
        price=Decimal("0.5"),
        total=Decimal("5"),
        fee_asset="USDT",
        date_only=True,
        zone="Europe/Budapest",
    )
    ledger, link = plug(ASSETS, ("propose_trade_add", sample("propose-add-date-only")))

    result = ledger.propose_add((day_only,), SAID)

    (check,) = result.checks
    assert check.outcome is CheckOutcome.PASSED
    _, sent = link.asked[1]
    (trade,) = sent["trades"]
    assert trade["occurredDate"] == "2026-11-19"
    assert "occurredTime" not in trade and "occurredTimeZone" not in trade
