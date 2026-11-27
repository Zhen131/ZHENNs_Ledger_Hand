"""Tests of a card sent with cells left empty, as the Assistant page draws it.

The page runs headless with the demo ledger taking cards, as the real
ledger does now, and a scripted model. A cell left empty reads ``none``,
the card says which cells to fill in on the ledger's page, and three
figures that do not agree show three suspicious cells, the total as said.
Nothing on the card can change the trade. Every sentence and figure is
invented.
"""

from __future__ import annotations

from ledger_hand.core.marks import MarkKind
from ledger_hand.ledger.demo_book import demo_ledger
from ledger_hand.ui.assistant_tables import IN_THE_LEDGER
from ledger_hand.ui.assistant_trade_cards import (
    SUSPICIOUS_TAG,
    TAGS,
    TO_FILL_IN,
    card_key,
    cell_key,
)
from tests.flows.scripted_flow import row
from tests.ui.assistant_harness import texts_of
from tests.ui.test_page_assistant_marks import markdown_of, said_on_page

NO_FEE = "今天上午10点买了0.1个ETH，价格2600 USDT"
NO_FEE_ROW = row(
    side="buy", coin="ETH", quantity="0.1个ETH", price="2600 USDT", time="今天上午10点"
)
SOL_200 = "今天上午8:25花了200 USDT买入了0.094326个SOL，均价212.03 USDT，手续费0"
SOL_200_ROW = row(
    side="buy",
    coin="SOL",
    quantity="0.094326个SOL",
    price="212.03 USDT",
    total="200 USDT",
    fee="0",
    time="今天上午8:25",
)


def test_a_fee_not_said_shows_none_and_what_to_fill_in() -> None:
    page = said_on_page(NO_FEE, NO_FEE_ROW, demo_ledger().taking_cards())

    assert texts_of(page, cell_key(1, 1, "Fee")) == ["Fee: none none"]
    lines = texts_of(page, card_key(1, 1))
    assert lines[-1] == TO_FILL_IN + "fee, feeAssetId"
    reply = texts_of(page, "assistant_exchange_1")[0]
    assert "with empty fields: fee, feeAssetId" in reply
    card = page.container(key=card_key(1, 1))
    for kind in ("text_input", "number_input", "selectbox", "text_area", "button", "checkbox"):
        assert len(getattr(card, kind)) == 0, kind
    assert not page.exception


def test_the_table_of_what_was_sent_says_the_card_waits_to_be_filled_in() -> None:
    page = said_on_page(NO_FEE, NO_FEE_ROW, demo_ledger().taking_cards())

    (table,) = [one for one in page.dataframe if IN_THE_LEDGER in one.value.columns]
    (cell,) = list(table.value[IN_THE_LEDGER])
    assert cell.startswith("waiting (proposal-1); fill in fee, feeAssetId")


def test_three_figures_that_disagree_show_three_suspicious_cells_and_the_total_said() -> None:
    page = said_on_page(SOL_200, SOL_200_ROW, demo_ledger().taking_cards())

    for label in ("Quantity", "Price", "Total"):
        assert markdown_of(page, cell_key(1, 1, label)) == [SUSPICIOUS_TAG], label
    total = texts_of(page, cell_key(1, 1, "Total"))
    assert total[0] == "Total: 200 USDT"
    assert "200 USDT" in total[1] and "does not guess which is wrong" in total[1]
    assert TAGS[MarkKind.SUSPICIOUS] == SUSPICIOUS_TAG
