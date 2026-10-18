"""Tests of the comparison of prompt versions on each set, and of its rule, on runs worked by hand.

Each run is built here, line by line, with the runner's own way of writing a
sentence line and the scripted model. On the debug set, ``first`` reads d01
whole and right, d24 (talk) with no draft and d29 (not to record) with no
draft; the candidate gets d01's opinion wrong with no issue, and gives d29
one draft. On the voice set, ``first`` copies u02's "20U" into the quantity
and the candidate reads it whole and right; u08 (not to record) gives no
draft in either. The expected numbers are counted by hand from the gold
answers of the sentences used. No model is called.
"""

from __future__ import annotations

import inspect
import io
import json
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from evals import compare_sets
from evals import run as runner
from evals.compare_sets import (
    FINAL_LINE,
    RULE,
    check_comparable,
    choice_markdown,
    choose,
    final_check,
    final_markdown,
    sets_markdown,
)
from evals.gold import DEBUG_SET, Split, load_set
from evals.methods import Method
from evals.records import Results, append_line
from evals.voice import VOICE_SET
from ledger_hand.extraction.prompts.first import FIRST_PROMPT
from tests.evals.test_run import D01, NOTHING
from tests.extraction.scripted_runs import row, table
from tests.fakes.scripted_model import ScriptedModel, Step

SENTENCES = {s.id: s for s in load_set(DEBUG_SET, Split.DEBUG) + load_set(VOICE_SET, Split.VOICE)}
END = {"record": "end", "finished_at": "2026-10-18T00:00:00+00:00"}
D01_HALF_OPINION = table(
    row(
        side="buy",
        coin="BTC",
        quantity="0.05 个 BTC",
        price="63,480",
        fee="1.6 USDT",
        time="昨晚 8 点 15 分",
        platform="币安",
        opinion="我觉得不亏",
    )
)
D29_ORDER = table(row(side="buy", coin="BTC", quantity="0.05 BTC", price="58,000"))
U02_AS_QUANTITY = table(
    row(
        side="buy",
        coin="ADA",
        quantity="20U",
        price="0.2968",
        fee="0.0673ADA",
        platform="OKX",
        opinion="还是想把平均成本拉下来",
    )
)
U02_RIGHT = table(
    row(
        side="buy",
        coin="ADA",
        price="0.2968",
        total="20U",
        fee="0.0673ADA",
        platform="OKX",
        opinion="还是想把平均成本拉下来",
    )
)


def line(name: str, step: Step, seconds: float) -> dict[str, object]:
    """The results-file line of sentence ``name``, read in one call that gets ``step``."""
    sentence = SENTENCES[name]
    recorder = runner.RecordingModel(ScriptedModel([step]))
    result, trace = runner.read_passage(sentence, recorder, FIRST_PROMPT, Method.ONE_LIST)
    return runner.sentence_line(sentence, result, recorder.replies, seconds, trace)


