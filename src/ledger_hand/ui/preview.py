"""The table of what will be recorded: one row per trade, with Don't save, Save and Discard all.

``rows`` turns a ``Progress`` into the table's cells, one row per trade in
passage order: where the trade stands, the time, the coin, buy or sell, the
quantity, the price and the total side by side (so a total written where the
price belongs shows at a glance), the fee and its coin, the platform and the
note. A trade that is complete shows its record; any other shows its
draft as it stands, with blanks where nothing is known yet. The amount the
program worked out from the other two is marked, read from the record, so
the mark appears only once the trade has passed the check. So is the fee
coin of a complete trade whose fee the ledger leaves out of the cost (paid
in a third coin; the core says which), and a sentence under the table says
why.

Numbers are written as the ledger writes them, from exact decimals; a draft
value the ledger could not hold is written out as the exact decimal it is.
A time is shown as a date, or a date and a wall-clock time, in the trade's
own zone, followed by that zone's name.

``draw`` shows the table, which cannot be edited (a value is changed by
answering a question), and under it the controls: Don't save for each
trade, Save and Discard all. Each is usable only when the flow offers it.

Names defined here: ``COLUMNS``, ``CALCULATED_MARK``, ``FEE_LEFT_OUT_MARK``,
``rows``, ``draw`` and the keys of the controls.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import streamlit as st

from ledger_hand.core.fee_cost import fee_left_out_of_cost
from ledger_hand.core.numbers import write_number
from ledger_hand.core.trade import Amount, OccurredTime, TimePrecision
from ledger_hand.flows.progress import Progress, TradeState, TradeStatus
from ledger_hand.ui import sayings, turns

TABLE_KEY = "preview_table"
SAVE_KEY = "save_button"
DISCARD_KEY = "discard_all_button"
DONT_SAVE_KEY = "dont_save_trade_{number}"

# Where a trade stands comes first, so it is in sight however narrow the window.
COLUMNS = (
    "#",
    "Status",
    "Time",
    "Coin",
    "Side",
    "Quantity",
    "Price",
    "Total",
    "Fee",
    "Fee coin",
    "Platform",
    "Note",
)
CALCULATED_MARK = " *"
# After the fee coin of a complete trade whose fee the ledger leaves out of the cost.
FEE_LEFT_OUT_MARK = " (not in cost)"
# The star stands alone in the sentence, so the caption does not read it as Markdown.
_LEGEND = "An amount marked * was worked out by the program from the other two."
# Wide enough for a date, a time and a zone name, and for a status with its reason.
_WIDTHS = {"#": 40, "Status": 140, "Time": 220}
_AMOUNT_COLUMNS = {Amount.QUANTITY: "Quantity", Amount.PRICE: "Price", Amount.TOTAL: "Total"}
_STATUS = {
    TradeStatus.OPEN: "asking",
    TradeStatus.RECORDED: "complete",
    TradeStatus.SKIPPED: "left out",
    TradeStatus.CANNOT_RECORD: "cannot record",
}


def rows(progress: Progress | None) -> list[dict[str, str]]:
    """One row of cells per trade, in passage order; none when nothing is being recorded."""
    if progress is None:
        return []
    return [_row(number, trade) for number, trade in enumerate(progress.trades, start=1)]


def draw(progress: Progress | None) -> None:
    """Show the table and, under it, the controls the flow offers now."""
    found = rows(progress)
    # The key is on a container: a table that cannot be selected from takes none of its own.
    with st.container(key=TABLE_KEY):
        st.dataframe(
            {column: [row[column] for row in found] for column in COLUMNS},
            hide_index=True,
            column_config={
                name: st.column_config.TextColumn(width=width) for name, width in _WIDTHS.items()
            },
        )
    st.caption(_LEGEND)
    for reminder in sayings.fees_left_out(progress):
        st.caption(reminder)
    if progress is not None and progress.trades:
        with st.container(horizontal=True):
            for number in range(1, len(progress.trades) + 1):
                st.button(
                    f"Don't save #{number}",
                    key=DONT_SAVE_KEY.format(number=number),
                    disabled=number not in progress.removable,
                    on_click=turns.drop_trade,
                    args=(number,),
                )
    with st.container(horizontal=True):
        st.button(
            "Save",
            key=SAVE_KEY,
            type="primary",
            disabled=progress is None or not progress.can_save,
            on_click=turns.save_passage,
        )
        st.button(
            "Discard all",
            key=DISCARD_KEY,
            disabled=progress is None or not progress.can_cancel,
            on_click=turns.discard_passage,
        )
    st.caption(sayings.save_hint(progress))


def _row(number: int, trade: TradeState) -> dict[str, str]:
    record = trade.record
    if trade.status is TradeStatus.RECORDED and record is not None:
        cells = {
            "Time": _time(record.occurred),
            "Coin": record.coin,
            "Side": record.side.value,
            "Quantity": _number(record.quantity),
            "Price": _number(record.price),
            "Total": _number(record.total),
            "Fee": _number(record.fee),
            "Fee coin": record.fee_coin,
            "Platform": record.platform or "",
            "Note": record.note or "",
        }
        if record.derived is not None:
            cells[_AMOUNT_COLUMNS[record.derived]] += CALCULATED_MARK
        if fee_left_out_of_cost(record):
            cells["Fee coin"] += FEE_LEFT_OUT_MARK
    else:
        draft = trade.draft
        cells = {
            "Time": _time(draft.occurred),
            "Coin": draft.coin or "",
            "Side": draft.side.value if draft.side is not None else "",
            "Quantity": _number(draft.quantity),
            "Price": _number(draft.price),
            "Total": _number(draft.total),
            "Fee": _number(draft.fee),
            "Fee coin": draft.fee_coin or "",
            "Platform": draft.platform or "",
            "Note": draft.note or "",
        }
    return {"#": str(number), "Status": _status(trade), **cells}


def _status(trade: TradeState) -> str:
    words = _STATUS[trade.status]
    if trade.status is TradeStatus.CANNOT_RECORD and trade.reason is not None:
        return f"{words}: {trade.reason.value}"
    return words


def _number(value: Decimal | None) -> str:
    if value is None:
        return ""
    try:
        return write_number(value)
    except ValueError:
        # A draft may hold a value the ledger cannot; show it as the exact decimal it is.
        return format(value, "f")


def _time(occurred: OccurredTime | None) -> str:
    if occurred is None:
        return ""
    value = occurred.value
    if isinstance(value, datetime):
        # The wall clock of the trade's own zone; the zone's name follows.
        spec = "seconds" if occurred.precision is TimePrecision.SECOND else "minutes"
        shown = value.replace(tzinfo=None).isoformat(sep=" ", timespec=spec)
    else:
        shown = value.isoformat()
    return f"{shown} ({occurred.time_zone})"
