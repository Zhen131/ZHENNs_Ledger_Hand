"""The live check of the deepseek plug: DeepSeek itself, with the key set on this machine.

Each test is marked ``live_cloud`` on its own, so ordinary runs leave it out
and ``scripts/check.sh cloud`` runs it. It costs a little money. Without
``DEEPSEEK_API_KEY`` set, each is skipped and says so. Only invented
sentences are sent, against the demo ledger; nothing is printed, so neither
the key nor what DeepSeek answers reaches the output.

- A table asked for as a JSON object comes back as one the program reads,
  and DeepSeek takes the prompt's words as they are.
- One thing said to the whole assistant: DeepSeek calls a tool, the result
  goes back under this side's id, and the turn ends in words.
- A model name DeepSeek does not have is said as a missing model, sending
  no reply worth paying for.
"""

from __future__ import annotations

import dataclasses
import os

import pytest

from ledger_hand.extraction.extractor import Extracted, extract
from ledger_hand.flows.conversation import AssistantChat, Route, say
from ledger_hand.ledger.demo_euro import demo_ledger_with_euro_rates
from ledger_hand.ledger.invented_book import INVENTED_NOW, INVENTED_ZONE
from ledger_hand.llm.cloud import reply_format_now
from ledger_hand.llm.connect import connect_model
from ledger_hand.ports import Message, ModelError, ModelErrorKind, Role
from ledger_hand.settings import (
    ModelSettings,
    Plug,
    ReplyFormat,
    Variable,
    effective_settings,
    load_model_settings,
)

ONE_BUY = "Bought 0.004 BTC at 63250 USDT on OKX on 20 November 2026 at 14:20, fee 0.25 USDT."
HOLDINGS = "Which coins and shares am I holding at the moment?"


def deepseek() -> ModelSettings:
    if not os.environ.get(Variable.DEEPSEEK_KEY.value, "").strip():
        pytest.skip(f"{Variable.DEEPSEEK_KEY.value} is not set, so DeepSeek cannot be asked")
    read = load_model_settings({**os.environ, Variable.PLUG.value: Plug.DEEPSEEK.value})
    return effective_settings(read)


@pytest.mark.live_cloud
def test_a_table_comes_back_as_a_json_object_the_program_reads() -> None:
    settings = deepseek()

    result = extract(ONE_BUY, connect_model(settings), now=INVENTED_NOW, zone=INVENTED_ZONE)

    assert isinstance(result, Extracted)
    (draft,) = result.drafts
    assert draft.coin == "BTC"
    assert reply_format_now(Plug.DEEPSEEK) is ReplyFormat.JSON_OBJECT


@pytest.mark.live_cloud
def test_the_assistant_calls_a_tool_and_answers_in_words() -> None:
    settings = deepseek()

    said = say(
        AssistantChat(),
        HOLDINGS,
        model=connect_model(settings),
        ledger=demo_ledger_with_euro_rates(),
        now=INVENTED_NOW,
        zone=INVENTED_ZONE,
        max_steps=6,
    )

    assert said.route is Route.MODEL
    assert said.turn is not None and said.turn.failure is None
    called = [taken.call.name for step in said.turn.steps for taken in step.calls]
    assert "get_positions" in called
    assert said.reply.strip()


@pytest.mark.live_cloud
def test_a_model_deepseek_does_not_have_is_said_as_missing() -> None:
    settings = dataclasses.replace(deepseek(), model="invented-model-x")

    with pytest.raises(ModelError) as caught:
        connect_model(settings).chat([Message(Role.USER, "hi")])

    assert caught.value.kind is ModelErrorKind.MODEL_NOT_FOUND
    assert caught.value.snippet is None
