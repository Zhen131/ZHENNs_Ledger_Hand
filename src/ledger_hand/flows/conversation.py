"""One thing the user says to the assistant, with recording a trade handed to the program.

``say`` is the entry for each thing the user says. It is handed the chat as
it stands (``AssistantChat``: the assistant's ``Chat``, and a passage whose
question waits for its answer, or a change that waits for the user to say
which trade or which amount follows, if one does) and gives back what came
of it (``Said``), with the chat to hand the next time. It takes one of three
routes (``Route``):

- A question waits: what the user says is its answer. The model that
  chooses tools is not asked; the recording flow reads the answer
  (``recording.answer``), "skip" and "cancel" among them, and asks the same
  question again when the answer cannot be used. A change that waits is
  answered the same way, read by the program (``editing.answer``). Only one
  thing ever waits: a new question takes the place of the one answered.
- Otherwise the model chooses tools (``assisting.take_turn``). When it asks
  to record a trade, what the user said, word for word, is handed to the
  recording flow (``recording.start``), once, however many such calls it
  made; the flow judges it, extracts the trades and asks what is missing.
  The model is not asked again in this turn: the program tells the user
  the question, or that a proposal was sent, or why nothing was.
- When the model goes wrong two steps in a row, the program takes over
  once: it hands what the user said to the recording flow as what may be
  a trade, and says what the flow found, in the same words as when the
  model asks to record: only things the ledger does not record, such as an
  open order, is said with its reason. Only when the flow finds no trade at
  all is the user told it could not be done. A turn stopped at the step
  limit, or by a failure, is not taken over. (Decided on 2026-11-24.)
  When the second wrong step holds a change or a deletion, what was said
  is not tried as a trade: the program goes on from that call alone
  (``editing.taken_over``), and when nothing in it can be gone on with,
  the turn's own words stand.

When the model asks to change or delete a trade, the program goes on with
that call (``editing.start``) and says how it ended; the model is not
asked again in this turn. What reached the ledger is kept apart from a
recording's (``Said.edit_sent``), and its proposal joins the chat's.

Once every trade is settled, the records are sent to the ledger as one
proposal (``proposing``); nothing is confirmed here, since the user confirms
on the ledger's own page. The program's words come from ``record_words``;
none of them is written by the model, and no figure of a trade passes
through it, apart from the number of a quantity said in another unit,
said back as it was read.

The recording flow records with the asset table made from the ledger's own
list of assets (``ledger_table``), asked for once when recording begins:
only an asset of the ledger can be recorded, priced in money the ledger
prices trades in. A trade whose quantity was said in a unit that is not
the asset traded ("25U" of ETH) is held back at the start, asked nothing
about and not sent; the reply says why (``recording.held_other_unit``).
The recording flow is handed no book of its own: what the assistant
records goes to the ledger. So there is no reminder that the same words
were saved before, and a coin the user confirms is known for that passage
only. Its calls to the model are not counted against the step limit; the
flow's progress keeps them apart.

This module reads no clock, no zone and no settings: all are handed in.

Names defined here: ``Route``, ``AssistantChat``, ``Said``, ``say``,
``ASSISTANT_SCREEN_PROMPT`` and ``ASSISTANT_EXTRACT_PROMPT``.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import datetime

from ledger_hand.assistant.edit_calls import EDIT_TOOLS
from ledger_hand.assistant.edit_words import not_done_words
from ledger_hand.assistant.outcome import Chat, Ending, TakenCall, TurnResult
from ledger_hand.core.ledger_records import Asset
from ledger_hand.core.ledger_table import table_of
from ledger_hand.extraction.prompts.first3 import FIRST_PROMPT_3
from ledger_hand.extraction.prompts.screen2 import SCREEN_PROMPT_2
from ledger_hand.flows import editing, recording
from ledger_hand.flows.assisting import close_editing, close_recording, first_edit, take_turn
from ledger_hand.flows.editing import Edited, EditEnding, EditSent, EditWaiting
from ledger_hand.flows.progress import DEFAULT_TUNING, Progress, Tuning
from ledger_hand.flows.proposing import propose
from ledger_hand.flows.record_words import reply_for
from ledger_hand.flows.recorded import (
    SETTLED_STAGES,
    STAGE_ENDINGS,
    Recorded,
    RecordEnding,
    Sent,
)
from ledger_hand.ports import LedgerError, LedgerPort, Message, ModelPort, Role, ToolCall

# The prompt versions the assistant judges and extracts what the user said
# with. The record page keeps the first ones. Measured on 2026-11-25 on
# sentences about a share bought with dollars, the first judging version
# read some as no trade at all, and the first extraction version put gaps
# into phrases; the assistant judges with the second judging version and
# extracts with the third extraction version, the one measured best.
ASSISTANT_SCREEN_PROMPT = SCREEN_PROMPT_2
ASSISTANT_EXTRACT_PROMPT = FIRST_PROMPT_3

# After a takeover, only this ending means it could not be done at all.
_NOT_A_TRADE = frozenset({RecordEnding.NO_TRADE})
# A turn of the model that ended with the user told something, nothing failing.
_TOLD = frozenset({Ending.ANSWERED, Ending.ANSWERED_BY_PROGRAM})


class Route(enum.Enum):
    """Which way what the user said went."""

    MODEL = "the model chose the tools"
    ANSWER = "taken as the answer to the question waiting"
    TAKEOVER = "the program took over after two wrong steps"


@dataclass(frozen=True, kw_only=True)
class AssistantChat:
    """The chat so far, and what waits for the user's answer, if anything does.

    ``recording`` is a passage whose question waits; ``editing`` a change
    that waits for which trade, or which amount follows. At most one waits.
    """

    chat: Chat = Chat()
    recording: Progress | None = None
    editing: EditWaiting | None = None

    def __post_init__(self) -> None:
        if self.recording is not None and self.editing is not None:
            raise ValueError("only one thing waits for the user's answer at a time")


@dataclass(frozen=True, kw_only=True)
class Said:
    """What came of one thing the user said.

    ``turn`` is the model's turn, when the model was asked; ``recorded`` how
    recording ended, when there was any; ``edited`` how a change or a
    deletion ended, when there was one; ``reply`` what the user is told;
    ``state`` the chat to hand the next time.
    """

    route: Route
    reply: str
    state: AssistantChat
    turn: TurnResult | None = None
    recorded: Recorded | None = None
    edited: Edited | None = None

    @property
    def edit_sent(self) -> EditSent | None:
        """The change or deletion that reached the ledger this time; ``None`` for none."""
        return self.edited.sent if self.edited is not None else None

    @property
    def sent(self) -> Sent | None:
        """What reached the ledger this time, by the program's own word; ``None`` for nothing."""
        return self.recorded.sent if self.recorded is not None else None

    @property
    def well_ended(self) -> bool:
        """Whether it was done, or the user was told why not, with nothing failing."""
        if self.edited is not None:
            return self.edited.ending is not EditEnding.LEDGER_FAILED
        if self.recorded is not None:
            if self.route is Route.TAKEOVER and self.recorded.ending in _NOT_A_TRADE:
                return False
            return self.recorded.well_ended
        return self.turn is not None and self.turn.ending in _TOLD


