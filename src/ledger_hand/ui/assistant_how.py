"""What the assistant page says about one thing said: who wrote the reply, what was sent, how.

Every line here is read off what the flows handed back (``conversation.Said``);
nothing is worked out again.

- ``words_by_line``: who wrote the words the person is told, as the result
  says (``Said.words_by``); for a question, who wrote its sentence too
  (``Question.writer``).
- ``sent_line``: the program's own word on what reached the ledger this
  time, said under every reply: a proposal to record, a change, a deletion,
  or nothing.
- ``how_lines``: how it was done, for the part of the page that opens on a
  click: which way it went; the money moved said that the assistant does
  not record, and what the ledger said of its cash, when either came up;
  each step of the model, each tool it asked for
  with the arguments given (those dropped unread named), a short piece of
  what was handed back, or why the call was a wrong step, or that it was
  not run; whether the program took over; how many steps the model took
  out of how many allowed; and how many times the recording asked the
  model, counted apart from the steps.

Names defined here: ``RESULT_SHOWN``, ``words_by_line``, ``sent_line`` and
``how_lines``.
"""

from __future__ import annotations

import json

from ledger_hand.assistant.outcome import NotRunCall, RefusedCall, Step
from ledger_hand.flows.cash_answers import CashSeen
from ledger_hand.flows.conversation import Route, Said, WordsBy

# What was handed back can run to a whole list; a line of it is enough to see
# what it was, and the table above shows the rest.
RESULT_SHOWN = 160


def words_by_line(said: Said) -> str:
    """Who wrote the reply, as the result says."""
    by = said.words_by
    if by is WordsBy.QUESTION and said.recorded is not None:
        question = said.recorded.question
        writer = question.writer.value if question is not None else WordsBy.PROGRAM.value
        return f"Words: {by.value}; its sentence by {writer}"
    return f"Words: {by.value}"


def sent_line(said: Said) -> str:
    """What reached the ledger this time, by the program's own word."""
    if said.sent is not None:
        trades = said.sent.trades
        what = f"{trades} trade{'s' if trades != 1 else ''} to record"
        return f"Sent to the ledger: {said.sent.proposal} ({what}), waiting for you to confirm"
    edit_sent = said.edit_sent
    if edit_sent is not None:
        return (
            f"Sent to the ledger: {edit_sent.proposal} ({edit_sent.kind.value} of trade "
            f"{edit_sent.trade}), waiting for you to confirm"
        )
    return "Sent to the ledger: nothing"


def _short(text: str) -> str:
    one_line = " ".join(text.split())
    if len(one_line) <= RESULT_SHOWN:
        return one_line
    return f"{one_line[:RESULT_SHOWN]}... ({len(one_line)} characters in all)"


def _step_lines(number: int, step: Step) -> list[str]:
    if not step.calls:
        return [f"Step {number}: the model answered"]
    lines = [f"Step {number}: the model asked for {len(step.calls)} tool(s)"]
    for handled in step.calls:
        arguments = json.dumps(dict(handled.call.arguments), ensure_ascii=False)
        lines.append(f"Tool: {handled.call.name} {arguments}")
        if isinstance(handled, RefusedCall):
            misstep = handled.misstep
            lines.append(f"Wrong step ({misstep.kind.value}): {misstep.detail}")
        elif isinstance(handled, NotRunCall):
            lines.append(f"Not run: {_short(handled.result)}")
        else:
            if handled.dropped:
                lines.append(f"Dropped, unread: {', '.join(handled.dropped)}")
            lines.append(f"Handed back: {_short(handled.result)}")
    return lines


def _cash_seen(seen: CashSeen) -> str:
    if seen.tool is False:
        return "the ledger has no tool for them"
    if seen.failure is not None:
        return f"the ledger could not be asked ({seen.failure.code})"
    if seen.balances is not None and seen.shown:
        return f"read from the ledger, counted up to {seen.balances.day.isoformat()}"
    return "the ledger has a tool for them"


def how_lines(said: Said, steps: int) -> tuple[str, ...]:
    """How ``said`` was done, one line each; ``steps`` is how many one turn allows."""
    lines = [f"Way: {said.route.value}"]
    if said.cash is not None:
        lines.append(f"Caught as a question about cash: {said.cash.value}")
    if said.manual is not None:
        kinds = ", ".join(kind.value for kind in said.manual.kinds)
        beside = "; a trade was spoken of beside it" if said.manual.with_trade else ""
        lines.append(f"Money moved that the assistant does not record: {kinds}{beside}")
    if said.cash_seen is not None:
        lines.append(f"Cash balances in the ledger: {_cash_seen(said.cash_seen)}")
    turn = said.turn
    if turn is not None:
        for number, step in enumerate(turn.steps, start=1):
            lines += _step_lines(number, step)
        lines.append(f"Steps of the model: {len(turn.steps)} of at most {steps}")
    else:
        lines.append("Steps of the model: none; the model that chooses tools was not asked")
    took_over = "yes" if said.route is Route.TAKEOVER else "no"
    lines.append(f"Taken over by the program: {took_over}")
    if said.recorded is not None:
        asked = len(said.recorded.progress.calls)
        lines.append(f"Calls to the model by the recording so far: {asked}, apart from the steps")
    return tuple(lines)
