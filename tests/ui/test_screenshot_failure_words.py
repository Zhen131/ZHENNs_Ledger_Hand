"""Tests of the plain sentence for every way an uploaded screenshot may not be read.

Every problem has its sentence: walking the enumeration makes a new problem
fail here until it has one. Each says what happened and what can be done;
the size of a file over the limit shows over it; a model's failure is said
with the vision model's name, never that of the model that extracts; status
400 and a reply not in the agreed form have sentences of their own for the
vision model; and no sentence ever holds the key. Every value is invented.
"""

from __future__ import annotations

import pytest

from ledger_hand.flows.uploading import BYTES_PER_MB, UploadNotRead, UploadProblem
from ledger_hand.ports import ModelError, ModelErrorKind
from ledger_hand.settings import ModelSettings, Secret
from ledger_hand.ui import sayings
from ledger_hand.ui.failure_words import (
    MODEL_FAILURES,
    MODEL_FAILURES_BY_STATUS,
    SCREENSHOT_FAILURES,
    model_trouble,
    screenshot_not_read,
    vision_trouble,
)
from tests.ui.test_failure_words import says_what_to_do

KEY = "sk-invented-screenshot-words-0123456789"
SETTINGS = ModelSettings(
    base_url="http://127.0.0.1:59999",
    model="invented-text:7b",
    vision_model="invented-vision:3b",
    api_key=Secret(KEY),
    timeout_seconds=45.5,
)
# With the problems a model's error comes with.
WITH_AN_ERROR = (UploadProblem.VISION_MODEL_UNCHECKED, UploadProblem.MODEL_FAILED)


def not_read(
    problem: UploadProblem,
    *,
    error: ModelError | None = None,
    size: int = 2_000_000,
    limit: int = 20,
) -> UploadNotRead:
    return UploadNotRead(problem, size, limit, error=error)


def every_sentence() -> list[str]:
    """Every problem's sentence, and every model failure's after the two that have one."""
    sentences = [
        screenshot_not_read(not_read(problem), SETTINGS)
        for problem in UploadProblem
        if problem not in WITH_AN_ERROR
    ]
    for problem in WITH_AN_ERROR:
        for kind in ModelErrorKind:
            for status in (None, 400, 401, 500):
                error = ModelError(kind, "invented", status=status, snippet=f"key {KEY}")
                sentences.append(screenshot_not_read(not_read(problem, error=error), SETTINGS))
    return sentences


# --- every problem has its sentence ------------------------------------------


def test_every_problem_has_its_own_sentence() -> None:
    assert set(SCREENSHOT_FAILURES) == set(UploadProblem)
    error = ModelError(ModelErrorKind.TIMED_OUT, "slow")
    sentences = [
        screenshot_not_read(not_read(problem, error=error), SETTINGS) for problem in UploadProblem
    ]
    assert len(set(sentences)) == len(sentences)


def test_each_sentence_ends_says_what_to_do_and_leaves_nothing_unfilled() -> None:
    for sentence in every_sentence():
        assert sentence.endswith("."), sentence
        assert says_what_to_do(sentence), sentence
        assert "{" not in sentence and "}" not in sentence, sentence


def test_no_sentence_holds_the_key() -> None:
    for sentence in [*every_sentence(), *_sayings()]:
        assert KEY not in sentence, sentence


def _sayings() -> list[str]:
    return [sayings.screenshot_read(), sayings.screenshot_waiting(), sayings.screenshot_dropped()]


def test_the_sayings_of_a_screenshot_say_what_to_do() -> None:
    sentences = _sayings()

    assert len(set(sentences)) == len(sentences)
    assert all(sentence.endswith(".") for sentence in sentences)
    assert all("Continue" in sentence for sentence in sentences[:2])
    assert "Drop" in sentences[0] and "Drop" in sentences[1]


# --- what each says -------------------------------------------------------------


def test_the_cloud_plug_names_the_plug_setting_and_says_typing_works() -> None:
    sentence = screenshot_not_read(not_read(UploadProblem.CLOUD_PLUG), SETTINGS)

    assert "LEDGER_HAND_MODEL_PLUG" in sentence
    assert "nothing was sent" in sentence
    assert "Typing a trade in the chat works" in sentence


def test_a_file_too_large_says_its_size_and_the_limit_in_mb() -> None:
    sentence = screenshot_not_read(
        not_read(UploadProblem.TOO_LARGE, size=25_000_000, limit=20), SETTINGS
    )

    assert "23.85 MB" in sentence
    assert "limit of 20 MB" in sentence
    assert "LEDGER_HAND_MODEL_SCREENSHOT_MAX_MB" in sentence
    assert "nothing was sent" in sentence


@pytest.mark.parametrize("limit", [1, 20, 200])
def test_one_byte_over_the_limit_shows_over_it(limit: int) -> None:
    sentence = screenshot_not_read(
        not_read(UploadProblem.TOO_LARGE, size=limit * BYTES_PER_MB + 1, limit=limit), SETTINGS
    )

    shown = sentence.split("The file is ")[1].split(" MB")[0]
    assert shown == f"{limit}.01"
    assert float(shown) > limit


