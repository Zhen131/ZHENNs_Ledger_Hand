"""Tests of the kind of the model's failure kept on a question asked again.

When an answer cannot be read because the model could not be asked to read
it, the same question is asked again, with the reason in words as before
and, beside it, the kind of the model's failure, for the interface to say in
its own words. Any other reason to ask again, a new question, or none at all
leaves that kind empty. Every passage and reply below is invented.
"""

from __future__ import annotations

import pytest

from ledger_hand.extraction.answer_phrase import AnswerProblem
from ledger_hand.flows.progress import Stage
from ledger_hand.flows.recording import answer
from ledger_hand.ports import ModelError, ModelErrorKind
from tests.fakes.routed_model import RoutedModel
from tests.flows.scripted_flow import begin, copied, row, screened, table

TWO_TRADES = "今天下午 3 点买了 0.5 ETH，又卖了 2 个 SOL，价格 150"
TWO_ROWS = table(
    row(side="buy", coin="ETH", quantity="0.5 ETH", time="今天下午 3 点"),
    row(side="sell", coin="SOL", quantity="2 个", price="150"),
)
SPOT = screened(("spot_trade", "买了 0.5 ETH"))
# An answer the rules cannot read, so the model is asked to copy the price.
FOR_THE_MODEL = "价格是 3420 刀"


@pytest.mark.parametrize("kind", list(ModelErrorKind))
def test_the_kind_is_kept_then_emptied_by_any_other_reason_and_by_the_next_question(
    kind: ModelErrorKind,
) -> None:
    model = RoutedModel(
        screen=[SPOT], extraction=[TWO_ROWS], answers=[ModelError(kind, "invented")]
    )
    first = begin(TWO_TRADES, model)
    assert first.question is not None and first.question.model_failure is None

    failed = answer(first, FOR_THE_MODEL, model)
    unread = answer(failed, "  ", model)
    next_one = answer(unread, "3420", model)

    assert failed.stage is Stage.ASKING and failed.question is not None
    assert failed.question.asked == first.question.asked
    assert failed.question.model_failure is kind
    assert failed.question.again == f"{AnswerProblem.MODEL_FAILED.value} ({kind.value})"
    assert unread.question is not None
    assert unread.question.asked == first.question.asked
    assert unread.question.model_failure is None
    assert unread.question.again == "no answer was received"
    assert next_one.question is not None
    assert next_one.question.asked != first.question.asked
    assert next_one.question.model_failure is None
    assert next_one.question.again is None


def test_a_reply_about_the_answer_that_cannot_be_used_keeps_no_kind() -> None:
    model = RoutedModel(screen=[SPOT], extraction=[TWO_ROWS], answers=[copied("3,000")])

    after = answer(begin(TWO_TRADES, model), FOR_THE_MODEL, model)

    assert after.question is not None
    assert after.question.again == "the model picked out words that are not in the answer"
    assert after.question.model_failure is None


def test_a_failure_then_a_good_answer_moves_on_with_no_kind() -> None:
    model = RoutedModel(
        screen=[SPOT],
        extraction=[TWO_ROWS],
        answers=[ModelError(ModelErrorKind.TIMED_OUT, "invented"), copied("3420 刀")],
    )
    first = begin(TWO_TRADES, model)

    failed = answer(first, FOR_THE_MODEL, model)
    read = answer(failed, FOR_THE_MODEL, model)

    assert failed.question is not None and failed.question.model_failure is ModelErrorKind.TIMED_OUT
    assert read.question is not None and first.question is not None
    assert read.question.asked != first.question.asked
    assert read.question.model_failure is None
