"""Tests of where a proposal stands, and of the demo ledger's save and reject.

The status is asked of the ledger each time; a ledger that cannot say is
said as such. Save and reject work on the demo ledger alone: with any other
ledger nothing is done. Every trade is invented.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from ledger_hand.core.ledger_records import TradeFacts, TradeFilter
from ledger_hand.core.proposals import ProposalState, ProposalStatus
from ledger_hand.core.trade import Side
from ledger_hand.flows.standing import (
    DemoOutcome,
    LedgerKind,
    demo_reject,
    demo_save,
    standing,
)
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ports import LedgerError, LedgerErrorKind

BUY = TradeFacts(
    occurred=datetime(2026, 11, 24, 9, 40, tzinfo=ZoneInfo("Europe/Budapest")),
    side=Side.BUY,
    asset="BTC",
    quantity=Decimal("0.02"),
    price=Decimal("94900"),
    total=Decimal("1898"),
    quote="USDT",
    fee=Decimal("2"),
    fee_asset="USDT",
    platform="Binance",
    note="",
    raw_text="invented",
    zone=None,
    date_only=False,
    cost_rate=None,
)


class NotTheDemo:
    """A ledger that is not the demo ledger: it only answers where a proposal stands."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def proposal_status(self, proposal_id: str) -> ProposalState:
        self.calls.append(proposal_id)
        return ProposalState(proposal_id=proposal_id, status=ProposalStatus.PENDING)


def proposed(ledger: FakeLedger) -> str:
    (proposal,) = ledger.propose_add((BUY,), "invented").proposal_ids
    return proposal


def test_the_one_kind_names_the_demo_ledger_as_invented() -> None:
    assert [kind.name for kind in LedgerKind] == ["DEMO"]
    assert "demo" in LedgerKind.DEMO.value
    assert "not your real ledger" in LedgerKind.DEMO.value


def test_a_pending_proposal_is_said_pending_then_saved_after_a_demo_save() -> None:
    ledger = FakeLedger()
    proposal = proposed(ledger)
    before = len(ledger.list_trades(TradeFilter()).trades)

    assert standing(ledger, proposal).status is ProposalStatus.PENDING
    done = demo_save(ledger, proposal)

    assert done.outcome is DemoOutcome.DONE
    assert standing(ledger, proposal).status is ProposalStatus.SAVED
    assert len(ledger.list_trades(TradeFilter()).trades) == before + 1


def test_a_demo_reject_leaves_the_book_as_it_was() -> None:
    ledger = FakeLedger()
    proposal = proposed(ledger)
    before = ledger.list_trades(TradeFilter()).trades

    assert demo_reject(ledger, proposal).outcome is DemoOutcome.DONE
    assert standing(ledger, proposal).status is ProposalStatus.REJECTED
    assert ledger.list_trades(TradeFilter()).trades == before


def test_an_unknown_proposal_is_said_as_the_ledgers_failure_not_as_a_status() -> None:
    now = standing(FakeLedger(), "proposal-9")

    assert now.status is None
    assert now.failure is not None and now.failure.kind is LedgerErrorKind.NOT_FOUND


def test_a_ledger_that_fails_is_said_as_failing() -> None:
    failure = LedgerError(LedgerErrorKind.UNREACHABLE, "unreachable", "Invented: no answer.")

    now = standing(FakeLedger(failure=failure), "proposal-1")

    assert now.status is None and now.failure is failure


def test_saving_what_is_no_longer_pending_is_the_ledgers_refusal() -> None:
    ledger = FakeLedger()
    proposal = proposed(ledger)
    demo_reject(ledger, proposal)

    done = demo_save(ledger, proposal)

    assert done.outcome is DemoOutcome.FAILED
    assert done.failure is not None and done.failure.code == "proposal_not_pending"


def test_with_any_other_ledger_save_and_reject_do_nothing() -> None:
    other = NotTheDemo()

    assert demo_save(other, "proposal-1").outcome is DemoOutcome.NOT_DEMO  # type: ignore[arg-type]
    assert demo_reject(other, "proposal-1").outcome is DemoOutcome.NOT_DEMO  # type: ignore[arg-type]
    assert other.calls == []
