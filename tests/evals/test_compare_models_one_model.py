"""Tests of the model comparison let through for two runs of one model that differ in one parameter.

Two runs of the same model are compared only with ``--parameter``, when the
parameter named is the only one that differs and the two runs have the same
model fingerprint and server version; the rows and columns are then named
by the model and that parameter's value, a run that does not have the
parameter being named as not sending it. Any other two runs of one model are
refused with the same words as before. The runs are built here from the
runner's own lines and the scripted model, as in the tests of two models.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from evals import compare_models
from evals.compare_models import check_comparable, comparison_markdown
from evals.records import Results, append_line
from tests.evals.test_compare_models import EMPTY, END, FILES, LATE, head, line, results
from tests.evals.test_run import D01, NOTHING

MODEL = "model-v"
BASE = {"temperature": 0.0, "max_reply_tokens": 1024}
SERVER = "0.0.1"


def reading(parameters: dict[str, object], **changes: object) -> Results:
    """Reads every passage: d01 whole right, d24 talk with no draft, d29 not to record."""
    lines = [line("d01", D01, 2.5), line("d24", NOTHING, 0.5), line("d29", NOTHING, 1.0)]
    run = head(MODEL, **{"parameters": parameters, "server_version": SERVER, **changes})
    return results(run, lines)


def failing(parameters: dict[str, object], **changes: object) -> Results:
    """Fails on d01 (an empty reply) and on d29 (no reply in time); d24 as the reader."""
    lines = [line("d01", EMPTY, 4.0), line("d24", NOTHING, 0.5), line("d29", LATE, 1.5)]
    run = head(MODEL, **{"parameters": parameters, "server_version": SERVER, **changes})
    return results(run, lines)


def not_sent() -> Results:
    return failing(dict(BASE))


def off() -> Results:
    return reading({**BASE, "think": "off"})


def test_two_runs_of_one_model_differing_in_the_named_parameter_are_compared() -> None:
    check_comparable(not_sent(), off(), "think")

    text = comparison_markdown(not_sent(), off(), FILES, "think")

    assert text.startswith(
        "The two runs are of the same model, `model-v`, with the same fingerprint on the same "
        "server version, and share the set, the prompt and the way of reading a passage; one "
        "parameter differs: think, not sent in the first run and off in the second.\n"
    )


def test_each_row_and_column_is_named_by_the_model_and_the_parameters_value() -> None:
    text = comparison_markdown(not_sent(), off(), FILES, "think")

    a, b = "`model-v`, think not sent", "`model-v`, think off"
    assert f"| {a} | 1 / 2 (50.0%) | 0 / 1 (0.0%) |" in text
    assert f"| {b} | 2 / 2 (100.0%) | 1 / 1 (100.0%) |" in text
    assert f"| {a} | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 3 | 6.0 | 2.00 | 4.0 | 4.0 (d01) |" in text
    assert f"| {b} | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 3 | 4.0 | 1.33 | 2.5 | 2.5 (d01) |" in text
    assert f"| Result | {a} | {b} |" in text
    assert "| - malformed_reply, of them an empty reply | 1 | 0 |" in text
    assert f"| Field | {a}, right / pairs | {b}, right / pairs |" in text
    assert f"| Sentence | Group | Result, {a} | Result, {b} | Drafts, {a} | Drafts, {b} " in text
    assert "The sentences where the two runs differ in result" in text
    assert "two models" not in text


def test_the_value_of_each_side_is_the_one_in_its_first_line() -> None:
    on = reading({**BASE, "think": "on"})

    text = comparison_markdown(off(), on, FILES, "think")

    assert "think, off in the first run and on in the second." in text
    assert "| `model-v`, think off | 2 / 2 (100.0%)" in text
    assert "| `model-v`, think on | 2 / 2 (100.0%)" in text


def test_another_parameter_named_by_its_value_too() -> None:
    longer = reading({**BASE, "max_reply_tokens": 2048})

    text = comparison_markdown(failing(dict(BASE)), longer, FILES, "max_reply_tokens")

    assert "| `model-v`, max_reply_tokens 1024 | 1 / 2 (50.0%)" in text
    assert "| `model-v`, max_reply_tokens 2048 | 2 / 2 (100.0%)" in text


@pytest.mark.parametrize(
    ("first", "second", "parameter"),
    [
        (lambda: not_sent(), lambda: off(), None),
        (lambda: not_sent(), lambda: reading(dict(BASE)), "think"),
        (
            lambda: not_sent(),
            lambda: reading({**BASE, "think": "off", "temperature": 0.5}),
            "think",
        ),
        (lambda: not_sent(), lambda: off(), "temperature"),
        (
            lambda: not_sent(),
            lambda: reading({**BASE, "think": "off"}, model_fingerprint="g" * 64),
            "think",
        ),
        (
            lambda: not_sent(),
            lambda: reading({**BASE, "think": "off"}, server_version="0.0.2"),
            "think",
        ),
    ],
    ids=[
        "no parameter named",
        "no parameter differs",
        "two parameters differ",
        "another parameter named",
        "another fingerprint",
        "another server version",
    ],
)
def test_any_other_two_runs_of_one_model_are_refused_as_before(
    first: object, second: object, parameter: str | None
) -> None:
    with pytest.raises(ValueError) as caught:
        check_comparable(first(), second(), parameter)  # type: ignore[operator]

    assert str(caught.value) == "both runs are of the model model-v"


def test_a_condition_that_differs_is_still_said_for_one_model() -> None:
    other_set = reading({**BASE, "think": "off"}, set_sha256="t" * 64)

    with pytest.raises(ValueError, match="the two runs differ in set_sha256"):
        check_comparable(not_sent(), other_set, "think")


def test_the_command_compares_two_runs_of_one_model_with_the_parameter_named(
    tmp_path: Path,
) -> None:
    one, other = tmp_path / "one.jsonl", tmp_path / "other.jsonl"
    for path, run in ((one, not_sent()), (other, off())):
        for data in (run.run, *run.sentences, END):
            append_line(path, data)
    out = io.StringIO()

    status = compare_models.main([str(one), str(other), "--parameter", "think"], out=out)

    assert status == 0
    assert "| `model-v`, think off |" in out.getvalue()

    refused = io.StringIO()
    assert compare_models.main([str(one), str(other)], out=refused) == 2
    assert refused.getvalue() == "cannot compare: both runs are of the model model-v\n"
