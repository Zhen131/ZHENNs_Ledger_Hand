"""One turn of the assistant: the user says something, and the model works through tools.

``take_turn`` hands the model the chat so far, what the user just said and
the eight tools. When the model answers in words, the turn is over. When it
asks for tools, each call is judged first (``assistant.judging``); a call
taken is run against the ledger, and what comes back is handed to the model
with the next ask; a wrong step is not run, and the model is shown what was
wrong instead. This goes on until the model answers or the program stops
it. The program holds the model to three limits:

- it is asked at most ``max_steps`` times in one turn (the settings say how
  many; six by default);
- a step is wrong when any call in it is: an unknown tool, arguments that do
  not follow the tool's schema, or a copied argument that is not the user's
  words. Calls of one step are judged and run in order;
- two wrong steps in a row stop the turn; a step with no wrong call between
  them starts the count again.

The model is asked once a step, whatever the number of calls in it, so the
number of asks never passes ``max_steps``.

A model failure stops the turn at once (the plug has already tried again
where waiting may help); so does a ledger that cannot be reached or fails in
a way of its own. A ledger that answers "no such asset" or "no such trade"
is not a failure of the turn: its code and sentence are handed to the model,
which tells the user.

Of the eight tools, only these reach the ledger so far: the list of
assets, the holdings, and where the last proposal of this chat stands
(none made yet, so far). The others are on the list, so that the model can
choose them, and are answered "not connected yet". The holdings and the
assets are handed to the model, which words the answer; that is for now
only, until the program lays such figures out itself.

The chat handed back holds every call and result of the turn, so that the
next turn can tie what the user says to what was listed. This module reads
no clock, no zone of the machine and no settings: all are handed in.

Names defined here: ``take_turn``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime

from ledger_hand.assistant.judging import Accepted, Misstep, judge
from ledger_hand.assistant.outcome import (
    STEP_LIMIT_REPLY,
    TWO_MISSTEPS_REPLY,
    Chat,
    Ending,
    RefusedCall,
    Step,
    TakenCall,
    TurnResult,
)
from ledger_hand.assistant.prompting import AssistantPrompt, system_message
from ledger_hand.assistant.prompts.assistant_first import ASSISTANT_FIRST
from ledger_hand.assistant.results import (
    assets_text,
    ledger_error_text,
    misstep_text,
    no_proposal_text,
    not_connected_text,
    positions_text,
    status_text,
)
from ledger_hand.assistant.tools import ToolName, tool_specs
from ledger_hand.ports import (
    ChatItem,
    LedgerError,
    LedgerErrorKind,
    LedgerPort,
    Message,
    ModelError,
    ModelPort,
    Role,
    ToolCall,
    ToolCallTurn,
    ToolResult,
)

# Ledger failures the model can tell the user about; any other ends the turn.
_TOLD_TO_THE_MODEL = frozenset({LedgerErrorKind.UNKNOWN_ASSET, LedgerErrorKind.NOT_FOUND})


class _LedgerFailedError(Exception):
    """Carries a ledger failure that ends the turn out of the step it happened in."""

    def __init__(self, error: LedgerError, step: Step) -> None:
        super().__init__(error)
        self.error = error
        self.step = step


@dataclass
class _Turn:
    """What a turn has gathered so far."""

    chat: Chat
    items: list[ChatItem]
    steps: list[Step] = field(default_factory=list)

    def ended(
        self,
        ending: Ending,
        reply: str,
        failure: ModelError | LedgerError | None = None,
    ) -> TurnResult:
        if reply:
            self.items.append(Message(Role.ASSISTANT, reply))
        chat = Chat(items=tuple(self.items), proposals=self.chat.proposals)
        return TurnResult(
            reply=reply, ending=ending, steps=tuple(self.steps), chat=chat, failure=failure
        )


def take_turn(
    chat: Chat,
    said: str,
    *,
    model: ModelPort,
    ledger: LedgerPort,
    now: datetime,
    zone: str,
    max_steps: int,
    prompt: AssistantPrompt = ASSISTANT_FIRST,
) -> TurnResult:
    """One turn: ``said`` by the user after ``chat``, until the model answers or is stopped."""
    if isinstance(max_steps, bool) or not isinstance(max_steps, int) or max_steps < 1:
        raise ValueError("max_steps is a whole number, 1 or more")
    turn = _Turn(chat=chat, items=[*chat.items, Message(Role.USER, said)])
    system = system_message(prompt, now, zone)
    tools = tool_specs()
    user_said = (*chat.user_said, said)
    wrong_in_a_row = 0
    for _ in range(max_steps):
        try:
            reply = model.chat_with_tools([system, *turn.items], tools)
        except ModelError as error:
            return turn.ended(Ending.MODEL_FAILED, "", error)
        if not reply.calls:
            turn.steps.append(Step(text=reply.text, calls=()))
            return turn.ended(Ending.ANSWERED, reply.text)
        turn.items.append(ToolCallTurn(text=reply.text, calls=reply.calls))
        try:
            step = _step(reply.text, reply.calls, turn, user_said, ledger)
        except _LedgerFailedError as stopped:
            turn.steps.append(stopped.step)
            return turn.ended(Ending.LEDGER_FAILED, "", stopped.error)
        turn.steps.append(step)
        wrong_in_a_row = wrong_in_a_row + 1 if step.wrong else 0
        if wrong_in_a_row == 2:
            return turn.ended(Ending.TWO_MISSTEPS, TWO_MISSTEPS_REPLY)
    return turn.ended(Ending.STEP_LIMIT, STEP_LIMIT_REPLY)


def _step(
    text: str,
    calls: Sequence[ToolCall],
    turn: _Turn,
    user_said: Sequence[str],
    ledger: LedgerPort,
) -> Step:
    """Judge and run each call of one step in order, handing every result back."""
    handled: list[TakenCall | RefusedCall] = []
    for call in calls:
        verdict = judge(call, user_said)
        if isinstance(verdict, Misstep):
            result = misstep_text(verdict)
            handled.append(RefusedCall(call=call, misstep=verdict, result=result))
        else:
            try:
                result = _run(verdict, ledger, turn.chat.proposals)
            except LedgerError as error:
                if error.kind not in _TOLD_TO_THE_MODEL:
                    raise _LedgerFailedError(error, Step(text=text, calls=tuple(handled))) from None
                result = ledger_error_text(error)
            handled.append(TakenCall(call=call, tool=verdict.tool, result=result))
        turn.items.append(ToolResult(name=call.name, content=result))
    return Step(text=text, calls=tuple(handled))


def _run(accepted: Accepted, ledger: LedgerPort, proposals: Sequence[str]) -> str:
    """What the program hands back for a call taken."""
    if accepted.tool is ToolName.LIST_ASSETS:
        return assets_text(ledger.list_assets())
    if accepted.tool is ToolName.GET_POSITIONS:
        return positions_text(ledger.positions())
    if accepted.tool is ToolName.GET_PROPOSAL_STATUS:
        if not proposals:
            return no_proposal_text()
        return status_text(proposals[-1], ledger.proposal_status(proposals[-1]))
    return not_connected_text()
