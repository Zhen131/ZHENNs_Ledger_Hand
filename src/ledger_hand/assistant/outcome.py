"""How one turn of the assistant's chat went, kept as values that never change.

- ``Chat``: the chat so far, everything in it: what the user and the
  assistant said, every tool call the model made and what the program handed
  back for it (the trades the ledger listed, with their identifiers, among
  them), and the proposals made in it. The next turn is handed it whole, so
  that what the user says next can be tied to what was listed before.
- ``Ending``: why the turn ended.
- ``TakenCall`` and ``RefusedCall``: one tool call, and what the program
  handed back for it, or the wrong step it was and why. ``NotRunCall``: a
  call that was not run, because its step went to recording instead.
- ``Step``: one answer of the model: its text, and the calls in it, in order.
- ``TurnResult``: what the assistant says at the end, why the turn ended,
  every step, the chat to hand the next turn, and the failure that stopped
  it, if one did.

``TWO_MISSTEPS_REPLY`` and ``STEP_LIMIT_REPLY`` are the program's own words
when it stops the model.

Names defined here: ``Ending``, ``Chat``, ``TakenCall``, ``RefusedCall``,
``NotRunCall``, ``Step``, ``TurnResult``, ``TWO_MISSTEPS_REPLY`` and ``STEP_LIMIT_REPLY``.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

from ledger_hand.assistant.judging import Misstep
from ledger_hand.assistant.tools import ToolName
from ledger_hand.ports import ChatItem, LedgerError, Message, ModelError, Role, ToolCall

TWO_MISSTEPS_REPLY = (
    "Sorry, I could not do that: I went wrong twice in a row. Please say it another way."
)
STEP_LIMIT_REPLY = (
    "Sorry, I could not finish that within the steps allowed. Please say it another way."
)


class Ending(enum.Enum):
    """Why a turn ended."""

    ANSWERED = "answered"
    """The model wrote its answer."""
    STEP_LIMIT = "step_limit"
    """The model was asked as often as one turn allows, and had still not answered."""
    TWO_MISSTEPS = "two_missteps"
    """The model went wrong two steps in a row."""
    MODEL_FAILED = "model_failed"
    """The model could not be asked."""
    LEDGER_FAILED = "ledger_failed"
    """The ledger could not be reached, or failed in a way the model cannot mend."""
    RECORDING = "recording"
    """The model chose to record a trade; the program takes what the user said on from there."""


@dataclass(frozen=True, kw_only=True)
class Chat:
    """The chat so far, and the identifiers of the proposals made in it, oldest first."""

    items: tuple[ChatItem, ...] = ()
    proposals: tuple[str, ...] = ()

    @property
    def user_said(self) -> tuple[str, ...]:
        """Everything the user said in the chat, in order."""
        return tuple(
            item.content
            for item in self.items
            if isinstance(item, Message) and item.role is Role.USER
        )


@dataclass(frozen=True, kw_only=True)
class TakenCall:
    """A call taken: the call as the model made it, the tool it named, the names of the
    arguments dropped unread (for a tool that takes none), and what was handed back."""

    call: ToolCall
    tool: ToolName
    result: str
    dropped: tuple[str, ...] = ()


@dataclass(frozen=True, kw_only=True)
class RefusedCall:
    """A call that was a wrong step: the call, why, and what was handed back for it."""

    call: ToolCall
    misstep: Misstep
    result: str


@dataclass(frozen=True, kw_only=True)
class NotRunCall:
    """A call not run, because its step went to recording, and what was handed back for it."""

    call: ToolCall
    result: str


@dataclass(frozen=True, kw_only=True)
class Step:
    """One answer of the model: its text, and its calls in order, each taken or refused."""

    text: str
    calls: tuple[TakenCall | RefusedCall | NotRunCall, ...]

    @property
    def wrong(self) -> bool:
        """Whether any call of the step was a wrong step."""
        return any(isinstance(call, RefusedCall) for call in self.calls)


@dataclass(frozen=True, kw_only=True)
class TurnResult:
    """How one turn went: the last word, why it ended, its steps, the chat, the failure."""

    reply: str
    ending: Ending
    steps: tuple[Step, ...]
    chat: Chat
    failure: ModelError | LedgerError | None = None
