"""Tests of the assistant page's sentences for failures, and of each failure drawn on the page.

Every table has a sentence for every member of its enumeration; each way a
reply can rest on a failure (the model, the ledger, the step limit, the
program's taking over, a recording that failed) is said in an error box
under the reply; the Record page's own sentences are untouched; the one
sentence for a vision model list that is not clear points at the server.
Every value is invented.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ledger_hand.flows.standing import DemoDone, DemoOutcome
from ledger_hand.flows.uploading import UploadNotRead, UploadProblem
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ports import (
    LedgerError,
    LedgerErrorKind,
    ModelError,
    ModelErrorKind,
    ToolCall,
    ToolReply,
)
from ledger_hand.settings import ModelSettings
from ledger_hand.ui import assistant_failure_words as words
from ledger_hand.ui import failure_words
from ledger_hand.ui.assistant_view import exchange_key
from tests.fakes.routed_model import RoutedModel
from tests.fakes.scripted_model import scripted_record
from tests.flows.scripted_flow import screened
from tests.ui.assistant_harness import errors, open_assistant, say_on_page

SETTINGS = ModelSettings()
UI = Path(__file__).resolve().parents[2] / "src" / "ledger_hand" / "ui"


def calls(name: str, **arguments: object) -> ToolReply:
    return ToolReply(
        text="", calls=(ToolCall(name=name, arguments=dict(arguments)),), record=scripted_record()
    )


# --- every kind has a sentence ------------------------------------------------------


def test_every_ledger_failure_kind_has_a_sentence() -> None:
    assert set(words.LEDGER_FAILURES) == set(LedgerErrorKind)
    assert all(sentence.strip() for sentence in words.LEDGER_FAILURES.values())


def test_every_way_the_page_stops_has_a_sentence() -> None:
    assert set(words.STOPS) == set(words.Stop)
    for stop in words.Stop:
        assert "{" not in words.stop_words(stop, 6)


def test_every_demo_outcome_but_done_has_a_sentence() -> None:
    assert set(words.DEMO_WORDS) == set(DemoOutcome) - {DemoOutcome.DONE}


def test_a_demo_failure_says_the_ledgers_words() -> None:
    failure = LedgerError(LedgerErrorKind.OTHER, "proposal_not_pending", "Invented: not pending.")

    said = words.demo_words(DemoDone(outcome=DemoOutcome.FAILED, failure=failure))

    assert said.endswith("(Invented: not pending.)")


@pytest.mark.parametrize("problem", list(UploadProblem))
def test_every_screenshot_problem_is_said_as_the_record_page_says_it(
    problem: UploadProblem,
) -> None:
    outcome = UploadNotRead(problem=problem, size_bytes=3_000_000, limit_mb=2)

    assert words.screenshot_not_read(outcome, SETTINGS) == failure_words.screenshot_not_read(
        outcome, SETTINGS
    )


@pytest.mark.parametrize(
    "error",
    [
        ModelError(ModelErrorKind.MALFORMED_REPLY, "invented: list unreadable"),
        ModelError(ModelErrorKind.SERVER_ERROR, "invented: refused", status=400),
    ],
    ids=["list not read", "status 400"],
)
def test_the_vision_list_not_clear_is_said_as_the_servers_side(error: ModelError) -> None:
    outcome = UploadNotRead(
        problem=UploadProblem.VISION_MODEL_UNCHECKED, size_bytes=1000, limit_mb=2, error=error
    )

    said = words.screenshot_not_read(outcome, SETTINGS)

    assert said == words.VISION_LIST_UNCLEAR.format(
        address=SETTINGS.base_url, model=SETTINGS.vision_model
    )
    assert "another way" not in said
    assert failure_words.screenshot_not_read(outcome, SETTINGS) != said


def test_the_vision_server_unreachable_is_still_said_the_record_pages_way() -> None:
    error = ModelError(ModelErrorKind.UNREACHABLE, "invented: refused")
    outcome = UploadNotRead(
        problem=UploadProblem.VISION_MODEL_UNCHECKED, size_bytes=1000, limit_mb=2, error=error
    )

    assert words.screenshot_not_read(outcome, SETTINGS) == failure_words.screenshot_not_read(
        outcome, SETTINGS
    )


def test_no_assistant_file_of_the_interface_names_one_money() -> None:
    named = [
        path.name
        for path in sorted(UI.glob("assistant_*.py"))
        if "USDT" in path.read_text(encoding="utf-8")
    ]

    assert named == []


# --- each failure drawn on the page -----------------------------------------------------


@pytest.mark.parametrize("kind", list(ModelErrorKind))
def test_each_model_failure_is_said_under_the_reply(kind: ModelErrorKind) -> None:
    error = ModelError(kind, "invented failure")
    page = open_assistant(RoutedModel(tools=[error]), ledger=FakeLedger())

    page = say_on_page(page, "我现在持有什么")

    assert errors(page, exchange_key(1)) == [failure_words.model_trouble(error, SETTINGS)]


@pytest.mark.parametrize("kind", list(LedgerErrorKind))
def test_each_ledger_failure_is_said_under_the_reply(kind: LedgerErrorKind) -> None:
    # Recording asks the ledger for its assets first; any failure of it ends there.
    failure = LedgerError(kind, "invented", "Invented: the ledger failed.")
    page = open_assistant(
        RoutedModel(tools=[calls("propose_trade_add")]), ledger=FakeLedger(failure=failure)
    )

    page = say_on_page(page, "今天买了0.02 BTC")

    (said,) = errors(page, exchange_key(1))
    assert said == words.ledger_trouble(failure)


def test_the_step_limit_is_said_under_the_reply() -> None:
    page = open_assistant(
        RoutedModel(tools=[calls("list_assets"), calls("list_assets")]),
        ledger=FakeLedger(),
        steps=2,
    )

    page = say_on_page(page, "有哪些资产")

    assert errors(page, exchange_key(1)) == [words.stop_words(words.Stop.STEP_LIMIT, 2)]


def test_a_takeover_that_finds_nothing_is_said_under_the_reply() -> None:
    wrong = calls("no_such_tool")
    page = open_assistant(
        RoutedModel(tools=[wrong, wrong], screen=[screened()]), ledger=FakeLedger()
    )

    page = say_on_page(page, "今天天气不错")

    assert errors(page, exchange_key(1)) == [words.stop_words(words.Stop.TAKEOVER_FAILED, 6)]


def test_a_recording_the_model_failed_is_said_under_the_reply() -> None:
    error = ModelError(ModelErrorKind.TIMED_OUT, "invented: too slow")
    page = open_assistant(
        RoutedModel(tools=[calls("propose_trade_add")], screen=[error]), ledger=FakeLedger()
    )

    page = say_on_page(page, "今天买了0.02 BTC")

    (said,) = errors(page, exchange_key(1))
    assert said.startswith("The model gave no usable reply while")
