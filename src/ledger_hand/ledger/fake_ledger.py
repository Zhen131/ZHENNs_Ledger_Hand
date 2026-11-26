"""The fake ledger: a plug for the ledger port that keeps an invented book in memory.

``FakeLedger`` does all the ledger port promises, against the invented book
of ``invented_book`` unless it is handed another. It reads and writes no
file, reaches no network and never reads the clock. It is the stand-in the
assistant is built against first, and it stays for the tests and for a
demonstration that must not depend on the real ledger.

It answers the way the real ledger's assistant link does (68B2, 2026-11-25):

- A call to record checks its trades one by one, each against the book as
  the trades before it that passed would leave it. Each trade that passes
  waits as a proposal of its own, with an identifier of its own; one that
  fails gets none, and the others still wait. A trade fails when an asset
  it names (the asset, the money it is priced in, the fee's asset) is not
  in the book, when that money cannot price a trade, or when, put in the
  book, it would make some sell take out more than was held then.
- A change or a deletion is one proposal; a trade not in the book fails
  its check with ``TARGET_NOT_FOUND``, as the real ledger answers.
- Trades are listed and summed by the day each falls on, on the clock of
  its own offset, both ends of a stretch counted; at most ``most_listed``
  of the latest are listed.

Two things the port does not offer are here for tests, the try-out
script and the assistant page's demo buttons: ``save`` a pending proposal
(only then does the book change) and ``reject`` one. Saving writes the
proposal's trade into the book as it stands then; every other pending
proposal that would no longer pass, or that changes or deletes the same
trade, becomes void, since it was checked against the book as it was. The
page reaches them only through ``flows/standing.py``, which does nothing
with any other ledger; the assistant's model is never handed them.

Cost and profit are worked out the fake ledger's own way
(``moving_average``), which says nothing about the real ledger's way.

Its market prices are the ones it is handed (``prices``, one amount for
each asset and money), each for the day ``prices_on``: by default the day
of the invented book's "now", 24 November 2026.

``failure``, when given, is raised by every call of the port, so that a test
can see what becomes of a ledger that fails; ``market_failure`` is raised
by the call for market prices alone. ``calls`` names every call of
the port made, in order; ``said`` keeps the words each proposal came with.

Names defined here: ``FakeLedger``.
"""

from __future__ import annotations

import enum
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from ledger_hand.core.ledger_records import (
    MOST_TRADES_LISTED,
    Asset,
    LedgerTrade,
    MarketPrice,
    MoneyAmount,
    PeriodRequest,
    PeriodSummary,
    Position,
    Pricing,
    TradeFacts,
    TradeFilter,
    TradeList,
)
from ledger_hand.core.proposals import (
    TARGET_NOT_FOUND,
    CheckOutcome,
    ProposalResult,
    ProposalState,
    ProposalStatus,
    TradeCheck,
)
from ledger_hand.ledger.fake_sums import period_summary, positions
from ledger_hand.ledger.invented_book import (
    INVENTED_ASSETS,
    INVENTED_MARKET_PRICES,
    INVENTED_NOW,
    INVENTED_TRADES,
)
from ledger_hand.ledger.moving_average import replay
from ledger_hand.ports import LedgerError, LedgerErrorKind

type Book = tuple[tuple[str, TradeFacts], ...]

# The day the invented book's market prices are for: that of its "now".
_INVENTED_DAY = INVENTED_NOW.date()

_OVERSOLD_CODE = "sells_more_than_held"
_OVERSOLD_WORDS = "With this, a sell would take out more than was held at the time."
_VOID_CODE = "TARGET_CHANGED"
_VOID_WORDS = "The ledger changed after this was sent, so it can no longer be saved."


class _Kind(enum.Enum):
    ADD = "add"
    UPDATE = "update"
    DELETE = "delete"


@dataclass
class _Proposal:
    kind: _Kind
    target: str | None
    facts: TradeFacts | None
    state: ProposalState