@dataclass(frozen=True)
class _Around:
    """What every part of one thing said is handed: the ports, the moment, the zone."""

    model: ModelPort
    ledger: LedgerPort
    now: datetime
    zone: str
    tuning: Tuning


def say(
    state: AssistantChat,
    said: str,
    *,
    model: ModelPort,
    ledger: LedgerPort,
    now: datetime,
    zone: str,
    max_steps: int,
    tuning: Tuning = DEFAULT_TUNING,
) -> Said:
    """What comes of the user saying ``said`` after ``state``.

    ``tuning`` is how the recording flow calls the model to word a question;
    the caller takes it from the settings (``recording.tuning_from``).
    """
    around = _Around(model, ledger, now, zone, tuning)
    if state.recording is not None:
        return _answered(state, state.recording, said, around)
    if state.editing is not None:
        return _edit_answered(state, state.editing, said, around)
    turn = take_turn(
        state.chat, said, model=model, ledger=ledger, now=now, zone=zone, max_steps=max_steps
    )
    if turn.ending is Ending.EDITING:
        return _edit_begun(turn, said, around)
    if turn.ending is Ending.RECORDING:
        recorded = _begun(said, around)
        reply = reply_for(recorded)
        closed = close_recording(turn, recorded.ending.value, reply, _proposal(recorded))
        state = AssistantChat(chat=closed.chat, recording=_waiting(recorded))
        return Said(route=Route.MODEL, reply=reply, state=state, turn=closed, recorded=recorded)
    if turn.ending is Ending.TWO_MISSTEPS:
        edit = first_edit([handled.call for handled in turn.steps[-1].calls])
        if edit is not None:
            return _edit_taken_over(turn, edit, around)
        return _taken_over(turn, said, around)
    return Said(route=Route.MODEL, reply=turn.reply, state=AssistantChat(chat=turn.chat), turn=turn)


