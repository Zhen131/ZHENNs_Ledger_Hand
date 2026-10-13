"""Gate: the comparison of two models in the record is what its results files give.

The record shows, for each of the three sets both models ran (debug, final,
voice), the comparison of the two runs (``compare_models``); the runs of
``qwen2.5:7b`` against its earlier runs of the same sets, sentence by
sentence (``same_replies``); and the parameter comparisons of
``qwen3-vl:8b`` beside the run they change one parameter of. Each is worked
out again here from the results files named below and must stand in the
record exactly. Only the files named here are read; the results directory
is not scanned, so a run made later for another purpose cannot change what
this gate checks.

The first line of each run must show what the run was: the model and the
set it was meant to run, the final-exam switch on for the final set only,
the prompt ``first`` read in one list, a clean work tree, the model server
on this machine, and the same set file, prompt content and reply table as
the second experiment's runs. Every run of a model has the same parameters
and the same fingerprint, written here; the two models have the same
parameters. That each fingerprint is the one the model server lists is
checked by hand: no test here asks the server. No model is called.
"""

from __future__ import annotations

import pytest

from evals.compare import row_of, rows_markdown
from evals.compare_models import comparison_markdown
from evals.records import Results, read_results
from evals.run import RESULTS_DIR
from evals.same_replies import compare_markdown, compare_runs

RECORD = RESULTS_DIR.parent / "RESULTS.md"
HEADING = "## 2026-10-13: second model, `qwen2.5:7b` and `qwen3-vl:8b`"
FIRST_MODEL = "qwen2.5:7b"
SECOND_MODEL = "qwen3-vl:8b"
FINGERPRINTS = {
    FIRST_MODEL: "845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e",
    SECOND_MODEL: "901cae73216286ea8c5aba8b46d307ff7188f737285ec500c795a12f05225d28",
}
# Each set's two runs: the first model's, then the second model's.
RUNS = {
    "debug": (
        "run-20261013T092724Z-debug-first.jsonl",
        "run-20261013T093206Z-debug-first.jsonl",
    ),
    "final": (
        "run-20261013T093036Z-final-first.jsonl",
        "run-20261013T100136Z-final-first.jsonl",
    ),
    "voice": (
        "run-20261013T092941Z-voice-first.jsonl",
        "run-20261013T095344Z-voice-first.jsonl",
    ),
}
# The second experiment's run of the debug set, and the first experiment's run of the
# final set: the earlier runs of the first model, with the same prompt and way.
EARLIER = {
    "debug": "run-20261009T055241Z-debug-first.jsonl",
    "final": "run-20261009T030436Z-final-first.jsonl",
}
# The parameter comparisons of the second model on the debug set: each file with the
# one parameter it changes from the run of the second model above.
PARAMETER_RUNS = (
    ("run-20261013T101512Z-debug-first.jsonl", "max_reply_tokens"),
    ("run-20261013T105345Z-debug-first.jsonl", "max_reply_tokens"),
)


def record() -> str:
    return RECORD.read_text(encoding="utf-8")


def results(name: str) -> Results:
    return read_results(RESULTS_DIR / name)


def every_run() -> list[tuple[str, str, str]]:
    """Each run of the comparison: its file, the set it ran and the model."""
    named = [
        (name, chosen, model)
        for chosen, pair in RUNS.items()
        for name, model in zip(pair, (FIRST_MODEL, SECOND_MODEL), strict=True)
    ]
    named += [(name, "debug", SECOND_MODEL) for name, _ in PARAMETER_RUNS]
    return named


@pytest.mark.parametrize(("name", "chosen", "model"), every_run(), ids=lambda x: str(x))
def test_each_run_is_what_it_was_meant_to_be(name: str, chosen: str, model: str) -> None:
    run = results(name)
    head = run.run

    assert run.end is not None
    assert "only" not in head
    assert (head["model"], head["model_fingerprint"]) == (model, FINGERPRINTS[model])
    assert (head["set"], head["final_exam_switch"]) == (chosen, chosen == "final")
    assert (head["prompt"], head["method"]) == ("first", "one_list")
    assert head["worktree_clean"] is True
    assert head["base_url"] == "http://127.0.0.1:11434"
    shared = results(EARLIER["debug"]).run
    for key in ("prompt_content_sha256", "reply_table_sha256"):
        assert head[key] == shared[key], key
    if chosen in EARLIER:
        assert head["set_sha256"] == results(EARLIER[chosen]).run["set_sha256"]


def test_every_run_of_the_matrix_has_the_same_parameters() -> None:
    heads = [results(name).run for pair in RUNS.values() for name in pair]

    assert all(head["parameters"] == heads[0]["parameters"] for head in heads)


def test_each_parameter_comparison_changes_one_parameter_of_the_second_models_debug_run() -> None:
    base = results(RUNS["debug"][1]).run["parameters"]
    assert isinstance(base, dict)

    for name, parameter in PARAMETER_RUNS:
        changed = results(name).run["parameters"]
        assert isinstance(changed, dict)
        differing = sorted(key for key in {*base, *changed} if base.get(key) != changed.get(key))
        assert differing == [parameter], name


@pytest.mark.parametrize("chosen", list(RUNS))
def test_the_record_shows_the_comparison_of_each_set(chosen: str) -> None:
    first, second = RUNS[chosen]
    text = comparison_markdown(
        results(first),
        results(second),
        (f"evals/results/{first}", f"evals/results/{second}"),
    )

    assert text in record()


@pytest.mark.parametrize("chosen", list(EARLIER))
def test_the_record_shows_the_first_model_against_its_earlier_run(chosen: str) -> None:
    compared = compare_runs(results(EARLIER[chosen]), results(RUNS[chosen][0]))

    assert compare_markdown(compared) in record()


def test_the_record_shows_each_parameter_comparison_beside_the_run_it_changes() -> None:
    base = RUNS["debug"][1]

    for name, _ in PARAMETER_RUNS:
        rows = [row_of(results(each), f"evals/results/{each}") for each in (base, name)]
        assert rows_markdown(rows) in record()


def test_the_section_is_in_the_record_after_every_earlier_one() -> None:
    text = record()

    assert text.count(HEADING) == 1
    assert "\n## " not in text[text.index(HEADING) + len(HEADING) :]
