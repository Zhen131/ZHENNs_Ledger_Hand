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

Made to (``takes_unfinished=True``, or ``taking_cards()`` on one made
already), it takes a trade with cells left empty, a card
(``propose_cards``), as the real ledger does since 2026-11-25 (72B). By
default it is a ledger from before, which takes none: every test and
measure written before then keeps the ledger it was written against, and
the demo ledger of the assistant page, the try-out script and the exam
book are made to take cards. A card whose every
cell is given is checked as a trade to record is, and turned down the
same way. A card with an empty cell is kept, cannot be saved, and says
which cells are empty (in the ledger's order) and what the cells given
show: a total that does not agree with quantity times price, or, when
the day, quantity, price, total and money used are all there, a sell of
more than was held (``INSUFFICIENT_HOLDINGS``); the holdings are not
checked otherwise (72B's revision 2). Marks are kept as they came and can
be read back (``marks_of``); they let nothing through and stop nothing.
Its marks are checked by the ledger's own rules, split as the ledger
splits them (72C1): an unknown cell or kind, or a reason longer than 256
UTF-16 units, refuses the whole call (``INVALID_ARGUMENTS``); a
suspicious mark with no reason, two marks on one cell, or a worked out or
assumed mark on an empty cell turns that card down alone. Saving a card
with an empty cell is refused, saying which cells, so no path writes an
unfinished trade into the book.

Its cash balances (``cash_balances``) are one of three kinds, chosen when
it is made (decided on 2026-11-26). By default it has no tool to read them,
as an older ledger has none: asked, it raises ``NO_CASH_TOOL`` and names no
call, so that every test written before then keeps the calls it counts.
Handed ``cash``, it hands back those balances as they are, as the real
ledger hands its own: one row for each cash asset of its list, in that
list's order, 0 for one not named; trades change nothing. Handed
``opening_cash``, each balance is that opening amount moved by every trade
in the book, the ledger's way (its ``tradeCashImpact.ts``): a buy takes
its total and a fee paid in the same money out, a sell brings its total
in less such a fee; a fee paid in any other asset moves no cash. For
example, 250000 USDT, then a buy of 1 BTC for 58000 USDT with a fee of 58
USDT: 191942 USDT. So a trade saved on the demo ledger shows in the
balances next asked for. They are counted up to the later of its market
prices' day and its latest trade's day.

``failure``, when given, is raised by every call of the port, so that a test
can see what becomes of a ledger that fails; ``market_failure`` is raised
by the call for market prices alone. ``calls`` names every call of
the port made, in order; ``said`` keeps the words each proposal came with.
A proposal of cards is named ``propose_add`` there, as the ledger's one
tool to record is (``propose_trade_add``), and one whose every card is
whole is made through ``propose_add`` itself; asking whether the ledger
takes cards asks nothing of the book and is not named.

Names defined here: ``FakeLedger``.
"""

from __future__ import annotations

import enum
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from ledger_hand.core.ledger_limits import text_length
from ledger_hand.core.ledger_records import (
    MOST_TRADES_LISTED,
    NO_CASH_TOOL,
    Asset,
    AssetKind,
    CashBalance,
    CashBalances,
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
from ledger_hand.core.marks import Field, MarkKind, SentMark
from ledger_hand.core.proposals import (
    TARGET_NOT_FOUND,
    CheckOutcome,
    LedgerProblem,
    ProposalResult,
    ProposalState,
    ProposalStatus,
    TradeCheck,
)
from ledger_hand.core.trade import Side
from ledger_hand.core.trade_card import TradeCard
from ledger_hand.core.validation import amounts_agree
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
_BAD_ARGUMENTS = "INVALID_ARGUMENTS"
_HOLDINGS_CODE = "INSUFFICIENT_HOLDINGS"
_MISMATCH_CODE = "TOTAL_VALUE_MISMATCH"
_MISMATCH_WORDS = "The total is not quantity times price."
_UNFINISHED_CODE = "PROPOSAL_UNFINISHED"
# The ledger's FIELD_MARK_REASON_MAX_LENGTH, in UTF-16 units.
_REASON_MOST = 256
_FIELDS = frozenset(field.value for field in Field)
_KINDS = frozenset(kind.value for kind in MarkKind)
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
    card: TradeCard | None = None


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
        takes_unfinished: bool = False,
        cash: Mapping[str, Decimal] | None = None,
        opening_cash: Mapping[str, Decimal] | None = None,
    ) -> None:
        if cash is not None and opening_cash is not None:
            raise ValueError("cash balances are given as they are, or as opening amounts, not both")
        held = {asset.code for asset in assets if asset.kind is AssetKind.CASH}
        for code in (*(cash or {}), *(opening_cash or {})):
            if code not in held:
                raise ValueError(f"{code} is not a cash asset of this ledger")
        self._cash = dict(cash) if cash is not None else None
        self._opening_cash = dict(opening_cash) if opening_cash is not None else None
        self._takes_unfinished = takes_unfinished
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

    def cash_balances(self) -> CashBalances:
        if self._cash is None and self._opening_cash is None:
            # A ledger with no such tool: not a call it answered, so not named.
            raise LedgerError(
                LedgerErrorKind.OTHER, NO_CASH_TOOL, "This ledger has no tool for cash balances."
            )
        self._called("cash_balances")
        if self._cash is not None:
            amounts = self._cash
        else:
            assert self._opening_cash is not None
            amounts = _moved_by(self._opening_cash, self._trades)
        rows = tuple(
            CashBalance(
                code=asset.code, name=asset.name, balance=amounts.get(asset.code, Decimal(0))
            )
            for asset in self._assets
            if asset.kind is AssetKind.CASH
        )
        days = [facts.day for _, facts in self._trades]
        if self._prices_on is not None:
            days.append(self._prices_on)
        return CashBalances(day=max(days, default=_INVENTED_DAY), balances=rows)

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

    def takes_unfinished(self) -> bool:
        return self._takes_unfinished

    def taking_cards(self) -> FakeLedger:
        """This same ledger, from now on one that takes cards, as the real ledger does now."""
        self._takes_unfinished = True
        return self

    def propose_cards(self, cards: tuple[TradeCard, ...], said: str) -> ProposalResult:
        if not cards:
            raise ValueError("a proposal to record holds at least one card")
        if not self._takes_unfinished:
            self._called("propose_add", said)
            raise LedgerError(
                LedgerErrorKind.OTHER,
                _BAD_ARGUMENTS,
                "This ledger does not take allowUnfinished or fieldMarks.",
            )
        whole = _whole_call_refusal(cards)
        if whole is not None:
            self._called("propose_add", said)
            raise LedgerError(LedgerErrorKind.OTHER, _BAD_ARGUMENTS, whole)
        if all(card.complete and _card_refusal(card) is None for card in cards):
            facts = tuple(card.facts for card in cards if card.facts is not None)
            result = self.propose_add(facts, said)
            return ProposalResult(
                checks=tuple(
                    self._as_card(check, card)
                    for check, card in zip(result.checks, cards, strict=True)
                )
            )
        self._called("propose_add", said)
        return ProposalResult(checks=self._cards_checked(cards))

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

    def marks_of(self, proposal_id: str) -> tuple[SentMark, ...]:
        """The marks a card waiting as ``proposal_id`` came with, as they came."""
        card = self._proposal(proposal_id).card
        return card.marks if card is not None else ()

    def card_of(self, proposal_id: str) -> TradeCard | None:
        """The card waiting as ``proposal_id``, as it came; ``None`` for a trade sent whole."""
        return self._proposal(proposal_id).card

    def save(self, proposal_id: str) -> None:
        """Save a pending proposal: the book changes; pending ones it spoils become void.

        A card with an empty cell is never saved: it is refused, naming the
        cells, as the ledger's page refuses it (72B, scene F).
        """
        proposal = self._pending(proposal_id)
        card = proposal.card
        if card is not None and not card.complete:
            raise LedgerError(
                LedgerErrorKind.OTHER,
                _UNFINISHED_CODE,
                f"This trade cannot be saved yet: fill in {', '.join(card.missing)} first.",
            )
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

    def _kept(
        self,
        kind: _Kind,
        target: str | None,
        facts: TradeFacts | None,
        card: TradeCard | None = None,
    ) -> TradeCheck:
        """Keep one passed change as a pending proposal of its own; its check."""
        proposal_id = f"proposal-{len(self._proposals) + 1}"
        state = ProposalState(proposal_id=proposal_id, status=ProposalStatus.PENDING)
        self._proposals[proposal_id] = _Proposal(
            kind=kind, target=target, facts=facts, state=state, card=card
        )
        return TradeCheck(outcome=CheckOutcome.PASSED, proposal_id=proposal_id)

    def _as_card(self, check: TradeCheck, card: TradeCard) -> TradeCheck:
        """A whole card's check as one sent with cards allowed: ready, nothing missing."""
        if check.outcome is not CheckOutcome.PASSED or check.proposal_id is None:
            return check
        self._proposals[check.proposal_id].card = card
        return TradeCheck(
            outcome=CheckOutcome.PASSED, proposal_id=check.proposal_id, ready=True, missing=()
        )

    def _cards_checked(self, cards: tuple[TradeCard, ...]) -> tuple[TradeCheck, ...]:
        """Each card checked against the book as the whole cards before it that passed leave it.

        A card with an empty cell never changes that book: the ones after
        it may not lean on it (72B's revision 2).
        """
        checks: list[TradeCheck] = []
        book = self._trades
        for number, card in enumerate(cards, start=1):
            refusal = _card_refusal(card)
            if refusal is not None:
                checks.append(_failed_check(_BAD_ARGUMENTS, refusal))
                continue
            facts = card.facts
            if facts is not None:
                added = (*book, (f"proposed-{number}", facts))
                failed = self._failed(facts, added)
                if failed is not None:
                    checks.append(failed)
                    continue
                book = added
                kept = self._kept(_Kind.ADD, None, facts, card)
                checks.append(self._as_card(kept, card))
                continue
            unknown = self._unknown_code(card)
            if unknown is not None:
                checks.append(unknown)
                continue
            kept = self._kept(_Kind.ADD, None, None, card)
            assert kept.proposal_id is not None
            checks.append(
                TradeCheck(
                    outcome=CheckOutcome.PASSED,
                    proposal_id=kept.proposal_id,
                    ready=False,
                    missing=card.missing,
                    problem=self._problem(card, book, number),
                )
            )
        return tuple(checks)

    def _unknown_code(self, card: TradeCard) -> TradeCheck | None:
        """Why a card with an empty cell is turned down: an asset the book lacks, or a money
        that prices nothing; ``None`` when it is taken."""
        codes = {asset.code: asset for asset in self._assets}
        for code in (card.asset, card.quote, card.fee_asset):
            if code is not None and code not in codes:
                return _failed_check("unknown_asset", f"The ledger has no asset {code}.")
        if card.quote is not None and codes[card.quote].pricing is not Pricing.CAN_PRICE:
            return _failed_check(
                "cannot_price", f"{card.quote} cannot be the money a trade is priced in."
            )
        return None

    def _problem(self, card: TradeCard, book: Book, number: int) -> LedgerProblem | None:
        """What the cells given of a card with an empty cell show, or ``None``.

        The total against quantity times price when all three are there;
        the holdings only when the day, the amounts and the money are.
        """
        quantity, price, total = card.quantity, card.price, card.total
        three = quantity is not None and price is not None and total is not None
        if three and not amounts_agree(quantity, price, total):  # type: ignore[arg-type]
            return LedgerProblem(
                code=_MISMATCH_CODE,
                category="check-failed",
                message=_MISMATCH_WORDS,
                field="totalValue",
            )
        if (
            card.occurred is None
            or quantity is None
            or price is None
            or total is None
            or card.quote is None
        ):
            return None
        facts = TradeFacts(
            occurred=card.occurred,
            side=card.side,
            asset=card.asset,
            quantity=quantity,
            price=price,
            total=total,
            quote=card.quote,
            fee=Decimal(0),
            fee_asset=card.quote,
            platform=card.platform,
            note=card.note,
            raw_text=card.raw_text,
            zone=card.zone,
            date_only=card.date_only,
            cost_rate=card.cost_rate,
        )
        if replay((*book, (f"proposed-{number}", facts))).oversold:
            return LedgerProblem(
                code=_HOLDINGS_CODE,
                category="check-failed",
                message=_OVERSOLD_WORDS,
                field="quantity",
            )
        return None

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


def _moved_by(opening: Mapping[str, Decimal], book: Book) -> dict[str, Decimal]:
    """Each opening amount moved by every trade of ``book``, the ledger's way.

    A buy takes its total out of the money it used, and its fee when paid
    in that same money; a sell brings its total in, less such a fee. A fee
    paid in any other asset moves no cash.
    """
    moved = dict(opening)
    for _, facts in book:
        fee = facts.fee if facts.fee_asset == facts.quote else Decimal(0)
        change = -(facts.total + fee) if facts.side is Side.BUY else facts.total - fee
        moved[facts.quote] = moved.get(facts.quote, Decimal(0)) + change
    return moved


def _whole_call_refusal(cards: tuple[TradeCard, ...]) -> str | None:
    """Why the ledger refuses a whole call for its marks, or ``None``: an unknown cell or
    kind, or a reason longer than the ledger takes (72C1)."""
    for number, card in enumerate(cards, start=1):
        for place, mark in enumerate(card.marks, start=1):
            where = f"trades[{number}].fieldMarks[{place}]"
            if mark.field not in _FIELDS:
                return f"{where}.field is not a field a mark can be on."
            if mark.kind not in _KINDS:
                return f"{where}.kind is not computed, inferred or suspicious."
            if mark.reason is not None and text_length(mark.reason) > _REASON_MOST:
                return f"{where}.reason is longer than {_REASON_MOST} characters."
    return None


def _card_refusal(card: TradeCard) -> str | None:
    """Why the ledger turns one card down for its marks, or ``None``: a suspicious mark with
    no reason, two marks on one cell, or a worked out or assumed mark on an empty cell."""
    seen: set[str] = set()
    empty = set(card.missing)
    for place, mark in enumerate(card.marks, start=1):
        if mark.field in seen:
            return f"fieldMarks[{place}]: a field carries one mark at most."
        seen.add(mark.field)
        blank = mark.reason is None or not mark.reason.strip()
        if mark.kind == MarkKind.SUSPICIOUS.value and blank:
            return f"fieldMarks[{place}].reason: a suspicious mark says why."
        if mark.field in empty and mark.kind != MarkKind.SUSPICIOUS.value:
            return f"fieldMarks[{place}]: an empty field can only be suspicious."
    return None


def _failed_check(code: str, message: str) -> TradeCheck:
    return TradeCheck(outcome=CheckOutcome.FAILED, code=code, message=message)


def _not_found(trade_id: str) -> TradeCheck:
    return _failed_check(TARGET_NOT_FOUND, f"The ledger has no trade {trade_id}.")


def _void(proposal_id: str) -> ProposalState:
    return ProposalState(
        proposal_id=proposal_id, status=ProposalStatus.VOID, reason=_VOID_CODE, message=_VOID_WORDS
    )
