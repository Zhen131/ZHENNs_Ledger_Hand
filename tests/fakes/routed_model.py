"""A stand-in for the model port that answers each kind of call from its own script.

The recording flow calls the model for four things: judging a passage,
extraction, wording a question and reading an answer. Each is told apart by
the JSON schema it sends, and each takes its replies from its own list, in
order, so that a test does not have to know how the calls interleave. A
kind whose list is used up fails the test, except the questions: with no
scripted question left, wording one fails as the model being unreachable,
so the program's own sentence is used and the transcript stays readable.

A call with pictures, reading a screenshot, sends no schema; every such call
takes its reply from a list of its own, ``pictures``, and a call after the
last one scripted fails the test.

A call with tools takes its reply from a list of its own, ``tools``, too.

Picking an asset from the ledger's list takes its replies from ``picks``;
with none scripted left, it fails as the model being unreachable, so the
trade goes on as if nothing had been picked, as it did before the step
was there.

Names defined here: ``RoutedModel``.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from ledger_hand.asking.question_text import QUESTION_TABLE
from ledger_hand.extraction.answer_table import ANSWER_TABLE
from ledger_hand.extraction.asset_picking import PICK_TABLE
from ledger_hand.extraction.reply_table import REPLY_TABLE
from ledger_hand.extraction.screen_table import SCREEN_TABLE
from ledger_hand.ports import (
    ChatItem,
    JsonSchema,
    Message,
    ModelError,
    ModelErrorKind,
    ModelParameters,
    ModelReply,
    Picture,
    ToolReply,
    ToolSpec,
)
from tests.fakes.scripted_model import ScriptedModel, Step


class RoutedModel:
    """A model port with one scripted model per kind of call."""

    def __init__(
        self,
        *,
        screen: Iterable[Step] = (),
        extraction: Iterable[Step] = (),
        questions: Iterable[Step] = (),
        answers: Iterable[Step] = (),
        pictures: Iterable[Step] = (),
        tools: Iterable[Step] = (),
        picks: Iterable[Step] = (),
    ) -> None:
        self.screen = ScriptedModel(screen)
        self.extraction = ScriptedModel(extraction)
        self.questions = ScriptedModel(questions)
        self.answers = ScriptedModel(answers)
        self.pictures = ScriptedModel(pictures)
        self.tools = ScriptedModel(tools)
        self.picks = ScriptedModel(picks)
        # The parameters of every attempt to word a question, scripted or not.
        self.question_parameters: list[ModelParameters | None] = []

    def chat(
        self,
        messages: Sequence[Message],
        *,
        reply_schema: JsonSchema | None = None,
        parameters: ModelParameters | None = None,
    ) -> ModelReply:
        routes = {
            id(SCREEN_TABLE): self.screen,
            id(REPLY_TABLE): self.extraction,
            id(QUESTION_TABLE): self.questions,
            id(ANSWER_TABLE): self.answers,
            id(PICK_TABLE): self.picks,
        }
        scripted = routes.get(id(reply_schema))
        if scripted is None:
            raise AssertionError(f"a call with an unknown schema: {reply_schema!r}")
        if scripted is self.questions:
            self.question_parameters.append(parameters)
            if scripted.steps_left == 0:
                raise ModelError(ModelErrorKind.UNREACHABLE, "no question is scripted")
        if scripted is self.picks and scripted.steps_left == 0:
            raise ModelError(ModelErrorKind.UNREACHABLE, "no pick is scripted")
        return scripted.chat(messages, reply_schema=reply_schema, parameters=parameters)

    def chat_with_pictures(
        self,
        messages: Sequence[Message],
        pictures: Sequence[Picture],
        *,
        parameters: ModelParameters | None = None,
    ) -> ModelReply:
        return self.pictures.chat_with_pictures(messages, pictures, parameters=parameters)

    def chat_with_tools(
        self,
        items: Sequence[ChatItem],
        tools: Sequence[ToolSpec],
        *,
        parameters: ModelParameters | None = None,
    ) -> ToolReply:
        return self.tools.chat_with_tools(items, tools, parameters=parameters)
