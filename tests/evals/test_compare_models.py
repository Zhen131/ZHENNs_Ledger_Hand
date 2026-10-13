"""Tests of the comparison of two models on one set, on small runs worked out by hand.

Each run is built here, line by line, with the runner's own way of writing a
sentence line and the scripted model: one model reads every passage, the
other fails on two of them (an empty reply, and no reply in time). The
expected rows are counted by hand from the gold answers of the sentences
used. No model is called.
"""

from __future__ import annotations

import io
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from evals import compare_models
from evals import run as runner
from evals.compare_models import check_comparable, comparison_markdown
from evals.gold import DEBUG_SET, Split, load_set
from evals.methods import Method
from evals.records import Results, append_line
from evals.voice import VOICE_SET
from ledger_hand.extraction.prompts.first import FIRST_PROMPT
from ledger_hand.ports import ModelError, ModelErrorKind
from tests.evals.test_run import D01, NOTHING
from tests.fakes.scripted_model import ScriptedModel, Step

SENTENCES = {s.id: s for s in load_set(DEBUG_SET, Split.DEBUG) + load_set(VOICE_SET, Split.VOICE)}
EMPTY = ModelError(
    ModelErrorKind.MALFORMED_REPLY, "the model server's answer has an empty reply", status=200
)
LATE = ModelError(ModelErrorKind.TIMED_OUT, "no complete reply within 120 seconds")
FILES = ("a.jsonl", "b.jsonl")
END = {"record": "end", "finished_at": "2026-10-13T00:00:00+00:00"}


def line(name: str, step: Step, seconds: float) -> dict[str, object]:
    """The results-file line of sentence ``name``, read in one call that gets ``step``."""
    sentence = SENTENCES[name]
    recorder = runner.RecordingModel(ScriptedModel([step]))
    result, trace = runner.read_passage(sentence, recorder, FIRST_PROMPT, Method.ONE_LIST)
    return runner.sentence_line(sentence, result, recorder.replies, seconds, trace)


def head(name: str, **changes: object) -> dict[str, object]:
    run: dict[str, object] = {
        "record": "run",
        "set": "debug",
        "set_sha256": "s" * 64,
        "prompt": "first",
        "prompt_content_sha256": "p" * 64,
        "reply_table_sha256": "r" * 64,
        "method": "one_list",
        "model": name,
        "model_fingerprint": "f" * 64,
        "parameters": {"temperature": 0.0, "max_reply_tokens": 1024},
    }
    run.update(changes)
    return run


def results(
    run: Mapping[str, object],
    lines: Sequence[Mapping[str, object]],
    end: Mapping[str, object] | None = END,
) -> Results:
    return Results(run, tuple(lines), end, 0)


def reader() -> Results:
    """Reads every passage: d01 whole right, d24 talk with no draft, d29 not to record."""
    lines = [line("d01", D01, 2.5), line("d24", NOTHING, 0.5), line("d29", NOTHING, 1.0)]
    return results(head("model-a"), lines)


def failer(**changes: object) -> Results:
    """Fails on d01 (an empty reply) and on d29 (no reply in time); d24 as the reader."""
    lines = [line("d01", EMPTY, 4.0), line("d24", NOTHING, 0.5), line("d29", LATE, 1.5)]
    return results(head("model-b", **changes), lines)


def test_the_scores_one_row_per_model() -> None:
    text = comparison_markdown(reader(), failer(), FILES)

    assert (
        "| `model-a` | 2 / 2 (100.0%) | 1 / 1 (100.0%) | 1 / 1 (100.0%) | 0 / 0 (-) | 0 | 0 "
        "| 0 / 2 (0.0%) | 1 / 1 (100.0%) |"
    ) in text
    assert (
        "| `model-b` | 1 / 2 (50.0%) | 0 / 1 (0.0%) | 0 / 1 (0.0%) | 0 / 0 (-) | 1 | 0 "
        "| 0 / 0 (-) | 1 / 1 (100.0%) |"
    ) in text


def test_the_cost_with_seconds_per_sentence_and_the_longest_sentence() -> None:
    text = comparison_markdown(reader(), failer(), FILES)

    # Calls: a failed call leaves no record; seconds per sentence: 4.0 / 3 and 6.0 / 3.
    assert "| `model-a` | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 3 | 4.0 | 1.33 | 2.5 | 2.5 (d01) |" in text
    assert "| `model-b` | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 3 | 6.0 | 2.00 | 4.0 | 4.0 (d01) |" in text
    assert "| `a.jsonl` |" in text and "| `b.jsonl` |" in text


def test_what_each_sentence_gave_with_the_failures_by_kind() -> None:
    text = comparison_markdown(reader(), failer(), FILES)

    expected = [
        "| Result | `model-a` | `model-b` |",
        "| --- | --- | --- |",
        "| all sentences | 3 | 3 |",
        "| extracted | 3 | 1 |",
        "| reply_unreadable | 0 | 0 |",
        "| model_failed | 0 | 2 |",
        "| - unreachable | 0 | 0 |",
        "| - timed_out | 0 | 1 |",
        "| - model_not_found | 0 | 0 |",
        "| - rate_limited | 0 | 0 |",
        "| - server_error | 0 | 0 |",
        "| - malformed_reply | 0 | 1 |",
        "| - malformed_reply, of them an empty reply | 0 | 1 |",
        "| passage_refused | 0 | 0 |",
    ]
    assert "\n".join(expected) in text


