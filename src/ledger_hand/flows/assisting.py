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

Of the eight tools, these reach the ledger: the four read tools (the list
of assets, the list of trades, the sums of a stretch of time, the
holdings; ``asking``) and where the last proposal of this chat stands. What
a read tool finds is kept as a ``Lookup`` on its call, which the program
lays out for the user, and handed to the model, which only writes a
sentence or two beside it. The asset and the side the model gives a read
tool are checked against what the user said and not used when the user
did not ask for them; that is not a wrong step. When the program cannot
read the period, or the user named an asset the ledger does not have, the
ledger is not asked: the program tells the user itself and the turn ends
there (``Ending.ANSWERED_BY_PROGRAM``), with a result after every call of
that step, so no call in the chat is left without one.

The model's last words are checked before the user sees them
(``assistant.explanation``): after a lookup, every number in them must be
in what the ledger returned, the table, or what the user just said; with
no lookup, they may hold no figure that looks like an amount. Words that
fail give way to the program's own, and the chat keeps the program's
words, so the model's wrong figure never reaches it again; the step keeps
the model's words for the record, and the turn says why
(``TurnResult.withheld``). The turn still ends as answered.

Recording a trade (``propose_trade_add``) is the program's, not the
model's: a step with such a call ends the loop at once (``Ending.RECORDING``),
however many such calls it holds, and the other calls of that step are not
run (``NotRunCall``) and count as no wrong step. Whoever called then
records what the user said and hands the outcome to ``close_recording``,
which puts a result after every call of that step and the program's own
words after them, so that no call in the chat is left without a result.
A period that is not the user's words is a wrong step as any copy is,
but what the model is handed for it also holds what the user just said,
word for word, and asks for the time to be copied from it as written, in
the user's language (the model tends to write "今年" for "this year" and
then write it again). No date the program worked out is in it.
(Decided on 2026-11-24.)

Changing or deleting a trade (``propose_trade_update``,
``propose_trade_delete``) is the program's too, once the call is taken
(``assistant.edit_calls``): a step whose first such call is taken ends the
loop at once (``Ending.EDITING``), and every other call of that step is not
run (``NotRunCall``): one change or deletion at a time. Whoever called then
goes on with that call (``editing``) and hands the outcome to
``close_editing``, which puts a result after every call of the step and the
program's words after them. A first such call that is not taken is a wrong
step, judged as any call is, its period too; any later one in the same step
is not run.

The chat handed back holds every call and result of the turn, so that the
next turn can tie what the user says to what was listed. A call to a tool
that takes no argument is kept in it with its arguments emptied: the ones
the model gave are dropped unread, and handing them back to the model would
bring the figures it wrote into the next ask. The steps keep the calls as
the model made them, for the record. This module reads
no clock, no zone of the machine and no settings: all are handed in.

Names defined here: ``DEFAULT_PROMPT``, ``take_turn``, ``close_recording``,
``close_editing`` and ``first_edit``.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime

from ledger_hand.assistant.edit_calls import EDIT_TOOLS, EditCall, judge_edit
from ledger_hand.assistant.explanation import (
    AFTER_A_TABLE,
    NO_TABLE,
    Withheld,
    check_explanation,
    check_plain_answer,
)
from ledger_hand.assistant.judging import Accepted, Misstep, MisstepKind, judge
from ledger_hand.assistant.lookups import lookup_lines
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
from ledger_hand.assistant.prompts.assistant_fourth import ASSISTANT_FOURTH
from ledger_hand.assistant.results import (
    answered_by_program_text,
    editing_text,
    ledger_error_text,
    lookup_text,
    misstep_text,
    no_proposal_text,
    not_connected_text,
    not_done_text,
    not_run_text,
    period_misstep_text,
    recording_text,
    skipped_text,
    status_text,
)
from ledger_hand.assistant.tools import ToolName, tool_named, tool_specs
from ledger_hand.flows.asking import (
    NARROWED_TOOLS,
    READ_TOOLS,
    ProgramWords,
    judge_read,
    look_up,
)
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

# The system prompt a turn uses unless it is handed another: the latest version.
DEFAULT_PROMPT = ASSISTANT_FOURTH

# Ledger failures the model can tell the user about; any other ends the turn.
_TOLD_TO_THE_MODEL = frozenset({LedgerErrorKind.UNKNOWN_ASSET, LedgerErrorKind.NOT_FOUND})


