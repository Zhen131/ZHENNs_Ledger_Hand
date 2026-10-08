"""Tests of reading the model's list of reports about a passage.

A reply is read only when it has exactly the shape of the list; anything
else is unreadable, with the part of the shape it missed. Every reply below
is invented.
"""

from __future__ import annotations

import json

import pytest

from ledger_hand.extraction.screen_table import (
    MAX_REPORTS,
    MAX_SCREEN_REPLY_CHARACTERS,
    NOT_TO_RECORD,
    SCREEN_TABLE,
    Kind,
    ScreenProblem,
    ScreenReplyUnreadable,
    ScreenReport,
    read_screen_reply,
)
from ledger_hand.ports import FinishReason, ModelReply, ReplyRecord


def reply(text: str, finish: FinishReason = FinishReason.STOPPED) -> ModelReply:
    record = ReplyRecord(
        model="scripted", elapsed_seconds=0.0, prompt_tokens=None, reply_tokens=None, finish=finish
    )
    return ModelReply(text=text, record=record)


def test_the_kinds_and_the_ones_not_recorded() -> None:
    assert [kind.value for kind in Kind] == [
        "spot_trade",
        "futures_or_leverage",
        "coin_for_coin",
        "open_order",
        "plan",
    ]
    assert frozenset(Kind) - {Kind.SPOT_TRADE} == NOT_TO_RECORD


def test_the_schema_lists_every_kind_and_asks_for_kind_and_evidence() -> None:
    item = SCREEN_TABLE["properties"]["reports"]["items"]  # type: ignore[index]

    assert item["properties"]["kind"]["enum"] == [kind.value for kind in Kind]
    assert item["required"] == ["kind", "evidence"]


def test_a_list_of_reports_is_read_in_order() -> None:
    text = json.dumps(
        {
            "reports": [
                {"kind": "spot_trade", "evidence": "买了 1 ETH"},
                {"kind": "plan", "evidence": "明天再说", "extra": 1},
            ],
            "note": "ignored",
        },
        ensure_ascii=False,
    )

    assert read_screen_reply(reply(text)) == (
        ScreenReport(Kind.SPOT_TRADE, "买了 1 ETH"),
        ScreenReport(Kind.PLAN, "明天再说"),
    )


def test_an_empty_list_and_a_missing_evidence_are_read() -> None:
    assert read_screen_reply(reply('{"reports": []}')) == ()
    assert read_screen_reply(reply('{"reports": [{"kind": "plan"}]}')) == (
        ScreenReport(Kind.PLAN, ""),
    )


@pytest.mark.parametrize(
    ("text", "problem"),
    [
        ("not json", ScreenProblem.NOT_JSON),
        ('{"reports": [], "reports": []}', ScreenProblem.REPEATED_KEY),
        (
            '{"reports": [{"kind": "plan", "kind": "plan", "evidence": ""}]}',
            ScreenProblem.REPEATED_KEY,
        ),
        ('{"reports": NaN}', ScreenProblem.NOT_JSON),
        ("[]", ScreenProblem.NO_REPORTS_LIST),
        ('{"trades": []}', ScreenProblem.NO_REPORTS_LIST),
        ('{"reports": {}}', ScreenProblem.NO_REPORTS_LIST),
        ('{"reports": ["plan"]}', ScreenProblem.REPORT_NOT_AN_OBJECT),
        ('{"reports": [{"kind": "swap", "evidence": ""}]}', ScreenProblem.KIND_NOT_ALLOWED),
        ('{"reports": [{"kind": 3, "evidence": ""}]}', ScreenProblem.KIND_NOT_ALLOWED),
        ('{"reports": [{"evidence": "x"}]}', ScreenProblem.KIND_NOT_ALLOWED),
        ('{"reports": [{"kind": "plan", "evidence": 1}]}', ScreenProblem.EVIDENCE_NOT_TEXT),
        ('{"reports": [{"kind": "plan", "evidence": "\\ud800"}]}', ScreenProblem.EVIDENCE_NOT_TEXT),
        ("[" * 100_000, ScreenProblem.NOT_JSON),
    ],
)
def test_a_reply_that_misses_the_shape_is_unreadable(text: str, problem: ScreenProblem) -> None:
    assert read_screen_reply(reply(text)) == ScreenReplyUnreadable(problem)


def test_a_reply_cut_off_or_too_long_is_unreadable() -> None:
    assert read_screen_reply(reply('{"reports": []}', FinishReason.LENGTH_LIMIT)) == (
        ScreenReplyUnreadable(ScreenProblem.CUT_OFF)
    )
    too_long = '{"reports": []}' + " " * MAX_SCREEN_REPLY_CHARACTERS
    assert read_screen_reply(reply(too_long)) == ScreenReplyUnreadable(ScreenProblem.TOO_LONG)


def test_too_many_reports_is_unreadable() -> None:
    many = {"reports": [{"kind": "plan", "evidence": ""}] * (MAX_REPORTS + 1)}

    assert read_screen_reply(reply(json.dumps(many))) == ScreenReplyUnreadable(
        ScreenProblem.TOO_MANY_REPORTS
    )