def _begun(said: str, around: _Around) -> Recorded:
    """What the user said, word for word, handed to the recording flow; no book is handed in.

    The ledger's list of assets is asked for first, once, and made into the
    asset table the flow records with; the proposal at the end of this turn
    uses the same list. When the ledger cannot be asked, or prices trades
    in no money at all, it ends there, and the model is asked nothing.
    """
    try:
        listed = around.ledger.list_assets()
    except LedgerError as error:
        unbegun = recording.unbegun(said, now=around.now, zone=around.zone, tuning=around.tuning)
        return Recorded(ending=RecordEnding.LEDGER_FAILED, progress=unbegun, failure=error)
    table = table_of(listed)
    if table is None:
        unbegun = recording.unbegun(said, now=around.now, zone=around.zone, tuning=around.tuning)
        return Recorded(ending=RecordEnding.NO_PRICING_MONEY, progress=unbegun)
    progress = recording.start(
        said,
        around.model,
        now=around.now,
        zone=around.zone,
        assets=table,
        tuning=around.tuning,
        screen_prompt=ASSISTANT_SCREEN_PROMPT,
        extract_prompt=ASSISTANT_EXTRACT_PROMPT,
        hold_other_unit=True,
    )
    return _onward(progress, around.ledger, listed)


def _onward(
    progress: Progress, ledger: LedgerPort, listed: tuple[Asset, ...] | None = None
) -> Recorded:
    """Settled trades go to the ledger; anything else ends where the flow stands.

    ``listed`` is the ledger's list of assets when it was asked for this
    turn; otherwise the proposal asks for it again, as it may have changed
    while a question waited.
    """
    if progress.stage in SETTLED_STAGES:
        return propose(progress, ledger, listed)
    return Recorded(ending=STAGE_ENDINGS[progress.stage], progress=progress)


def _answered(state: AssistantChat, waiting: Progress, said: str, around: _Around) -> Said:
    recorded = _onward(recording.answer(waiting, said, around.model), around.ledger)
    reply = reply_for(recorded)
    chat = _with_words(state.chat, (Message(Role.USER, said), Message(Role.ASSISTANT, reply)))
    chat = _with_proposal(chat, recorded)
    return Said(
        route=Route.ANSWER,
        reply=reply,
        state=AssistantChat(chat=chat, recording=_waiting(recorded)),
        recorded=recorded,
    )


