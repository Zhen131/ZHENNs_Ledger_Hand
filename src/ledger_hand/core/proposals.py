"""What the ledger says back to a proposal to record, change or delete trades.

A proposal never writes to the ledger: it waits there until the person
saves or rejects it on the ledger's own page. The ledger checks each trade
of a proposal as it comes in, and keeps each trade that passes as a
proposal of its own, with an identifier of its own: one call to record
three trades may leave two waiting and turn one down (the ledger's
``assistant-link/README.md``, "One proposal id per trade"). A trade that
fails the check is not an error: the answer says, for each trade in order,
either the identifier it waits under, or a fixed code and one plain
sentence (in the language of the ledger's page) why it was turned down.

- ``CheckOutcome``: passed or failed.
- ``TradeCheck``: the check of one trade, and its proposal's identifier
  when it passed. A trade sent with cells left empty (a card, the
  ledger's ``allowUnfinished``) that the ledger took also says whether it
  can be saved as it is, which cells are empty, and what the ledger's
  checks found in the cells given (``LedgerProblem``).
- ``LedgerProblem``: what the ledger's checks found in a card it took
  anyway: a fixed code, its kind, the ledger's sentence, and the cell.
- ``ProposalResult``: the checks of every trade of one call, in order.
- ``ProposalStatus``: where a kept proposal stands.
- ``ProposalState``: that, with the trade written when it was saved, and
  why it became void when it did.

Names defined here: ``TARGET_NOT_FOUND``, ``CheckOutcome``, ``LedgerProblem``, ``TradeCheck``,
``ProposalResult``, ``ProposalStatus`` and ``ProposalState``.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

# The code of a failed check that means the trade to change or delete is no
# longer in the ledger; the real ledger's own code, which every plug uses.
TARGET_NOT_FOUND = "PROPOSAL_TARGET_NOT_FOUND"


class CheckOutcome(enum.Enum):
    """Whether one trade of a proposal passed the ledger's check."""

    PASSED = "passed"
    FAILED = "failed"


def _is_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


@dataclass(frozen=True, kw_only=True)
class LedgerProblem:
    """What the ledger's checks found in the cells given of a card it took anyway.

    ``code`` is the ledger's fixed code (``INSUFFICIENT_HOLDINGS``),
    ``category`` its kind (``check-failed``), ``message`` its sentence, in
    the language of its page, carried as it came; ``field`` the cell, when
    the ledger names one.
    """

    code: str
    message: str
    category: str | None = None
    field: str | None = None

    def __post_init__(self) -> None:
        if not _is_text(self.code) or not _is_text(self.message):
            raise ValueError("a problem the ledger found has a code and a sentence, both text")


@dataclass(frozen=True, kw_only=True)
class TradeCheck:
    """The check of one trade: passed, waiting as ``proposal_id``; or failed, with a fixed
    code and a sentence.

    A card the ledger took also says, when it was sent so (``allowUnfinished``):
    ``ready``, whether it can be saved as it is; ``missing``, the ledger's
    names of the cells left empty, in the ledger's order; ``problem``, what
    the ledger's checks found in the cells given, or ``None``. ``ready`` is
    ``None`` for a trade sent the old way, which says none of it.
    """

    outcome: CheckOutcome
    proposal_id: str | None = None
    code: str | None = None
    message: str | None = None
    ready: bool | None = None
    missing: tuple[str, ...] = ()
    problem: LedgerProblem | None = None

    def __post_init__(self) -> None:
        self._require_card_fits()
        if not isinstance(self.outcome, CheckOutcome):
            raise TypeError(f"a check's outcome is a CheckOutcome, not {self.outcome!r}")
        said = (self.code, self.message)
        if self.outcome is CheckOutcome.PASSED:
            if said != (None, None):
                raise ValueError("a trade that passed has no code and no message")
            if not _is_text(self.proposal_id):
                raise ValueError("a trade that passed waits under an identifier, which is text")
        if self.outcome is CheckOutcome.FAILED:
            if not all(_is_text(part) for part in said):
                raise ValueError("a trade that failed has a code and a message, both text")
            if self.proposal_id is not None:
                raise ValueError("a trade that failed waits under no identifier")

    def _require_card_fits(self) -> None:
        """What a card's check says fits it: taken, and empty cells only when not ready."""
        if self.ready is None and (self.missing or self.problem is not None):
            raise ValueError("only a card sent with empty cells allowed says what is missing")
        if self.ready is not None and self.outcome is not CheckOutcome.PASSED:
            raise ValueError("only a card the ledger took says whether it can be saved")
        if self.ready is True and self.missing:
            raise ValueError("a card that can be saved as it is has no empty cell")


@dataclass(frozen=True, kw_only=True)
class ProposalResult:
    """The checks of a call's trades, in the order they were sent."""

    checks: tuple[TradeCheck, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.checks, tuple) or not self.checks:
            raise ValueError("a proposal's result holds a tuple of at least one check")
        if not all(isinstance(check, TradeCheck) for check in self.checks):
            raise TypeError("a proposal's checks are TradeCheck values")

    @property
    def all_passed(self) -> bool:
        """Whether every trade of the call passed the check."""
        return all(check.outcome is CheckOutcome.PASSED for check in self.checks)

    @property
    def none_passed(self) -> bool:
        """Whether no trade of the call passed the check: nothing waits in the ledger."""
        return all(check.outcome is CheckOutcome.FAILED for check in self.checks)

    @property
    def proposal_ids(self) -> tuple[str, ...]:
        """The identifiers of the trades that passed, in the order they were sent."""
        return tuple(check.proposal_id for check in self.checks if check.proposal_id is not None)


class ProposalStatus(enum.Enum):
    """Where a kept proposal stands."""

    PENDING = "pending"
    """It waits for the person to save or reject it."""
    SAVED = "saved"
    """The person saved it; the ledger has changed."""
    REJECTED = "rejected"
    """The person rejected it; the ledger has not changed."""
    VOID = "void"
    """It can no longer be saved: the ledger changed under it, or the page let it go."""


@dataclass(frozen=True, kw_only=True)
class ProposalState:
    """Where one proposal stands.

    ``trade_id`` is, once saved, the trade written (or deleted, for a
    deletion). ``reason`` and ``message`` say why it became void: a fixed
    code (such as ``ASSISTANT_DISCONNECTED``) and the ledger's sentence.
    """

    proposal_id: str
    status: ProposalStatus
    trade_id: str | None = None
    reason: str | None = None
    message: str | None = None

    def __post_init__(self) -> None:
        if not _is_text(self.proposal_id):
            raise ValueError("a proposal's identifier is text that is not blank")
        if not isinstance(self.status, ProposalStatus):
            raise TypeError(f"a proposal's status is a ProposalStatus, not {self.status!r}")
        if self.trade_id is not None and self.status is not ProposalStatus.SAVED:
            raise ValueError("only a saved proposal names the trade it wrote")
        if (self.reason, self.message) != (None, None) and self.status is not ProposalStatus.VOID:
            raise ValueError("only a void proposal says why it became void")
