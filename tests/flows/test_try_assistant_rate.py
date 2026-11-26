"""Tests of the try-out script on a trade paid in another money: its rate, its question.

The script runs with a scripted model and the demo ledger with a euro; no
model is called. Every sentence and figure is invented.
"""

from __future__ import annotations

import io

from ledger_hand.ledger.demo_euro import demo_ledger_with_euro
from scripts import try_assistant
from tests.fakes.routed_model import RoutedModel
from tests.flows.scripted_flow import row, screened, table
from tests.flows.test_paid_apart_examples import E1, E1_ROW, E16, E16_ROW, RECORD


def run(*sentences: str, cells: dict[str, str]) -> str:
    model = RoutedModel(
        tools=[RECORD], screen=[screened(("spot_trade", "KO"))], extraction=[table(row(**cells))]
    )
    out = io.StringIO()
    try_assistant.main(
        list(sentences),
        model=model,
        max_steps=6,
        ledger=demo_ledger_with_euro().taking_cards(),
        out=out,
    )
    return out.getvalue()


def test_the_rate_is_printed_under_the_trade_with_what_it_came_from() -> None:
    printed = run(E1, cells=E1_ROW)

    assert "at 64 EUR, total 128 EUR, fee 0.19 EUR" in printed
    assert (
        "    rate: 1.0859375 USD for 1 EUR, from the 69.5 USD a share said (2 × 69.5 ÷ 128); "
        "compared with: none in the ledger"
    ) in printed
    assert "without any FX fee" in printed


def test_the_question_of_the_price_in_dollars_is_named() -> None:
    printed = run(E16, cells=E16_ROW)

    assert "asked about: price-in-USD" in printed
    assert "How much was one share in USD?" in printed
