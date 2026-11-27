"""Tests of a card whose three figures do not agree, as the Assistant page draws it.

The page runs headless with the demo ledger taking cards, and a scripted
model. The three figures are drawn as said, each suspicious; under the card a
line says to put the figures right on the ledger's page before saving, and
the table's cell says the same, never "fill in" with nothing to fill. Every
sentence and figure is invented.
"""

from __future__ import annotations

from ledger_hand.ledger.demo_book import demo_ledger
from ledger_hand.ui.assistant_tables import IN_THE_LEDGER
from ledger_hand.ui.assistant_trade_cards import FIX_FIGURES, TO_FILL_IN, card_key, cell_key
from tests.ui.assistant_harness import texts_of
from tests.ui.test_page_assistant_empty_cells import SOL_200, SOL_200_ROW
from tests.ui.test_page_assistant_marks import said_on_page


def test_the_card_says_to_put_the_figures_right_and_shows_the_total_said() -> None:
    page = said_on_page(SOL_200, SOL_200_ROW, demo_ledger().taking_cards())

    assert texts_of(page, cell_key(1, 1, "Total"))[0] == "Total: 200 USDT"
    lines = texts_of(page, card_key(1, 1))
    assert lines[-1] == FIX_FIGURES
    assert not any(line.startswith(TO_FILL_IN) for line in lines)
    assert not page.exception


def test_the_table_says_to_fix_the_figures_not_to_fill_in_nothing() -> None:
    page = said_on_page(SOL_200, SOL_200_ROW, demo_ledger().taking_cards())

    (table,) = [one for one in page.dataframe if IN_THE_LEDGER in one.value.columns]
    (cell,) = list(table.value[IN_THE_LEDGER])
    assert cell.startswith("waiting (proposal-1); quantity × price does not match the total")
    assert "fill in" not in cell