class FakeLedger:
    """A ledger port that keeps an invented book in memory."""

    def __init__(
        self,
        *,
        assets: Sequence[Asset] = INVENTED_ASSETS,
        trades: Sequence[tuple[str, TradeFacts]] = INVENTED_TRADES,
        prices: Mapping[tuple[str, str], Decimal] = INVENTED_MARKET_PRICES,
        failure: LedgerError | None = None,
        most_listed: int = MOST_TRADES_LISTED,
        prices_on: date | None = _INVENTED_DAY,
        market_failure: LedgerError | None = None,
    ) -> None:
        self._assets = tuple(assets)
        self._trades: Book = tuple(trades)
        self._prices = dict(prices)
        self._prices_on = prices_on
        self._market_failure = market_failure
        self._failure = failure
        self._most_listed = most_listed
        self._proposals: dict[str, _Proposal] = {}
        self._next_trade = len(self._trades) + 1
        self.calls: list[str] = []
        self.said: list[str] = []

    # --- the port -------------------------------------------------------------

    def list_assets(self) -> tuple[Asset, ...]:
        self._called("list_assets")
        return self._assets

    def list_trades(self, trade_filter: TradeFilter) -> TradeList:
        self._called("list_trades")
        if trade_filter.asset is not None:
            self._known_asset(trade_filter.asset)
        realized = replay(self._trades).realized
        found = tuple(
            LedgerTrade(
                id=key,
                facts=facts,
                realized=realized.get(key),
                realized_unreliable=None,
                dated_after_today=False,
            )
            for key, facts in sorted(self._trades, key=lambda pair: pair[1].occurred)
            if trade_filter.holds(facts)
        )
        cut = len(found) > self._most_listed
        return TradeList(trades=found[-self._most_listed :] if cut else found, cut=cut)

    def period_summary(self, request: PeriodRequest) -> PeriodSummary:
        self._called("period_summary")
        if request.asset is not None:
            self._known_asset(request.asset)
        return period_summary(self._trades, replay(self._trades), request)

    def positions(self) -> tuple[Position, ...]:
        self._called("positions")
        return positions(replay(self._trades), self._prices)

    def market_prices(self) -> tuple[MarketPrice, ...]:
        self._called("market_prices")
        if self._market_failure is not None:
            raise self._market_failure
        return tuple(
            MarketPrice(
                asset=asset,
                price=MoneyAmount(currency=money, amount=amount),
                day=self._prices_on,
            )
            for (asset, money), amount in sorted(self._prices.items())
        )

    def propose_add(self, trades: tuple[TradeFacts, ...], said: str) -> ProposalResult:
        self._called("propose_add", said)
        if not trades:
            raise ValueError("a proposal to record holds at least one trade")
        checks: list[TradeCheck] = []
        book = self._trades
        for number, facts in enumerate(trades, start=1):
            added = (*book, (f"proposed-{number}", facts))
            failed = self._failed(facts, added)
            if failed is not None:
                checks.append(failed)
                continue
            book = added
            checks.append(self._kept(_Kind.ADD, None, facts))
        return ProposalResult(checks=tuple(checks))

    def propose_update(self, trade_id: str, facts: TradeFacts, said: str) -> ProposalResult:
        self._called("propose_update", said)
        if trade_id not in self._keys():
            return ProposalResult(checks=(_not_found(trade_id),))
        changed = tuple((key, facts if key == trade_id else old) for key, old in self._trades)
        failed = self._failed(facts, changed)
        check = failed if failed is not None else self._kept(_Kind.UPDATE, trade_id, facts)
        return ProposalResult(checks=(check,))

    def propose_delete(self, trade_id: str, said: str) -> ProposalResult:
        self._called("propose_delete", said)
        if trade_id not in self._keys():
            return ProposalResult(checks=(_not_found(trade_id),))
        left = tuple(pair for pair in self._trades if pair[0] != trade_id)
        if replay(left).oversold:
            check = _failed_check(_OVERSOLD_CODE, _OVERSOLD_WORDS)
        else:
            check = self._kept(_Kind.DELETE, trade_id, None)
        return ProposalResult(checks=(check,))

    def proposal_status(self, proposal_id: str) -> ProposalState:
        self._called("proposal_status")
        return self._proposal(proposal_id).state

    # --- outside the port: what the person does on the ledger's own page ------

    def save(self, proposal_id: str) -> None:
        """Save a pending proposal: the book changes; pending ones it spoils become void."""
        proposal = self._pending(proposal_id)
        after = self._applied(proposal, self._trades)
        if after is None:
            proposal.state = _void(proposal_id)
            return
        book, written = after
        if proposal.kind is _Kind.ADD:
            self._next_trade += 1
        self._trades = book
        proposal.state = ProposalState(
            proposal_id=proposal_id, status=ProposalStatus.SAVED, trade_id=written
        )
        for key, other in self._proposals.items():
            if other.state.status is not ProposalStatus.PENDING:
                continue
            same_target = other.target is not None and other.target == proposal.target
            if same_target or self._applied(other, self._trades) is None:
                other.state = _void(key)

    def reject(self, proposal_id: str) -> None:
        """Reject a pending proposal: the book stays as it is."""
        self._pending(proposal_id)
        self._proposals[proposal_id].state = ProposalState(
            proposal_id=proposal_id, status=ProposalStatus.REJECTED
        )

    # --- inside ---------------------------------------------------------------

    def _called(self, name: str, said: str | None = None) -> None:
        self.calls.append(name)
        if said is not None:
            self.said.append(said)
        if self._failure is not None:
            raise self._failure

    def _keys(self) -> set[str]:
        return {key for key, _ in self._trades}

    def _known_asset(self, code: str) -> None:
        if code not in {asset.code for asset in self._assets}:
            raise LedgerError(
                LedgerErrorKind.UNKNOWN_ASSET, "unknown_asset", f"The ledger has no asset {code}."
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
        status = proposal.state.status
        if status is not ProposalStatus.PENDING:
            raise LedgerError(
                LedgerErrorKind.OTHER,
                "proposal_not_pending",
                f"The proposal {proposal_id} is {status.value}, not pending.",
            )
        return proposal

    def _failed(self, facts: TradeFacts, book: Book) -> TradeCheck | None:
        """Why one trade fails, as it would stand in ``book``; ``None`` when it passes."""
        codes = {asset.code: asset for asset in self._assets}
        for code in (facts.asset, facts.quote, facts.fee_asset):
            if code not in codes:
                return _failed_check("unknown_asset", f"The ledger has no asset {code}.")
        if codes[facts.quote].pricing is not Pricing.CAN_PRICE:
            return _failed_check(
                "cannot_price", f"{facts.quote} cannot be the money a trade is priced in."
            )
        if replay(book).oversold:
            return _failed_check(_OVERSOLD_CODE, _OVERSOLD_WORDS)
        return None

    def _kept(self, kind: _Kind, target: str | None, facts: TradeFacts | None) -> TradeCheck:
        """Keep one passed change as a pending proposal of its own; its check."""
        proposal_id = f"proposal-{len(self._proposals) + 1}"
        state = ProposalState(proposal_id=proposal_id, status=ProposalStatus.PENDING)
        self._proposals[proposal_id] = _Proposal(kind=kind, target=target, facts=facts, state=state)
        return TradeCheck(outcome=CheckOutcome.PASSED, proposal_id=proposal_id)

    def _applied(self, proposal: _Proposal, book: Book) -> tuple[Book, str] | None:
        """``book`` with the proposal's change in it, and the trade it writes; ``None`` when
        the change no longer fits the book. A new trade's key is the next one free."""
        if proposal.kind is _Kind.ADD:
            assert proposal.facts is not None
            key = f"t-{self._next_trade:02d}"
            added: Book = (*book, (key, proposal.facts))
            return None if self._failed(proposal.facts, added) is not None else (added, key)
        target = proposal.target
        assert target is not None
        if target not in {key for key, _ in book}:
            return None
        if proposal.kind is _Kind.DELETE:
            left = tuple(pair for pair in book if pair[0] != target)
            return None if replay(left).oversold else (left, target)
        facts = proposal.facts
        assert facts is not None
        changed = tuple((key, facts if key == target else old) for key, old in book)
        return None if self._failed(facts, changed) is not None else (changed, target)


def _failed_check(code: str, message: str) -> TradeCheck:
    return TradeCheck(outcome=CheckOutcome.FAILED, code=code, message=message)


def _not_found(trade_id: str) -> TradeCheck:
    return _failed_check(TARGET_NOT_FOUND, f"The ledger has no trade {trade_id}.")


def _void(proposal_id: str) -> ProposalState:
    return ProposalState(
        proposal_id=proposal_id, status=ProposalStatus.VOID, reason=_VOID_CODE, message=_VOID_WORDS
    )
