"""Tests of judging a passage before extraction, with the scripted model playing the replies.

The model says which kinds of thing a passage reports; the program decides
what follows. Every passage and reply below is invented.
"""

from __future__ import annotations

import json

import pytest

from ledger_hand.extraction.extractor import DEFAULT_ASKS_AGAIN, PassageProblem, PassageRefused
from ledger_hand.extraction.prompts.screen import SCREEN_PROMPT
from ledger_hand.extraction.screen_table import SCREEN_TABLE, Kind, ScreenProblem
from ledger_hand.extraction.screening import (
    REASONS,
    Decision,
    Report,
    Screened,
    ScreenFailed,
    ScreenUnreadable,
    screen,
)
from ledger_hand.ports import ModelError, ModelErrorKind, ModelParameters, Role
from tests.fakes.scripted_model import ScriptedModel

LEVERAGE = "前天用 5 倍杠杆开多 SOL，开仓 150"
MIXED = "早上买了 0.3 ETH，价格 3,050；打算周末再卖掉"


def reports(*items: tuple[str, str]) -> str:
    return json.dumps(
        {"reports": [{"kind": kind, "evidence": evidence} for kind, evidence in items]},
        ensure_ascii=False,
    )


def screened(passage: str, *steps: str | ModelError) -> tuple[object, ScriptedModel]:
    model = ScriptedModel(steps)
    return screen(passage, model), model


def test_only_a_kind_not_recorded_stops_the_passage_with_its_words() -> None:
    result, model = screened(LEVERAGE, reports(("futures_or_leverage", "5 倍杠杆开多")))

    assert result == Screened(
        Decision.STOP,
        (Report(Kind.FUTURES_OR_LEVERAGE, "5 倍杠杆开多"),),
        result.calls,  # type: ignore[union-attr]
    )
    assert len(model.calls) == 1


def test_a_filled_spot_trade_goes_on_and_hands_on_the_rest() -> None:
    result, _ = screened(
        MIXED, reports(("spot_trade", "早上买了 0.3 ETH"), ("plan", "打算周末再卖掉"))
    )

    assert isinstance(result, Screened)
    assert result.decision is Decision.EXTRACT
    assert result.set_aside == (Report(Kind.PLAN, "打算周末再卖掉"),)


def test_nothing_reported_is_no_trade() -> None:
    result, _ = screened("今天行情真无聊", reports())

    assert isinstance(result, Screened)
    assert result.decision is Decision.NO_TRADE
    assert result.reports == ()


def test_evidence_that_is_not_a_piece_of_the_passage_is_dropped_and_the_kind_kept() -> None:
    result, _ = screened(LEVERAGE, reports(("futures_or_leverage", "opened a 5x long")))

    assert isinstance(result, Screened)
    assert result.decision is Decision.STOP
    assert result.reports == (Report(Kind.FUTURES_OR_LEVERAGE, None),)


def test_evidence_is_given_in_the_passage_s_own_writing() -> None:
    result, _ = screened("用５倍杠杆开多 SOL", reports(("futures_or_leverage", "用5倍杠杆开多")))

    assert isinstance(result, Screened)
    assert result.reports == (Report(Kind.FUTURES_OR_LEVERAGE, "用５倍杠杆开多"),)


def test_the_same_report_twice_is_kept_once() -> None:
    result, _ = screened(
        LEVERAGE,
        reports(("futures_or_leverage", "5 倍杠杆"), ("futures_or_leverage", "5 倍杠杆")),
    )

    assert isinstance(result, Screened)
    assert result.reports == (Report(Kind.FUTURES_OR_LEVERAGE, "5 倍杠杆"),)


def test_a_spot_trade_beside_a_kind_not_recorded_is_never_stopped_nor_hidden() -> None:
    result, _ = screened(LEVERAGE, reports(("spot_trade", ""), ("futures_or_leverage", "")))

    assert isinstance(result, Screened)
    assert result.decision is Decision.EXTRACT
    assert result.set_aside == (Report(Kind.FUTURES_OR_LEVERAGE, None),)


def test_the_model_is_asked_with_the_prompt_the_passage_and_the_list() -> None:
    parameters = ModelParameters(
        temperature=0.0, top_p=1.0, max_reply_tokens=10, context_tokens=100, timeout_seconds=5.0
    )
    model = ScriptedModel([reports()])

    screen(MIXED, model, parameters=parameters)

    (call,) = model.calls
    assert [(message.role, message.content) for message in call.messages] == [
        (Role.SYSTEM, SCREEN_PROMPT.instructions),
        (Role.USER, MIXED),
    ]
    assert call.reply_schema == SCREEN_TABLE
    assert call.parameters == parameters


def test_an_unreadable_reply_is_asked_again_once_with_what_was_wrong() -> None:
    result, model = screened(MIXED, "not json", reports(("spot_trade", "早上买了 0.3 ETH")))

    assert isinstance(result, Screened)
    assert len(model.calls) == 2
    assert ScreenProblem.NOT_JSON.value in model.calls[1].messages[-1].content
    assert DEFAULT_ASKS_AGAIN == 1


def test_replies_that_stay_unreadable_decide_nothing() -> None:
    result, model = screened(MIXED, "not json", '{"reports": [{"kind": "swap"}]}')

    assert result == ScreenUnreadable(
        (ScreenProblem.NOT_JSON, ScreenProblem.KIND_NOT_ALLOWED),
        result.calls,  # type: ignore[union-attr]
    )
    assert len(model.calls) == 2


def test_a_model_error_is_handed_back_as_raised_and_decides_nothing() -> None:
    error = ModelError(ModelErrorKind.TIMED_OUT, "invented")

    result, _ = screened(MIXED, error)

    assert isinstance(result, ScreenFailed)
    assert result.error is error


@pytest.mark.parametrize(
    ("passage", "problem"),
    [
        ("", PassageProblem.EMPTY),
        ("  \n ", PassageProblem.EMPTY),
        ("\ud800", PassageProblem.NOT_VALID_TEXT),
    ],
)
def test_a_passage_that_cannot_be_sent_is_never_sent(passage: str, problem: PassageProblem) -> None:
    result, model = screened(passage)

    assert result == PassageRefused(problem)
    assert model.calls == []


def test_every_kind_not_recorded_has_a_reason() -> None:
    assert set(REASONS) == set(Kind) - {Kind.SPOT_TRADE}
