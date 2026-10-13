"""Tests of the page when the model fails while reading an answer: its words, then the question.

The same question is asked again, after one plain sentence for the kind of
failure, looked up as every model failure is (``failure_words``), never with
the kind's code. With a cloud plug, a missing model is said the cloud way.
Every passage and reply below is invented; the model is scripted and nothing
reaches the network.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from ledger_hand.ports import ModelError, ModelErrorKind
from ledger_hand.settings import ModelSettings, Plug, Secret
from ledger_hand.ui.failure_words import model_kind_trouble
from tests.fakes.memory_store import MemoryStore
from tests.fakes.routed_model import RoutedModel
from tests.flows.scripted_flow import row, screened, table
from tests.ui.app_harness import program_said, send
from tests.ui.page_harness import open_with

LOCAL = ModelSettings(
    base_url="http://127.0.0.1:59999", model="invented-model:3b", timeout_seconds=45
)
CLOUD = dataclasses.replace(
    LOCAL,
    plug=Plug.CLOUD,
    base_url="http://127.0.0.1:59999/v1",
    api_key=Secret("sk-invented-answer-failures-0123456789"),
)
PASSAGE = "今天下午 3 点买了 0.5 ETH，又卖了 2 个 SOL，价格 150"
ROWS = table(
    row(side="buy", coin="ETH", quantity="0.5 ETH", time="今天下午 3 点"),
    row(side="sell", coin="SOL", quantity="2 个", price="150"),
)
SPOT = screened(("spot_trade", "买了 0.5 ETH"))
# An answer the rules cannot read, so the model is asked to copy the price.
FOR_THE_MODEL = "价格是 3420 刀"
LABEL = "[Trade 1 of 2: price]"


def after_failing(kind: ModelErrorKind, settings: ModelSettings, tmp_path: Path) -> AppTest:
    model = RoutedModel(screen=[SPOT], extraction=[ROWS], answers=[ModelError(kind, "invented")])
    page = send(open_with(model, MemoryStore(), tmp_path / "data", settings=settings), PASSAGE)
    return send(page, FOR_THE_MODEL)


@pytest.mark.parametrize("kind", list(ModelErrorKind))
def test_each_kind_is_said_in_its_own_words_and_the_question_is_asked_again(
    kind: ModelErrorKind, tmp_path: Path
) -> None:
    page = after_failing(kind, LOCAL, tmp_path)

    assert not page.exception
    said = program_said(page)[-1]
    assert model_kind_trouble(kind, LOCAL) in said
    assert kind.value not in said
    assert said.startswith("The model could not be asked to read that answer. ")
    assert LABEL in said
    assert program_said(page)[-2].count(LABEL) == 1


def test_the_sentences_differ_from_kind_to_kind(tmp_path: Path) -> None:
    sentences = [
        program_said(after_failing(kind, LOCAL, tmp_path / kind.value))[-1]
        for kind in ModelErrorKind
    ]

    assert len(set(sentences)) == len(sentences)


def test_a_missing_model_with_the_cloud_plug_is_said_the_cloud_way(tmp_path: Path) -> None:
    page = after_failing(ModelErrorKind.MODEL_NOT_FOUND, CLOUD, tmp_path)

    assert not page.exception
    said = program_said(page)[-1]
    assert model_kind_trouble(ModelErrorKind.MODEL_NOT_FOUND, CLOUD) in said
    assert "http://127.0.0.1:59999/v1" in said
    assert "ollama" not in said.lower()
    assert LABEL in said


def test_an_answer_not_understood_is_said_as_before(tmp_path: Path) -> None:
    model = RoutedModel(screen=[SPOT], extraction=[ROWS])
    page = send(open_with(model, MemoryStore(), tmp_path / "data", settings=LOCAL), PASSAGE)

    page = send(page, "  ")

    said = program_said(page)[-1]
    assert said.startswith("That answer could not be used: no answer was received.")
    assert LABEL in said
