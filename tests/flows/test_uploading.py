"""Tests of the checks made on an uploaded screenshot before it is read, and of the reading.

The checks go in their order and stop at the first that does not pass: the
plug, the size, whether the file is a PNG or a JPEG by its own first bytes,
whether the model server has the vision model; then the picture is read.
The first three ask nothing of the vision model or of the server; the
fourth sends no picture. Every byte, reply and name here is invented.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from evals.compare_models import _EMPTY_REPLY
from ledger_hand.extraction.picture_reading import PictureNotRead, PictureRead, ReadingProblem
from ledger_hand.flows.uploading import (
    _READING_PROBLEMS,
    BYTES_PER_MB,
    EMPTY_REPLY_WORDS,
    UploadNotRead,
    UploadProblem,
    UploadRead,
    VisionModelPresence,
    read_upload,
)
from ledger_hand.ports import (
    FinishReason,
    ModelError,
    ModelErrorKind,
    ModelReply,
    PictureKind,
    ReplyRecord,
)
from ledger_hand.settings import ModelSettings, Plug
from tests.fakes.scripted_model import ScriptedModel

PNG = b"\x89PNG\r\n\x1a\n" + b"invented picture bytes" * 3
JPEG = b"\xff\xd8\xff\xe0" + b"invented picture bytes" * 3
TEXT = b"Bought 0.02 BTC, not a picture at all"
# Text a little over one MB.
LONG_TEXT = TEXT * (1_048_576 // len(TEXT) + 1)
READ = "Side: buy\nPair: BTC/USDT\nFilled: 0.02 BTC\n"
LOCAL = ModelSettings()
CLOUD = ModelSettings(plug=Plug.CLOUD, base_url="https://api.example.com/v1")


class Check:
    """Stands in for asking the server; says what it is told to, and counts the asks."""

    def __init__(self, answer: VisionModelPresence | ModelError = VisionModelPresence.PRESENT):
        self.answer = answer
        self.asked = 0

    def __call__(self) -> VisionModelPresence:
        self.asked += 1
        if isinstance(self.answer, ModelError):
            raise self.answer
        return self.answer


def taken(
    data: bytes,
    *,
    settings: ModelSettings = LOCAL,
    model: ScriptedModel | None = None,
    check: Check | None = None,
) -> tuple[object, ScriptedModel, Check]:
    used_model = ScriptedModel([READ]) if model is None else model
    used_check = Check() if check is None else check
    outcome = read_upload(data, settings, vision_model=used_model, check=used_check)
    return outcome, used_model, used_check


def limited(megabytes: int) -> ModelSettings:
    return ModelSettings(screenshot_max_mb=megabytes)


def png_of(size: int) -> bytes:
    return PNG + b"\0" * (size - len(PNG))


def cut_off() -> ModelReply:
    record = ReplyRecord(
        model="invented-vision",
        elapsed_seconds=1.5,
        prompt_tokens=20,
        reply_tokens=1024,
        finish=FinishReason.LENGTH_LIMIT,
    )
    return ModelReply(text="Side: buy\nPair: BT", record=record)


# --- what was read ------------------------------------------------------------


def test_a_png_is_read_and_the_reading_comes_back_whole() -> None:
    outcome, model, check = taken(PNG)

    assert isinstance(outcome, UploadRead)
    assert isinstance(outcome.reading, PictureRead)
    assert outcome.reading.text == READ
    assert outcome.reading.version == "read-1"
    assert check.asked == 1
    (call,) = model.calls
    (picture,) = call.pictures
    assert (picture.data, picture.kind) == (PNG, PictureKind.PNG)


def test_a_jpeg_is_read_too() -> None:
    outcome, model, _ = taken(JPEG)

    assert isinstance(outcome, UploadRead)
    assert model.calls[0].pictures[0].kind is PictureKind.JPEG


def test_the_name_and_the_type_the_browser_gave_play_no_part() -> None:
    # Only bytes are handed in: the name and the type never reach the checks.
    outcome, _, _ = taken(TEXT)

    assert isinstance(outcome, UploadNotRead)
    assert outcome.problem is UploadProblem.NOT_A_PICTURE


# --- each problem, and that nothing is asked before it is needed ---------------


def test_the_cloud_plug_reads_nothing_and_asks_nothing() -> None:
    outcome, model, check = taken(PNG, settings=CLOUD)

    assert outcome == UploadNotRead(UploadProblem.CLOUD_PLUG, len(PNG), CLOUD.screenshot_max_mb)
    assert (model.calls, check.asked) == ([], 0)


def test_the_cloud_plug_needs_no_vision_model_and_no_check() -> None:
    outcome = read_upload(PNG, CLOUD, vision_model=None, check=None)

    assert isinstance(outcome, UploadNotRead)
    assert outcome.problem is UploadProblem.CLOUD_PLUG


def test_a_file_of_exactly_the_limit_is_taken_and_one_byte_more_is_not() -> None:
    exactly, _, _ = taken(png_of(BYTES_PER_MB), settings=limited(1))
    over, model, check = taken(png_of(BYTES_PER_MB + 1), settings=limited(1))

    assert isinstance(exactly, UploadRead)
    assert over == UploadNotRead(UploadProblem.TOO_LARGE, BYTES_PER_MB + 1, 1)
    assert (model.calls, check.asked) == ([], 0)


def test_a_megabyte_is_counted_as_streamlit_counts_its_own_limit() -> None:
    assert BYTES_PER_MB == 1_048_576


@pytest.mark.parametrize(
    "data",
    [TEXT, b"", b"GIF89a invented", b"\x89PN", b"\xff\xd8"],
    ids=["text", "empty", "gif", "half a png start", "half a jpeg start"],
)
def test_anything_but_a_png_or_a_jpeg_is_not_a_picture_and_asks_nothing(data: bytes) -> None:
    outcome, model, check = taken(data)

    assert outcome == UploadNotRead(UploadProblem.NOT_A_PICTURE, len(data), LOCAL.screenshot_max_mb)
    assert (model.calls, check.asked) == ([], 0)


def test_a_server_without_the_vision_model_is_shown_no_picture() -> None:
    outcome, model, check = taken(PNG, check=Check(VisionModelPresence.MISSING))

    assert isinstance(outcome, UploadNotRead)
    assert outcome.problem is UploadProblem.VISION_MODEL_MISSING
    assert outcome.error is None
    assert (model.calls, check.asked) == ([], 1)


@pytest.mark.parametrize("kind", list(ModelErrorKind))
def test_a_server_that_cannot_be_asked_is_shown_no_picture_and_its_error_is_kept(
    kind: ModelErrorKind,
) -> None:
    error = ModelError(kind, "invented", status=500)

    outcome, model, _ = taken(PNG, check=Check(error))

    assert isinstance(outcome, UploadNotRead)
    assert outcome.problem is UploadProblem.VISION_MODEL_UNCHECKED
    assert outcome.error is error
    assert model.calls == []


@pytest.mark.parametrize("kind", list(ModelErrorKind))
def test_a_model_failure_while_reading_keeps_the_error_and_the_reading(
    kind: ModelErrorKind,
) -> None:
    error = ModelError(kind, "the invented server broke", status=503)

    outcome, model, _ = taken(PNG, model=ScriptedModel([error]))

    assert isinstance(outcome, UploadNotRead)
    assert outcome.problem is UploadProblem.MODEL_FAILED
    assert outcome.error is error
    assert isinstance(outcome.reading, PictureNotRead)
    assert outcome.reading.error is error
    assert len(model.calls) == 1


def test_a_malformed_reply_that_is_not_an_empty_one_is_a_model_failure() -> None:
    error = ModelError(ModelErrorKind.MALFORMED_REPLY, "the answer is not marked as complete")

    outcome, _, _ = taken(PNG, model=ScriptedModel([error]))

    assert isinstance(outcome, UploadNotRead)
    assert outcome.problem is UploadProblem.MODEL_FAILED


def test_an_empty_reply_is_told_by_the_plugs_words() -> None:
    error = ModelError(
        ModelErrorKind.MALFORMED_REPLY,
        f"the model server's answer {EMPTY_REPLY_WORDS}; the model wrote only its thinking",
    )

    outcome, _, _ = taken(PNG, model=ScriptedModel([error]))

    assert isinstance(outcome, UploadNotRead)
    assert outcome.problem is UploadProblem.EMPTY
    assert outcome.error is error


def test_the_same_words_of_another_kind_are_not_an_empty_reply() -> None:
    error = ModelError(ModelErrorKind.SERVER_ERROR, f"it {EMPTY_REPLY_WORDS}")

    outcome, _, _ = taken(PNG, model=ScriptedModel([error]))

    assert isinstance(outcome, UploadNotRead)
    assert outcome.problem is UploadProblem.MODEL_FAILED


@pytest.mark.parametrize("text", ["", "   ", "\n\t"])
def test_a_reading_of_blank_text_is_empty(text: str) -> None:
    outcome, _, _ = taken(PNG, model=ScriptedModel([text]))

    assert isinstance(outcome, UploadNotRead)
    assert outcome.problem is UploadProblem.EMPTY


def test_a_reading_cut_off_is_said_as_such_with_its_call() -> None:
    reply = cut_off()

    outcome, _, _ = taken(PNG, model=ScriptedModel([reply]))

    assert isinstance(outcome, UploadNotRead)
    assert outcome.problem is UploadProblem.CUT_OFF
    assert outcome.error is None
    assert outcome.reading is not None
    assert outcome.reading.problems == (ReadingProblem.CUT_OFF,)
    assert outcome.reading.calls == (reply.record,)


def test_every_problem_of_a_reply_has_its_own_problem_here() -> None:
    assert set(_READING_PROBLEMS) == set(ReadingProblem)


# --- the order: several at once, the first is said ----------------------------

FAILING: dict[str, Callable[[], tuple[object, ScriptedModel, Check]]] = {
    "cloud, too large and not a picture": lambda: taken(
        LONG_TEXT, settings=ModelSettings(plug=Plug.CLOUD, screenshot_max_mb=1)
    ),
    "too large and not a picture": lambda: taken(LONG_TEXT, settings=limited(1)),
    "too large, and the model is missing": lambda: taken(
        png_of(BYTES_PER_MB + 1),
        settings=limited(1),
        check=Check(VisionModelPresence.MISSING),
    ),
    "not a picture, and the server cannot be asked": lambda: taken(
        TEXT, check=Check(ModelError(ModelErrorKind.UNREACHABLE, "nobody"))
    ),
    "the model is missing, and reading would fail": lambda: taken(
        PNG,
        model=ScriptedModel([ModelError(ModelErrorKind.TIMED_OUT, "slow")]),
        check=Check(VisionModelPresence.MISSING),
    ),
}
FIRST = {
    "cloud, too large and not a picture": UploadProblem.CLOUD_PLUG,
    "too large and not a picture": UploadProblem.TOO_LARGE,
    "too large, and the model is missing": UploadProblem.TOO_LARGE,
    "not a picture, and the server cannot be asked": UploadProblem.NOT_A_PICTURE,
    "the model is missing, and reading would fail": UploadProblem.VISION_MODEL_MISSING,
}


@pytest.mark.parametrize("case", list(FAILING))
def test_when_several_steps_would_not_pass_the_first_is_said(case: str) -> None:
    outcome, model, _ = FAILING[case]()

    assert isinstance(outcome, UploadNotRead)
    assert outcome.problem is FIRST[case]
    assert model.calls == []


# --- the words that tell an empty reply ---------------------------------------


def test_the_words_are_those_the_model_comparison_counts_an_empty_reply_by() -> None:
    assert EMPTY_REPLY_WORDS == _EMPTY_REPLY


# --- the caller's mistakes ----------------------------------------------------


def test_an_upload_is_bytes() -> None:
    with pytest.raises(TypeError, match="an upload is bytes"):
        read_upload(bytearray(PNG), LOCAL, vision_model=ScriptedModel([]), check=Check())  # type: ignore[arg-type]


@pytest.mark.parametrize("missing", ["vision model", "check"])
def test_the_local_plug_needs_the_vision_model_and_the_check(missing: str) -> None:
    model = None if missing == "vision model" else ScriptedModel([])
    check = None if missing == "check" else Check()

    with pytest.raises(ValueError, match="vision model and its check"):
        read_upload(PNG, LOCAL, vision_model=model, check=check)
