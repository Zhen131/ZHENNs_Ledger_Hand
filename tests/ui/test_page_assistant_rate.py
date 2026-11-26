"""Tests of the card the Assistant page draws for a trade paid in another money than its own.

The page runs headless with the demo ledger with a euro, "now" its fixed
moment, and a scripted model. Two shares of KO, priced in US dollars,
bought for 128 euros at 69.5 dollars a share: the card shows the price and
total in euros, a rate cell after the fee with its mark and reason, and a
line with the price said in dollars. Every sentence and figure is invented.
"""

from __future__ import annotations

from streamlit.testing.v1 import AppTest

from ledger_hand.core.marks import MarkKind
from ledger_hand.ledger.demo_euro import demo_ledger_with_euro
from ledger_hand.ui.assistant_trade_cards import SAID_PRICE, TAGS, card_key, cell_key
from ledger_hand.ui.assistant_view import exchange_key
from tests.fakes.routed_model import RoutedModel
from tests.flows.scripted_flow import row, screened, table
from tests.flows.test_paid_apart_examples import E1, E1_ROW, RECORD
from tests.ui.assistant_harness import open_assistant, say_on_page, texts_of


def said_on_page() -> AppTest:
    model = RoutedModel(
        tools=[RECORD], screen=[screened(("spot_trade", "KO"))], extraction=[table(row(**E1_ROW))]
    )
    return say_on_page(open_assistant(model, ledger=demo_ledger_with_euro().taking_cards()), E1)


def markdown_of(page: AppTest, key: str) -> list[str]:
    return [str(one.value) for one in page.container(key=key).markdown]


def test_the_card_shows_the_euro_price_the_rate_and_the_dollar_price_said() -> None:
    page = said_on_page()

    assert texts_of(page, cell_key(1, 1, "Price"))[0] == "Price: 64 EUR"
    assert texts_of(page, cell_key(1, 1, "Total"))[0] == "Total: 128 EUR"
    rate = cell_key(1, 1, "Rate")
    assert texts_of(page, rate) == [
        "Rate: 1.0859375 USD for 1 EUR",
        "worked out from the 69.5 USD a share you said: 2 × 69.5 ÷ 128",
    ]
    assert markdown_of(page, rate) == [TAGS[MarkKind.COMPUTED]]
    assert f"{SAID_PRICE}69.5 USD a share" in texts_of(page, card_key(1, 1))


def test_the_reply_says_the_amount_paid_is_taken_without_any_fx_fee() -> None:
    page = said_on_page()

    reply = texts_of(page, exchange_key(1))[0]
    assert "without any FX fee" in reply
    assert "(USD for 1 EUR)" in reply
