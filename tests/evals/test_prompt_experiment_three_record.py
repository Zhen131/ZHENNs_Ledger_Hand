"""Gate: the third prompt experiment in the record is what its results files give.

The record shows, for each of the three sets the versions ran (debug, voice,
writings), the comparison of the runs of ``first`` and of each candidate
(``compare_sets``); for each candidate, the rule applied to its runs and
those of ``first``; and the runs of ``first`` against its earlier runs of
the same sets, sentence by sentence (``same_replies``). Each is worked out
again here from the results files named below and must stand in the record
exactly. Only the files named here are read; the results directory is not
scanned, so a run made later for another purpose cannot change what this
gate checks.

The first line of each run must show what the run was: ``qwen2.5:7b`` with
the fingerprint written here, the set and the prompt it was meant to run,
the final-exam switch off, one list, a clean work tree and the model server
on this machine; the parameters and the reply table of the comparison of
two models' run of the debug set; for ``first``, the content fingerprint of
the baseline; and the set file of the earlier runs of the same set. That
the fingerprint is the one the model server lists is checked by hand: no
test here asks the server. No model is called.
"""

from __future__ import annotations

import pytest

from evals.compare_sets import RULE, choice_markdown, choose, sets_markdown
from evals.records import Results, read_results
from evals.run import RESULTS_DIR
from evals.same_replies import compare_markdown, compare_runs
from tests.evals.test_run_versions import FIRST_CONTENT_SHA256

RECORD = RESULTS_DIR.parent / "RESULTS.md"
HEADING = (
    "## 2026-10-18: prompt experiment three, more examples for the owner's way of writing, "
    "`qwen2.5:7b`"
)
EARLIER_HEADING = "## 2026-10-13: second model, `qwen2.5:7b` and `qwen3-vl:8b`"
MODEL = "qwen2.5:7b"
FINGERPRINT = "845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e"
CANDIDATES = ("second", "third")
# Each set's runs, one per version: first, then each candidate.
RUNS = {
    "debug": {
        "first": "run-20261018T173752Z-debug-first.jsonl",
        "second": "run-20261018T174235Z-debug-second.jsonl",
        "third": "run-20261019T074847Z-debug-third.jsonl",
    },
    "voice": {
        "first": "run-20261018T174017Z-voice-first.jsonl",
        "second": "run-20261018T174449Z-voice-second.jsonl",
        "third": "run-20261019T075107Z-voice-third.jsonl",
    },
    "writings": {
        "first": "run-20261018T174114Z-writings-first.jsonl",
        "second": "run-20261018T174542Z-writings-second.jsonl",
        "third": "run-20261019T075208Z-writings-third.jsonl",
    },
}
# The earlier runs of first on each set: the comparison of two models' runs of the debug
# and the voice set, and the first prompt experiment's run of the writings set.
EARLIER = {
    "debug": "run-20261013T092724Z-debug-first.jsonl",
    "voice": "run-20261013T092941Z-voice-first.jsonl",
    "writings": "run-20261009T024502Z-writings-first.jsonl",
}


def record() -> str:
    return RECORD.read_text(encoding="utf-8")


def results(name: str) -> Results:
    return read_results(RESULTS_DIR / name)


def every_run() -> list[tuple[str, str, str]]:
    """Each run of the experiment: its file, the set it ran and the prompt."""
    return [
        (name, chosen, prompt) for chosen, runs in RUNS.items() for prompt, name in runs.items()
    ]


@pytest.mark.parametrize(("name", "chosen", "prompt"), every_run(), ids=lambda x: str(x))
def test_each_run_is_what_it_was_meant_to_be(name: str, chosen: str, prompt: str) -> None:
    run = results(name)
    head = run.run
    base = results(EARLIER["debug"]).run

    assert run.end is not None
    assert "only" not in head
    assert (head["model"], head["model_fingerprint"]) == (MODEL, FINGERPRINT)
    assert (head["set"], head["prompt"], head["final_exam_switch"]) == (chosen, prompt, False)
    assert head["method"] == "one_list"
    assert head["worktree_clean"] is True
    assert head["base_url"] == "http://127.0.0.1:11434"
    assert head["parameters"] == base["parameters"]
    assert head["reply_table_sha256"] == base["reply_table_sha256"]
    assert head["set_sha256"] == results(EARLIER[chosen]).run["set_sha256"]
    if prompt == "first":
        assert head["prompt_content_sha256"] == FIRST_CONTENT_SHA256


def test_every_run_has_the_same_server_and_each_version_one_content() -> None:
    heads = [results(name).run for name, _, _ in every_run()]

    assert {head["server_version"] for head in heads} == {"0.34.3"}
    for prompt in ("first", *CANDIDATES):
        contents = {results(runs[prompt]).run["prompt_content_sha256"] for runs in RUNS.values()}
        assert len(contents) == 1, prompt


@pytest.mark.parametrize("chosen", list(RUNS))
def test_the_record_shows_the_versions_on_each_set(chosen: str) -> None:
    runs = [(results(name), f"evals/results/{name}") for name in RUNS[chosen].values()]

    assert sets_markdown(runs) in record()


@pytest.mark.parametrize("candidate", CANDIDATES)
def test_the_record_shows_the_rule_applied_to_each_candidate(candidate: str) -> None:
    runs = [results(each[name]) for each in RUNS.values() for name in ("first", candidate)]

    assert choice_markdown(choose(runs)) in record()


def section() -> str:
    """The section of the experiment: from its heading to the next heading of two marks."""
    text = record()
    start = text.index(HEADING)
    end = text.find("\n## ", start + len(HEADING))
    return text[start:] if end == -1 else text[start:end]


def test_the_record_shows_the_rule_once_more_as_it_was_fixed() -> None:
    assert section().count(RULE.rstrip("\n")) == 1 + len(CANDIDATES)


@pytest.mark.parametrize("chosen", list(EARLIER))
def test_the_record_shows_first_against_its_earlier_run(chosen: str) -> None:
    compared = compare_runs(results(EARLIER[chosen]), results(RUNS[chosen]["first"]))

    assert compare_markdown(compared) in record()


def test_the_section_stands_once_after_the_comparison_of_two_models() -> None:
    text = record()

    assert text.count(HEADING) == 1
    assert text.index(EARLIER_HEADING) < text.index(HEADING)
