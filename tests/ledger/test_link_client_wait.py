"""Tests of a call to the ledger's assistant link with a shorter wait of the caller's own.

The stand-in link (``fake_link.py``, scenario ``late_rates``) answers the
call for exchange rates only after a while; every other call at once. A
caller that gave up waiting must never take that late answer for the next
call's. Invented data only.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ledger_hand.ledger.link_client import LedgerLink
from ledger_hand.ledger.link_failures import LedgerLinkError, LinkFailure
from tests.ledger.test_link_client import ledger_folder, node, setup, started

__all__ = ["ledger_folder", "node", "started"]  # the stand-in link's fixtures, used below


def test_a_call_with_a_shorter_wait_times_out_and_its_late_answer_is_never_the_next_ones(
    ledger_folder: Path, node: str
) -> None:
    with LedgerLink(setup(ledger_folder, node, "late_rates", FAKE_LINK_LATE="1")) as link:
        with pytest.raises(LedgerLinkError) as raised:
            link.call_within("list_exchange_rates", {}, 0.2)
        answer = link.call("echo", {"asked": "propose_trade_add"})

    assert raised.value.failure is LinkFailure.TIMED_OUT
    assert answer.content == {"echoed": {"asked": "propose_trade_add"}}


def test_a_call_with_no_time_left_is_not_sent(started: LedgerLink) -> None:
    with pytest.raises(LedgerLinkError) as raised:
        started.call_within("echo", {}, 0)

    assert raised.value.failure is LinkFailure.TIMED_OUT
    assert started.call("echo", {"one": 1}).content == {"echoed": {"one": 1}}
