"""The assistant page's chat: every exchange so far, with the tables and buttons under each reply.

For each exchange the person's words are shown as typed. When tidying
changed them, a small line under them, in the same bubble and under the
key ``read_as_key``, says what the program read them as ("Read as: ...");
it stays out of the reply's own container, whose lines tests read by
place. Then the program's reply as the flows put it, as plain text. Under
the reply:

- who wrote it, as the result says (``assistant_how.words_by_line``);
- each failure the reply rests on, in one plain sentence
  (``assistant_failure_words``), in an error box;
- the tables the program lays out (``assistant_tables``): what each read
  tool found, under its header, a table of holdings or of sums with a line
  that it holds no cash balance (``NO_CASH``); the trades sent; a change before and after,
  or the trade to delete; the trades found when the program asks which;
- under the latest reply only, while the flows wait for its answer, one
  button for each answer offered: a question's choices, each listed trade's
  number, each amount that may follow. Pressing one says that answer, as if
  typed (``assistant_turns.take_text``);
- the line on what reached the ledger (``assistant_how.sent_line``);
- "How this was done", closed until opened (``assistant_how.how_lines``);
- when the reply was not kept in the assistant's record, why, under the
  key ``record_key`` (``assistant_record_words.not_kept_words``): a missing
  data folder as a plain line, any other reason as a warning, never an
  error box, since what was said was done.

A note the page said by itself (a screenshot read, dropped or not read, a
demo button that did nothing) is shown alone, a failure in an error box.

Names defined here: ``exchange_key``, ``table_key``, ``choice_key``,
``how_key``, ``record_key``, ``read_as_key``, ``READ_AS`` and ``draw``.
"""

from __future__ import annotations

from collections.abc import Sequence

import streamlit as st

from ledger_hand.assistant.lookups import header_lines
from ledger_hand.assistant.tools import ToolName
from ledger_hand.flows.assistant_record import NotKept, RecordProblem
from ledger_hand.flows.conversation import Said
from ledger_hand.flows.editing import Choosing, Picking
from ledger_hand.ui import assistant_session, assistant_turns
from ledger_hand.ui.assistant_failure_words import failure_lines
from ledger_hand.ui.assistant_how import how_lines, sent_line, words_by_line
from ledger_hand.ui.assistant_record_words import not_kept_words
from ledger_hand.ui.assistant_session import Exchange, NoteTone
from ledger_hand.ui.assistant_tables import (
    FEES_INSIDE,
    NO_CASH,
    change_rows,
    listed_rows,
    lookup_rows,
    proposed_rows,
)
from ledger_hand.wiring import Parts

# The tables that hold money but never cash: each gets ``NO_CASH`` under it.
_WITHOUT_CASH = frozenset({ToolName.GET_POSITIONS, ToolName.GET_PERIOD_SUMMARY})


def exchange_key(number: int) -> str:
    """The key of the container that holds exchange ``number``'s reply."""
    return f"assistant_exchange_{number}"


def table_key(number: int, kind: str, index: int = 0) -> str:
    """The key of a table under exchange ``number``: ``kind`` is lookup, proposed, change or
    listed; ``index`` counts the lookups of one reply from 0."""
    return f"assistant_table_{number}_{kind}_{index}"


def choice_key(number: int, index: int) -> str:
    """The key of answer button ``index`` (from 0) under exchange ``number``."""
    return f"assistant_choice_{number}_{index}"


def how_key(number: int) -> str:
    """The key of the container that holds how exchange ``number`` was done."""
    return f"assistant_how_{number}"


def record_key(number: int) -> str:
    """The key of the container that says exchange ``number`` was not kept in the record."""
    return f"assistant_record_{number}"


def read_as_key(number: int) -> str:
    """The key of the container that says what exchange ``number``'s words were read as."""
    return f"assistant_read_as_{number}"


# The start of the line that says what the words were read as.
READ_AS = "Read as: "


