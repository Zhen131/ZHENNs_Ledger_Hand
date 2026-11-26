"""The tables the assistant page lays out from what the flows handed back, cell by cell.

Each function turns one part of a ``conversation.Said`` into rows of text
cells, one dictionary a row, for ``st.dataframe``; nothing is added, rounded
or converted, and every figure is written by ``assistant_numbers.shown``.
The money a price, a total or a sum is in is always written beside it, as
the result names it: a trade's own money, a fee's own asset, a sum's own
money. No money is assumed.

- ``proposed_rows``: the trades sent as one proposal, numbered as said;
  when the ledger turned some down, or a card with cells left empty waits
  there, each row also says, under ``IN_THE_LEDGER``, whether it waits in
  the ledger (and which cells are still to be filled in) or was not taken
  and why. A cell a card left empty reads ``none``.
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
- ``cash_rows``: the ledger's cash balances, one row a money, in its
  order, each in its own money, 0 and below 0 as given; never a total.

Under a table of holdings or of sums, ``NO_CASH`` says that it holds no cash
balance: the assistant cannot look up cash yet. When the ledger has a tool
for cash balances (as it said when the reply was made, never asked again
while the page draws), ``NO_CASH_ASKABLE`` says instead how to see them.
Either is laid out on the page only, never handed to the model.

Names defined here: ``CHANGED_MARK``, ``IN_THE_LEDGER``, ``FEES_INSIDE``, ``NO_CASH``,
``NO_CASH_ASKABLE``, ``cash_rows``, ``proposed_rows``,
``lookup_rows``,
``change_rows`` and ``listed_rows``.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from ledger_hand.assistant.lookups import Lookup, when_text
from ledger_hand.assistant.tools import ToolName
from ledger_hand.core.ledger_records import (
    Asset,
    CashBalances,
    CurrencyTotals,
    Figure,
    LedgerTrade,
    MoneyAmount,
    PeriodSummary,
    Position,
    TradeFacts,
)
from ledger_hand.core.proposals import CheckOutcome, TradeCheck
from ledger_hand.core.trade_card import TradeCard
from ledger_hand.ui.assistant_numbers import shown

type Row = dict[str, str]

CHANGED_MARK = "changed"
IN_THE_LEDGER = "In the ledger"
# A cell a card left empty.
_EMPTY = "none"


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


def _proposed_cells(trade: TradeFacts | TradeCard) -> Row:
    """A trade's cells as ``_trade_cells`` writes them; a card's empty cell reads ``none``."""
    if isinstance(trade, TradeFacts):
        return _trade_cells(trade)
    whole = trade.facts
    if whole is not None:
        return _trade_cells(whole)
    quote, fee_asset = trade.quote or _EMPTY, trade.fee_asset or _EMPTY
    return {
        "Time": _card_when(trade),
        "Side": trade.side.value,
        "Asset": trade.asset,
        "Quantity": _maybe_shown(trade.quantity),
        "Price": f"{_maybe_shown(trade.price)} {quote}",
        "Total": f"{_maybe_shown(trade.total)} {quote}",
        "Fee": f"{_maybe_shown(trade.fee)} {fee_asset}",
        "Platform": trade.platform or "-",
    }


def _maybe_shown(value: Decimal | None) -> str:
    return shown(value) if value is not None else _EMPTY


def _card_when(card: TradeCard) -> str:
    if card.occurred is None:
        return _EMPTY
    if card.date_only:
        return card.occurred.date().isoformat()
    return card.occurred.strftime("%Y-%m-%d %H:%M")


def proposed_rows(
    numbers: Sequence[int],
    trades: Sequence[TradeFacts | TradeCard],
    checks: Sequence[TradeCheck] = (),
) -> list[Row]:
    """One row for each trade sent, with its number in what was said and its note.

    When the ledger turned any of them down (``checks``, one for each trade),
    or a card waits that cannot be saved yet, each row also says whether it
    waits in the ledger or was not taken, and why (68B3, addition 1); when
    it took them all whole, the rows are as before.
    """
    rows = [
        {"#": str(number), **_proposed_cells(facts), "Note": facts.note or "-"}
        for number, facts in zip(numbers, trades, strict=True)
    ]
    if len(checks) != len(rows) or all(
        c.outcome is CheckOutcome.PASSED and c.ready is not False for c in checks
    ):
        return rows
    # Beside the number, so it is seen without scrolling a wide table sideways.
    return [
        {"#": row["#"], IN_THE_LEDGER: _in_the_ledger(check), **row}
        for row, check in zip(rows, checks, strict=True)
    ]


def _in_the_ledger(check: TradeCheck) -> str:
    if check.outcome is CheckOutcome.PASSED and check.ready is False:
        return (
            f"waiting ({check.proposal_id}); fill in {', '.join(check.missing)} "
            "on the ledger's page before you save it"
        )
    if check.outcome is CheckOutcome.PASSED:
        return f"waiting for you to confirm ({check.proposal_id})"
    return f"not taken: {check.message or check.code or 'no reason given'}"


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

# Said under every table of holdings or of sums (the product owner, 2026-11-25).
NO_CASH = "This table holds no cash balance: the assistant cannot look up cash yet."
# Said instead under such a table when the ledger has a tool for cash balances.
NO_CASH_ASKABLE = (
    "This table holds no cash balance; ask how much of a money you still have, such as "
    '"how much cash do I have", to see the cash balances.'
)


def cash_rows(balances: CashBalances) -> list[Row]:
    """The ledger's cash balances, one row a money, as it gave them; nothing added up."""
    return [
        {"Money": row.code, "Name": row.name, "Balance": f"{shown(row.balance)} {row.code}"}
        for row in balances.balances
    ]


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
