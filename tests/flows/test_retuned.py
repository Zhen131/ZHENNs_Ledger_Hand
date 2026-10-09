"""Tests of a passage retuned half-way: the settings changed while it was being recorded.

From the next step on, the model is called as the new tuning says; nothing
else about the passage changes. Every passage and reply below is invented.
"""

from __future__ import annotations

import dataclasses

from ledger_hand.flows.progress import DEFAULT_TUNING, Stage, Tuning
from ledger_hand.flows.recording import answer, retuned
from ledger_hand.ports import ModelParameters
from tests.fakes.routed_model import RoutedModel
from tests.flows.scripted_flow import begin, row, screened, table

SPOT = screened(("spot_trade", "Bought 0.5 ETH"))
# Neither the fee nor the time: two questions, one after the other.
PASSAGE = "Bought 0.5 ETH at 3,420"
ROWS = table(row(side="buy", coin="ETH", quantity="0.5 ETH", price="3,420"))
WARMER = Tuning(
    question_parameters=ModelParameters(
        temperature=0.2, top_p=1.0, max_reply_tokens=64, context_tokens=2048, timeout_seconds=9.0
    )
)


def test_a_retuned_passage_differs_only_in_its_tuning() -> None:
    progress = begin(PASSAGE, RoutedModel(screen=[SPOT], extraction=[ROWS]))

    changed = retuned(progress, WARMER)

    assert changed.setting.tuning == WARMER
    assert changed == dataclasses.replace(
        progress, setting=dataclasses.replace(progress.setting, tuning=WARMER)
    )


def test_the_same_tuning_gives_back_the_same_passage() -> None:
    progress = begin(PASSAGE, RoutedModel(screen=[SPOT], extraction=[ROWS]))

    assert retuned(progress, progress.setting.tuning) is progress


def test_the_next_question_is_worded_as_the_new_tuning_says() -> None:
    model = RoutedModel(screen=[SPOT], extraction=[ROWS])
    progress = begin(PASSAGE, model)
    assert progress.stage is Stage.ASKING
    assert progress.setting.tuning == DEFAULT_TUNING
    asked_before = len(model.question_parameters)

    after = answer(retuned(progress, WARMER), "1 USDT", model)

    assert after.stage is Stage.ASKING
    assert model.question_parameters[asked_before:] == [WARMER.question_parameters]