def draw(parts: Parts, exchanges: Sequence[Exchange]) -> None:
    """Show every exchange, oldest first; buttons for the answers only under the latest."""
    for exchange in exchanges:
        latest = exchange is exchanges[-1]
        if exchange.words is not None:
            with st.chat_message("user"):
                st.text(exchange.words)
                _read_as(exchange)
        with st.chat_message("assistant"), st.container(key=exchange_key(exchange.number)):
            _reply(parts, exchange, latest=latest)


def _read_as(exchange: Exchange) -> None:
    """The words as tidied, only when tidying changed them."""
    said = exchange.said
    if said is None or said.read_as is None or not said.read_as.changed:
        return
    with st.container(key=read_as_key(exchange.number)):
        st.caption(READ_AS + said.read_as.text)


def _reply(parts: Parts, exchange: Exchange, *, latest: bool) -> None:
    said = exchange.said
    if said is None:
        if exchange.tone is NoteTone.FAILED:
            st.error(exchange.note or "")
        else:
            st.text(exchange.note or "")
        return
    number = exchange.number
    st.caption(words_by_line(said))
    if said.reply:
        st.text(said.reply)
    for line in failure_lines(said, parts.settings, parts.assistant_steps):
        st.error(line)
    _tables(said, number)
    if latest:
        _choices(exchange)
    st.caption(sent_line(said))
    with st.expander("How this was done"), st.container(key=how_key(number)):
        for line in how_lines(said, parts.assistant_steps):
            st.text(line)
    _not_kept(exchange)


def _not_kept(exchange: Exchange) -> None:
    kept = exchange.kept
    if not isinstance(kept, NotKept):
        return
    with st.container(key=record_key(exchange.number)):
        if kept.problem is RecordProblem.NO_DATA_FOLDER:
            st.caption(not_kept_words(kept))
        else:
            st.warning(not_kept_words(kept))


def _table(rows: list[dict[str, str]], key: str, header: Sequence[str] = ()) -> None:
    with st.container(key=key):
        if header:
            st.text("\n".join(header))
        if rows:
            st.dataframe(rows, hide_index=True)
        else:
            st.text("Nothing in the ledger matches.")


def _tables(said: Said, number: int) -> None:
    if said.turn is not None:
        for index, lookup in enumerate(said.turn.lookups):
            _table(lookup_rows(lookup), table_key(number, "lookup", index), header_lines(lookup))
            if lookup.summary is not None and lookup.summary.by_currency:
                st.caption(FEES_INSIDE)
            if lookup.tool in _WITHOUT_CASH:
                st.caption(NO_CASH)
    recorded = said.recorded
    if recorded is not None and recorded.trades:
        st.caption("The trades in the proposal:")
        rows = proposed_rows(recorded.numbers, recorded.trades, recorded.checks)
        _table(rows, table_key(number, "proposed"))
    edited = said.edited
    if edited is not None and edited.before is not None and edited.sent is not None:
        caption = "Before and after:" if edited.after is not None else "The trade to delete:"
        st.caption(caption)
        _table(change_rows(edited.before, edited.after), table_key(number, "change"))
    if edited is not None and edited.listed:
        _table(listed_rows(edited.listed), table_key(number, "listed"))


def _choices(exchange: Exchange) -> None:
    """One button for each answer offered, while the flows wait for it."""
    said = exchange.said
    if said is None:
        return
    state = assistant_session.chat()
    answers: list[tuple[str, str]] = []
    question = said.recorded.question if said.recorded is not None else None
    if state.recording is not None and question is not None:
        answers = [(choice, choice) for choice in question.choices]
    waiting = said.edited.waiting if said.edited is not None else None
    if state.editing is not None and isinstance(waiting, Picking):
        answers = [(f"Trade {n}", str(n)) for n in range(1, len(waiting.trades) + 1)]
    if state.editing is not None and isinstance(waiting, Choosing):
        answers = [
            (f"{n}: the {amount.value} follows", str(n))
            for n, amount in enumerate(waiting.offered, start=1)
        ]
    if not answers:
        return
    with st.container(horizontal=True):
        for index, (label, answer) in enumerate(answers):
            st.button(
                label,
                key=choice_key(exchange.number, index),
                on_click=assistant_turns.take_text,
                args=(answer,),
                help="Answers with this, as if you typed it.",
            )
