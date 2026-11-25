"""Tests of recording from a screenshot, with fake models standing in for every call.

The text read off the picture and the note are joined into one passage,
which goes the way a typed passage goes; the reading's call and prompt come
first in the passage's state. A screenshot that was not read ends the
passage at the reading step, without calling the model that extracts or
reading the book. Every passage, reply and picture byte here is invented.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from ledger_hand.core.assets import BUILT_IN_ASSETS
from ledger_hand.extraction.picture_reading import PictureNotRead, PictureRead, ReadingProblem
from ledger_hand.flows.progress import (
    DEFAULT_TUNING,
    Call,
    Failure,
    Progress,
    Setting,
    Stage,
    Step,
    TradeStatus,
)
from ledger_hand.flows.recording import start
from ledger_hand.flows.screenshot import (
    NOTE_SEPARATOR,
    joined_passage,
    read_screenshot,
    start_from_reading,
    start_from_screenshot,
)
from ledger_hand.ports import (
    FinishReason,
    ModelError,
    ModelErrorKind,
    ModelReply,
    Picture,
    PictureKind,
    ReplyRecord,
)
from tests.fakes.memory_store import MemoryStore
from tests.fakes.routed_model import RoutedModel
from tests.flows.scripted_flow import NOW, ZONE, row, screened, table

PICTURE = Picture(b"\x89PNG\r\n\x1a\n invented", PictureKind.PNG)
READ = "方向: 买入\n币对: ETH/USDT\n成交数量: 0.5 ETH\n成交均价: 3,420 USDT\n时间: 昨天\n"
NOTE = "  手续费 0.2 USDT，在 OKX 买的 \n"
JOINED = READ.strip() + NOTE_SEPARATOR + NOTE.strip()
ROWS = table(
    row(
        side="buy",
        coin="ETH",
        quantity="0.5 ETH",
        price="3,420 USDT",
        fee="0.2 USDT",
        time="昨天",
        platform="OKX",
    )
)
SPOT = screened(("spot_trade", "买入"))
READING_RECORD = ReplyRecord(
    model="invented-vl",
    elapsed_seconds=6.5,
    prompt_tokens=1200,
    reply_tokens=60,
    finish=FinishReason.STOPPED,
)
READ_REPLY = ModelReply(text=READ, record=READING_RECORD)


def vision(*steps: object) -> RoutedModel:
    return RoutedModel(pictures=steps)  # type: ignore[arg-type]


def extraction() -> RoutedModel:
    return RoutedModel(screen=[SPOT], extraction=[ROWS])


def reading() -> PictureRead:
    result = read_screenshot(PICTURE, vision(READ_REPLY))
    assert isinstance(result, PictureRead)
    return result


# --- joining the text read and the note ---------------------------------------------


def test_the_text_read_comes_first_then_the_note_each_as_it_was() -> None:
    joined = joined_passage(READ, NOTE)

    assert joined == JOINED
    assert joined.startswith(READ.strip())
    assert joined.endswith(NOTE.strip())
    assert READ.strip() in joined and NOTE.strip() in joined
    assert NOTE_SEPARATOR == "\n\n"


@pytest.mark.parametrize("note", ["", "  ", "\n\t"])
def test_a_blank_note_leaves_the_text_read_alone(note: str) -> None:
    assert joined_passage(READ, note) == READ.strip()


def test_a_blank_text_leaves_the_note_alone() -> None:
    assert joined_passage("  \n", NOTE) == NOTE.strip()


@pytest.mark.parametrize(("text", "note"), [(None, ""), ("read", None), (b"read", "")])
def test_both_parts_are_text(text: object, note: object) -> None:
    with pytest.raises(TypeError):
        joined_passage(text, note)  # type: ignore[arg-type]


# --- reading -------------------------------------------------------------------------


def test_reading_is_the_extraction_step_with_read_1() -> None:
    model = vision(READ_REPLY)

    result = read_screenshot(PICTURE, model)

    assert result == PictureRead(READ, (READING_RECORD,), "read-1")
    assert model.pictures.calls[0].pictures == (PICTURE,)


def test_the_step_of_reading_is_said_as_the_others_are() -> None:
    assert Step.READING.value == "reading the screenshot"
    assert list(Step)[0] is Step.READING


# --- starting from a reading -------------------------------------------------------------


def test_the_model_that_extracts_is_given_the_joined_passage() -> None:
    model = extraction()

    progress = start_from_reading(reading(), model, now=NOW, zone=ZONE, note=NOTE)

    assert progress.passage == JOINED
    assert model.extraction.calls[0].messages[-1].content == JOINED
    assert model.screen.calls[0].messages[-1].content == JOINED


def test_each_draft_holds_the_joined_passage_and_the_note_fills_what_the_screen_left_out() -> None:
    progress = start_from_reading(reading(), extraction(), now=NOW, zone=ZONE, note=NOTE)

    (trade,) = progress.trades
    assert trade.draft.raw_text == JOINED
    assert trade.draft.fee == Decimal("0.2")
    assert trade.draft.fee_coin == "USDT"
    assert trade.draft.platform == "OKX"
    assert trade.status is TradeStatus.RECORDED
    assert progress.stage is Stage.REVIEWING


def test_the_reading_comes_first_among_the_calls_and_the_prompts() -> None:
    progress = start_from_reading(reading(), extraction(), now=NOW, zone=ZONE, note=NOTE)

    assert progress.calls[0] == Call(Step.READING, READING_RECORD)
    assert [call.step for call in progress.calls] == [
        Step.READING,
        Step.SCREENING,
        Step.EXTRACTION,
    ]
    assert progress.prompts[0] == (Step.READING, "read-1")
    assert [step for step, _ in progress.prompts] == [
        Step.READING,
        Step.SCREENING,
        Step.EXTRACTION,
    ]


def test_starting_from_a_reading_is_starting_the_joined_passage_with_the_reading_first() -> None:
    from_reading = start_from_reading(reading(), extraction(), now=NOW, zone=ZONE, note=NOTE)
    typed = start(JOINED, extraction(), now=NOW, zone=ZONE)

    assert from_reading.calls[1:] == typed.calls
    assert from_reading.prompts[1:] == typed.prompts
    assert from_reading.trades == typed.trades
    assert from_reading.passage == typed.passage


def test_a_text_the_person_changed_is_used_and_the_reading_still_comes_first() -> None:
    changed = READ.replace("0.5 ETH", "0.6 ETH")
    model = RoutedModel(
        screen=[SPOT], extraction=[table(row(side="buy", coin="ETH", quantity="0.6 ETH"))]
    )

    progress = start_from_reading(reading(), model, now=NOW, zone=ZONE, text=changed, note=NOTE)

    assert progress.passage == changed.strip() + NOTE_SEPARATOR + NOTE.strip()
    assert progress.calls[0] == Call(Step.READING, READING_RECORD)
    assert progress.prompts[0] == (Step.READING, "read-1")


def test_the_book_is_read_as_for_a_typed_passage() -> None:
    book = MemoryStore()

    start_from_reading(reading(), extraction(), now=NOW, zone=ZONE, note=NOTE, book=book)

    assert book.calls == ["earlier_saves", "confirmed_coins"]


def test_a_reading_that_was_not_made_is_refused() -> None:
    not_read = PictureNotRead(ModelError(ModelErrorKind.TIMED_OUT, "slow"), (), (), "read-1")
    model = extraction()

    with pytest.raises(ValueError, match="was not read"):
        start_from_reading(not_read, model, now=NOW, zone=ZONE)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        start_from_reading(READ, model, now=NOW, zone=ZONE)  # type: ignore[arg-type]

    assert model.screen.calls == []


# --- all at once ---------------------------------------------------------------------


def test_all_at_once_gives_what_starting_from_the_reading_gives() -> None:
    at_once = start_from_screenshot(
        PICTURE, vision(READ_REPLY), extraction(), now=NOW, zone=ZONE, note=NOTE
    )
    in_two = start_from_reading(reading(), extraction(), now=NOW, zone=ZONE, note=NOTE)

    assert at_once == in_two


def failed(reading_step: object, *, note: str = NOTE) -> tuple[Progress, RoutedModel, MemoryStore]:
    model, book = extraction(), MemoryStore()
    progress = start_from_screenshot(
        PICTURE, vision(reading_step), model, now=NOW, zone=ZONE, note=note, book=book
    )
    return progress, model, book


def test_a_model_failure_while_reading_ends_the_passage_there() -> None:
    error = ModelError(ModelErrorKind.MALFORMED_REPLY, "has an empty reply")

    progress, model, book = failed(error)

    assert progress == Progress(
        Stage.FAILED,
        NOTE.strip(),
        Setting(NOW, ZONE, BUILT_IN_ASSETS, DEFAULT_TUNING),
        failure=Failure(Step.READING, error, ()),
        prompts=((Step.READING, "read-1"),),
        calls=(),
    )
    assert model.screen.calls == [] and model.extraction.calls == []
    assert book.calls == []


def test_a_reading_cut_off_ends_the_passage_there_with_its_call() -> None:
    cut = ModelReply(
        text="方向: 买入\n币对: ET",
        record=ReplyRecord(
            model="invented-vl",
            elapsed_seconds=30.0,
            prompt_tokens=1200,
            reply_tokens=1024,
            finish=FinishReason.LENGTH_LIMIT,
        ),
    )

    progress, model, book = failed(cut)

    assert progress.stage is Stage.FAILED
    assert progress.failure == Failure(Step.READING, None, (ReadingProblem.CUT_OFF.value,))
    assert progress.calls == (Call(Step.READING, cut.record),)
    assert progress.prompts == ((Step.READING, "read-1"),)
    assert progress.passage == NOTE.strip()
    assert progress.trades == ()
    assert model.screen.calls == [] and model.extraction.calls == []
    assert book.calls == []


def test_with_no_note_a_failed_reading_leaves_an_empty_passage() -> None:
    progress, _, _ = failed(ModelError(ModelErrorKind.TIMED_OUT, "slow"), note="")

    assert progress.passage == ""
    assert progress.over


@pytest.mark.parametrize(
    ("now", "zone"),
    [
        (datetime(2026, 10, 7, 21, 0), ZONE),
        ("2026-10-07T21:00:00+02:00", ZONE),
        (NOW, "Mars/Olympus"),
        (NOW, None),
    ],
    ids=["no offset", "text", "unknown zone", "no zone"],
)
def test_a_wrong_moment_or_zone_is_refused_before_the_picture_is_sent(
    now: object, zone: object
) -> None:
    seeing, model = vision(READ_REPLY), extraction()

    with pytest.raises(ValueError):
        start_from_screenshot(PICTURE, seeing, model, now=now, zone=zone)  # type: ignore[arg-type]

    assert seeing.pictures.calls == []
    assert model.screen.calls == []


def test_the_refusals_say_what_starting_a_typed_passage_says() -> None:
    for now, zone in ((datetime(2026, 10, 7, 21, 0), ZONE), (NOW, "Mars/Olympus")):
        with pytest.raises(ValueError) as typed:
            start("买了 0.5 ETH", extraction(), now=now, zone=zone)
        with pytest.raises(ValueError) as shown:
            start_from_screenshot(PICTURE, vision(READ_REPLY), extraction(), now=now, zone=zone)
        assert str(shown.value) == str(typed.value)
