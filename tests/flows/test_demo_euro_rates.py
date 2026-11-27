"""Tests of the demo ledger's made-up exchange rates, as the assistant page and the
try-out script use them.

The demo ledger with a euro has no tool for exchange rates unless it is
turned on (``listing_rates``), so every test written before keeps its
ledger; the page and the script turn it on (``demo_ledger_with_euro_rates``).
The demonstration sentence, two shares of KO for 128 euros at 69.5 dollars
a share, works out 1.0859375 and is not marked. A scripted model stands in
for every call. Every sentence and figure is invented.
"""

from __future__ import annotations

import io
from datetime import date

import pytest

from ledger_hand.core.ledger_rate import LedgerRateOutcome, RateRequest
from ledger_hand.core.marks import MarkKind
from ledger_hand.ledger.demo_euro import (
    DEMO_EURO_RATES,
    demo_ledger_with_euro,
    demo_ledger_with_euro_rates,
)
from ledger_hand.ledger.invented_book import INVENTED_NOW
from ledger_hand.ports import LedgerError
from scripts import try_assistant
from tests.fakes.routed_model import RoutedModel
from tests.flows.scripted_flow import row, screened, table
from tests.flows.test_paid_apart_examples import E1, E1_ROW, RECORD, mark_on, one, sent


def test_the_demo_ledger_with_a_euro_alone_has_no_tool_for_exchange_rates() -> None:
    request = RateRequest(
        currency_id="asset-eur",
        other_id="asset-usd",
        last_day=date(2026, 11, 24),
        enough_day=date(2026, 11, 24),
    )
    with pytest.raises(LedgerError) as caught:
        demo_ledger_with_euro().exchange_rates(request)

    assert caught.value.code == "NO_RATE_TOOL"


def test_its_made_up_rates_go_both_ways_on_different_days_none_after_its_today() -> None:
    directions = {(rate.base_code, rate.quote_code) for rate in DEMO_EURO_RATES}
    days = {rate.rate_date for rate in DEMO_EURO_RATES}

    assert directions == {("EUR", "USD"), ("USD", "EUR")}
    assert len(days) == 2
    assert all(date.fromisoformat(day) <= INVENTED_NOW.date() for day in days)


def test_the_demonstration_sentence_is_compared_with_the_ledgers_rate_and_not_marked() -> None:
    said = one(E1, E1_ROW, demo_ledger_with_euro_rates())
    (card,) = sent(said)

    assert said.recorded is not None
    note = said.recorded.marked[0].rate
    assert note is not None and note.ledger is not None
    assert note.ledger.outcome is LedgerRateOutcome.COMPARED and not note.ledger.far
    assert note.ledger.picked is not None and note.ledger.picked.row.source == "online"
    found = mark_on(card, "costRate")
    assert found is not None and found[0] != MarkKind.SUSPICIOUS.value
    assert "compared with the ledger's exchange rate of 2026-11-21 (frankfurter)" in said.reply
    assert "1 USD = 0.93 EUR" in said.reply
    assert "was not compared with one" not in said.reply


def test_the_try_out_script_uses_the_demo_ledger_with_its_rates_by_default() -> None:
    model = RoutedModel(
        tools=[RECORD], screen=[screened(("spot_trade", "KO"))], extraction=[table(row(**E1_ROW))]
    )
    out = io.StringIO()
    try_assistant.main([E1], model=model, max_steps=6, out=out)

    printed = out.getvalue()
    assert "compared with: the ledger's rate 1.0752688172 of 2026-11-21 (frankfurter)" in printed
