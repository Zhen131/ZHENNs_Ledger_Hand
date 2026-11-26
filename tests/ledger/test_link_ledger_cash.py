"""Tests of the real ledger's plug reading cash balances, against answers written from its README.

No running ledger was asked: each answer is a sample written from the
ledger's ``assistant-link/README.md`` and its own tests, and says so
(``_source``). The test names say "documented" for that reason. Every
figure is invented.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

import pytest

from ledger_hand.core.ledger_records import NO_CASH_TOOL
from ledger_hand.ledger.link_client import AnswerKind, ToolAnswer
from ledger_hand.ports import LedgerError, LedgerErrorKind
from tests.ledger.test_link_ledger import SAMPLES, plug, sample


def test_documented_samples_say_they_were_written_not_captured() -> None:
    for name in (
        "cash-balances-documented",
        "cash-balances-empty-documented",
        "cash-balances-unknown-tool-documented",
    ):
        kept = json.loads((SAMPLES / f"{name}.json").read_text(encoding="utf-8"))
        assert "not captured" in kept["_source"]
        assert (kept["tool"], kept["arguments"]) == ("get_cash_balances", {})


def test_documented_balances_come_back_one_row_a_money_as_the_ledger_gave_them() -> None:
    ledger, link = plug(("get_cash_balances", sample("cash-balances-documented")))

    balances = ledger.cash_balances()

    assert link.asked == [("get_cash_balances", {})]
    assert balances.day == date(2026, 11, 25)
    assert [(row.code, row.name, row.balance) for row in balances.balances] == [
        ("USDT", "Tether USD", Decimal("1200.5")),
        ("USD", "US Dollar", Decimal("-30")),
        ("CNY", "Chinese Yuan", Decimal("0")),
    ]


def test_documented_empty_balances_come_back_as_no_row() -> None:
    ledger, _ = plug(("get_cash_balances", sample("cash-balances-empty-documented")))

    assert ledger.cash_balances().balances == ()


def test_documented_unknown_tool_is_said_as_a_ledger_with_no_cash_tool() -> None:
    ledger, _ = plug(("get_cash_balances", sample("cash-balances-unknown-tool-documented")))

    with pytest.raises(LedgerError) as raised:
        ledger.cash_balances()

    assert raised.value.code == NO_CASH_TOOL
    assert raised.value.kind is LedgerErrorKind.OTHER


def test_documented_ledger_not_ready_stays_a_ledger_that_could_not_be_asked() -> None:
    not_ready = ToolAnswer(
        kind=AnswerKind.ERROR,
        content={
            "code": "LEDGER_NOT_READY",
            "category": "temporarily-unavailable",
            "message": "No ledger is open.",
        },
    )
    ledger, _ = plug(("get_cash_balances", not_ready))

    with pytest.raises(LedgerError) as raised:
        ledger.cash_balances()

    assert (raised.value.kind, raised.value.code) == (
        LedgerErrorKind.UNREACHABLE,
        "LEDGER_NOT_READY",
    )


@pytest.mark.parametrize(
    "content",
    [
        {"kind": "cash-balances", "todayDate": "not a day", "balances": []},
        {"kind": "cash-balances", "todayDate": "2026-11-25"},
        {"kind": "cash-balances", "todayDate": "2026-11-25", "balances": [{"currencyCode": "X"}]},
        {
            "kind": "cash-balances",
            "todayDate": "2026-11-25",
            "balances": [{"currencyCode": "USDT", "currencyName": "Tether", "balance": "a lot"}],
        },
    ],
    ids=["no day", "no list", "a row cut short", "no number"],
)
def test_an_answer_not_as_documented_is_a_failure_never_a_figure(
    content: dict[str, object],
) -> None:
    ledger, _ = plug(("get_cash_balances", ToolAnswer(kind=AnswerKind.RESULT, content=content)))

    with pytest.raises(LedgerError) as raised:
        ledger.cash_balances()

    assert raised.value.code == "HAND_ANSWER_UNEXPECTED"
