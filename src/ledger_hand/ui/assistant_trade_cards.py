"""The assistant page's card for each trade sent: its cells, each with its mark, read only.

Under a reply that sent trades, one bordered card a trade (``draw``), its
cells one to a line in a fixed order: asset, side, quantity, price and
total (each with its money), the money used, the fee with its asset, the
day and the time of day, then the platform and the note when there are
any. A cell with nothing in it says ``none``. Beside a cell, its mark
(``core/marks.py``): "worked out by the program", "assumed by the
program", or, in red and in words, "SUSPICIOUS:" with the reason written
out, so the reason is seen without pointing at anything and a reader who
cannot tell red apart still sees the word. When the price was not compared
with the market price, a plain line under the card says why
(``record_words.not_checked_words``): no mark is not the same as checked.

A reason is drawn as plain text (``st.text``), never as Markdown or HTML,
so whatever it holds is shown as it is. Only fixed words are Markdown. A
card holds no input and no button: it cannot change the trade. The demo
ledger's save and reject stay on the card of the proposal
(``assistant_cards``).

The cards sit in the reply's speech bubble, after the reply's own
container, so the lines read from that container by place stay where they
were. The figures are the proposal's own, written by
``assistant_numbers.shown``. (Decided on 2026-11-25.)

Names defined here: ``TAGS``, ``SUSPICIOUS_TAG``, ``NOT_CHECKED``,
``card_key``, ``cell_key`` and ``draw``.
"""

from __future__ import annotations

from collections.abc import Sequence
from types import MappingProxyType

import streamlit as st

from ledger_hand.core.ledger_records import TradeFacts
from ledger_hand.core.marks import Field, FieldMark, MarkKind, TradeMarks
from ledger_hand.flows.record_words import not_checked_words
from ledger_hand.flows.recorded import Recorded
from ledger_hand.ui.assistant_numbers import shown

# The words beside a marked cell, fixed, so they may be Markdown.
TAGS = MappingProxyType(
    {
        MarkKind.COMPUTED: ":blue[worked out by the program]",
        MarkKind.INFERRED: ":orange[assumed by the program]",
        MarkKind.SUSPICIOUS: ":red[**SUSPICIOUS:**]",
    }
)
SUSPICIOUS_TAG = TAGS[MarkKind.SUSPICIOUS]
# The start of the line under a card whose price was not compared.
NOT_CHECKED = "price not checked: "
_NONE = "none"

type _Cell = tuple[str, str, tuple[Field, ...]]


def card_key(exchange: int, number: int) -> str:
    """The key of the card of trade ``number`` under exchange ``exchange``."""
    return f"assistant_trade_card_{exchange}_{number}"


def cell_key(exchange: int, number: int, label: str) -> str:
    """The key of the cell named ``label`` ("Price") on that card."""
    return f"{card_key(exchange, number)}_{label.lower().replace(' ', '_')}"


def draw(recorded: Recorded | None, exchange: int) -> None:
    """One card for each trade ``recorded`` sent, with its marks; nothing when none was."""
    if recorded is None or not recorded.trades or len(recorded.marked) != len(recorded.trades):
        return
    for number, facts, marked in zip(
        recorded.numbers, recorded.trades, recorded.marked, strict=True
    ):
        with st.container(border=True, key=card_key(exchange, number)):
            st.markdown(f"**Trade {number}**")
            for label, value, fields in _cells(facts):
                _cell(exchange, number, label, value, _marks_on(marked.marks, fields))
            reason = not_checked_words(marked.price)
            if reason is not None:
                st.text(NOT_CHECKED + reason)


def _cells(facts: TradeFacts) -> list[_Cell]:
    """Each cell of the card: its name, its value as shown, and the cells of the ledger it is."""
    cells: list[_Cell] = [
        ("Asset", facts.asset, (Field.ASSET_ID,)),
        ("Side", facts.side.value, (Field.TYPE,)),
        ("Quantity", shown(facts.quantity), (Field.QUANTITY,)),
        ("Price", f"{shown(facts.price)} {facts.quote}", (Field.PRICE,)),
        ("Total", f"{shown(facts.total)} {facts.quote}", (Field.TOTAL_VALUE,)),
        ("Money used", facts.quote, (Field.QUOTE_ASSET_ID,)),
        ("Fee", f"{shown(facts.fee)} {facts.fee_asset}", (Field.FEE, Field.FEE_ASSET_ID)),
        ("Day", facts.day.isoformat(), (Field.OCCURRED_DATE,)),
        (
            "Time of day",
            _NONE if facts.date_only else facts.occurred.strftime("%H:%M"),
            (Field.OCCURRED_TIME, Field.OCCURRED_TIME_ZONE),
        ),
    ]
    if facts.platform:
        cells.append(("Platform", facts.platform, (Field.PLATFORM,)))
    if facts.note:
        cells.append(("Note", facts.note, (Field.NOTE,)))
    return cells


def _marks_on(marks: TradeMarks, fields: Sequence[Field]) -> list[FieldMark]:
    return [mark for mark in (marks.on(field) for field in fields) if mark is not None]


def _cell(exchange: int, number: int, label: str, value: str, marks: list[FieldMark]) -> None:
    """One cell: its value, then each mark on it and the mark's reason, as plain text."""
    with st.container(key=cell_key(exchange, number, label)):
        st.text(f"{label}: {value}")
        for mark in marks:
            st.markdown(TAGS[mark.kind])
            if mark.reason is not None:
                st.text(mark.reason)
