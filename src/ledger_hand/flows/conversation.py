"""One thing the user says to the assistant, with recording a trade handed to the program.

``say`` is the entry for each thing the user says. It is handed the chat as
it stands (``AssistantChat``: the assistant's ``Chat``, and a passage whose
question waits for its answer, if one does) and gives back what came of it
(``Said``), with the chat to hand the next time. It takes one of three
routes (``Route``):

- A question waits: what the user says is its answer. The model that
  chooses tools is not asked; the recording flow reads the answer
  (``recording.answer``), "skip" and "cancel" among them, and asks the same
  question again when the answer cannot be used.
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

Once every trade is settled, the records are sent to the ledger as one
proposal (``proposing``); nothing is confirmed here, since the user confirms
on the ledger's own page. The program's words come from ``record_words``;
none of them is written by the model, and no figure of a trade passes
through it.

The recording flow is handed no book of its own: what the assistant
records goes to the ledger. So there is no reminder that the same words
were saved before, and a coin the user confirms is known for that passage
only. Its calls to the model are not counted against the step limit; the
flow's progress keeps them apart.

This module reads no clock, no zone and no settings: all are handed in.

Names defined here: ``Route``, ``AssistantChat``, ``Said`` and ``say``.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import datetime

from ledger_hand.assistant.outcome import Chat, Ending, TurnResult
from ledger_hand.flows import recording
from ledger_hand.flows.assisting import close_recording, take_turn
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
from ledger_hand.ports import LedgerPort, Message, ModelPort, Role

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
    """The chat so far, and the passage whose question waits for its answer, if one does."""

    chat: Chat = Chat()
    recording: Progress | None = None


@dataclass(frozen=True, kw_only=True)
class Said:
    """What came of one thing the user said.

    ``turn`` is the model's turn, when the model was asked; ``recorded`` how
    recording ended, when there was any; ``reply`` what the user is told;
    ``state`` the chat to hand the next time.
    """

    route: Route
    reply: str
    state: AssistantChat
    turn: TurnResult | None = None
    recorded: Recorded | None = None

    @property
    def sent(self) -> Sent | None:
        """What reached the ledger this time, by the program's own word; ``None`` for nothing."""
        return self.recorded.sent if self.recorded is not None else None

    @property
    def well_ended(self) -> bool:
        """Whether it was done, or the user was told why not, with nothing failing."""
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
    turn = take_turn(
        state.chat, said, model=model, ledger=ledger, now=now, zone=zone, max_steps=max_steps
    )
    if turn.ending is Ending.RECORDING:
        recorded = _begun(said, around)
        reply = reply_for(recorded)
        closed = close_recording(turn, recorded.ending.value, reply, _proposal(recorded))
        state = AssistantChat(chat=closed.chat, recording=_waiting(recorded))
        return Said(route=Route.MODEL, reply=reply, state=state, turn=closed, recorded=recorded)
    if turn.ending is Ending.TWO_MISSTEPS:
        return _taken_over(turn, said, around)
    return Said(route=Route.MODEL, reply=turn.reply, state=AssistantChat(chat=turn.chat), turn=turn)


def _begun(said: str, around: _Around) -> Recorded:
    """What the user said, word for word, handed to the recording flow; no book is handed in."""
    progress = recording.start(
        said, around.model, now=around.now, zone=around.zone, tuning=around.tuning
    )
    return _onward(progress, around.ledger)


def _onward(progress: Progress, ledger: LedgerPort) -> Recorded:
    """Settled trades go to the ledger; anything else ends where the flow stands."""
    if progress.stage in SETTLED_STAGES:
        return propose(progress, ledger)
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