class _LedgerFailedError(Exception):
    """Carries a ledger failure that ends the turn out of the step it happened in."""

    def __init__(self, error: LedgerError, step: Step) -> None:
        super().__init__(error)
        self.error = error
        self.step = step


class _AnsweredByProgramError(Exception):
    """Carries the program's own words, and the step they ended, out of that step."""

    def __init__(self, words: str, step: Step) -> None:
        super().__init__(words)
        self.words = words
        self.step = step


@dataclass(frozen=True)
class _Around:
    """What every call of a turn is handed: the ledger, the user's words, the moment, the zone."""

    ledger: LedgerPort
    user_said: tuple[str, ...]
    now: datetime
    zone: str


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
        withheld: Withheld | None = None,
    ) -> TurnResult:
        if reply:
            self.items.append(Message(Role.ASSISTANT, reply))
        chat = Chat(items=tuple(self.items), proposals=self.chat.proposals)
        return TurnResult(
            reply=reply,
            ending=ending,
            steps=tuple(self.steps),
            chat=chat,
            failure=failure,
            withheld=withheld,
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
    prompt: AssistantPrompt = DEFAULT_PROMPT,
) -> TurnResult:
    """One turn: ``said`` by the user after ``chat``, until the model answers or is stopped."""
    if isinstance(max_steps, bool) or not isinstance(max_steps, int) or max_steps < 1:
        raise ValueError("max_steps is a whole number, 1 or more")
    turn = _Turn(chat=chat, items=[*chat.items, Message(Role.USER, said)])
    system = system_message(prompt, now, zone)
    tools = tool_specs()
    around = _Around(ledger, (*chat.user_said, said), now, zone)
    wrong_in_a_row = 0
    for _ in range(max_steps):
        try:
            reply = model.chat_with_tools([system, *turn.items], tools)
        except ModelError as error:
            return turn.ended(Ending.MODEL_FAILED, "", error)
        if not reply.calls:
            turn.steps.append(Step(text=reply.text, calls=()))
            words, withheld = _checked_words(reply.text, turn.steps, said)
            return turn.ended(Ending.ANSWERED, words, withheld=withheld)
        turn.items.append(ToolCallTurn(text=reply.text, calls=_as_kept(reply.calls)))
        if any(call.name == ToolName.PROPOSE_TRADE_ADD.value for call in reply.calls):
            turn.steps.append(_to_recording(reply.text, reply.calls, around.user_said))
            return turn.ended(Ending.RECORDING, "")
        edit = first_edit(reply.calls)
        if edit is not None and isinstance(judge_edit(edit, around.user_said), EditCall):
            turn.steps.append(_to_editing(reply.text, reply.calls, edit))
            return turn.ended(Ending.EDITING, "")
        try:
            step = _step(reply.text, reply.calls, turn, around)
        except _LedgerFailedError as stopped:
            turn.steps.append(stopped.step)
            return turn.ended(Ending.LEDGER_FAILED, "", stopped.error)
        except _AnsweredByProgramError as answered:
            turn.steps.append(answered.step)
            return turn.ended(Ending.ANSWERED_BY_PROGRAM, answered.words)
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


def close_editing(result: TurnResult, ending: str, reply: str, proposal: str | None) -> TurnResult:
    """``result``, ended in a change or deletion, with its last step's results and words.

    ``ending`` says in one word how the change ended; ``proposal`` is the
    identifier of the proposal it made, if it made one.
    """
    if result.ending is not Ending.EDITING:
        raise ValueError(f"the turn did not go to a change: {result.ending.value}")
    *earlier, last = result.steps
    handed = editing_text(ending)
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


def first_edit(calls: Sequence[ToolCall]) -> ToolCall | None:
    """The first call of a step that changes or deletes a trade, if there is one."""
    return next((call for call in calls if call.name in EDIT_TOOLS), None)


def _to_editing(text: str, calls: Sequence[ToolCall], edit: ToolCall) -> Step:
    """The step that goes to a change: its first change or deletion taken, every other not run."""
    handled: list[TakenCall | RefusedCall | NotRunCall] = []
    for call in calls:
        if call is edit:
            handled.append(TakenCall(call=call, tool=ToolName(call.name), result=""))
        else:
            handled.append(NotRunCall(call=call, result=not_done_text()))
    return Step(text=text, calls=tuple(handled))


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


