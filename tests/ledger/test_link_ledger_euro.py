"""Tests of the real ledger's plug with a trade paid in another money, against written answers.

No running ledger was asked: each answer is a sample written from the
ledger's ``assistant-link/README.md`` and its own tests, and says so
(``_source``); the test names say "documented" for that reason. Every
figure is invented: two shares of KO, priced in US dollars, bought for 128
euros at a rate of 1.0859375.
"""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from ledger_hand.core.ledger_records import TradeFacts, TradeFilter
from ledger_hand.core.proposals import CheckOutcome
from ledger_hand.core.trade import Side
from tests.ledger.test_link_ledger import SAMPLES, plug, sample

_BUDAPEST = ZoneInfo("Europe/Budapest")
SAID = "今天15:30花了128欧元买了2股KO，一股69.5美元，换汇费0.19欧元"
EURO_ASSETS = ("list_assets", sample("list-assets-euro-documented"))
NAMES = (
    "list-assets-euro-documented",
    "list-assets-euro-older-documented",
    "propose-add-euro-rate-documented",
    "propose-add-euro-no-rate-documented",
    "list-trades-euro-rate-documented",
)


def paid_in_euros(rate: Decimal | None) -> TradeFacts:
    return TradeFacts(
        occurred=datetime(2026, 11, 24, 15, 30, tzinfo=_BUDAPEST),
        side=Side.BUY,
        asset="KO",
        quantity=Decimal(2),
        price=Decimal(64),
        total=Decimal(128),
        quote="EUR",
        fee=Decimal("0.19"),
        fee_asset="EUR",
        platform="",
        note="",
        raw_text=SAID,
        zone="Europe/Budapest",
        date_only=False,
        cost_rate=rate,
    )


def test_documented_euro_samples_say_they_were_written_not_captured() -> None:
    for name in NAMES:
        kept = json.loads((SAMPLES / f"{name}.json").read_text(encoding="utf-8"))
        assert "not captured" in kept["_source"], name


def test_documented_euro_asset_list_names_the_money_ko_is_priced_in() -> None:
    ledger, _ = plug(EURO_ASSETS)

    assets = {asset.code: asset for asset in ledger.list_assets()}

    assert assets["KO"].price_currency == "USD"
    assert assets["EUR"].price_currency is None


def test_documented_trade_paid_in_euros_goes_with_its_rate_and_is_taken() -> None:
    answer = ("propose_trade_add", sample("propose-add-euro-rate-documented"))
    ledger, link = plug(EURO_ASSETS, answer)

    result = ledger.propose_add((paid_in_euros(Decimal("1.0859375")),), SAID)

    (check,) = result.checks
    assert (check.outcome, check.proposal_id) == (CheckOutcome.PASSED, "proposal-eur-1")
    (sent,) = link.asked[-1][1]["trades"]
    assert (sent["quoteAssetId"], sent["costRate"]) == ("asset-eur", "1.0859375")
    assert (sent["price"], sent["totalValue"], sent["fee"]) == ("64", "128", "0.19")


def test_documented_trade_paid_in_euros_with_no_rate_is_not_sent_by_the_plug() -> None:
    ledger, link = plug(EURO_ASSETS)

    result = ledger.propose_add((paid_in_euros(None),), SAID)

    (check,) = result.checks
    assert (check.outcome, check.code) == (CheckOutcome.FAILED, "HAND_NEEDS_COST_RATE")
    assert [name for name, _ in link.asked] == ["list_assets"]


def test_documented_ledger_naming_no_own_money_turns_down_a_trade_with_no_rate() -> None:
    older = ("list_assets", sample("list-assets-euro-older-documented"))
    answer = ("propose_trade_add", sample("propose-add-euro-no-rate-documented"))
    ledger, link = plug(older, answer)

    result = ledger.propose_add((paid_in_euros(None),), SAID)

    (check,) = result.checks
    assert (check.outcome, check.code) == (CheckOutcome.FAILED, "CURRENCY_MISMATCH")
    (sent,) = link.asked[-1][1]["trades"]
    assert sent["costRate"] is None


def test_documented_trade_listed_with_its_rate_comes_back_with_it() -> None:
    answer = ("list_trades", sample("list-trades-euro-rate-documented"))
    ledger, _ = plug(EURO_ASSETS, answer)

    (trade,) = ledger.list_trades(TradeFilter(asset="KO")).trades

    assert (trade.facts.quote, trade.facts.cost_rate) == ("EUR", Decimal("1.0859"))
