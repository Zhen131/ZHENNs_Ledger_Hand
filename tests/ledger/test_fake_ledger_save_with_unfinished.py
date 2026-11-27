"""Tests of saving one trade while a card with an empty cell waits in the fake ledger.

The real ledger saves the one proposal asked for and leaves a card with an
empty cell waiting as it was. The fake ledger does the same: saving a whole
card writes that one trade into the book and marks it saved; the card with
an empty cell stays pending, whether its only fault is the empty cell or
its three figures disagree as well. Every figure is invented.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ledger_hand.core.ledger_records import TradeFilter
from ledger_hand.core.proposals import ProposalStatus
from ledger_hand.ledger.demo_book import demo_ledger
from ledger_hand.ledger.fake_ledger import FakeLedger
from tests.ledger.test_cards_to_the_ledger import eth

DAY = TradeFilter(first_day=date(2026, 11, 24), last_day=date(2026, 11, 24), asset="ETH")

# A: no fee said. C: no fee said, and 0.1 ETH at 2600 USDT is 260, not 250.
UNFINISHED = {
    "no fee": {"fee": None, "fee_asset": None},
    "no fee and a total that does not agree": {
        "fee": None,
        "fee_asset": None,
        "total": Decimal("250"),
    },
}


def taking() -> FakeLedger:
    return demo_ledger().taking_cards()


def eth_on_the_day(ledger: FakeLedger) -> int:
    return len(ledger.list_trades(DAY).trades)


@pytest.mark.parametrize("unfinished", UNFINISHED.values(), ids=UNFINISHED.keys())
def test_saving_a_whole_card_leaves_the_unfinished_one_pending(
    unfinished: dict[str, object],
) -> None:
    ledger = taking()
    waiting, whole = ledger.propose_cards((eth(**unfinished), eth()), "invented").checks
    assert waiting.proposal_id is not None and whole.proposal_id is not None
    assert waiting.ready is False and whole.ready is True
    before = eth_on_the_day(ledger)

    ledger.save(whole.proposal_id)

    assert ledger.proposal_status(whole.proposal_id).status is ProposalStatus.SAVED
    assert ledger.proposal_status(waiting.proposal_id).status is ProposalStatus.PENDING
    assert eth_on_the_day(ledger) == before + 1
