"""What the ledger says back to a proposal to record, change or delete trades.

A proposal never writes to the ledger: it waits there until the person
saves or rejects it on the ledger's own page. The ledger checks each trade
of a proposal as it comes in. A trade that fails the check is not an error:
the answer says, for each trade in order, whether it passed, and for one
that failed a fixed code and one plain English sentence. Whether a proposal
with a failed trade is still kept, and so gets an identifier, is for the
ledger behind the port to say, so the identifier may be missing.

- ``CheckOutcome``: passed or failed.
- ``TradeCheck``: the check of one trade.
- ``ProposalResult``: the checks of every trade of one proposal, and the
  proposal's identifier when the ledger kept it.
- ``ProposalStatus``: where a kept proposal stands.

Names defined here: ``CheckOutcome``, ``TradeCheck``, ``ProposalResult`` and
``ProposalStatus``.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass


class CheckOutcome(enum.Enum):
    """Whether one trade of a proposal passed the ledger's check."""

    PASSED = "passed"
    FAILED = "failed"


@dataclass(frozen=True, kw_only=True)
class TradeCheck:
    """The check of one trade: passed, or failed with a fixed code and a sentence."""

    outcome: CheckOutcome
    code: str | None = None
    message: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.outcome, CheckOutcome):
            raise TypeError(f"a check's outcome is a CheckOutcome, not {self.outcome!r}")
        said = (self.code, self.message)
        if self.outcome is CheckOutcome.PASSED and said != (None, None):
            raise ValueError("a trade that passed has no code and no message")
        if self.outcome is CheckOutcome.FAILED and not all(
            isinstance(part, str) and part.strip() for part in said
        ):
            raise ValueError("a trade that failed has a code and a message, both text")


@dataclass(frozen=True, kw_only=True)
class ProposalResult:
    """The checks of a proposal's trades, in order, and its identifier when it was kept."""

    checks: tuple[TradeCheck, ...]
    proposal_id: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.checks, tuple) or not self.checks:
            raise ValueError("a proposal's result holds a tuple of at least one check")
        if not all(isinstance(check, TradeCheck) for check in self.checks):
            raise TypeError("a proposal's checks are TradeCheck values")
        if self.proposal_id is not None and (
            not isinstance(self.proposal_id, str) or not self.proposal_id.strip()
        ):
            raise ValueError("a proposal's identifier is text that is not blank")

    @property
    def all_passed(self) -> bool:
        """Whether every trade of the proposal passed the check."""
        return all(check.outcome is CheckOutcome.PASSED for check in self.checks)


class ProposalStatus(enum.Enum):
    """Where a kept proposal stands."""

    PENDING = "pending"
    """It waits for the person to save or reject it."""
    SAVED = "saved"
    """The person saved it; the ledger has changed."""
    REJECTED = "rejected"
    """The person rejected it; the ledger has not changed."""
    VOID = "void"
    """It can no longer be saved: the ledger changed under it."""
