"""What a read tool found, kept as the ledger gave it, and laid out as a header and a table.

The program, not the model, lays out what the ledger hands back for a read
tool. A ``Lookup`` keeps it as it came: the trades, the sums of a stretch of
time, the holdings or the assets, every figure the ledger's own value; and,
for the two tools that are narrowed, the ``Conditions`` the ledger was
actually asked with: the days, the asset and the side, and a sentence for
each thing the model asked for that was not used. Nothing here adds,
rounds or converts a figure, and money of two kinds is never added
together.

``lookup_lines`` lays a lookup out as plain lines, the header first: the
script prints them, and they are what the model's explanation is checked
against (``explanation``). A figure is written out in full, as the ledger
holds it; how a screen shows it (thousands marks, places) is the screen's
business.

A list of trades longer than ``MOST_TRADES_SHOWN`` shows only the latest
ones, in time order, and says how many there are in all.

Names defined here: ``MOST_TRADES_SHOWN``, ``Conditions``, ``Lookup``,
``latest_trades`` and ``lookup_lines``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from ledger_hand.assistant.tools import ToolName
from ledger_hand.core.ledger_records import (
    Asset,
    Figure,
    LedgerTrade,
    MoneyAmount,
    PeriodSummary,
    Position,
)
from ledger_hand.core.time_range import Period
from ledger_hand.core.trade import Side

# A list in a chat is read at a glance; twenty trades is about one screen,
# and keeps what is handed to the model short. This is a guess, to be
# checked against how the person reads the list.
MOST_TRADES_SHOWN = 20


@dataclass(frozen=True, kw_only=True)
class Conditions:
    """What a lookup was actually narrowed by; ``None`` for a part that does not narrow it.

    ``period_words`` are the user's own words the program took the period
    from, when it took it from them rather than from the model.

    ``not_narrowed`` holds one sentence for each thing the model asked for
    that the program did not use, and why.
    """

    period: Period | None = None
    period_words: str | None = None
    asset: str | None = None
    side: Side | None = None
    not_narrowed: tuple[str, ...] = ()


@dataclass(frozen=True, kw_only=True)
class Lookup:
    """What one read tool found.

    ``trades`` are the trades shown, at most ``MOST_TRADES_SHOWN``;
    ``trade_count`` is how many the ledger listed or summed in all.
    """

    tool: ToolName
    conditions: Conditions | None = None
    trades: tuple[LedgerTrade, ...] = ()
    trade_count: int | None = None
    summary: PeriodSummary | None = None
    positions: tuple[Position, ...] = ()
    assets: tuple[Asset, ...] = ()


def latest_trades(trades: Sequence[LedgerTrade]) -> tuple[LedgerTrade, ...]:
    """The latest ``MOST_TRADES_SHOWN`` of ``trades``, which come in time order."""
    return tuple(trades[-MOST_TRADES_SHOWN:])


def _n(value: Decimal) -> str:
    return format(value, "f")


def _money(figure: Figure) -> str:
    if isinstance(figure, MoneyAmount):
        return f"{_n(figure.amount)} {figure.currency}"
    return f"not worked out: {figure.reason}"


def _period_words(period: Period | None) -> str:
    if period is None:
        return "all time"
    if period.first_day == period.last_day:
        return period.first_day.isoformat()
    return f"{period.first_day.isoformat()} to {period.last_day.isoformat()}"


def _header(lookup: Lookup) -> list[str]:
    conditions = lookup.conditions
    if conditions is None:
        return []
    lines = [
        f"Time: {_period_words(conditions.period)}",
        f"Asset: {conditions.asset or 'all assets'}",
    ]
    if conditions.period_words is not None:
        lines.insert(1, f"Time taken from your words: {conditions.period_words!r}")
    if lookup.tool is ToolName.LIST_TRADES:
        side = f"{conditions.side.value}s" if conditions.side else "buys and sells"
        lines.append(f"Side: {side}")
    lines.extend(conditions.not_narrowed)
    if lookup.tool is ToolName.GET_PERIOD_SUMMARY:
        lines.append(f"Trades in this time: {lookup.trade_count}")
    if lookup.tool is ToolName.LIST_TRADES:
        shown = len(lookup.trades)
        lines.append(
            f"Trades: {lookup.trade_count}"
            + (f"; shown: the latest {shown}" if shown != lookup.trade_count else "")
        )
    return lines


def _trade_row(trade: LedgerTrade) -> str:
    facts = trade.facts
    row = (
        f"{facts.occurred.strftime('%Y-%m-%d %H:%M')} | {facts.side.value} | {facts.asset} | "
        f"{_n(facts.quantity)} | price {_n(facts.price)} {facts.quote} | "
        f"total {_n(facts.total)} {facts.quote} | fee {_n(facts.fee)} {facts.fee_asset} | "
        f"{facts.platform or '-'}"
    )
    if trade.realized is not None:
        row += f" | realized {_money(trade.realized)}"
    return row


def _summary_rows(summary: PeriodSummary) -> list[str]:
    rows = [
        f"{totals.currency} | spent on buys {_n(totals.spent)} | "
        f"received from sells {_n(totals.received)} | realized {_money(totals.realized)}"
        for totals in summary.by_currency
    ]
    rows.extend(f"fees taken in {fee.currency}: {_n(fee.amount)}" for fee in summary.fees)
    return rows


def _position_row(position: Position) -> str:
    return (
        f"{position.asset} | {_n(position.quantity)} | cost {_money(position.cost)} | "
        f"unrealized {_money(position.unrealized)}"
    )


def _asset_row(asset: Asset) -> str:
    pricing = "can price trades" if asset.pricing.value == "can_price" else "cannot price trades"
    return f"{asset.code} | {asset.name} | {asset.kind.value} | {pricing}"


def _rows(lookup: Lookup) -> list[str]:
    if lookup.tool is ToolName.LIST_TRADES:
        return [_trade_row(trade) for trade in lookup.trades]
    if lookup.tool is ToolName.GET_PERIOD_SUMMARY and lookup.summary is not None:
        return _summary_rows(lookup.summary)
    if lookup.tool is ToolName.GET_POSITIONS:
        return [_position_row(position) for position in lookup.positions]
    return [_asset_row(asset) for asset in lookup.assets]


_NOTHING = "Nothing in the ledger matches."


def lookup_lines(lookup: Lookup) -> tuple[str, ...]:
    """The header, then one line a row; one fixed line when there is no row."""
    rows = _rows(lookup)
    return (*_header(lookup), *(rows or [_NOTHING]))
