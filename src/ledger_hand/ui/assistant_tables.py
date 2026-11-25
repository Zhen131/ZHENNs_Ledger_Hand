"""The tables the assistant page lays out from what the flows handed back, cell by cell.

Each function turns one part of a ``conversation.Said`` into rows of text
cells, one dictionary a row, for ``st.dataframe``; nothing is added, rounded
or converted, and every figure is written by ``assistant_numbers.shown``.
The money a price, a total or a sum is in is always written beside it, as
the result names it: a trade's own money, a fee's own asset, a sum's own
money. No money is assumed.

- ``proposed_rows``: the trades sent as one proposal, numbered as said.
- ``lookup_rows``: what a read tool found: trades, the sums of a stretch of
  time, holdings or assets. Its header (the days, the asset, the side, the
  counts) is the program's (``lookups.header_lines``). The sums are one row
  a money, with its buys and sells counted and its fees, which
  ``FEES_INSIDE`` says are inside its sums when taken in that money; a
  holding names the asset's own money, every figure of it in that money.
  A trade known only to its day shows its day alone.
- ``change_rows``: a change, the trade before and after side by side, one
  row a part, the parts that change marked; or a deletion, the trade alone.
- ``listed_rows``: the trades a change or deletion found, numbered from 1
  as the program numbered them when it asked which.

Names defined here: ``CHANGED_MARK``, ``FEES_INSIDE``, ``proposed_rows``, ``lookup_rows``,
``change_rows`` and ``listed_rows``.
"""

from __future__ import annotations

from collections.abc import Sequence

from ledger_hand.assistant.lookups import Lookup, when_text
from ledger_hand.assistant.tools import ToolName
from ledger_hand.core.ledger_records import (
    Asset,
    CurrencyTotals,
    Figure,
    LedgerTrade,
    MoneyAmount,
    PeriodSummary,
    Position,
    TradeFacts,
)
from ledger_hand.ui.assistant_numbers import shown

type Row = dict[str, str]

CHANGED_MARK = "changed"


def _when(facts: TradeFacts) -> str:
    return when_text(facts)


def _figure(figure: Figure | None) -> str:
    if figure is None:
        return "-"
    if isinstance(figure, MoneyAmount):
        return f"{shown(figure.amount)} {figure.currency}"
    return f"not worked out: {figure.reason}"


def _trade_cells(facts: TradeFacts) -> Row:
    return {
        "Time": _when(facts),
        "Side": facts.side.value,
        "Asset": facts.asset,
        "Quantity": shown(facts.quantity),
        "Price": f"{shown(facts.price)} {facts.quote}",
        "Total": f"{shown(facts.total)} {facts.quote}",
        "Fee": f"{shown(facts.fee)} {facts.fee_asset}",
        "Platform": facts.platform or "-",
    }


def proposed_rows(numbers: Sequence[int], trades: Sequence[TradeFacts]) -> list[Row]:
    """One row for each trade sent, with its number in what was said and its note."""
    return [
        {"#": str(number), **_trade_cells(facts), "Note": facts.note or "-"}
        for number, facts in zip(numbers, trades, strict=True)
    ]


def _realized(trade: LedgerTrade) -> str:
    shown_figure = _figure(trade.realized)
    if trade.realized_unreliable is not None:
        shown_figure += f" (not reliable: {trade.realized_unreliable})"
    if trade.dated_after_today:
        shown_figure += " (dated after today, in no sum)"
    return shown_figure


def _ledger_trade(trade: LedgerTrade) -> Row:
    return {**_trade_cells(trade.facts), "Realized": _realized(trade)}


def _sum(figure: Figure) -> str:
    if isinstance(figure, MoneyAmount):
        return shown(figure.amount)
    return f"not worked out: {figure.reason}"


def _group_realized(totals: CurrencyTotals) -> str:
    said = _figure(totals.realized)
    transfers = totals.realized_from_transfers
    if not (isinstance(transfers, MoneyAmount) and transfers.amount == 0):
        said += (
            f" (from sells {_figure(totals.realized_from_sells)}; cost taken out by "
            f"transfers {_figure(transfers)}, not a loss from selling)"
        )
    return said


# Said under every summary: a fee taken in the group's own money is inside its
# two sums already (the ledger's assistant-link/README.md, rule 7).
FEES_INSIDE = "Fees paid in a group's own money are already inside its spent and received."


def _summary(summary: PeriodSummary) -> list[Row]:
    rows: list[Row] = []
    for totals in summary.by_currency:
        rows.append(
            {
                "Money": totals.currency,
                "Buys": str(totals.buy_count),
                "Sells": str(totals.sell_count),
                "Spent on buys": _sum(totals.spent),
                "Received from sells": _sum(totals.received),
                "Realized": _group_realized(totals),
                "Fees": ", ".join(f"{shown(fee.amount)} {fee.currency}" for fee in totals.fees)
                or "-",
            }
        )
        rows += [
            {
                "Money": totals.currency,
                "Buys": "-",
                "Sells": "-",
                "Spent on buys": "-",
                "Received from sells": "-",
                "Realized": f"{row.asset}: {_figure(row.realized)}, not reliable: {row.unreliable}",
                "Fees": "-",
            }
            for row in totals.by_asset
            if row.unreliable is not None
        ]
    return rows


def _position(position: Position) -> Row:
    cost = _figure(position.cost)
    if position.cost_unreliable is not None:
        cost += f" (not reliable: {position.cost_unreliable})"
    return {
        "Asset": position.asset,
        "In": position.currency,
        "Quantity": shown(position.quantity),
        "Cost": cost,
        "Unrealized": _figure(position.unrealized),
    }


def _asset(asset: Asset) -> Row:
    return {
        "Code": asset.code,
        "Name": asset.name,
        "Kind": asset.kind.value,
        "Prices trades": asset.pricing.value,
    }


def lookup_rows(lookup: Lookup) -> list[Row]:
    """One row for each trade, sum, holding or asset the read tool found."""
    if lookup.tool is ToolName.LIST_TRADES:
        return [_ledger_trade(trade) for trade in lookup.trades]
    if lookup.tool is ToolName.GET_PERIOD_SUMMARY:
        return _summary(lookup.summary) if lookup.summary is not None else []
    if lookup.tool is ToolName.GET_POSITIONS:
        return [_position(position) for position in lookup.positions]
    return [_asset(asset) for asset in lookup.assets]


def _parts(facts: TradeFacts) -> Row:
    return {**_trade_cells(facts), "Note": facts.note or "-"}


def change_rows(before: LedgerTrade, after: TradeFacts | None) -> list[Row]:
    """A change: one row a part, before and after, the parts that change marked; a deletion: one."""
    was = _parts(before.facts)
    if after is None:
        return [{"Part": part, "In the ledger": value} for part, value in was.items()]
    will = _parts(after)
    return [
        {
            "Part": part,
            "Before": value,
            "After": will[part],
            "Changes": CHANGED_MARK if will[part] != value else "",
        }
        for part, value in was.items()
    ]


def listed_rows(trades: Sequence[LedgerTrade]) -> list[Row]:
    """The trades found, numbered from 1 in the order the program listed them."""
    return [
        {"#": str(number), **_ledger_trade(trade)} for number, trade in enumerate(trades, start=1)
    ]
