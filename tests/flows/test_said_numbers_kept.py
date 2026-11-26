"""Tests of the assistant keeping a number said in place of a figure it only rounds to.

The demo ledger, taking cards; "now" its fixed moment. Every sentence and
figure is invented: a total of 2500 said, worked out as 2500.0005 from 0.94
and 2659.575; a quantity of 0.0412959 said, worked out as 0.04129586 from
100 and 2421.55.
"""

from __future__ import annotations

from decimal import Decimal

from ledger_hand.core.marks import Field, MarkKind
from ledger_hand.extraction.issues import IssueKind
from ledger_hand.flows.progress import Setting
from ledger_hand.ledger.invented_book import INVENTED_NOW, INVENTED_ZONE
from tests.flows.test_cards_examples import card, mark_on, one

TOTAL_WORDS = "今天上午10点买了0.94个ETH，均价2659.575 USDT，总额2500 USDT，手续费0"
TOTAL_CELLS = {
    "side": "buy",
    "coin": "ETH",
    "quantity": "0.94个ETH",
    "price": "2659.575 USDT",
    "fee": "0",
    "time": "今天上午10点",
}
QUANTITY_WORDS = "今天上午10点花了100 USDT买了ETH，均价2421.55 USDT，我相当于买了0.0412959"
QUANTITY_CELLS = {
    "side": "buy",
    "coin": "ETH",
    "total": "100 USDT",
    "price": "2421.55 USDT",
    "time": "今天上午10点",
}


def left_over(said: object) -> tuple[str, ...]:
    recorded = said.recorded  # type: ignore[attr-defined]
    return tuple(
        number
        for issue in recorded.progress.issues
        if issue.kind is IssueKind.NUMBERS_LEFT_OVER
        for number in issue.numbers
    )


def test_a_total_worked_out_is_put_back_to_the_total_said_and_says_so() -> None:
    said = one(TOTAL_WORDS, TOTAL_CELLS)

    sent, marked = card(said)
    assert sent.total == Decimal("2500")
    total = mark_on(marked.marks, Field.TOTAL_VALUE)
    assert total.kind is MarkKind.COMPUTED
    assert total.reason == "worked out as 2500.0005, but you said 2500; your figure is kept"
    assert "2500" not in left_over(said)
    assert "2500" not in said.reply


def test_a_quantity_worked_out_on_a_card_is_put_back_to_the_quantity_said() -> None:
    said = one(QUANTITY_WORDS, QUANTITY_CELLS)

    sent, marked = card(said)
    assert sent.quantity == Decimal("0.0412959")
    assert sent.fee is None  # still a card, its fee empty
    quantity = mark_on(marked.marks, Field.QUANTITY)
    assert quantity.kind is MarkKind.COMPUTED and "0.0412959" in (quantity.reason or "")


def test_a_figure_the_model_copied_is_never_changed() -> None:
    cells = TOTAL_CELLS | {"total": "2500 USDT"}
    said = one(TOTAL_WORDS, cells)

    sent, marked = card(said)
    assert sent.total == Decimal("2500")
    assert marked.marks.on(Field.TOTAL_VALUE) is None  # nothing worked out, nothing marked


def test_a_number_said_too_far_off_leaves_the_figure_worked_out() -> None:
    words = "今天上午10点买了0.94个ETH，均价2659.575 USDT，大概2400 USDT，手续费0"
    said = one(words, TOTAL_CELLS)

    sent, marked = card(said)
    assert sent.total == Decimal("2500.0005")
    assert mark_on(marked.marks, Field.TOTAL_VALUE).reason == "worked out as quantity × price"
    assert "2400" in left_over(said)


def test_the_record_page_keeps_no_number_said_in_place_of_a_figure() -> None:
    assert Setting(INVENTED_NOW, INVENTED_ZONE, None).said_gap is None  # type: ignore[arg-type]
