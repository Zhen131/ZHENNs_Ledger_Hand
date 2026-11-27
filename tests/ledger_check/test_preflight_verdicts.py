"""Tests of how the ledger tier reads what the ledger's import preflight says.

The preflight puts a fixed English prefix before what its structural check
says; selling more than is held and an offset the two time zone databases
disagree on are still recognised behind it. When a schema 5 file cannot be
upgraded, the preflight adds one line summing up the other errors: it is
left out when there are others, and is an error like any other alone. A
check the ledger could not do keeps a file from being accepted.
"""

from __future__ import annotations

import json

from scripts.ledger_check import (
    STRUCTURE_PREFIX,
    Accepted,
    HoldingsOnly,
    LedgerError,
    PlantedError,
    Refused,
    Verdict,
    is_holdings_shortfall,
    judge,
    parse_report,
    zone_data_errors,
)
from tests.ledger_check.cases import UPGRADE_ADDED_ASSETS, UPGRADE_SUMMED_UP

SUMMED_UP = PlantedError(*UPGRADE_SUMMED_UP)
SUMMING_UP = LedgerError(
    "BACKUP_SCHEMA_UPGRADE_FAILED",
    "ledgerData",
    "This ledger schema V5 backup could not be upgraded to V8, so nothing was imported; "
    "the backup file itself was not changed.",
)
SHORTFALL = LedgerError(
    "LEDGER_DATA_INVALID_TRADE_TIMELINE",
    "trades",
    STRUCTURE_PREFIX + "Cannot sell more SOL than current position",
)


def test_selling_more_than_held_is_recognised_behind_the_prefix_and_without_it() -> None:
    assert is_holdings_shortfall(SHORTFALL)
    bare = LedgerError(SHORTFALL.code, SHORTFALL.path, "Cannot sell SOL with zero current position")
    assert is_holdings_shortfall(bare)
    other = LedgerError(SHORTFALL.code, SHORTFALL.path, "Some prefix: Cannot sell more SOL than")
    assert not is_holdings_shortfall(other)


def test_an_offset_the_databases_disagree_on_is_recognised_behind_the_prefix() -> None:
    error = LedgerError(
        "LEDGER_DATA_INVALID_ENTITY",
        "trades[14].occurredAt",
        STRUCTURE_PREFIX
        + "trades[14].occurredAt offset must match occurredTimeZone at its instant",
    )
    verdict = Verdict(accepted=False, errors=(error,))

    assert zone_data_errors(verdict, frozenset({14})) == [error]


def test_the_summing_up_line_beside_a_shortfall_is_left_out() -> None:
    verdict = Verdict(accepted=False, errors=(SUMMING_UP, SHORTFALL))

    assert judge(HoldingsOnly(), verdict, summed_up=SUMMED_UP) == []
    assert judge(HoldingsOnly(), verdict) != []


def test_the_summing_up_line_beside_planted_errors_is_left_out() -> None:
    planted = PlantedError("LEDGER_DATA_INVALID_ENTITY", "trades[0].totalValue", "TOTAL_VALUE")
    reported = LedgerError(planted.code, planted.path, STRUCTURE_PREFIX + "TOTAL_VALUE_MISMATCH")
    verdict = Verdict(accepted=False, errors=(SUMMING_UP, reported))

    assert judge(Refused((planted,)), verdict, summed_up=SUMMED_UP) == []


def test_the_summing_up_line_alone_is_an_error() -> None:
    verdict = Verdict(accepted=False, errors=(SUMMING_UP,))

    assert judge(HoldingsOnly(), verdict, summed_up=SUMMED_UP) != []
    assert judge(Accepted(), verdict, summed_up=SUMMED_UP) != []


def test_a_check_not_done_keeps_a_file_from_being_accepted() -> None:
    verdict = Verdict(accepted=False, errors=(), skipped=("import-policy: not safe",))

    assert judge(Accepted(), verdict) == [
        "should have been accepted; not done: import-policy: not safe"
    ]


def test_the_report_carries_checks_not_done_and_groups_maybe_twice() -> None:
    document = {
        "backupFormatVersion": 3,
        "ledgerSchemaVersion": 8,
        "results": [
            {
                "file": "a.json",
                "ok": True,
                "errors": [],
                "skipped": [],
                "suspiciousGroups": 2,
            },
            {
                "file": "b.json",
                "ok": False,
                "errors": [],
                "skipped": [{"check": "import-policy", "reason": "not safe"}],
                "suspiciousGroups": 0,
            },
        ],
    }

    report = parse_report(json.dumps(document))

    assert report.verdicts[0] == Verdict(accepted=True, errors=(), suspicious_groups=2)
    assert report.verdicts[1].skipped == ("import-policy: not safe",)


def test_the_upgrade_adds_three_assets_to_the_limit() -> None:
    assert UPGRADE_ADDED_ASSETS == 3
