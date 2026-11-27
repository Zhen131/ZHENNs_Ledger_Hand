"""Tests of three figures that do not agree, sent as said to a ledger that takes cards.

Since the product owner's rule of 2026-11-26 the quantity, the price and the
total are sent as said, all three marked suspicious, none left empty. The
ledger (dev 3f4223e and after) takes such a card, cannot save it, and says
``TOTAL_VALUE_MISMATCH``: the program then says its own fixed sentence, chosen
by that code alone, before the ledger's own words, whatever language they
are in. With a sell of more than was held as well, the ledger turns the card
down whole and the program says so; it never sends the card again with the
total left empty. A ledger that takes no cards is asked as before. Every
sentence and figure is invented.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ledger_hand.core.proposals import CheckOutcome, LedgerProblem, ProposalResult, TradeCheck
from ledger_hand.core.trade_card import TradeCard
from ledger_hand.flows.record_words import FIX_FIGURES_WORDS, MISMATCH_CODE
from ledger_hand.flows.recorded import RecordEnding
from ledger_hand.ledger.demo_book import (
    DEMO_ASSETS,
    DEMO_MARKET_PRICES,
    DEMO_TRADES,
    demo_ledger,
)
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ui.assistant_tables import IN_THE_LEDGER, proposed_rows
from tests.flows.scripted_flow import row
from tests.flows.test_cards_examples import SOL_200, card, one, talk

WORDS = "今天上午8:25花了200 USDT买入了0.094326个SOL，均价212.03 USDT，手续费0"
SAID_AS = "All three were sent as you said"

# The ledger's own sentence for the code, as its page says it in Chinese and in
# English, and joined with a second sentence (its README, "Unfinished trades").
CHINESE = "成交金额与数量 × 成交均价不一致"
ENGLISH = "The execution amount does not match quantity × average execution price"
JOINED = "成交金额与数量 × 成交均价不一致；卖出数量超过该时间点的可用持仓"


class SaysInOtherWords(FakeLedger):
    """The demo ledger taking cards, whose problem for a card is said in ``words``."""

    def __init__(self, words: str, code: str = MISMATCH_CODE) -> None:
        super().__init__(
            assets=DEMO_ASSETS,
            trades=DEMO_TRADES,
            prices=DEMO_MARKET_PRICES,
            takes_unfinished=True,
        )
        self.words = words
        self.code = code

    def propose_cards(self, cards: tuple[TradeCard, ...], said: str) -> ProposalResult:
        result = super().propose_cards(cards, said)
        return ProposalResult(checks=tuple(self._reworded(check) for check in result.checks))

    def _reworded(self, check: TradeCheck) -> TradeCheck:
        if check.problem is None:
            return check
        problem = LedgerProblem(
            code=self.code,
            message=self.words,
            category=check.problem.category,
            field=check.problem.field,
        )
        return TradeCheck(
            outcome=check.outcome,
            proposal_id=check.proposal_id,
            ready=check.ready,
            missing=check.missing,
            problem=problem,
        )


def test_the_three_figures_are_sent_as_said_none_empty_all_three_marked() -> None:
    said = one(WORDS, SOL_200)

    sent, marked = card(said)
    assert (sent.quantity, sent.price, sent.total) == (
        Decimal("0.094326"),
        Decimal("212.03"),
        Decimal("200"),
    )
    assert sent.missing == ()
    assert {mark.field for mark in sent.marks} >= {"quantity", "price", "totalValue"}
    assert SAID_AS in said.reply and "left empty" not in said.reply


@pytest.mark.parametrize("words", [CHINESE, ENGLISH, JOINED])
def test_the_programs_own_sentence_is_the_same_whatever_the_ledger_says(words: str) -> None:
    said = one(WORDS, SOL_200, SaysInOtherWords(words))

    sent, _ = card(said)
    recorded = said.recorded
    assert recorded is not None
    (check,) = recorded.checks
    assert (check.ready, check.missing) == (False, ())
    fixed = FIX_FIGURES_WORDS.format(number=1)
    ledgers = f"Trade 1: the ledger says: {words}"
    lines = said.reply.splitlines()
    assert lines.count(fixed) == 1 and lines.count(ledgers) == 1
    assert lines.index(fixed) + 1 == lines.index(ledgers)
    assert "fill in" not in said.reply and "with empty fields" not in said.reply
    (shown,) = proposed_rows(recorded.numbers, recorded.trades, recorded.checks)
    cell = shown[IN_THE_LEDGER]
    assert "fix the figures" in cell and "fill in" not in cell


def test_the_fixed_sentence_goes_by_the_code_never_by_the_words() -> None:
    said = one(WORDS, SOL_200, SaysInOtherWords(CHINESE, code="SOME_OTHER_CODE"))

    assert FIX_FIGURES_WORDS.format(number=1) not in said.reply
    assert f"Trade 1: the ledger says: {CHINESE}" in said.reply


def test_the_fixed_sentence_is_said_for_a_card_with_an_empty_cell_too() -> None:
    no_fee = SOL_200 | {"fee": ""}
    said = one("今天上午8:25花了200 USDT买入了0.094326个SOL，均价212.03 USDT", no_fee)

    recorded = said.recorded
    assert recorded is not None
    (check,) = recorded.checks
    assert check.problem is not None and check.problem.code == MISMATCH_CODE
    assert "with empty fields: fee, feeAssetId" in said.reply
    assert FIX_FIGURES_WORDS.format(number=1) in said.reply


def test_a_sell_of_more_than_held_as_well_is_turned_down_and_never_sent_again() -> None:
    cells = SOL_200 | {"side": "sell", "quantity": "1000个SOL", "total": "300 USDT"}
    (said,), ledger = talk("今天上午8:25卖了1000个SOL，均价212.03 USDT，一共300 USDT，手续费0",
                           rows=[row(**cells)])  # fmt: skip

    recorded = said.recorded
    assert recorded is not None and recorded.ending is RecordEnding.LEDGER_REFUSED
    (check,) = recorded.checks
    assert check.outcome is CheckOutcome.FAILED and check.code == MISMATCH_CODE
    assert check.message is not None and check.message in said.reply
    assert ledger.calls.count("propose_add") == 1
    (sent,) = recorded.trades
    assert sent.total == Decimal("300")


def test_a_ledger_that_takes_no_card_is_asked_as_before() -> None:
    said = one(WORDS, SOL_200, demo_ledger())

    assert said.recorded is not None
    assert said.recorded.ending is RecordEnding.ASKING
    assert said.reply == START_REPLY_OLD_LEDGER


# The reply to WORDS from a ledger that takes no cards, as the code before this
# change gave it (run on the start of this work, 2026-11-27).
START_REPLY_OLD_LEDGER = (
    "[Trade 1 of 1: quantity or price or total] Quantity times price does not match the total; "
    "which of the three is wrong, and what is its right value?\n"
    "Now: quantity 0.094326, price 212.03, total 200.\n"
    "Answer with the one that is wrong and its right value (such as 'price <value>'), or say "
    "the passage did not say it (such as 'price not said').\n"
    "Say 'skip' to leave this trade out, or 'cancel' to drop the whole passage."
)
