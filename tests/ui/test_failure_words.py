"""Tests of the plain sentence for every way something can fail.

Every kind of every failure has a sentence: walking each enumeration makes a
new kind fail here until it has one. Each sentence says what happened and
what can be done; the one for a model nobody answers names the address; a
status code can have a sentence of its own; and no sentence ever holds the
key. Every value below is invented.
"""

from __future__ import annotations

from pathlib import Path
from types import MappingProxyType

import pytest

from ledger_hand.export.backup import ExportIssue, ExportProblem
from ledger_hand.extraction.passage_check import PassageProblem
from ledger_hand.flows.export_file import WriteProblem
from ledger_hand.flows.progress import Failure, Step
from ledger_hand.ports import ModelError, ModelErrorKind, StorageError, StorageErrorKind
from ledger_hand.settings import ModelSettings, Secret
from ledger_hand.ui import failure_words
from ledger_hand.ui.failure_words import (
    ASSEMBLY_FAILURES,
    MODEL_FAILURES,
    PASSAGE_REFUSALS,
    REPLY_UNREADABLE,
    STORAGE_FAILURES,
    WRITE_FAILURES,
    assembly_failed,
    book_trouble,
    export_not_marked,
    export_not_written,
    export_refused,
    model_failed,
    model_trouble,
    passage_refused,
)
from ledger_hand.wiring import AssemblyError, AssemblyProblem

KEY = "sk-invented-words-0123456789"
SETTINGS = ModelSettings(
    base_url="http://127.0.0.1:59999",
    model="invented-model:3b",
    api_key=Secret(KEY),
    timeout_seconds=45.5,
)
# Words that tell the person what they can do next.
NEXT_STEP = ("Try again", "try again", "Settings page", "Wait", "Check", "Close", "Use the")


def says_what_to_do(sentence: str) -> bool:
    return any(words in sentence for words in NEXT_STEP)


# --- every kind has its sentence ---------------------------------------------


def test_every_kind_of_model_failure_has_its_own_sentence() -> None:
    assert set(MODEL_FAILURES) == set(ModelErrorKind)
    sentences = [model_trouble(ModelError(kind, "invented"), SETTINGS) for kind in ModelErrorKind]
    assert len(set(sentences)) == len(sentences)
    for sentence in sentences:
        assert sentence.endswith("."), sentence
        assert says_what_to_do(sentence), sentence
        assert "{" not in sentence and "}" not in sentence, sentence


def test_every_kind_of_storage_failure_has_its_own_sentence() -> None:
    assert set(STORAGE_FAILURES) == set(StorageErrorKind)
    sentences = list(STORAGE_FAILURES.values())
    assert len(set(sentences)) == len(sentences)
    for sentence in sentences:
        assert sentence.endswith("."), sentence
        assert says_what_to_do(sentence) or "start the program again" in sentence, sentence


def test_every_passage_refusal_every_assembly_problem_and_every_write_problem_is_said() -> None:
    assert set(PASSAGE_REFUSALS) == set(PassageProblem)
    assert set(ASSEMBLY_FAILURES) == set(AssemblyProblem)
    assert set(WRITE_FAILURES) == set(WriteProblem)


# --- the model -------------------------------------------------------------------


def test_nobody_answering_names_the_address_and_ollama() -> None:
    sentence = model_trouble(ModelError(ModelErrorKind.UNREACHABLE, "refused"), SETTINGS)

    assert "http://127.0.0.1:59999" in sentence
    assert "Ollama is running" in sentence
    assert "Settings page" in sentence


def test_a_timeout_names_the_time_allowed_and_the_first_slow_call() -> None:
    sentence = model_trouble(ModelError(ModelErrorKind.TIMED_OUT, "slow"), SETTINGS)

    assert "45.5 seconds" in sentence
    assert "first call" in sentence
    assert "more time on the Settings page" in sentence


def test_a_model_not_found_names_the_model_and_how_to_install_it() -> None:
    sentence = model_trouble(ModelError(ModelErrorKind.MODEL_NOT_FOUND, "no model"), SETTINGS)

    assert "invented-model:3b" in sentence
    assert "ollama pull invented-model:3b" in sentence


def test_rate_limiting_says_to_wait_and_try_again() -> None:
    sentence = model_trouble(ModelError(ModelErrorKind.RATE_LIMITED, "429", status=429), SETTINGS)

    assert "called too often" in sentence
    assert "Wait a little, then try again" in sentence


def test_a_server_error_names_its_status_when_there_is_one() -> None:
    with_status = model_trouble(
        ModelError(ModelErrorKind.SERVER_ERROR, "oops", status=503), SETTINGS
    )
    without = model_trouble(ModelError(ModelErrorKind.SERVER_ERROR, "oops"), SETTINGS)

    assert "(status 503)" in with_status
    assert "status" not in without


def test_a_status_code_can_have_a_sentence_of_its_own(monkeypatch: pytest.MonkeyPatch) -> None:
    own = {(ModelErrorKind.SERVER_ERROR, 401): "The server at {address} did not take the key."}
    monkeypatch.setattr(failure_words, "MODEL_FAILURES_BY_STATUS", MappingProxyType(own))

    for_401 = model_trouble(ModelError(ModelErrorKind.SERVER_ERROR, "no", status=401), SETTINGS)
    for_500 = model_trouble(ModelError(ModelErrorKind.SERVER_ERROR, "no", status=500), SETTINGS)

    assert for_401 == "The server at http://127.0.0.1:59999 did not take the key."
    assert for_500 == MODEL_FAILURES[ModelErrorKind.SERVER_ERROR].format(
        address="", model="", seconds="", status=" (status 500)"
    )