def test_not_a_picture_says_only_png_and_jpeg_judged_by_what_it_holds() -> None:
    sentence = screenshot_not_read(not_read(UploadProblem.NOT_A_PICTURE), SETTINGS)

    assert "neither a PNG nor a JPEG" in sentence
    assert "not by its name" in sentence or "rather than by its name" in sentence
    assert "nothing was sent" in sentence


def test_a_missing_vision_model_names_it_its_setting_and_how_to_install_it() -> None:
    sentence = screenshot_not_read(not_read(UploadProblem.VISION_MODEL_MISSING), SETTINGS)

    assert "http://127.0.0.1:59999" in sentence
    assert "invented-vision:3b" in sentence
    assert "LEDGER_HAND_MODEL_VISION_NAME" in sentence
    assert "ollama pull invented-vision:3b" in sentence
    assert "not the model that extracts" in sentence
    assert "invented-text:7b" not in sentence


def test_an_empty_reading_and_a_cut_off_one_point_at_the_longest_reply_and_thinking() -> None:
    for problem in (UploadProblem.EMPTY, UploadProblem.CUT_OFF):
        sentence = screenshot_not_read(not_read(problem), SETTINGS)

        assert "LEDGER_HAND_MODEL_MAX_REPLY_TOKENS" in sentence, problem
        assert "LEDGER_HAND_MODEL_THINK" in sentence, problem
        assert "nothing was recorded" in sentence, problem


def test_an_empty_reading_is_not_followed_by_the_malformed_reply_sentence() -> None:
    error = ModelError(ModelErrorKind.MALFORMED_REPLY, "the answer has an empty reply")

    sentence = screenshot_not_read(not_read(UploadProblem.EMPTY, error=error), SETTINGS)

    assert sentence == screenshot_not_read(not_read(UploadProblem.EMPTY), SETTINGS)


# --- the model's failures name the vision model -----------------------------------


@pytest.mark.parametrize("problem", WITH_AN_ERROR)
@pytest.mark.parametrize("kind", list(ModelErrorKind))
def test_a_model_failure_names_the_vision_model_and_never_the_one_that_extracts(
    problem: UploadProblem, kind: ModelErrorKind
) -> None:
    error = ModelError(kind, "invented", status=None)

    sentence = screenshot_not_read(not_read(problem, error=error), SETTINGS)

    assert "invented-vision:3b" in sentence
    assert "invented-text:7b" not in sentence


@pytest.mark.parametrize("problem", WITH_AN_ERROR)
def test_it_says_where_it_went_wrong_then_the_failure(problem: UploadProblem) -> None:
    error = ModelError(ModelErrorKind.UNREACHABLE, "refused")

    sentence = screenshot_not_read(not_read(problem, error=error), SETTINGS)

    where = "could not be asked" if problem is UploadProblem.VISION_MODEL_UNCHECKED else "reading"
    assert where in sentence
    assert sentence.endswith(vision_trouble(error, SETTINGS))
    assert "Ollama is running" in sentence


def test_a_vision_model_the_server_does_not_have_while_reading_is_named_to_install() -> None:
    error = ModelError(ModelErrorKind.MODEL_NOT_FOUND, "no model", status=404)

    sentence = vision_trouble(error, SETTINGS)

    assert "ollama pull invented-vision:3b" in sentence
    assert "invented-text:7b" not in sentence


def test_status_400_has_its_own_sentence_for_the_vision_model() -> None:
    error = ModelError(ModelErrorKind.SERVER_ERROR, "turned down", status=400, snippet="bad")

    sentence = vision_trouble(error, SETTINGS)
    for_a_passage = model_trouble(error, SETTINGS)

    assert sentence != for_a_passage
    assert "reply table" in MODEL_FAILURES_BY_STATUS[(ModelErrorKind.SERVER_ERROR, 400)]
    assert "reply table" not in sentence
    assert "can see pictures" in sentence
    assert "LEDGER_HAND_MODEL_VISION_NAME" in sentence
    assert "(status 400)" in sentence
    assert '"bad"' in sentence


def test_a_reply_not_in_the_agreed_form_has_its_own_sentence_for_the_vision_model() -> None:
    error = ModelError(ModelErrorKind.MALFORMED_REPLY, "is not marked as complete")

    sentence = vision_trouble(error, SETTINGS)

    assert sentence != model_trouble(error, SETTINGS)
    assert "another way" in MODEL_FAILURES[ModelErrorKind.MALFORMED_REPLY]
    assert "another way" not in sentence
    assert "passage" not in sentence


def test_the_key_written_back_by_a_server_is_hidden() -> None:
    error = ModelError(ModelErrorKind.SERVER_ERROR, "turned down", status=400, snippet=KEY)

    sentence = screenshot_not_read(not_read(UploadProblem.MODEL_FAILED, error=error), SETTINGS)

    assert KEY not in sentence
