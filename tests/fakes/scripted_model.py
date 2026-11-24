"""A scripted stand-in for the model port, for tests that must not touch a real model.

``ScriptedModel`` is given its script up front: one step per expected call.
A step is the text of a reply, a whole ``ModelReply``, or a ``ModelError`` to
raise. Each call takes the next step, in order, and is recorded with what it
was sent, so a test can check both what the code under test did with the
replies and what it asked. A call after the last step raises
``ScriptExhaustedError``: the test expected fewer calls than the code made.

A call with pictures (``chat_with_pictures``) takes the next step of the
same script, and is recorded the same way, with the pictures it was shown
and no reply schema. Like the real plugs, it first refuses a call in the
wrong shape (no pictures, or a last message that is not the user's), with
``TypeError`` or ``ValueError``, taking no step.

A call with tools (``chat_with_tools``) also takes the next step of the
same script. A step for it may be a ``ToolReply`` (text, tool calls or both)
as well as text, a reply or an error; text, or a reply's text, comes back
as a reply with no call. It is recorded with the conversation it was sent
(``items``) and the tools it was handed, and it first refuses a call in the
wrong shape, as the real plugs do.

It needs no network and no settings, and it never waits.

Names defined here: ``Step``, ``RecordedCall``, ``ScriptExhaustedError``,
``ScriptedModel``, ``SCRIPTED_MODEL_NAME``, ``scripted_record``.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from ledger_hand.llm.request_body import check_call, check_pictures, check_tools
from ledger_hand.ports import (
    ChatItem,
    FinishReason,
    JsonSchema,
    Message,
    ModelError,
    ModelParameters,
    ModelReply,
    Picture,
    ReplyRecord,
    ToolReply,
    ToolSpec,
)

SCRIPTED_MODEL_NAME = "scripted"

type Step = str | ModelReply | ModelError | ToolReply


@dataclass(frozen=True)
class RecordedCall:
    """What one call to the scripted model was sent."""

    messages: tuple[Message, ...]
    reply_schema: JsonSchema | None
    parameters: ModelParameters | None
    # The pictures of a call with pictures; none for any other call.
    pictures: tuple[Picture, ...] = ()
    # The conversation and the tools of a call with tools; none for any other call.
    items: tuple[ChatItem, ...] = ()
    tools: tuple[ToolSpec, ...] = ()


class ScriptExhaustedError(AssertionError):
    """The code under test called the model more often than the script has steps."""


class ScriptedModel:
    """A model port that plays back its script, one step per call."""

    def __init__(self, steps: Iterable[Step]) -> None:
        self._steps = list(steps)
        for step in self._steps:
            if not isinstance(step, str | ModelReply | ModelError | ToolReply):
                raise TypeError(f"a script step is text, a reply or an error, not {step!r}")
        self.calls: list[RecordedCall] = []

    @property
    def steps_left(self) -> int:
        return len(self._steps) - len(self.calls)

    def chat(
        self,
        messages: Sequence[Message],
        *,
        reply_schema: JsonSchema | None = None,
        parameters: ModelParameters | None = None,
    ) -> ModelReply:
        if self.steps_left == 0:
            raise ScriptExhaustedError(
                f"the script is used up: it has {len(self._steps)} step(s) and "
                f"call {len(self.calls) + 1} asked for another"
            )
        step = self._steps[len(self.calls)]
        self.calls.append(RecordedCall(tuple(messages), reply_schema, parameters))
        if isinstance(step, ModelError):
            raise step
        if isinstance(step, ModelReply):
            return step
        return ModelReply(text=step, record=_record())

    def chat_with_pictures(
        self,
        messages: Sequence[Message],
        pictures: Sequence[Picture],
        *,
        parameters: ModelParameters | None = None,
    ) -> ModelReply:
        check_call(messages, None, parameters or _ANY_PARAMETERS)
        check_pictures(messages, pictures)
        if self.steps_left == 0:
            raise ScriptExhaustedError(
                f"the script is used up: it has {len(self._steps)} step(s) and "
                f"call {len(self.calls) + 1}, with pictures, asked for another"
            )
        step = self._steps[len(self.calls)]
        self.calls.append(RecordedCall(tuple(messages), None, parameters, tuple(pictures)))
        if isinstance(step, ModelError):
            raise step
        if isinstance(step, ModelReply):
            return step
        return ModelReply(text=step, record=_record())

    def chat_with_tools(
        self,
        items: Sequence[ChatItem],
        tools: Sequence[ToolSpec],
        *,
        parameters: ModelParameters | None = None,
    ) -> ToolReply:
        check_tools(items, tools, parameters or _ANY_PARAMETERS)
        if self.steps_left == 0:
            raise ScriptExhaustedError(
                f"the script is used up: it has {len(self._steps)} step(s) and "
                f"call {len(self.calls) + 1}, with tools, asked for another"
            )
        step = self._steps[len(self.calls)]
        self.calls.append(
            RecordedCall((), None, parameters, items=tuple(items), tools=tuple(tools))
        )
        if isinstance(step, ModelError):
            raise step
        if isinstance(step, ToolReply):
            return step
        text = step.text if isinstance(step, ModelReply) else step
        return ToolReply(text=text, calls=(), record=_record())


# Stands in for the parameters a call without any would be sent with, for the checks only.
_ANY_PARAMETERS = ModelParameters(
    temperature=0.0, top_p=1.0, max_reply_tokens=1, context_tokens=1, timeout_seconds=1.0
)


def scripted_record() -> ReplyRecord:
    """The record every scripted reply carries."""
    return _record()


def _record() -> ReplyRecord:
    return ReplyRecord(
        model=SCRIPTED_MODEL_NAME,
        elapsed_seconds=0.0,
        prompt_tokens=None,
        reply_tokens=None,
        finish=FinishReason.STOPPED,
    )
