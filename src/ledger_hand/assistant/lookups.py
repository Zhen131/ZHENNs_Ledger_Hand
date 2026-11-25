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

``trade_row`` and ``conditions_lines`` lay out one trade, and the
conditions trades were found by, the same way, for the program's words
when it changes or deletes a trade. ``header_lines`` gives the header
alone, for a screen that lays the rows out as a table of its own.

A trade known only to its day is shown with its day alone, never as
midnight (``when_text``).

Names defined here: ``MOST_TRADES_SHOWN``, ``CUT_WORDS``, ``Conditions``,
``Lookup``, ``latest_trades``, ``when_text``, ``lookup_lines``,
``header_lines``, ``trade_row`` and ``conditions_lines``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from ledger_hand.assistant.tools import ToolName
from ledger_hand.core.ledger_records import (
    MOST_TRADES_LISTED,
    Asset,
    Figure,
    LedgerTrade,
    MoneyAmount,
    PeriodSummary,
    Position,
    TradeFacts,
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

    ``not_narrowed`` holds one sentence for each thing the model asked for
    that the program did not use, and why.
    """

    period: Period | None = None
    asset: str | None = None
    side: Side | None = None
    not_narrowed: tuple[str, ...] = ()


@dataclass(frozen=True, kw_only=True)
class Lookup:
    """What one read tool found.

    ``trades`` are the trades shown, at most ``MOST_TRADES_SHOWN``;
    ``trade_count`` is how many the ledger listed or summed in all. ``cut``
    says the ledger listed only its latest ``MOST_TRADES_LISTED`` trades,
    and older ones matched too.
    """

    tool: ToolName
    conditions: Conditions | None = None
    trades: tuple[LedgerTrade, ...] = ()
    trade_count: int | None = None
    cut: bool = False
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
        if lookup.cut:
            lines.append(CUT_WORDS)
    return lines


def when_text(facts: TradeFacts) -> str:
    """When a trade happened: its day and time, or its day alone when only that is known."""
    if facts.date_only:
        return facts.day.isoformat()
    return facts.occurred.strftime("%Y-%m-%d %H:%M")


def _trade_row(trade: LedgerTrade) -> str:
    facts = trade.facts
    row = (
        f"{when_text(facts)} | {facts.side.value} | {facts.asset} | "
        f"{_n(facts.quantity)} | price {_n(facts.price)} {facts.quote} | "
        f"total {_n(facts.total)} {facts.quote} | fee {_n(facts.fee)} {facts.fee_asset} | "
        f"{facts.platform or '-'}"
    )
    if trade.realized is not None:
        row += f" | realized {_money(trade.realized)}"
        if trade.realized_unreliable is not None:
            row += f" (not reliable: {trade.realized_unreliable})"
    if trade.dated_after_today:
        row += " | dated after today, in no sum"
    return row


def _sum_text(figure: Figure) -> str:
    if isinstance(figure, MoneyAmount):
        return _n(figure.amount)
    return f"not worked out: {figure.reason}"


def _summary_rows(summary: PeriodSummary) -> list[str]:
    rows = []
    for totals in summary.by_currency:
        rows.append(
            f"{totals.currency} | spent on buys {_sum_text(totals.spent)} | "
            f"received from sells {_sum_text(totals.received)} | "
            f"realized {_money(totals.realized)}"
        )
        transfers = totals.realized_from_transfers
        if not (isinstance(transfers, MoneyAmount) and transfers.amount == 0):
            rows.append(
                f"{totals.currency} | of the realized: from sells "
                f"{_money(totals.realized_from_sells)}; cost taken out by transfers "
                f"{_money(transfers)} (not a losing sale)"
            )
        rows.extend(
            f"{totals.currency} | {row.asset} realized {_money(row.realized)}, "
            f"not reliable: {row.unreliable}"
            for row in totals.by_asset
            if row.unreliable is not None
        )
    rows.extend(f"fees taken in {fee.currency}: {_n(fee.amount)}" for fee in summary.fees)
    return rows


def _position_row(position: Position) -> str:
    row = (
        f"{position.asset} | {_n(position.quantity)} | cost {_money(position.cost)} | "
        f"unrealized {_money(position.unrealized)}"
    )
    if position.cost_unreliable is not None:
        row += f" | cost not reliable: {position.cost_unreliable}"
    return row


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

# Said when the ledger listed only its latest trades (68B2, part 9).
CUT_WORDS = (
    f"Only the latest {MOST_TRADES_LISTED} trades were taken; older ones are not counted here."
)


def lookup_lines(lookup: Lookup) -> tuple[str, ...]:
    """The header, then one line a row; one fixed line when there is no row."""
    rows = _rows(lookup)
    return (*_header(lookup), *(rows or [_NOTHING]))


def header_lines(lookup: Lookup) -> tuple[str, ...]:
    """The header alone, as ``lookup_lines`` begins: the days, the asset, the side, the counts."""
    return tuple(_header(lookup))


def trade_row(trade: LedgerTrade) -> str:
    """One trade on one line, as a list of trades shows it."""
    return _trade_row(trade)


def conditions_lines(conditions: Conditions) -> tuple[str, ...]:
    """The days, the asset and the side trades were found by, as a list's header has them."""
    side = f"{conditions.side.value}s" if conditions.side else "buys and sells"
    return (
        f"Time: {_period_words(conditions.period)}",
        f"Asset: {conditions.asset or 'all assets'}",
        f"Side: {side}",
        *conditions.not_narrowed,
    )
