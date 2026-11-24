"""The fake ledger's sums and holdings, worked out from a replay of its trades.

``period_summary`` sums the trades of a stretch of time: how many, and for
each money they were priced in what the buys spent, what the sells brought
in and the profit or loss of the sells (``moving_average`` works each one
out); the fees, one sum for each asset they were taken in. Money of two
kinds is never added together. ``positions`` gives each holding that is
not empty, with its profit or loss on paper at the market price the book
gives, or why it is not worked out (no market price, or a pool whose
figures are broken).

Names defined here: ``period_summary`` and ``positions``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal

from ledger_hand.core.arithmetic import round_half_up, working_context
from ledger_hand.core.ledger_records import (
    CurrencyTotals,
    Figure,
    MoneyAmount,
    NotWorkedOut,
    PeriodRequest,
    PeriodSummary,
    Position,
    TradeFacts,
)
from ledger_hand.core.trade import Side
from ledger_hand.ledger.moving_average import PLACES, Pool, Replay


def _in_period(facts: TradeFacts, request: PeriodRequest) -> bool:
    if request.start is not None and facts.occurred < request.start:
        return False
    if request.end is not None and facts.occurred >= request.end:
        return False
    return request.asset is None or facts.asset == request.asset


def period_summary(
    trades: Sequence[tuple[str, TradeFacts]], replayed: Replay, request: PeriodRequest
) -> PeriodSummary:
    """The sums of the trades ``request`` names; ``replayed`` holds each sell's profit or loss."""
    context = working_context()
    chosen = [(key, facts) for key, facts in trades if _in_period(facts, request)]
    spent: dict[str, Decimal] = {}
    received: dict[str, Decimal] = {}
    realized: dict[str, list[Figure]] = {}
    fees: dict[str, Decimal] = {}
    for key, facts in chosen:
        spent.setdefault(facts.quote, Decimal(0))
        received.setdefault(facts.quote, Decimal(0))
        realized.setdefault(facts.quote, [])
        if facts.side is Side.BUY:
            spent[facts.quote] = context.add(spent[facts.quote], facts.total)
        else:
            received[facts.quote] = context.add(received[facts.quote], facts.total)
            realized[facts.quote].append(replayed.realized[key])
        fees[facts.fee_asset] = context.add(fees.get(facts.fee_asset, Decimal(0)), facts.fee)
    return PeriodSummary(
        request=request,
        trade_count=len(chosen),
        by_currency=tuple(
            CurrencyTotals(
                currency=quote,
                spent=spent[quote],
                received=received[quote],
                realized=_added(quote, realized[quote]),
            )
            for quote in sorted(spent)
        ),
        fees=tuple(MoneyAmount(currency=asset, amount=fees[asset]) for asset in sorted(fees)),
    )


def _added(quote: str, figures: list[Figure]) -> Figure:
    """The figures added together, or the first reason one of them was not worked out."""
    context = working_context()
    total = Decimal(0)
    for figure in figures:
        if isinstance(figure, NotWorkedOut):
            return figure
        total = context.add(total, figure.amount)
    return MoneyAmount(currency=quote, amount=total)


def positions(replayed: Replay, prices: Mapping[tuple[str, str], Decimal]) -> tuple[Position, ...]:
    """Every holding that is not empty, in the order of asset and money."""
    return tuple(
        _position(pool, prices.get((pool.asset, pool.quote)))
        for _, pool in sorted(replayed.pools.items())
        if pool.quantity > 0
    )


def _position(pool: Pool, price: Decimal | None) -> Position:
    context = working_context()
    unrealized: Figure
    if pool.broken is not None:
        unrealized = NotWorkedOut(reason=pool.broken)
    elif price is None:
        unrealized = NotWorkedOut(
            reason=f"there is no market price for {pool.asset} in {pool.quote}"
        )
    else:
        worth = context.multiply(pool.quantity, price)
        amount = round_half_up(context.subtract(worth, pool.cost), PLACES)
        unrealized = MoneyAmount(currency=pool.quote, amount=amount)
    return Position(
        asset=pool.asset,
        quote=pool.quote,
        quantity=pool.quantity,
        cost=MoneyAmount(currency=pool.quote, amount=pool.cost),
        unrealized=unrealized,
    )
