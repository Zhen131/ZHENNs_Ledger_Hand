"""Where a proposal stands, and the demo ledger's save and reject, for the assistant page.

The assistant page shows one card for every proposal sent in its chat. It
does not reach the ledger itself: it hands each card's identifier here and
draws what comes back.

- ``LedgerKind`` names which kind of ledger the parts hold. There is one
  so far, the demo ledger (``ledger/fake_ledger.py``: an invented book in
  memory). The page reads it to know whether the demo buttons may be shown;
  it never guesses from the ledger itself.
- ``standing`` asks the ledger where one proposal stands
  (``proposal_status``). A ledger that cannot say is said as such
  (``Standing.failure``), never as the last status seen.
- ``demo_save`` and ``demo_reject`` do on the demo ledger what the person
  does on the real ledger's own page. They work on the demo ledger alone:
  for any other ledger they do nothing and say so (``DemoOutcome.NOT_DEMO``),
  so no button can write into a real ledger from here. A proposal that is
  not pending, or not known, is said by the ledger's own failure.

This module reads no clock, no zone and no settings.

Names defined here: ``LedgerKind``, ``Standing``, ``DemoOutcome``,
``DemoDone``, ``standing``, ``demo_save`` and ``demo_reject``.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

from ledger_hand.core.proposals import ProposalState, ProposalStatus
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ports import LedgerError, LedgerPort


class LedgerKind(enum.Enum):
    """Which kind of ledger the parts hold."""

    DEMO = "the demo ledger (an invented book in memory, not your real ledger)"


@dataclass(frozen=True, kw_only=True)
class Standing:
    """Where one proposal stands: its status, or the ledger's failure when it could not say.

    ``state`` is all the ledger said: the trade a saved proposal wrote, why a
    void one became void.
    """

    proposal: str
    status: ProposalStatus | None = None
    state: ProposalState | None = None
    failure: LedgerError | None = None


class DemoOutcome(enum.Enum):
    """What came of a demo save or reject."""

    DONE = "done"
    NOT_DEMO = "not the demo ledger, so nothing was done"
    FAILED = "the ledger said no"


@dataclass(frozen=True, kw_only=True)
class DemoDone:
    """What came of a demo save or reject, and the ledger's failure when it said no."""

    outcome: DemoOutcome
    failure: LedgerError | None = None


def standing(ledger: LedgerPort, proposal: str) -> Standing:
    """Where ``proposal`` stands, asked of ``ledger`` now."""
    try:
        state = ledger.proposal_status(proposal)
    except LedgerError as error:
        return Standing(proposal=proposal, failure=error)
    return Standing(proposal=proposal, status=state.status, state=state)


def demo_save(ledger: LedgerPort, proposal: str) -> DemoDone:
    """Save ``proposal`` in the demo ledger, as the person would on the ledger's own page."""
    if not isinstance(ledger, FakeLedger):
        return DemoDone(outcome=DemoOutcome.NOT_DEMO)
    try:
        ledger.save(proposal)
    except LedgerError as error:
        return DemoDone(outcome=DemoOutcome.FAILED, failure=error)
    return DemoDone(outcome=DemoOutcome.DONE)


def demo_reject(ledger: LedgerPort, proposal: str) -> DemoDone:
    """Reject ``proposal`` in the demo ledger, as the person would on the ledger's own page."""
    if not isinstance(ledger, FakeLedger):
        return DemoDone(outcome=DemoOutcome.NOT_DEMO)
    try:
        ledger.reject(proposal)
    except LedgerError as error:
        return DemoDone(outcome=DemoOutcome.FAILED, failure=error)
    return DemoDone(outcome=DemoOutcome.DONE)
