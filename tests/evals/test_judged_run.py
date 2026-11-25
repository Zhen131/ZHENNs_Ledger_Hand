"""Tests of scoring the extraction sets through the start of recording.

What the start of recording gives is handed to the scorer as extraction
alone would be: a model failure as one, a passage judged to hold no trade
as no draft; and the fields wrong with nothing said are counted as the
tables count them. A scripted model stands in; every reply is invented.
"""

from __future__ import annotations

from evals.gold import DEBUG_SET, Split, load_set
from evals.judged_run import SCREENS, produced_of, silent_wrong
from evals.scoring import ResultKind, score_sentence
from ledger_hand.core.assets import BUILT_IN_ASSETS
from ledger_hand.flows.progress import Progress, Setting, Stage
from ledger_hand.flows.recording import start
from ledger_hand.ports import ModelError, ModelErrorKind
from tests.fakes.routed_model import RoutedModel
from tests.flows.scripted_flow import screened

SENTENCE = next(one for one in load_set(DEBUG_SET, Split.DEBUG) if one.trades)


def test_both_judging_versions_can_be_named() -> None:
    assert sorted(SCREENS) == ["screen-1", "screen-2"]


def test_a_passage_judged_to_hold_no_trade_gives_no_draft_and_nothing_wrong() -> None:
    model = RoutedModel(screen=[screened()])
    progress = start(SENTENCE.text, model, now=SENTENCE.now, zone=SENTENCE.zone)

    produced = produced_of(progress)

    assert progress.stage is Stage.NO_TRADE
    assert (produced.kind, produced.drafts) == (ResultKind.EXTRACTED, ())
    score = score_sentence(SENTENCE, produced)
    assert score.whole_right == 0
    assert silent_wrong(score) == 0


def test_a_model_failure_is_scored_as_one() -> None:
    failure = ModelError(ModelErrorKind.UNREACHABLE, "not running")
    model = RoutedModel(screen=[failure] * 4)
    progress = start(SENTENCE.text, model, now=SENTENCE.now, zone=SENTENCE.zone)

    assert produced_of(progress).kind is ResultKind.MODEL_FAILED


def test_a_refused_passage_is_scored_as_one() -> None:
    setting = Setting(SENTENCE.now, SENTENCE.zone, BUILT_IN_ASSETS)

    assert produced_of(Progress(Stage.REFUSED, "", setting)).kind is ResultKind.PASSAGE_REFUSED
