"""A stand-in for the model port that answers each kind of call from its own script.

The recording flow calls the model for four things: judging a passage,
extraction, wording a question and reading an answer. Each is told apart by
the JSON schema it sends, and each takes its replies from its own list, in
order, so that a test does not have to know how the calls interleave. A
kind whose list is used up fails the test, except the questions: with no
scripted question left, wording one fails as the model being unreachable,
so the program's own sentence is used and the transcript stays readable.

Names defined here: ``RoutedModel``.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from ledger_hand.asking.question_text import QUESTION_TABLE
from ledger_hand.extraction.answer_table import ANSWER_TABLE
from ledger_hand.extraction.reply_table import REPLY_TABLE
from ledger_hand.extraction.screen_table import SCREEN_TABLE
from ledger_hand.ports import (
    JsonSchema,
    Message,
    ModelError,
    ModelErrorKind,
    ModelParameters,
    ModelReply,
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
    ) -> None:
        self.screen = ScriptedModel(screen)
        self.extraction = ScriptedModel(extraction)
        self.questions = ScriptedModel(questions)
        self.answers = ScriptedModel(answers)
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
        }
        scripted = routes.get(id(reply_schema))
        if scripted is None:
            raise AssertionError(f"a call with an unknown schema: {reply_schema!r}")
        if scripted is self.questions:
            self.question_parameters.append(parameters)
            if scripted.steps_left == 0:
                raise ModelError(ModelErrorKind.UNREACHABLE, "no question is scripted")
        return scripted.chat(messages, reply_schema=reply_schema, parameters=parameters)
