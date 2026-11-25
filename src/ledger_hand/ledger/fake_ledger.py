"""The fake ledger: a plug for the ledger port that keeps an invented book in memory.

``FakeLedger`` does all the ledger port promises, against the invented book
of ``invented_book`` unless it is handed another. It reads and writes no
file, reaches no network and never reads the clock. It is the stand-in the
assistant is built against first, and it stays for the tests and for a
demonstration that must not depend on the real ledger.

A proposal is checked as it comes in, trade by trade. A trade fails when an
asset it names (the asset, the money it is priced in, the fee's asset) is
not in the book, when the money it is priced in cannot price a trade, or
when, put in the book, it would make some sell take out more than was held
then; a change or a deletion fails on that last count too. When one trade
fails, the proposal is not kept and gets no identifier; when all pass, it
waits as pending, and the book does not change.

Two things the port does not offer are here for tests, the try-out
script and the assistant page's demo buttons: ``save`` a pending proposal
(only then does the book change, and every other pending proposal becomes
void, since it was checked against the book as it was) and ``reject`` one.
The page reaches them only through ``flows/standing.py``, which does
nothing with any other ledger; the assistant's model is never handed them.

Cost and profit are worked out the fake ledger's own way
(``moving_average``), which says nothing about the real ledger's way.

``failure``, when given, is raised by every call of the port, so that a test
can see what becomes of a ledger that fails. ``calls`` names every call of
the port made, in order.

Names defined here: ``FakeLedger``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

from ledger_hand.core.ledger_records import (
    Asset,
    LedgerTrade,
    PeriodRequest,
    PeriodSummary,
    Position,
    Pricing,
    TradeFacts,
    TradeFilter,
)
from ledger_hand.core.proposals import CheckOutcome, ProposalResult, ProposalStatus, TradeCheck
from ledger_hand.ledger.fake_sums import period_summary, positions
from ledger_hand.ledger.invented_book import (
    INVENTED_ASSETS,
    INVENTED_MARKET_PRICES,
    INVENTED_TRADES,
)
from ledger_hand.ledger.moving_average import replay
from ledger_hand.ports import LedgerError, LedgerErrorKind

type Book = tuple[tuple[str, TradeFacts], ...]

_PASSED = TradeCheck(outcome=CheckOutcome.PASSED)
_OVERSOLD = TradeCheck(
    outcome=CheckOutcome.FAILED,
    code="sells_more_than_held",
    message="With this, a sell would take out more than was held at the time.",
)


@dataclass
class _Proposal:
    status: ProposalStatus
    after: Book


class FakeLedger:
    """A ledger port that keeps an invented book in memory."""

    def __init__(
        self,
        *,
        assets: Sequence[Asset] = INVENTED_ASSETS,
        trades: Sequence[tuple[str, TradeFacts]] = INVENTED_TRADES,
        prices: Mapping[tuple[str, str], Decimal] = INVENTED_MARKET_PRICES,
        failure: LedgerError | None = None,
    ) -> None:
        self._assets = tuple(assets)
        self._trades: Book = tuple(trades)
        self._prices = dict(prices)
        self._failure = failure
        self._proposals: dict[str, _Proposal] = {}
        self._next_trade = len(self._trades) + 1
        self.calls: list[str] = []

    # --- the port -------------------------------------------------------------

    def list_assets(self) -> tuple[Asset, ...]:
        self._called("list_assets")
        return self._assets

    def list_trades(self, trade_filter: TradeFilter) -> tuple[LedgerTrade, ...]:
        self._called("list_trades")
        if trade_filter.asset is not None:
            self._known_asset(trade_filter.asset)
        realized = replay(self._trades).realized
        return tuple(
            LedgerTrade(id=key, facts=facts, realized=realized.get(key))
            for key, facts in sorted(self._trades, key=lambda pair: pair[1].occurred)
            if _matches(facts, trade_filter)
        )

    def period_summary(self, request: PeriodRequest) -> PeriodSummary:
        self._called("period_summary")
        if request.asset is not None:
            self._known_asset(request.asset)
        return period_summary(self._trades, replay(self._trades), request)

    def positions(self) -> tuple[Position, ...]:
        self._called("positions")
        return positions(replay(self._trades), self._prices)

    def propose_add(self, trades: tuple[TradeFacts, ...]) -> ProposalResult:
        self._called("propose_add")
        if not trades:
            raise ValueError("a proposal to record holds at least one trade")
        checks: list[TradeCheck] = []
        book = self._trades
        for facts in trades:
            added = (*book, (f"t-{self._next_trade + len(book) - len(self._trades):02d}", facts))
            check = self._checked(facts, added)
            checks.append(check)
            if check is _PASSED:
                book = added
        return self._kept(tuple(checks), book)

    def propose_update(self, trade_id: str, facts: TradeFacts) -> ProposalResult:
        self._called("propose_update")
        self._known_trade(trade_id)
        changed = tuple((key, facts if key == trade_id else old) for key, old in self._trades)
        return self._kept((self._checked(facts, changed),), changed)

    def propose_delete(self, trade_id: str) -> ProposalResult:
        self._called("propose_delete")
        self._known_trade(trade_id)
        left = tuple(pair for pair in self._trades if pair[0] != trade_id)
        check = _OVERSOLD if replay(left).oversold else _PASSED
        return self._kept((check,), left)

    def proposal_status(self, proposal_id: str) -> ProposalStatus:
        self._called("proposal_status")
        return self._proposal(proposal_id).status

    # --- outside the port: what the person does on the ledger's own page ------

    def save(self, proposal_id: str) -> None:
        """Save a pending proposal: the book changes, and every other pending one is void."""
        proposal = self._pending(proposal_id)
        self._next_trade += max(0, len(proposal.after) - len(self._trades))
        self._trades = proposal.after
        proposal.status = ProposalStatus.SAVED
        for other in self._proposals.values():
            if other.status is ProposalStatus.PENDING:
                other.status = ProposalStatus.VOID

    def reject(self, proposal_id: str) -> None:
        """Reject a pending proposal: the book stays as it is."""
        self._pending(proposal_id).status = ProposalStatus.REJECTED

    # --- inside ---------------------------------------------------------------

    def _called(self, name: str) -> None:
        self.calls.append(name)
        if self._failure is not None:
            raise self._failure

    def _known_asset(self, code: str) -> None:
        if code not in {asset.code for asset in self._assets}:
            raise LedgerError(
                LedgerErrorKind.UNKNOWN_ASSET, "unknown_asset", f"The ledger has no asset {code}."
            )

    def _known_trade(self, trade_id: str) -> None:
        if trade_id not in {key for key, _ in self._trades}:
            raise LedgerError(
                LedgerErrorKind.NOT_FOUND, "trade_not_found", f"The ledger has no trade {trade_id}."
            )

    def _proposal(self, proposal_id: str) -> _Proposal:
        if proposal_id not in self._proposals:
            raise LedgerError(
                LedgerErrorKind.NOT_FOUND,
                "proposal_not_found",
                f"The ledger has no proposal {proposal_id}.",
            )
        return self._proposals[proposal_id]

    def _pending(self, proposal_id: str) -> _Proposal:
        proposal = self._proposal(proposal_id)
        if proposal.status is not ProposalStatus.PENDING:
            raise LedgerError(
                LedgerErrorKind.OTHER,
                "proposal_not_pending",
                f"The proposal {proposal_id} is {proposal.status.value}, not pending.",
            )
        return proposal

    def _checked(self, facts: TradeFacts, book: Book) -> TradeCheck:
        """The check of one trade, as it would stand in ``book``."""
        codes = {asset.code: asset for asset in self._assets}
        for code in (facts.asset, facts.quote, facts.fee_asset):
            if code not in codes:
                return TradeCheck(
                    outcome=CheckOutcome.FAILED,
                    code="unknown_asset",
                    message=f"The ledger has no asset {code}.",
                )
        if codes[facts.quote].pricing is not Pricing.CAN_PRICE:
            return TradeCheck(
                outcome=CheckOutcome.FAILED,
                code="cannot_price",
                message=f"{facts.quote} cannot be the money a trade is priced in.",
            )
        return _OVERSOLD if replay(book).oversold else _PASSED

    def _kept(self, checks: tuple[TradeCheck, ...], after: Book) -> ProposalResult:
        """The result of a proposal; kept as pending, with an identifier, only when all passed."""
        if any(check.outcome is CheckOutcome.FAILED for check in checks):
            return ProposalResult(checks=checks, proposal_id=None)
        proposal_id = f"proposal-{len(self._proposals) + 1}"
        self._proposals[proposal_id] = _Proposal(status=ProposalStatus.PENDING, after=after)
        return ProposalResult(checks=checks, proposal_id=proposal_id)


def _matches(facts: TradeFacts, trade_filter: TradeFilter) -> bool:
    if trade_filter.start is not None and facts.occurred < trade_filter.start:
        return False
    if trade_filter.end is not None and facts.occurred >= trade_filter.end:
        return False
    if trade_filter.asset is not None and facts.asset != trade_filter.asset:
        return False
    return trade_filter.side is None or facts.side is trade_filter.side
