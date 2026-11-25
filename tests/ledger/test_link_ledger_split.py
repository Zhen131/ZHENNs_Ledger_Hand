"""Tests of the plug's two rare cases (68B3, addition 1): a later call that fails, a status unknown.

Eleven trades go to the ledger in two calls (``MOST_PER_CALL`` is ten). When
the second call fails after the first was taken, the first ten are handed
back as waiting, and the eleventh is said as the failure leaves it: one
that timed out "may already have reached the ledger" and is never sent
again. The ten results of the first call are written in the shape of the
captured sample ``propose-add-two-taken.json``; the identifiers are
invented. A status word the ledger answers that this program does not
know is a plain failure, never a program error. Every figure is invented.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ledger_hand.core.proposals import CheckOutcome
from ledger_hand.ledger.link_client import AnswerKind, ToolAnswer
from ledger_hand.ledger.link_failures import LedgerLinkError, LinkFailure
from ledger_hand.ledger.link_ledger import MOST_PER_CALL
from ledger_hand.ports import LedgerError, LedgerErrorKind
from tests.ledger.test_link_ledger import ASSETS, SAID, facts, plug


def taken(count: int) -> ToolAnswer:
    """``count`` trades taken, in the shape of the sample ``propose-add-two-taken``."""
    results = [{"ok": True, "proposalId": f"invented-{n:02d}"} for n in range(1, count + 1)]
    return ToolAnswer(kind=AnswerKind.RESULT, content={"results": results})


ELEVEN = tuple(
    facts(quantity=Decimal(f"0.0{n}"), total=Decimal(f"{n}00")) for n in range(1, 10)
) + (
    facts(quantity=Decimal("0.1"), total=Decimal("6000")),
    facts(quantity=Decimal("0.2"), total=Decimal("12000")),
)


def test_eleven_trades_go_in_two_calls_of_ten_and_one() -> None:
    assert MOST_PER_CALL == 10
    ledger, link = plug(ASSETS, ("propose_trade_add", taken(10)), ("propose_trade_add", taken(1)))

    result = ledger.propose_add(ELEVEN, SAID)

    assert len(result.checks) == 11
    assert [len(arguments["trades"]) for name, arguments in link.asked[1:]] == [10, 1]


def test_a_second_call_timing_out_keeps_ten_and_says_the_last_may_have_arrived() -> None:
    timed_out = LedgerLinkError(LinkFailure.TIMED_OUT, "waiting for an answer")
    ledger, link = plug(ASSETS, ("propose_trade_add", taken(10)), ("propose_trade_add", timed_out))

    result = ledger.propose_add(ELEVEN, SAID)

    assert result.proposal_ids == tuple(f"invented-{n:02d}" for n in range(1, 11))
    last = result.checks[10]
    assert (last.outcome, last.code) == (CheckOutcome.FAILED, "HAND_MAY_HAVE_ARRIVED")
    assert "may already have reached the ledger" in (last.message or "")
    assert "pending list" in (last.message or "")
    # Never sent again: the assets, the first call, the second; nothing after.
    assert link.names() == ["list_assets", "propose_trade_add", "propose_trade_add"]


def test_a_second_call_finding_the_page_gone_keeps_ten_and_says_the_last_was_not_sent() -> None:
    gone = ToolAnswer(
        kind=AnswerKind.ERROR,
        content={
            "code": "LEDGER_PAGE_DISCONNECTED",
            "category": "temporarily-unavailable",
            "message": "The ledger page disconnected.",
        },
    )
    ledger, _ = plug(ASSETS, ("propose_trade_add", taken(10)), ("propose_trade_add", gone))

    result = ledger.propose_add(ELEVEN, SAID)

    assert len(result.proposal_ids) == 10
    last = result.checks[10]
    assert (last.code, last.message) == (
        "LEDGER_PAGE_DISCONNECTED",
        "It was not sent: The ledger page disconnected.",
    )


def test_a_first_call_that_times_out_is_still_the_ledgers_failure() -> None:
    timed_out = LedgerLinkError(LinkFailure.TIMED_OUT, "waiting for an answer")
    ledger, _ = plug(ASSETS, ("propose_trade_add", timed_out))

    with pytest.raises(LedgerError) as raised:
        ledger.propose_add(ELEVEN, SAID)

    assert raised.value.kind is LedgerErrorKind.TIMED_OUT


def test_a_status_word_this_program_does_not_know_is_a_plain_failure() -> None:
    odd = ToolAnswer(
        kind=AnswerKind.RESULT, content={"proposalId": "invented-01", "status": "archived"}
    )
    ledger, _ = plug(("get_proposal_status", odd))

    with pytest.raises(LedgerError) as raised:
        ledger.proposal_status("invented-01")

    assert (raised.value.kind, raised.value.code) == (LedgerErrorKind.OTHER, "HAND_STATUS_UNKNOWN")
    assert "'archived'" in raised.value.message
    assert "please look at the ledger" in raised.value.message