def _step(text: str, calls: Sequence[ToolCall], turn: _Turn, around: _Around) -> Step:
    """Judge and run each call of one step in order, handing every result back."""
    handled: list[TakenCall | RefusedCall | NotRunCall] = []
    edit = first_edit(calls)
    for index, call in enumerate(calls):
        if call.name in EDIT_TOOLS and call is not edit:
            not_done = NotRunCall(call=call, result=not_done_text())
            handled.append(not_done)
            turn.items.append(ToolResult(name=call.name, content=not_done.result))
            continue
        try:
            done = _handled(call, turn, around)
        except LedgerError as error:
            if error.kind not in _TOLD_TO_THE_MODEL:
                raise _LedgerFailedError(error, Step(text=text, calls=tuple(handled))) from None
            # Only a call taken reaches the ledger, so its tool is on the list.
            tool = ToolName(call.name)
            done = TakenCall(call=call, tool=tool, result=ledger_error_text(error))
        except _AnsweredByProgramError as answered:
            rest = [NotRunCall(call=other, result=skipped_text()) for other in calls[index + 1 :]]
            for one in (*answered.step.calls, *rest):
                turn.items.append(ToolResult(name=one.call.name, content=one.result))
            step = Step(text=text, calls=(*handled, *answered.step.calls, *rest))
            raise _AnsweredByProgramError(answered.words, step) from None
        handled.append(done)
        turn.items.append(ToolResult(name=call.name, content=done.result))
    return Step(text=text, calls=tuple(handled))


def _handled(call: ToolCall, turn: _Turn, around: _Around) -> TakenCall | RefusedCall:
    """One call judged, and run when it is taken."""
    asset: str | None = None
    if call.name in NARROWED_TOOLS:
        verdict, asset = judge_read(call, around.user_said)
    elif call.name in EDIT_TOOLS:
        # Only a first change that is not taken reaches here: a taken one ends the loop.
        edit_verdict = judge_edit(call, around.user_said)
        if isinstance(edit_verdict, EditCall):
            raise AssertionError("a change taken is gone on with before the step is run")
        verdict = edit_verdict
    else:
        verdict = judge(call, around.user_said)
    if isinstance(verdict, Misstep):
        if _period_not_copied(verdict):
            result = period_misstep_text(verdict, around.user_said[-1])
        else:
            result = misstep_text(verdict)
        return RefusedCall(call=call, misstep=verdict, result=result)
    if verdict.tool in READ_TOOLS:
        found = look_up(
            verdict, asset, around.ledger, around.user_said, now=around.now, zone=around.zone
        )
        if isinstance(found, ProgramWords):
            taken = TakenCall(
                call=call, tool=verdict.tool, result=answered_by_program_text(found.words)
            )
            raise _AnsweredByProgramError(found.words, Step(text="", calls=(taken,)))
        return TakenCall(
            call=call,
            tool=verdict.tool,
            result=lookup_text(found),
            dropped=verdict.dropped,
            lookup=found,
        )
    result = _run(verdict, around.ledger, turn.chat.proposals)
    return TakenCall(call=call, tool=verdict.tool, result=result, dropped=verdict.dropped)


def _period_not_copied(misstep: Misstep) -> bool:
    """Whether the wrong step is a period that is not the user's words."""
    return misstep.kind is MisstepKind.NOT_COPIED and misstep.detail.startswith("'period' is ")


def _checked_words(text: str, steps: Sequence[Step], said: str) -> tuple[str, Withheld | None]:
    """The model's last words, or the program's when they fail the check, and why."""
    taken = [call for step in steps for call in step.calls if isinstance(call, TakenCall)]
    lookups = [call.lookup for call in taken if call.lookup is not None]
    if not lookups:
        withheld = check_plain_answer(text)
        return (NO_TABLE, withheld) if withheld is not None else (text, None)
    against = [call.result for call in taken]
    against.extend(line for lookup in lookups for line in lookup_lines(lookup))
    against.append(said)
    withheld = check_explanation(text, against)
    return (AFTER_A_TABLE, withheld) if withheld is not None else (text, None)


def _run(accepted: Accepted, ledger: LedgerPort, proposals: Sequence[str]) -> str:
    """What the program hands back for a call taken that is not a read tool."""
    if accepted.tool is ToolName.GET_PROPOSAL_STATUS:
        if not proposals:
            return no_proposal_text()
        return status_text(proposals[-1], ledger.proposal_status(proposals[-1]))
    return not_connected_text()
