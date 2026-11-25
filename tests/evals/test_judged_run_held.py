"""Tests of what the judged run adds for each draft: its reminders, whether it is whole, if held.

Holding back a quantity said in another unit changes nothing scored: the
drafts are scored as extracted, and the line says which were held. A
scripted model stands in; every reply is invented.
"""

from __future__ import annotations

from evals.gold import DEBUG_SET, Split, load_set
from evals.judged_run import held_of, produced_of, reminders_of, whole_right_of
from evals.scoring import SentenceScore, score_sentence
from ledger_hand.flows.progress import Progress
from ledger_hand.flows.recording import start
from tests.extraction.scripted_runs import row, table
from tests.fakes.routed_model import RoutedModel
from tests.flows.scripted_flow import screened

SENTENCE = next(one for one in load_set(DEBUG_SET, Split.DEBUG) if one.trades)
U25 = row(side="buy", coin="ETH", quantity="25U", price="2,388", time="今天下午3点", platform="OKX")


def _started(*, hold: bool) -> tuple[Progress, SentenceScore]:
    model = RoutedModel(screen=[screened(("spot_trade", "x"))], extraction=[table(U25)])
    progress = start(
        "今天下午3点OKX顺手25U买了点ETH，2,388一个",
        model,
        now=SENTENCE.now,
        zone=SENTENCE.zone,
        hold_other_unit=hold,
    )
    return progress, score_sentence(SENTENCE, produced_of(progress))


def test_a_held_trade_is_named_and_scored_as_extracted() -> None:
    held, held_score = _started(hold=True)
    kept, kept_score = _started(hold=False)

    assert held_of(held) == [0]
    assert held_of(kept) == []
    assert held_score == kept_score


def test_each_draft_names_its_kinds_of_reminder() -> None:
    progress, score = _started(hold=True)

    by_draft, passage = reminders_of(progress)

    assert by_draft == [["UNIT_NOT_THE_COIN"]]
    assert passage == ["NUMBERS_LEFT_OVER"]
    assert len(whole_right_of(score, 1)) == 1
