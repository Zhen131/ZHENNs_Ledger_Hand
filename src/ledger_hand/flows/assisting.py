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
  words. Arguments given to a tool that takes none are dropped instead, and
  the step records their names. Calls of one step are judged and run in
  order;
- two wrong steps in a row stop the turn; a step with no wrong call between
  them starts the count again.

The model is asked once a step, whatever the number of calls in it, so the
number of asks never passes ``max_steps``.

A model failure stops the turn at once (the plug has already tried again
where waiting may help); so does a ledger that cannot be reached or fails in
a way of its own. A ledger that answers "no such asset" or "no such trade"
is not a failure of the turn: its code and sentence are handed to the model,
which tells the user.

Of the eight tools, these reach the ledger so far: the list of assets,
the holdings, and where the last proposal of this chat stands. The
holdings and the assets are handed to the model, which words the answer;
that is for now only, until the program lays such figures out itself.

Recording a trade (``propose_trade_add``) is the program's, not the
model's: a step with such a call ends the loop at once (``Ending.RECORDING``),
however many such calls it holds, and the other calls of that step are not
run (``NotRunCall``) and count as no wrong step. Whoever called then
records what the user said and hands the outcome to ``close_recording``,
which puts a result after every call of that step and the program's own
words after them, so that no call in the chat is left without a result.
Asking about the ledger, changing and deleting are on the list, so that the
model can choose them, and are answered "not connected yet".

The chat handed back holds every call and result of the turn, so that the
next turn can tie what the user says to what was listed. A call to a tool
that takes no argument is kept in it with its arguments emptied: the ones
the model gave are dropped unread, and handing them back to the model would
bring the figures it wrote into the next ask. The steps keep the calls as
the model made them, for the record. This module reads
no clock, no zone of the machine and no settings: all are handed in.

Names defined here: ``take_turn`` and ``close_recording``.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime

from ledger_hand.assistant.judging import Accepted, Misstep, judge
from ledger_hand.assistant.outcome import (
    STEP_LIMIT_REPLY,
    TWO_MISSTEPS_REPLY,
    Chat,
    Ending,
    NotRunCall,
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
    not_run_text,
    positions_text,
    recording_text,
    status_text,
)
from ledger_hand.assistant.tools import ToolName, tool_named, tool_specs
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
        turn.items.append(ToolCallTurn(text=reply.text, calls=_as_kept(reply.calls)))
        if any(call.name == ToolName.PROPOSE_TRADE_ADD.value for call in reply.calls):
            turn.steps.append(_to_recording(reply.text, reply.calls, user_said))
            return turn.ended(Ending.RECORDING, "")
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


def close_recording(
    result: TurnResult, ending: str, reply: str, proposal: str | None
) -> TurnResult:
    """``result``, ended in recording, with its last step's results and the program's words.

    ``ending`` says in one word how the recording ended; ``proposal`` is the
    identifier of the proposal it made, if it made one.
    """
    if result.ending is not Ending.RECORDING:
        raise ValueError(f"the turn did not go to recording: {result.ending.value}")
    *earlier, last = result.steps
    handed = recording_text(ending)
    calls = tuple(
        dataclasses.replace(call, result=handed) if isinstance(call, TakenCall) else call
        for call in last.calls
    )
    items = (
        *result.chat.items,
        *(ToolResult(name=call.call.name, content=call.result) for call in calls),
        Message(Role.ASSISTANT, reply),
    )
    proposals = result.chat.proposals + ((proposal,) if proposal is not None else ())
    return dataclasses.replace(
        result,
        reply=reply,
        steps=(*earlier, dataclasses.replace(last, calls=calls)),
        chat=Chat(items=items, proposals=proposals),
    )


def _to_recording(text: str, calls: Sequence[ToolCall], user_said: Sequence[str]) -> Step:
    """The step that goes to recording: its recording calls taken, every other call not run."""
    handled: list[TakenCall | RefusedCall | NotRunCall] = []
    for call in calls:
        verdict = judge(call, user_said)
        if call.name == ToolName.PROPOSE_TRADE_ADD.value and isinstance(verdict, Accepted):
            handled.append(
                TakenCall(call=call, tool=verdict.tool, result="", dropped=verdict.dropped)
            )
        else:
            handled.append(NotRunCall(call=call, result=not_run_text()))
    return Step(text=text, calls=tuple(handled))


def _as_kept(calls: Sequence[ToolCall]) -> tuple[ToolCall, ...]:
    """The calls as the chat keeps them: a tool that takes no argument gets none."""
    return tuple(
        ToolCall(name=call.name, arguments={}) if _takes_nothing(call.name) else call
        for call in calls
    )


def _takes_nothing(name: str) -> bool:
    tool = tool_named(name)
    return tool is not None and not tool.arguments


def _step(
    text: str,
    calls: Sequence[ToolCall],
    turn: _Turn,
    user_said: Sequence[str],
    ledger: LedgerPort,
) -> Step:
    """Judge and run each call of one step in order, handing every result back."""
    handled: list[TakenCall | RefusedCall | NotRunCall] = []
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
            handled.append(
                TakenCall(call=call, tool=verdict.tool, result=result, dropped=verdict.dropped)
            )
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
