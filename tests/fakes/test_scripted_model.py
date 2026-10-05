"""Tests of the scripted stand-in for the model port."""

from __future__ import annotations

import pytest

from ledger_hand.ports import (
    FinishReason,
    Message,
    ModelError,
    ModelErrorKind,
    ModelParameters,
    ModelPort,
    ModelReply,
    ReplyRecord,
    Role,
)
from tests.fakes.scripted_model import (
    SCRIPTED_MODEL_NAME,
    RecordedCall,
    ScriptedModel,
    ScriptExhaustedError,
)

HELLO = [Message(Role.USER, "Say hello to the invented shop owner.")]
SCHEMA = {"type": "object", "properties": {"greeting": {"type": "string"}}}
PARAMETERS = ModelParameters(
    temperature=0.2, top_p=0.9, max_reply_tokens=16, context_tokens=512, timeout_seconds=3
)


def ask(model: ModelPort, text: str) -> str:
    """Code under test only knows the port; this checks the fake fits it."""
    return model.chat([Message(Role.USER, text)]).text


def test_three_steps_come_back_in_order_and_a_fourth_call_is_refused() -> None:
    model = ScriptedModel(["one", "two", "three"])

    assert [ask(model, "first"), ask(model, "second"), ask(model, "third")] == [
        "one",
        "two",
        "three",
    ]
    with pytest.raises(ScriptExhaustedError, match="script is used up"):
        ask(model, "fourth")
    assert [call.messages[0].content for call in model.calls] == ["first", "second", "third"]
    assert model.steps_left == 0


def test_every_call_is_recorded_with_what_it_was_sent() -> None:
    model = ScriptedModel(["a", "b"])

    model.chat(HELLO, reply_schema=SCHEMA, parameters=PARAMETERS)
    model.chat(HELLO)

    assert model.calls == [
        RecordedCall(tuple(HELLO), SCHEMA, PARAMETERS),
        RecordedCall(tuple(HELLO), None, None),
    ]


def test_a_text_step_comes_back_with_a_plain_record() -> None:
    reply = ScriptedModel(["text"]).chat(HELLO)

    assert reply.text == "text"
    assert reply.record.model == SCRIPTED_MODEL_NAME
    assert reply.record.finish is FinishReason.STOPPED
    assert reply.record.prompt_tokens is None


def test_an_error_step_is_raised_and_the_call_is_still_recorded() -> None:
    error = ModelError(ModelErrorKind.RATE_LIMITED, "slow down")
    model = ScriptedModel([error, "after the wait"])

    with pytest.raises(ModelError) as caught:
        model.chat(HELLO)
    assert caught.value is error
    assert model.chat(HELLO).text == "after the wait"
    assert len(model.calls) == 2


def test_a_whole_reply_step_comes_back_as_it_is() -> None:
    record = ReplyRecord(
        model="m",
        elapsed_seconds=1.5,
        prompt_tokens=10,
        reply_tokens=2,
        finish=FinishReason.LENGTH_LIMIT,
    )
    reply = ModelReply(text="cut", record=record)

    assert ScriptedModel([reply]).chat(HELLO) is reply


def test_an_empty_script_refuses_the_first_call() -> None:
    model = ScriptedModel([])

    with pytest.raises(ScriptExhaustedError, match="0 step"):
        model.chat(HELLO)
    assert model.calls == []


def test_a_step_of_another_type_is_refused_up_front() -> None:
    with pytest.raises(TypeError):
        ScriptedModel(["fine", 42])  # type: ignore[list-item]


def test_a_used_up_script_is_an_assertion_failure_not_a_model_error() -> None:
    model = ScriptedModel([])

    with pytest.raises(AssertionError):
        model.chat(HELLO)
    assert not issubclass(ScriptExhaustedError, ModelError)
