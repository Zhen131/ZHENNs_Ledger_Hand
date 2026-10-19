"""Gate: the thinking switch in the record is what its results files give, and so is the default.

``qwen3-vl:8b`` ran the debug set and the voice set with thinking off. Each
run is compared with the run of the same set from the second-model
comparison, which sent no think field (``compare_models`` with
``--parameter think``); the comparison is worked out again here and must
stand in the record exactly. Only the files named here are read; the
results directory is not scanned.

The first line of each run must show what the run was: the model and the
fingerprint written here, the set it was meant to run, prompt ``first``, one
list, the final-exam switch off, a clean work tree and the model server on
this machine; the same server version, set file, prompt content and reply
table as the earlier run; and the same parameters but one, ``think``, off.
That the fingerprint is the one the model server lists is checked by hand:
no test here asks the server.

The rule, fixed before the runs, is applied again here from the summaries
of the two runs of the debug set: when thinking off gets at least as many
trades whole as nothing sent, the default is off, and only after a guard run
of ``qwen2.5:7b``; when it gets fewer, the default stays model. The default
the settings use must be the one the rule gives, and the record must say the
guard run was not made when the rule kept model. No model is called.
"""

from __future__ import annotations

import json
from collections.abc import Mapping

import pytest

from evals.compare_models import comparison_markdown
from evals.records import Results, read_results
from evals.run import RESULTS_DIR
from evals.summarize import summary_path
from ledger_hand.settings import ABOUT, DEFAULT_THINK, Thinking, Variable
from tests.evals.test_model_comparison_record import RUNS as SECOND_MODEL_RUNS
from tests.evals.test_prompt_experiment_four_record import HEADING as FOUR_HEADING

RECORD = RESULTS_DIR.parent / "RESULTS.md"
HEADING = "## 2026-10-19: the thinking switch, `qwen3-vl:8b`"
MODEL = "qwen3-vl:8b"
FINGERPRINT = "901cae73216286ea8c5aba8b46d307ff7188f737285ec500c795a12f05225d28"
PARAMETER = "think"
# Each set's two runs: the earlier one, which sent no think field, then the one with it off.
RUNS: Mapping[str, tuple[str, str]] = {
    "debug": (SECOND_MODEL_RUNS["debug"][1], "run-20261019T122846Z-debug-first.jsonl"),
    "voice": (SECOND_MODEL_RUNS["voice"][1], "run-20261019T123144Z-voice-first.jsonl"),
}
# The set the rule judges; the voice set is shown only.
JUDGED = "debug"
# The guard run of the default model with thinking off, made only when the rule gives off.
GUARD: tuple[str, str] | None = None
BASELINE_FILE = "run-20261005T150537Z-debug-first.jsonl"
NOT_RUN = "### The guard run\n\nNot run: "


def record() -> str:
    return RECORD.read_text(encoding="utf-8")


def section() -> str:
    """The section of the switch: from its heading to the next heading of two marks."""
    text = record()
    start = text.index(HEADING)
    end = text.find("\n## ", start + len(HEADING))
    return text[start:] if end == -1 else text[start:end]


def results(name: str) -> Results:
    return read_results(RESULTS_DIR / name)


def whole_right(name: str) -> int:
    """``whole_right`` of all scored sentences, read from the saved summary of the run."""
    summary = json.loads(summary_path(RESULTS_DIR / name).read_text(encoding="utf-8"))
    return int(summary["groups"]["all scored sentences"]["whole_right"])


def ruled() -> Thinking:
    """The default the rule gives, from the two runs of the judged set."""
    before, off = RUNS[JUDGED]
    return Thinking.OFF if whole_right(off) >= whole_right(before) else Thinking.MODEL


@pytest.mark.parametrize("chosen", list(RUNS))
def test_each_run_with_thinking_off_is_what_it_was_meant_to_be(chosen: str) -> None:
    before_name, off_name = RUNS[chosen]
    run, before = results(off_name), results(before_name)
    head, earlier = run.run, before.run

    assert run.end is not None
    assert "only" not in head
    assert (head["model"], head["model_fingerprint"]) == (MODEL, FINGERPRINT)
    assert (earlier["model"], earlier["model_fingerprint"]) == (MODEL, FINGERPRINT)
    assert (head["set"], head["prompt"], head["final_exam_switch"]) == (chosen, "first", False)
    assert head["method"] == "one_list"
    assert head["worktree_clean"] is True
    assert head["base_url"] == "http://127.0.0.1:11434"
    for key in ("server_version", "set_sha256", "prompt_content_sha256", "reply_table_sha256"):
        assert head[key] == earlier[key], key
    parameters, earlier_parameters = head["parameters"], earlier["parameters"]
    assert isinstance(parameters, dict) and isinstance(earlier_parameters, dict)
    assert PARAMETER not in earlier_parameters
    assert parameters == {**earlier_parameters, PARAMETER: Thinking.OFF.value}


@pytest.mark.parametrize("chosen", list(RUNS))
def test_the_record_names_the_commit_each_run_was_made_at(chosen: str) -> None:
    commit = str(results(RUNS[chosen][1]).run["commit"])

    assert f"| {chosen} set, `{MODEL}`, thinking off | `{commit[:7]}` |" in section()


@pytest.mark.parametrize("chosen", list(RUNS))
def test_the_record_shows_each_set_with_thinking_not_sent_and_off(chosen: str) -> None:
    before, off = RUNS[chosen]
    shown = comparison_markdown(
        results(before),
        results(off),
        (f"evals/results/{before}", f"evals/results/{off}"),
        PARAMETER,
    )

    assert shown in section()


def test_the_default_is_the_one_the_rule_gives() -> None:
    assert DEFAULT_THINK is ruled()


def test_the_guard_run_was_made_only_when_the_rule_gave_off() -> None:
    if ruled() is Thinking.MODEL:
        assert GUARD is None
        assert section().count(NOT_RUN) == 1
        return
    assert GUARD is not None
    assert NOT_RUN not in section()


def test_the_record_names_the_numbers_the_rule_was_applied_to_and_what_it_gave() -> None:
    before, off = RUNS[JUDGED]
    summary = json.loads(summary_path(RESULTS_DIR / off).read_text(encoding="utf-8"))
    trades = summary["groups"]["all scored sentences"]["gold_trades"]
    gave = ruled().value

    assert f"| debug | {whole_right(before)} of {trades} | {whole_right(off)} of {trades} |" in (
        section()
    )
    assert f"so the default {'stays' if ruled() is Thinking.MODEL else 'becomes'} {gave}" in (
        section()
    )


def test_the_settings_say_the_default_was_measured_and_where() -> None:
    reason = ABOUT[Variable.THINK].reason

    assert HEADING.removeprefix("## ") in reason
    assert "evals/RESULTS.md" in reason
    assert reason.startswith(f"{DEFAULT_THINK.value.capitalize()}:")


def test_the_section_stands_once_after_prompt_experiment_four() -> None:
    text = record()

    assert text.count(HEADING) == 1
    assert text.index(FOUR_HEADING) < text.index(HEADING)


def test_the_section_names_no_baseline_file_and_no_earlier_heading_as_a_heading() -> None:
    text = section()

    assert BASELINE_FILE not in text
    for line in text.splitlines()[1:]:
        if line.startswith("## "):
            pytest.fail(f"another heading of two marks inside the section: {line}")
