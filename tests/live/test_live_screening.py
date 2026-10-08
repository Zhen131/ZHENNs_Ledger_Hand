"""The live check of judging a passage: the debug set through the real model.

Marked ``live_model``, so ordinary runs leave it out; ``scripts/check.sh
live`` runs it, with the settings read from the environment as the program
reads them. It needs the model server running and the model there. Only the
debug set is read; the final set is never sent to a model here.

- The four debug sentences that report only what the ledger does not record
  (leverage, one coin for another, an order not filled, a plan) go through
  the start of recording, each with its own moment and zone. Each must be
  stopped: nothing extracted, no question asked, at least one reason given.
  The kind the model named is printed beside the kind the sentence was
  written as; a different kind does not fail the check.
- The other debug sentences are only judged, and where each would go is
  printed (stopped, no trade, on to extraction). Nothing is checked about
  where they go: these are numbers to read, not a bar to pass.

If a model or a version of the model server stops these four from being
stopped, that is a finding to report, not a test to loosen.
"""

from __future__ import annotations

import time

import pytest

from evals.gold import DEBUG_SET, Group, Sentence, Split, load_set
from ledger_hand.extraction.screening import Screened, screen
from ledger_hand.flows.progress import Stage, Step
from ledger_hand.flows.recording import start
from ledger_hand.llm.local import connect_local_model
from ledger_hand.settings import load_model_settings

pytestmark = pytest.mark.live_model

DEBUG = load_set(DEBUG_SET, Split.DEBUG)
NOT_TO_RECORD = [s for s in DEBUG if s.group is Group.NOT_TO_RECORD]
THE_REST = [s for s in DEBUG if s.group is not Group.NOT_TO_RECORD]


def test_the_four_sentences_not_to_record_are_the_ones_expected() -> None:
    assert [s.id for s in NOT_TO_RECORD] == ["d27", "d28", "d29", "d30"]
    assert len(THE_REST) == 26


@pytest.mark.parametrize("sentence", NOT_TO_RECORD, ids=lambda s: s.id)
def test_a_sentence_of_only_what_is_not_recorded_is_stopped(sentence: Sentence) -> None:
    model = connect_local_model(load_model_settings())

    began = time.monotonic()
    progress = start(sentence.text, model, now=sentence.now, zone=sentence.zone)
    took = time.monotonic() - began

    kinds = [report.kind.value for report in progress.stopped]
    evidence = [report.evidence for report in progress.stopped]
    expected = sentence.kind.value if sentence.kind is not None else None
    print(
        f"\n{sentence.id} | {progress.stage.name} | model: {kinds} | written as: {expected}"
        f" | evidence: {evidence} | {took:.1f} s"
    )
    if progress.stage is Stage.FAILED:
        pytest.fail(f"the live check could not talk to the model: {progress.failure}")
    assert progress.stage is Stage.STOPPED
    assert progress.question is None
    assert progress.trades == ()
    assert {call.step for call in progress.calls} == {Step.SCREENING}
    assert progress.stopped


@pytest.mark.parametrize("sentence", THE_REST, ids=lambda s: s.id)
def test_the_other_sentences_are_judged_and_where_they_go_is_printed(sentence: Sentence) -> None:
    model = connect_local_model(load_model_settings())

    began = time.monotonic()
    judged = screen(sentence.text, model)
    took = time.monotonic() - began

    if not isinstance(judged, Screened):
        pytest.fail(f"the passage could not be judged: {judged}")
    reports = [(report.kind.value, report.evidence) for report in judged.reports]
    print(
        f"\n{sentence.id} | trades in gold: {len(sentence.trades)} | {judged.decision.name}"
        f" | {reports} | {took:.1f} s"
    )
