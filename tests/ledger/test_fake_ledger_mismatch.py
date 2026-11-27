"""Tests of a card whose total is not quantity times price, sent to the fake ledger.

The fake ledger does what the real ledger does since its dev 3f4223e
(2026-11-27): with cards taken, a card whose every cell is given and whose
only fault is its total is kept, not ready, nothing missing, and shows
``TOTAL_VALUE_MISMATCH`` on the total; with a sell of more than was held as
well, it is turned down whole. Saving it is refused and it stays pending;
saving another trade does not void it. Sent whole, with no cards taken,
such a trade is turned down. Every figure is invented.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ledger_hand.core.ledger_records import TradeFilter
from ledger_hand.core.proposals import CheckOutcome, ProposalStatus
from ledger_hand.core.trade import Side
from ledger_hand.ledger.demo_book import demo_ledger
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ports import LedgerError
from tests.ledger.test_cards_to_the_ledger import eth

# 0.1 ETH at 2600 USDT is 260, not 250.
OFF = {"total": Decimal("250")}


def taking() -> FakeLedger:
    return demo_ledger().taking_cards()


def test_a_whole_card_whose_total_does_not_agree_is_kept_not_ready() -> None:
    ledger = taking()

    (check,) = ledger.propose_cards((eth(**OFF),), "invented").checks

    assert check.outcome is CheckOutcome.PASSED
    assert check.ready is False and check.missing == ()
    assert check.problem is not None
    assert (check.problem.code, check.problem.field) == ("TOTAL_VALUE_MISMATCH", "totalValue")
    assert check.problem.category == "check-failed"
    assert check.proposal_id is not None
    status = ledger.proposal_status(check.proposal_id).status
    assert status is ProposalStatus.PENDING


def test_the_same_card_selling_more_than_held_is_turned_down_whole() -> None:
    ledger = taking()
    sell = eth(side=Side.SELL, quantity=Decimal("1000"), price=Decimal("2600"), total=Decimal("1"))

    (check,) = ledger.propose_cards((sell,), "invented").checks

    assert check.outcome is CheckOutcome.FAILED
    assert check.code == "TOTAL_VALUE_MISMATCH"
    assert check.message is not None and "more than was held" in check.message


def test_saving_it_is_refused_and_it_stays_pending_with_the_book_unchanged() -> None:
    ledger = taking()
    (check,) = ledger.propose_cards((eth(**OFF),), "invented").checks
    assert check.proposal_id is not None
    before = ledger.positions()

    with pytest.raises(LedgerError) as refused:
        ledger.save(check.proposal_id)

    assert refused.value.code == "TOTAL_VALUE_MISMATCH"
    assert ledger.proposal_status(check.proposal_id).status is ProposalStatus.PENDING
    assert ledger.positions() == before


def test_saving_another_trade_leaves_it_pending() -> None:
    ledger = taking()
    off, whole = ledger.propose_cards((eth(**OFF), eth()), "invented").checks
    assert off.proposal_id is not None and whole.proposal_id is not None
    assert whole.ready is True

    ledger.save(whole.proposal_id)

    assert ledger.proposal_status(whole.proposal_id).status is ProposalStatus.SAVED
    assert ledger.proposal_status(off.proposal_id).status is ProposalStatus.PENDING


def test_a_card_kept_whose_total_does_not_agree_changes_no_book_for_the_cards_after() -> None:
    ledger = taking()
    held = sum((row.quantity for row in ledger.positions() if row.asset == "ETH"), start=Decimal(0))
    buy_off = eth(quantity=Decimal("5"), total=Decimal("1"))
    sell = eth(side=Side.SELL, quantity=held + Decimal("1"), total=(held + 1) * Decimal("2600"))

    first, second = ledger.propose_cards((buy_off, sell), "invented").checks

    assert first.outcome is CheckOutcome.PASSED and first.ready is False
    assert second.outcome is CheckOutcome.FAILED


@pytest.mark.parametrize("way", ["add", "update"])
def test_sent_whole_with_no_cards_taken_it_is_turned_down(way: str) -> None:
    ledger = demo_ledger()
    facts = eth(**OFF).facts
    assert facts is not None

    if way == "add":
        (check,) = ledger.propose_add((facts,), "invented").checks
    else:
        trade = ledger.list_trades(TradeFilter()).trades[-1]
        (check,) = ledger.propose_update(trade.id, facts, "invented").checks

    assert check.outcome is CheckOutcome.FAILED
    assert check.code == "TOTAL_VALUE_MISMATCH"


def test_a_whole_card_that_agrees_is_still_taken_ready() -> None:
    (check,) = taking().propose_cards((eth(),), "invented").checks

    assert check.outcome is CheckOutcome.PASSED and check.ready is True