def _taken_over(turn: TurnResult, said: str, around: _Around) -> Said:
    """Two wrong steps: what the user said is tried once as a trade to record."""
    recorded = _begun(said, around)
    if recorded.ending in _NOT_A_TRADE:
        state = AssistantChat(chat=turn.chat)
        return Said(
            route=Route.TAKEOVER, reply=turn.reply, state=state, turn=turn, recorded=recorded
        )
    reply = reply_for(recorded)
    # The model's apology for its wrong steps gives way to the program's words.
    kept = Chat(items=turn.chat.items[:-1], proposals=turn.chat.proposals)
    chat = _with_proposal(_with_words(kept, (Message(Role.ASSISTANT, reply),)), recorded)
    return Said(
        route=Route.TAKEOVER,
        reply=reply,
        state=AssistantChat(chat=chat, recording=_waiting(recorded)),
        turn=turn,
        recorded=recorded,
    )


def _waiting(recorded: Recorded) -> Progress | None:
    return recorded.progress if recorded.ending is RecordEnding.ASKING else None


def _proposal(recorded: Recorded) -> str | None:
    return recorded.sent.proposal if recorded.sent is not None else None


def _with_words(chat: Chat, said: tuple[Message, ...]) -> Chat:
    return Chat(items=(*chat.items, *said), proposals=chat.proposals)


def _with_proposal(chat: Chat, recorded: Recorded) -> Chat:
    proposal = _proposal(recorded)
    if proposal is None:
        return chat
    return Chat(items=chat.items, proposals=(*chat.proposals, proposal))


def _edit_begun(turn: TurnResult, said: str, around: _Around) -> Said:
    """The model's change or deletion, gone on with by the program."""
    taken = next(call for call in turn.steps[-1].calls if isinstance(call, TakenCall))
    edited = editing.begun(
        taken.call, around.ledger, turn.chat.user_said, now=around.now, zone=around.zone
    )
    left = [
        (
            one.call.name,
            _text(one.call.arguments.get("field")),
            _text(one.call.arguments.get("new_value")),
        )
        for one in turn.steps[-1].calls
        if one.call.name in EDIT_TOOLS and one.call is not taken.call
    ]
    reply = edited.reply if not left else f"{edited.reply}\n{not_done_words(left)}"
    proposal = edited.sent.proposal if edited.sent is not None else None
    closed = close_editing(turn, edited.ending.value, reply, proposal)
    state = AssistantChat(chat=closed.chat, editing=edited.waiting)
    return Said(route=Route.MODEL, reply=reply, state=state, turn=closed, edited=edited)


def _text(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _edit_answered(state: AssistantChat, waiting: EditWaiting, said: str, around: _Around) -> Said:
    edited = editing.answer(waiting, said, around.ledger, now=around.now, zone=around.zone)
    chat = _with_words(
        state.chat, (Message(Role.USER, said), Message(Role.ASSISTANT, edited.reply))
    )
    if edited.sent is not None:
        chat = Chat(items=chat.items, proposals=(*chat.proposals, edited.sent.proposal))
    return Said(
        route=Route.ANSWER,
        reply=edited.reply,
        state=AssistantChat(chat=chat, editing=edited.waiting),
        edited=edited,
    )


def _edit_taken_over(turn: TurnResult, call: ToolCall, around: _Around) -> Said:
    """Two wrong steps, the last a change or a deletion: the program goes on from that call."""
    user_said = turn.chat.user_said
    edited = editing.taken_over(call, around.ledger, user_said, now=around.now, zone=around.zone)
    if edited is None:
        return Said(
            route=Route.TAKEOVER, reply=turn.reply, state=AssistantChat(chat=turn.chat), turn=turn
        )
    # The model's apology for its wrong steps gives way to the program's words.
    kept = Chat(items=turn.chat.items[:-1], proposals=turn.chat.proposals)
    chat = _with_words(kept, (Message(Role.ASSISTANT, edited.reply),))
    if edited.sent is not None:
        chat = Chat(items=chat.items, proposals=(*chat.proposals, edited.sent.proposal))
    return Said(
        route=Route.TAKEOVER,
        reply=edited.reply,
        state=AssistantChat(chat=chat, editing=edited.waiting),
        turn=turn,
        edited=edited,
    )