def test_each_field_right_of_the_pairs_for_both_models() -> None:
    text = comparison_markdown(reader(), failer(), FILES)

    assert "| Field | `model-a`, right / pairs | `model-b`, right / pairs |" in text
    assert "| side | 1 / 1 (100.0%) | 0 / 0 (-) |" in text
    assert "| opinion | 1 / 1 (100.0%) | 0 / 0 (-) |" in text


def test_only_the_sentences_that_differ_are_listed_for_the_debug_set() -> None:
    text = comparison_markdown(reader(), failer(), FILES)

    assert "the fields not right (2 of 3):" in text
    assert "| d01 | scored | extracted | model_failed | 1 | 0 | 1 | 0 | - | - |" in text
    assert "| d29 | not_to_record | extracted | model_failed | 0 | 0 | - | - | - | - |" in text
    assert "| d24 |" not in text


def test_every_sentence_is_listed_for_the_voice_set() -> None:
    voice = head("model-a", set="voice")
    lines = [line("u02", NOTHING, 1.0), line("u08", NOTHING, 1.0)]
    one, other = results(voice, lines), results({**voice, "model": "model-b"}, lines)

    text = comparison_markdown(one, other, FILES)

    assert "Every sentence (2 of 2):" in text
    assert "| u02 | scored | extracted | extracted | 0 | 0 | 0 | 0 | - | - |" in text
    assert "| u08 | not_to_record | extracted | extracted | 0 | 0 | - | - | - | - |" in text


def test_the_two_runs_are_said_to_differ_in_the_model_only() -> None:
    text = comparison_markdown(reader(), failer(), FILES)

    assert text.startswith(
        "The two runs share the set, the prompt, the way of reading a passage and every "
        "parameter; only the model differs: `model-a` and `model-b`.\n"
    )


def test_one_parameter_named_may_differ_and_is_said() -> None:
    changed = failer(parameters={"temperature": 0.0, "max_reply_tokens": 4096})

    text = comparison_markdown(reader(), changed, FILES, "max_reply_tokens")

    assert (
        "one parameter differs: max_reply_tokens, 1024 for `model-a` and 4096 for `model-b`."
        in (text)
    )


@pytest.mark.parametrize(
    ("changes", "said"),
    [
        ({"set": "voice"}, "differ in set"),
        ({"set_sha256": "t" * 64}, "differ in set_sha256"),
        ({"prompt": "persona"}, "differ in prompt"),
        ({"prompt_content_sha256": "q" * 64}, "differ in prompt_content_sha256"),
        ({"reply_table_sha256": "u" * 64}, "differ in reply_table_sha256"),
        ({"method": "split_first"}, "differ in method"),
        ({"parameters": {"temperature": 0.7, "max_reply_tokens": 1024}}, "temperature"),
        ({"only": ["d01"]}, "ran only some sentences"),
        ({"model": "model-a"}, "both runs are of the model model-a"),
    ],
)
def test_runs_that_differ_in_more_than_the_model_are_refused_saying_in_what(
    changes: dict[str, object], said: str
) -> None:
    with pytest.raises(ValueError, match=said):
        check_comparable(reader(), failer(**changes))


def test_a_run_that_did_not_finish_is_refused() -> None:
    cut = results(head("model-b"), failer().sentences, None)

    with pytest.raises(ValueError, match="did not finish"):
        check_comparable(reader(), cut)


def test_the_parameter_named_must_be_the_only_one_that_differs() -> None:
    both = failer(parameters={"temperature": 0.7, "max_reply_tokens": 4096})

    with pytest.raises(ValueError, match="temperature"):
        check_comparable(reader(), both, "max_reply_tokens")
    with pytest.raises(ValueError, match="none"):
        check_comparable(reader(), failer(), "max_reply_tokens")


def test_a_run_line_with_no_method_is_read_as_one_list() -> None:
    older = reader()
    run = {key: value for key, value in older.run.items() if key != "method"}

    check_comparable(results(run, older.sentences), failer())


def test_runs_that_hold_different_sentences_are_refused() -> None:
    fewer = results(head("model-b"), failer().sentences[:2])

    with pytest.raises(ValueError, match="different sentences"):
        check_comparable(reader(), fewer)


def write(path: Path, run: Results) -> Path:
    append_line(path, run.run)
    for each in run.sentences:
        append_line(path, each)
    if run.end is not None:
        append_line(path, run.end)
    return path


def test_the_command_prints_the_comparison(tmp_path: Path) -> None:
    one = write(tmp_path / "a.jsonl", reader())
    other = write(tmp_path / "b.jsonl", failer())
    out = io.StringIO()

    status = compare_models.main([str(one), str(other)], out=out)

    assert status == 0
    assert out.getvalue() == comparison_markdown(reader(), failer(), FILES) + "\n"


def test_the_command_lets_one_parameter_through_by_name(tmp_path: Path) -> None:
    one = write(tmp_path / "a.jsonl", reader())
    changed = failer(parameters={"temperature": 0.0, "max_reply_tokens": 4096})
    other = write(tmp_path / "b.jsonl", changed)
    out = io.StringIO()

    assert compare_models.main([str(one), str(other)], out=out) == 2
    assert "cannot compare: the two runs differ in the parameters max_reply_tokens" in (
        out.getvalue()
    )
    out = io.StringIO()
    status = compare_models.main([str(one), str(other), "--parameter", "max_reply_tokens"], out=out)
    assert status == 0
    assert "one parameter differs: max_reply_tokens" in out.getvalue()


def test_the_command_says_when_it_cannot_read(tmp_path: Path) -> None:
    out = io.StringIO()

    assert compare_models.main([str(tmp_path / "a"), str(tmp_path / "b")], out=out) == 2
    assert "cannot read" in out.getvalue()
