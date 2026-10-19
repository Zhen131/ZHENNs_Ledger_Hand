"""Gate: the fourth prompt experiment in the record is what its results files give.

The record shows, for each of the three sets (debug, voice, writings), the
comparison of the runs of ``first``, ``third`` and the candidate
(``compare_sets``); for the candidate, the rule applied to its runs and those
of ``first``; and, for ``first`` and the candidate, the room a prompt leaves
in the context. Each is worked out again here from the results files named
below and must stand in the record exactly. Only the files named here are
read; the results directory is not scanned, so a run made later for another
purpose cannot change what this gate checks.

The runs of ``first`` and ``third`` are those of the third prompt experiment,
named by its gate and not made again; ``third`` is shown beside the others
and judged by none of the rule's conditions. The record says why the runs of
``first`` may stand for runs of this experiment, and this gate checks what
that rests on: every run named here has the same model server version, model
fingerprint, parameters, set file and reply table, and ``first`` the content
fingerprint of the baseline.

The first line of each run must show what the run was: ``qwen2.5:7b`` with
the fingerprint written here, the set and the prompt it was meant to run,
the final-exam switch off, one list, a clean work tree and the model server
on this machine. That the fingerprint is the one the model server lists is
checked by hand: no test here asks the server. The final set is run only for
a candidate the rule picks whose prompt fits in the context with the longest
passage and the longest reply; when there is none, no final run is named
here and the record says the final set was not run. No model is called.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import pytest

from evals.compare_sets import RULE, choice_markdown, choose, final_markdown, sets_markdown
from evals.records import Results, read_results
from evals.run import RESULTS_DIR
from ledger_hand.settings import ABOUT, Variable
from tests.evals.test_prompt_experiment_three_record import HEADING as THREE_HEADING
from tests.evals.test_prompt_experiment_three_record import RUNS as THREE_RUNS
from tests.evals.test_run_versions import FIRST_CONTENT_SHA256

RECORD = RESULTS_DIR.parent / "RESULTS.md"
HEADING = (
    "## 2026-10-19: prompt experiment four, new examples with English passages and Chinese "
    "numbers, `qwen2.5:7b`"
)
MODEL = "qwen2.5:7b"
FINGERPRINT = "845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e"
CANDIDATES = ("fourth",)
# Shown beside the others and judged by none of the conditions.
SHOWN_ONLY = ("third",)
# Each set's runs, in the order the comparison is given them: first, the version shown
# only, then each candidate. The runs of first and third are the third experiment's.
RUNS: Mapping[str, Mapping[str, str]] = {
    "debug": {
        "first": THREE_RUNS["debug"]["first"],
        "third": THREE_RUNS["debug"]["third"],
        "fourth": "run-20261019T110619Z-debug-fourth.jsonl",
    },
    "voice": {
        "first": THREE_RUNS["voice"]["first"],
        "third": THREE_RUNS["voice"]["third"],
        "fourth": "run-20261019T110945Z-voice-fourth.jsonl",
    },
    "writings": {
        "first": THREE_RUNS["writings"]["first"],
        "third": THREE_RUNS["writings"]["third"],
        "fourth": "run-20261019T111040Z-writings-fourth.jsonl",
    },
}
# The run whose parameters and reply table every run here shares: the comparison of two
# models' run of the debug set.
BASE = "run-20261013T092724Z-debug-first.jsonl"
# The longest passage the ledger keeps, in tokens, as the settings describe the context.
LONGEST_PASSAGE_TOKENS = 11_600
REUSED = (
    'In this section, "the run of `first` made in the same experiment" is each of the three '
    "runs of `first` made for prompt experiment three, reused here and not made again"
)
FACTS = (
    "The new examples were written after the errors of `first` on the voice set and after "
    "the errors of `second` and `third` on the debug and the writings set, so the scores of "
    "`fourth` on all three sets are not scores on passages it has not seen; the only passages "
    "it has not seen are those of the final set and of the owner's later use.",
    "`first` already gets every trade of the final set whole, so the final set can show only "
    "whether a candidate falls behind `first`, not whether it does better.",
)
# The run of the final set this experiment made: one, of the candidate the rule picked
# whose prompt fits in the context, or none when there is no such candidate.
FINALS: tuple[str, ...] = ("run-20261019T111751Z-final-fourth.jsonl",)
NOT_RUN = "### The final set\n\nNot run: "
# The earlier run of first on the final set that a final run is compared with.
EARLIER_FINAL = "run-20261013T093036Z-final-first.jsonl"


def record() -> str:
    return RECORD.read_text(encoding="utf-8")


def results(name: str) -> Results:
    return read_results(RESULTS_DIR / name)


def every_run() -> list[tuple[str, str, str]]:
    """Each run named here: its file, the set it ran and the prompt."""
    return [
        (name, chosen, prompt) for chosen, runs in RUNS.items() for prompt, name in runs.items()
    ]


def section() -> str:
    """The section of the experiment: from its heading to the next heading of two marks."""
    text = record()
    start = text.index(HEADING)
    end = text.find("\n## ", start + len(HEADING))
    return text[start:] if end == -1 else text[start:end]


@pytest.mark.parametrize(("name", "chosen", "prompt"), every_run(), ids=lambda x: str(x))
def test_each_run_is_what_it_was_meant_to_be(name: str, chosen: str, prompt: str) -> None:
    run = results(name)
    head = run.run
    base = results(BASE).run

    assert run.end is not None
    assert "only" not in head
    assert (head["model"], head["model_fingerprint"]) == (MODEL, FINGERPRINT)
    assert (head["set"], head["prompt"], head["final_exam_switch"]) == (chosen, prompt, False)
    assert head["method"] == "one_list"
    assert head["worktree_clean"] is True
    assert head["base_url"] == "http://127.0.0.1:11434"
    assert head["parameters"] == base["parameters"]
    assert head["reply_table_sha256"] == base["reply_table_sha256"]
    assert head["set_sha256"] == results(THREE_RUNS[chosen]["first"]).run["set_sha256"]
    if prompt == "first":
        assert head["prompt_content_sha256"] == FIRST_CONTENT_SHA256


def test_the_runs_of_first_and_third_are_those_of_prompt_experiment_three() -> None:
    for chosen, runs in RUNS.items():
        assert runs["first"] == THREE_RUNS[chosen]["first"]
        assert runs["third"] == THREE_RUNS[chosen]["third"]


def test_every_run_has_the_same_server_and_each_version_one_content() -> None:
    heads = [results(name).run for name, _, _ in every_run()]

    assert len({head["server_version"] for head in heads}) == 1
    for prompt in ("first", *SHOWN_ONLY, *CANDIDATES):
        contents = {results(runs[prompt]).run["prompt_content_sha256"] for runs in RUNS.values()}
        assert len(contents) == 1, prompt


@pytest.mark.parametrize("chosen", list(RUNS))
def test_the_record_shows_the_versions_on_each_set(chosen: str) -> None:
    runs = [(results(name), f"evals/results/{name}") for name in RUNS[chosen].values()]

    assert sets_markdown(runs) in section()


@pytest.mark.parametrize("candidate", CANDIDATES)
def test_the_record_shows_the_rule_applied_to_each_candidate(candidate: str) -> None:
    runs = [results(each[name]) for each in RUNS.values() for name in ("first", candidate)]

    assert choice_markdown(choose(runs)) in section()


def test_the_record_shows_the_rule_once_more_as_it_was_fixed() -> None:
    assert section().count(RULE.rstrip("\n")) == 1 + len(CANDIDATES)


def test_the_record_says_why_the_runs_of_first_are_reused() -> None:
    assert REUSED in " ".join(section().split())


def test_the_record_states_the_two_facts_that_bear_on_every_number() -> None:
    flat = " ".join(section().split())

    for fact in FACTS:
        assert flat.count(fact) >= 2, fact


@dataclass(frozen=True)
class Room:
    """The room a version's prompt leaves in the context, from its run of the voice set."""

    sentence: str
    characters: int
    read: int
    added: int
    context: int

    @property
    def fits(self) -> bool:
        return self.added <= self.context