def head(version: str, chosen: str = "debug", **changes: object) -> dict[str, object]:
    run: dict[str, object] = {
        "record": "run",
        "set": chosen,
        "set_sha256": chosen[0] * 64,
        "prompt": version,
        "prompt_content_sha256": version[0] * 64,
        "reply_table_sha256": "r" * 64,
        "method": "one_list",
        "commit": version[-1] * 40,
        "model": "model-a",
        "model_fingerprint": "f" * 64,
        "server_version": "0.0.1",
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


def debug_first(**changes: object) -> Results:
    lines = [line("d01", D01, 2.5), line("d24", NOTHING, 0.5), line("d29", NOTHING, 1.0)]
    return results(head("first", **changes), lines)


def debug_second(**changes: object) -> Results:
    lines = [line("d01", D01_HALF_OPINION, 3.0), line("d24", NOTHING, 0.5)]
    lines.append(line("d29", D29_ORDER, 1.5))
    return results(head("second", **changes), lines)


def voice_first(**changes: object) -> Results:
    lines = [line("u02", U02_AS_QUANTITY, 4.0), line("u08", NOTHING, 1.0)]
    return results(head("first", "voice", **changes), lines)


def voice_second(**changes: object) -> Results:
    lines = [line("u02", U02_RIGHT, 5.0), line("u08", NOTHING, 2.0)]
    return results(head("second", "voice", **changes), lines)


FILES = ("a.jsonl", "b.jsonl")


def debug_pair() -> list[tuple[Results, str]]:
    return [(debug_first(), FILES[0]), (debug_second(), FILES[1])]


# --- one set side by side ----------------------------------------------------------------


def test_the_runs_are_said_to_differ_in_the_version_only() -> None:
    text = sets_markdown(debug_pair())

    assert text.startswith(
        "The runs share the set, the model, the way of reading a passage and every parameter; "
        "only the prompt version differs: `first`, `second`.\n"
    )


def test_the_scores_one_row_per_version_first_first() -> None:
    text = sets_markdown(list(reversed(debug_pair())))

    first = (
        "| `first` | 2 / 2 (100.0%) | 1 / 1 (100.0%) | 1 / 1 (100.0%) | 0 / 0 (-) | 0 | 0 "
        "| 0 / 2 (0.0%) | 1 / 1 (100.0%) |"
    )
    second = (
        "| `second` | 2 / 2 (100.0%) | 0 / 1 (0.0%) | 0 / 1 (0.0%) | 0 / 0 (-) | 0 | 0 "
        "| 0 / 2 (0.0%) | 1 / 1 (100.0%) |"
    )
    assert first in text and second in text
    assert text.index(first) < text.index(second)


def test_the_cost_with_seconds_per_sentence_and_the_longest_sentence() -> None:
    text = sets_markdown(debug_pair())

    # Seconds per sentence: 4.0 / 3 and 5.0 / 3; the half opinion is a wrong value, no issue.
    assert "| `first` | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 3 | 4.0 | 1.33 | 2.5 | 2.5 (d01) |" in text
    assert "| `second` | 1 | 0 | 1 | 1 | 0 | 0 | 3 | 3 | 5.0 | 1.67 | 3.0 | 3.0 (d01) |" in text
    assert "| `a.jsonl` |" in text and "| `b.jsonl` |" in text


def test_each_field_right_of_the_pairs_for_each_version() -> None:
    text = sets_markdown(debug_pair())

    assert "| Field | `first`, right / pairs | `second`, right / pairs |" in text
    assert "| side | 1 / 1 (100.0%) | 1 / 1 (100.0%) |" in text
    assert "| opinion | 1 / 1 (100.0%) | 0 / 1 (0.0%) |" in text


def test_only_the_sentences_that_differ_are_listed_with_the_checks_and_a_mark() -> None:
    text = sets_markdown(debug_pair())

    assert "the fields not right, and every sentence not to record (2 of 3):" in text
    assert (
        "| d01 | scored | extracted | extracted | 1 | 1 | 1 | 0 | - | 1.opinion:WRONG_SILENT "
        "| - | - | `second` |"
    ) in text
    assert (
        "| d29 | not_to_record | extracted | extracted | 0 | 1 | - | - | - | - | - | stopped | - |"
        in (text)
    )
    assert "| d24 |" not in text


def test_a_sentence_not_to_record_is_listed_even_when_the_versions_agree() -> None:
    same = results(head("second"), debug_first().sentences)

    text = sets_markdown([(debug_first(), FILES[0]), (same, FILES[1])])

    assert "every sentence not to record (1 of 3):" in text
    assert (
        "| d29 | not_to_record | extracted | extracted | 0 | 0 | - | - | - | - | - | - | - |"
        in text
    )


def test_every_sentence_is_listed_for_the_voice_set_and_none_marked_when_none_fell() -> None:
    text = sets_markdown([(voice_first(), FILES[0]), (voice_second(), FILES[1])])

    assert "Every sentence (2 of 2):" in text
    assert (
        "| u02 | scored | extracted | extracted | 1 | 1 | 0 | 1 "
        "| 1.quantity:MADE_UP, 1.total:LEFT_EMPTY_BY_MODEL, 1.price_currency:LEFT_EMPTY_BY_MODEL "
        "| - | - | - | - |"
    ) in text
    assert (
        "| u08 | not_to_record | extracted | extracted | 0 | 0 | - | - | - | - | - | - | - |"
        in (text)
    )


@pytest.mark.parametrize(
    ("changes", "said"),
    [
        ({"set": "voice"}, "differ in set"),
        ({"set_sha256": "t" * 64}, "differ in set_sha256"),
        ({"model": "model-b"}, "differ in model"),
        ({"model_fingerprint": "g" * 64}, "differ in model_fingerprint"),
        ({"server_version": "0.0.2"}, "differ in server_version"),
        ({"method": "split_first"}, "differ in method"),
        ({"parameters": {"temperature": 0.7, "max_reply_tokens": 1024}}, "differ in parameters"),
        ({"reply_table_sha256": "u" * 64}, "differ in reply_table_sha256"),
        ({"only": ["d01"]}, "ran only some sentences"),
        ({"prompt": "first"}, "two runs are of the same version"),
    ],
)
def test_runs_that_differ_in_more_than_the_version_are_refused_saying_in_what(
    changes: dict[str, object], said: str
) -> None:
    with pytest.raises(ValueError, match=said):
        check_comparable([debug_first(), debug_second(**changes)])


def test_the_version_its_content_and_the_commit_may_differ() -> None:
    check_comparable([debug_first(), debug_second()])
    assert debug_first().run["commit"] != debug_second().run["commit"]


def test_a_run_that_did_not_finish_or_no_run_of_first_is_refused() -> None:
    cut = results(head("second"), debug_second().sentences, None)

    with pytest.raises(ValueError, match="did not finish"):
        check_comparable([debug_first(), cut])
    with pytest.raises(ValueError, match="no run is of `first`"):
        check_comparable([debug_second(), debug_second(prompt="third")])


def test_runs_that_hold_different_sentences_are_refused() -> None:
    fewer = results(head("second"), debug_second().sentences[:2])

    with pytest.raises(ValueError, match="different sentences"):
        check_comparable([debug_first(), fewer])


def test_a_run_line_with_no_method_is_read_as_one_list() -> None:
    older = debug_first()
    run = {key: value for key, value in older.run.items() if key != "method"}

    check_comparable([results(run, older.sentences), debug_second()])


# --- the rule ------------------------------------------------------------------------------


def flat(text: str) -> str:
    return " ".join(text.replace("``", "`").split())


def test_the_rule_and_the_final_line_are_the_ones_the_module_says() -> None:
    said = flat(inspect.getdoc(compare_sets) or "")

    assert flat(RULE) in said
    assert flat(FINAL_LINE) in said


def test_a_candidate_better_on_voice_but_worse_on_debug_is_not_picked() -> None:
    judged = choose([debug_first(), debug_second(), voice_first(), voice_second()])

    assert judged.candidate == "second"
    assert judged.conditions == (
        ("1. more whole trades right", "voice", 0, 1, True),
        ("2. no fewer whole trades right", "debug", 1, 0, False),
        ("3. no more wrong values with no issue", "debug", 0, 1, False),
        ("4. no more trades missed and extra", "debug", 0, 0, True),
        ("5. no more wrong values with no issue", "voice", 0, 0, True),
    )
    assert not judged.picked
    assert judged.beside == ()


def test_a_candidate_for_which_all_five_hold_is_picked() -> None:
    same = results(head("second"), debug_first().sentences)

    judged = choose([debug_first(), same, voice_first(), voice_second()])

    assert judged.picked
    assert [holds for *_, holds in judged.conditions] == [True] * 5


def test_one_more_whole_trade_on_voice_is_needed_not_an_equal_count() -> None:
    same_voice = results(head("second", "voice"), voice_first().sentences)
    same_debug = results(head("second"), debug_first().sentences)

    judged = choose([debug_first(), same_debug, voice_first(), same_voice])

    assert judged.conditions[0][2:] == (0, 0, False)
    assert not judged.picked


def test_the_choice_prints_the_rule_the_conditions_and_the_verdict() -> None:
    text = choice_markdown(choose([debug_first(), debug_second(), voice_first(), voice_second()]))

    assert text.startswith("The rule, fixed before the first run it judges:\n\n" + RULE)
    assert "| Condition | Set | `first` | `second` | Holds |" in text
    assert "| 2. no fewer whole trades right | debug | 1 | 0 | no |" in text
    assert text.endswith("Not picked: `second`; conditions 2 and 3 do not hold.\n")


def test_the_writings_set_is_shown_beside_and_judged_by_none() -> None:
    writings_first = results(head("first", "writings"), [line("d01", D01, 1.0)])
    writings_second = results(head("second", "writings"), [line("d01", D01_HALF_OPINION, 1.0)])
    same = results(head("second"), debug_first().sentences)
    runs = [debug_first(), same, voice_first(), voice_second(), writings_first, writings_second]

    judged = choose(runs)
    text = choice_markdown(judged)

    assert judged.picked
    assert judged.beside == (
        ("Whole trades right", 1, 0),
        ("Wrong values with no issue", 0, 1),
        ("Trades missed and extra", 0, 0),
    )
    assert "The same counts on the writings set, judged by none of the conditions:" in text
    assert text.endswith("Picked: `second`; all five conditions hold.\n")


@pytest.mark.parametrize(
    ("runs", "said"),
    [
        (lambda: [debug_first(), debug_second()], "voice set"),
        (lambda: [voice_first(), voice_second()], "debug set"),
        (
            lambda: [debug_first(), debug_second(), voice_first(), voice_second(prompt="third")],
            "one candidate",
        ),
        (
            lambda: [debug_first(), debug_second(), voice_first(), voice_second(model="model-b")],
            "differ in model",
        ),
        (
            lambda: [
                debug_first(),
                debug_second(),
                voice_first(),
                voice_second(prompt_content_sha256="x" * 64),
            ],
            "differ in prompt_content_sha256",
        ),
        (lambda: [debug_first(), debug_first(), voice_first()], "two runs of `first`"),
    ],
)
def test_runs_the_rule_does_not_take_are_refused(runs: object, said: str) -> None:
    assert callable(runs)
    with pytest.raises(ValueError, match=said):
        choose(runs())


# --- the final set -------------------------------------------------------------------------


def final_pair(**changes: object) -> tuple[Results, Results]:
    earlier = results(head("first", "final", final_exam_switch=True), debug_first().sentences)
    later = results(
        head("second", "final", final_exam_switch=True, **changes), debug_second().sentences
    )
    return earlier, later


def test_the_final_line_holds_its_three_conditions_with_the_two_counts() -> None:
    earlier, later = final_pair()

    assert final_check(earlier, later) == (
        ("1. no fewer whole trades right", 1, 0, False),
        ("2. no more trades missed and extra", 0, 0, True),
        ("3. no more wrong values with no issue", 0, 1, False),
    )
    same = results(later.run, earlier.sentences)
    assert all(holds for *_, holds in final_check(earlier, same))


def test_the_final_line_counts_an_extra_draft_against_the_candidate() -> None:
    earlier, _ = final_pair()
    d01 = json.loads(D01)["trades"][0]
    one_more = table(d01, row(side="buy", coin="BTC", quantity="0.05 个 BTC"))
    lines = [line("d01", one_more, 1.0), *earlier.sentences[1:]]
    later = results(head("second", "final", final_exam_switch=True), lines)

    checked = final_check(earlier, later)

    assert checked[1] == ("2. no more trades missed and extra", 0, 1, False)


def test_the_final_markdown_shows_the_tables_then_the_line() -> None:
    earlier, later = final_pair()

    text = final_markdown((earlier, "evals/results/a.jsonl"), (later, "evals/results/b.jsonl"))

    assert text.startswith("The runs share the set")
    assert FINAL_LINE.rstrip("\n") in text
    assert "`second` against `first` in `evals/results/a.jsonl`:" in text
    assert "| 3. no more wrong values with no issue | 0 | 1 | no |" in text
    assert text.endswith("Not passed: `second`; conditions 1 and 3 do not hold.\n")


@pytest.mark.parametrize(
    ("pair", "said"),
    [
        (lambda: (final_pair()[1], final_pair()[0]), "earlier run is of `first`"),
        (lambda: (debug_first(), debug_second()), "not of the final set"),
        (lambda: final_pair(parameters={"temperature": 0.7}), "differ in parameters"),
    ],
)
def test_final_runs_that_cannot_be_held_to_the_line_are_refused(pair: object, said: str) -> None:
    assert callable(pair)
    earlier, later = pair()
    with pytest.raises(ValueError, match=said):
        final_check(earlier, later)


# --- the command -------------------------------------------------------------------------


def write(path: Path, run: Results) -> Path:
    append_line(path, run.run)
    for each in run.sentences:
        append_line(path, each)
    if run.end is not None:
        append_line(path, run.end)
    return path


def test_the_command_prints_the_comparison_the_choice_and_the_final_line(tmp_path: Path) -> None:
    one = write(tmp_path / "a.jsonl", debug_first())
    other = write(tmp_path / "b.jsonl", debug_second())
    voice = [
        write(tmp_path / "c.jsonl", voice_first()),
        write(tmp_path / "d.jsonl", voice_second()),
    ]
    earlier, later = final_pair()
    finals = [write(tmp_path / "e.jsonl", earlier), write(tmp_path / "f.jsonl", later)]

    out = io.StringIO()
    assert compare_sets.main([str(one), str(other)], out=out) == 0
    assert out.getvalue() == sets_markdown(debug_pair()) + "\n"

    out = io.StringIO()
    assert compare_sets.main(["--choose", str(one), str(other), *map(str, voice)], out=out) == 0
    judged = choose([debug_first(), debug_second(), voice_first(), voice_second()])
    assert out.getvalue() == choice_markdown(judged) + "\n"

    out = io.StringIO()
    assert compare_sets.main(["--final", *map(str, finals)], out=out) == 0
    assert out.getvalue() == final_markdown((earlier, "e.jsonl"), (later, "f.jsonl")) + "\n"


def test_the_command_says_when_it_cannot_read_or_compare(tmp_path: Path) -> None:
    out = io.StringIO()
    assert compare_sets.main([str(tmp_path / "a"), str(tmp_path / "b")], out=out) == 2
    assert "cannot read" in out.getvalue()

    one = write(tmp_path / "a.jsonl", debug_first())
    out = io.StringIO()
    assert compare_sets.main([str(one), str(one)], out=out) == 2
    assert "cannot compare: two runs are of the same version" in out.getvalue()
    out = io.StringIO()
    assert compare_sets.main(["--final", str(one)], out=out) == 2
    assert "cannot compare: the final line takes two runs" in out.getvalue()