def test_only_400_401_and_403_have_a_sentence_of_their_own() -> None:
    assert set(failure_words.MODEL_FAILURES_BY_STATUS) == {
        (ModelErrorKind.SERVER_ERROR, 400),
        (ModelErrorKind.SERVER_ERROR, 401),
        (ModelErrorKind.SERVER_ERROR, 403),
    }


@pytest.mark.parametrize("step", [Step.SCREENING, Step.EXTRACTION])
@pytest.mark.parametrize("kind", list(ModelErrorKind))
def test_a_passage_that_failed_says_so_then_what_happened(step: Step, kind: ModelErrorKind) -> None:
    said = model_failed(Failure(step, ModelError(kind, "invented")), SETTINGS)

    assert said.startswith(f"The model gave no usable reply while {step.value}, ")
    assert "nothing was recorded" in said
    assert said.endswith(model_trouble(ModelError(kind, "invented"), SETTINGS))


def test_replies_that_cannot_be_read_as_a_table_are_said_apart() -> None:
    said = model_failed(Failure(Step.EXTRACTION, None, ("not valid JSON",)), SETTINGS)

    assert said.endswith(REPLY_UNREADABLE)
    assert "nothing was recorded" in said


@pytest.mark.parametrize("status", [None, 400, 401, 403, 429, 500, 503])
@pytest.mark.parametrize("kind", list(ModelErrorKind))
def test_no_sentence_holds_the_key(kind: ModelErrorKind, status: int | None) -> None:
    # Even an error whose own words held the key (the plug never lets one) is said without it.
    error = ModelError(kind, f"the server said {KEY}", status=status, snippet=KEY)

    assert KEY not in model_trouble(error, SETTINGS)
    assert KEY not in model_failed(Failure(Step.SCREENING, error), SETTINGS)


# --- the passage ---------------------------------------------------------------------


def test_an_empty_passage_is_said_as_it_always_was() -> None:
    assert passage_refused(PassageProblem.EMPTY) == (
        "Nothing was sent to the model: the passage is empty."
    )


def test_a_passage_too_long_names_the_limit_and_what_to_do() -> None:
    said = passage_refused(PassageProblem.TOO_LONG)

    assert said.startswith("Nothing was sent to the model: ")
    assert "16,384 characters" in said
    assert "Split it into shorter passages" in said


def test_a_passage_that_is_not_valid_text_says_what_to_do() -> None:
    said = passage_refused(PassageProblem.NOT_VALID_TEXT)

    assert "not valid text" in said
    assert "Type it again" in said


# --- the book ------------------------------------------------------------------------


@pytest.mark.parametrize("kind", list(StorageErrorKind))
def test_the_book_failing_is_said_with_its_own_words_and_path(kind: StorageErrorKind) -> None:
    error = StorageError(kind, "the book (/invented/data/ledger-hand-book.sqlite3): invented")

    said = book_trouble(error)

    assert said.startswith(STORAGE_FAILURES[kind])
    assert "/invented/data/ledger-hand-book.sqlite3" in said


def test_a_book_of_a_newer_version_is_left_alone_and_says_what_to_do() -> None:
    sentence = STORAGE_FAILURES[StorageErrorKind.NEWER_VERSION]

    assert "newer version of this program" in sentence
    assert "does not touch it" in sentence
    assert "LEDGER_HAND_DATA_DIR" in sentence


# --- settings and the parts ----------------------------------------------------------


def test_a_refused_change_names_the_setting_and_its_rule_and_changes_nothing() -> None:
    error = AssemblyError(
        AssemblyProblem.CHANGE_REFUSED,
        "LEDGER_HAND_MODEL_TEMPERATURE: '-1' is not a plain number such as 0.5",
    )

    assert assembly_failed(error) == (
        "Not applied: LEDGER_HAND_MODEL_TEMPERATURE: '-1' is not a plain number such as 0.5. "
        "The settings were not changed."
    )


def test_a_refused_environment_variable_says_the_program_cannot_start_and_what_to_do() -> None:
    error = AssemblyError(AssemblyProblem.SETTING_REFUSED, "LEDGER_HAND_MODEL_TOP_P: refused")

    said = assembly_failed(error)

    assert said.startswith("The program cannot start: a setting was refused: ")
    assert "LEDGER_HAND_MODEL_TOP_P" in said
    assert "start the program again" in said


# --- exports ---------------------------------------------------------------------------


def test_an_export_refused_gives_every_reason_on_a_line_of_its_own() -> None:
    issues = [
        ExportIssue(ExportProblem.DATED_AFTER_TODAY, "hand-invented-1"),
        ExportIssue(ExportProblem.DATED_AFTER_TODAY, "hand-invented-2"),
    ]

    lines = export_refused(issues).split("\n")

    assert lines[0].startswith("Nothing was exported and nothing was marked as exported")
    assert lines[1:] == [
        f"    {ExportProblem.DATED_AFTER_TODAY.value}: hand-invented-1",
        f"    {ExportProblem.DATED_AFTER_TODAY.value}: hand-invented-2",
    ]


@pytest.mark.parametrize("problem", list(WriteProblem))
def test_an_export_file_not_written_says_nothing_was_marked(problem: WriteProblem) -> None:
    said = export_not_written(problem, "[Errno 20] Not a directory")

    assert said.startswith("Nothing was exported and nothing was marked as exported. ")
    assert WRITE_FAILURES[problem] in said
    assert said.endswith("([Errno 20] Not a directory)")


def test_an_export_file_not_marked_names_the_file_and_the_book() -> None:
    error = StorageError(StorageErrorKind.LOCKED, "the book (/invented/book): busy")

    said = export_not_marked(Path("/invented/exports/file.json"), error)

    assert "/invented/exports/file.json" in said
    assert "next export writes them again" in said
    assert "in use by another program" in said