def room(prompt: str) -> Room:
    """The room in the context, from the first call on the shortest passage of the voice set.

    The tokens that call read bound the prompt's own size from above; the longest passage
    and the longest reply are added to them.
    """
    run = results(RUNS["voice"][prompt])
    shortest = min(run.sentences, key=lambda line: len(str(line["text"])))
    calls = shortest["calls"]
    assert isinstance(calls, list) and calls
    read = int(calls[0]["prompt_tokens"])
    parameters = run.run["parameters"]
    assert isinstance(parameters, dict)
    return Room(
        sentence=str(shortest["id"]),
        characters=len(str(shortest["text"])),
        read=read,
        added=read + LONGEST_PASSAGE_TOKENS + int(parameters["max_reply_tokens"]),
        context=int(parameters["context_tokens"]),
    )


def room_markdown() -> str:
    """The room in the context, one row for ``first`` and one for each candidate."""
    lines = [
        "| Version | Shortest passage of the voice set | Characters | Tokens read, first call "
        "| With the longest passage and the longest reply | Context | Room left | Fits |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for prompt in ("first", *CANDIDATES):
        each = room(prompt)
        lines.append(
            f"| `{prompt}` | {each.sentence} | {each.characters} | {each.read:,} "
            f"| {each.added:,} | {each.context:,} | {each.context - each.added:,} "
            f"| {'yes' if each.fits else 'no'} |"
        )
    return "\n".join(lines) + "\n"


def test_the_longest_passage_is_the_one_the_settings_describe() -> None:
    assert f"{LONGEST_PASSAGE_TOKENS:,}" in ABOUT[Variable.CONTEXT_TOKENS].reason


def test_the_record_shows_the_room_in_the_context_the_results_files_give() -> None:
    assert room_markdown() in section()


def test_the_section_stands_once_after_prompt_experiment_three() -> None:
    text = record()

    assert text.count(HEADING) == 1
    assert text.index(THREE_HEADING) < text.index(HEADING)


def picked(candidate: str) -> bool:
    """Whether the rule picks ``candidate`` over ``first``."""
    runs = [results(each[name]) for each in RUNS.values() for name in ("first", candidate)]
    return choose(runs).picked


def test_the_final_set_was_run_only_for_a_candidate_picked_whose_prompt_fits() -> None:
    allowed = [c for c in CANDIDATES if picked(c) and room(c).fits]

    assert len(FINALS) == len(allowed) <= 1
    for candidate in CANDIDATES:
        if picked(candidate) and not room(candidate).fits:
            said = f"`{candidate}` is picked by the rule, but its prompt does not fit"
            assert said in " ".join(section().split()), candidate
    if not FINALS:
        assert section().count(NOT_RUN) == 1
        return
    (final,) = FINALS
    head = results(final).run
    base = results(BASE).run
    assert results(final).end is not None
    assert "only" not in head
    assert (head["model"], head["model_fingerprint"]) == (MODEL, FINGERPRINT)
    assert (head["set"], head["prompt"], head["final_exam_switch"]) == ("final", allowed[0], True)
    assert head["method"] == "one_list"
    assert head["worktree_clean"] is True
    assert head["base_url"] == "http://127.0.0.1:11434"
    assert head["parameters"] == base["parameters"]
    assert head["reply_table_sha256"] == base["reply_table_sha256"]
    assert head["set_sha256"] == results(EARLIER_FINAL).run["set_sha256"]
    assert head["server_version"] == results(RUNS["debug"]["first"]).run["server_version"]
    assert {results(runs[allowed[0]]).run["prompt_content_sha256"] for runs in RUNS.values()} == {
        head["prompt_content_sha256"]
    }


def test_the_record_shows_the_final_set_against_the_earlier_run_of_first() -> None:
    for final in FINALS:
        shown = final_markdown(
            (results(EARLIER_FINAL), f"evals/results/{EARLIER_FINAL}"),
            (results(final), f"evals/results/{final}"),
        )
        assert "### The final set\n\n" in section()
        assert shown in section()
