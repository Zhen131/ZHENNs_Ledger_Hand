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

A trade paid in another money than its asset's own has one more cell
after the fee, its rate ("1.0859375 USD for 1 EUR") with its mark, and a
plain line under its cells with the price said in the asset's own money
(``SAID_PRICE``), which is in none of the cells (2026-11-26).

A card sent with cells left empty says ``none`` in each, and under its
cells which are to be filled in on the ledger's page before it can be
saved (``TO_FILL_IN``); a cell left empty for being wrong carries its
suspicious mark with the value said. A card the ledger took whose total is
not quantity times price (its code ``TOTAL_VALUE_MISMATCH``) says under its
cells that the figures are to be put right there first (``FIX_FIGURES``).

The cards sit in the reply's speech bubble, after the reply's own
container, so the lines read from that container by place stay where they
were. The figures are the proposal's own, written by
``assistant_numbers.shown``. (Decided on 2026-11-25.)

Names defined here: ``TAGS``, ``SUSPICIOUS_TAG``, ``NOT_CHECKED``,
``TO_FILL_IN``, ``FIX_FIGURES``, ``SAID_PRICE``, ``card_key``, ``cell_key`` and
``draw``.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from types import MappingProxyType

import streamlit as st

from ledger_hand.core.cost_rate import RateNote
from ledger_hand.core.marks import Field, FieldMark, MarkKind, TradeMarks
from ledger_hand.core.trade_card import TradeCard, card_of
from ledger_hand.flows.record_words import MISMATCH_CODE, not_checked_words
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
# The start of the line under a card sent with cells left empty.
TO_FILL_IN = "to fill in on the ledger's page before saving: "
# The line under a card the ledger took whose total is not quantity times price,
# chosen by the ledger's code alone (2026-11-27).
FIX_FIGURES = (
    "to put right on the ledger's page before saving: quantity × price does not match the total"
)
# The start of the line under a card paid in another money than its asset's own.
SAID_PRICE = "price you said in the asset's own money: "
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
    checks = recorded.checks if len(recorded.checks) == len(recorded.trades) else None
    for place, (number, sent, marked) in enumerate(
        zip(recorded.numbers, recorded.trades, recorded.marked, strict=True)
    ):
        # A trade handed in whole (older callers) is drawn as its card.
        facts = sent if isinstance(sent, TradeCard) else card_of(sent)
        with st.container(border=True, key=card_key(exchange, number)):
            st.markdown(f"**Trade {number}**")
            for label, value, fields in _cells(facts, marked.marks, marked.rate):
                _cell(exchange, number, label, value, _marks_on(marked.marks, fields))
            if marked.rate is not None:
                said = marked.rate.said
                st.text(f"{SAID_PRICE}{shown(said.amount)} {said.money} {marked.rate.each}")
            reason = not_checked_words(marked.price)
            if reason is not None:
                st.text(NOT_CHECKED + reason)
            if not facts.complete:
                st.text(TO_FILL_IN + ", ".join(facts.missing))
            problem = checks[place].problem if checks is not None else None
            if problem is not None and problem.code == MISMATCH_CODE:
                st.text(FIX_FIGURES)


def _shown(value: Decimal | None) -> str:
    return shown(value) if value is not None else _NONE


def _cells(facts: TradeCard, marks: TradeMarks, rate: RateNote | None = None) -> list[_Cell]:
    """Each cell of the card: its name, its value as shown, and the cells of the ledger it is.

    A cell left empty is ``none``; so is a money left empty beside a figure.
    The rate is a cell only for a trade paid in another money (``rate``).
    """
    quote, fee_asset = facts.quote or _NONE, facts.fee_asset or _NONE
    moment = facts.occurred
    cells: list[_Cell] = [
        ("Asset", facts.asset, (Field.ASSET_ID,)),
        ("Side", facts.side.value, (Field.TYPE,)),
        ("Quantity", _shown(facts.quantity), (Field.QUANTITY,)),
        ("Price", f"{_shown(facts.price)} {quote}", (Field.PRICE,)),
        ("Total", f"{_shown(facts.total)} {quote}", (Field.TOTAL_VALUE,)),
        ("Money used", quote, (Field.QUOTE_ASSET_ID,)),
        ("Fee", f"{_shown(facts.fee)} {fee_asset}", (Field.FEE, Field.FEE_ASSET_ID)),
        *(
            [
                (
                    "Rate",
                    f"{_shown(facts.cost_rate)} {rate.said.money} for 1 {quote}",
                    (Field.COST_RATE,),
                )
            ]
            if rate is not None
            else []
        ),
        ("Day", moment.date().isoformat() if moment is not None else _NONE, (Field.OCCURRED_DATE,)),
        (
            "Time of day",
            _NONE if moment is None or facts.date_only else moment.strftime("%H:%M"),
            (Field.OCCURRED_TIME, Field.OCCURRED_TIME_ZONE),
        ),
    ]
    if facts.platform or marks.on(Field.PLATFORM) is not None:
        cells.append(("Platform", facts.platform or _NONE, (Field.PLATFORM,)))
    if facts.note or marks.on(Field.NOTE) is not None:
        cells.append(("Note", facts.note or _NONE, (Field.NOTE,)))
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
