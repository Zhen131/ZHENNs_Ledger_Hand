"""Tests of the ledger tier's own logic, with no ledger checkout and no validator run.

What the ledger itself says is checked by the tier (``scripts/check.sh ledger``),
not here. These tests pin down how the tier judges a verdict, when it skips,
how it reads the Git files of a checkout, and which samples it hands over.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from ledger_hand.core.trade import NOT_ZONE_NAMES
from ledger_hand.core.zones import is_zone_name
from scripts import ledger_check
from scripts.ledger_check import (
    Accepted,
    HoldingsOnly,
    LedgerError,
    PlantedError,
    Refused,
    Verdict,
    is_holdings_shortfall,
    judge,
    locate_ledger,
)
from tests.export.samples import (
    GOLDEN_FILE,
    broken_texts,
    golden_text,
    zone_candidates,
    zones_taken,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

SHORTFALL = LedgerError(
    "LEDGER_DATA_INVALID_TRADE_TIMELINE", "trades", "Cannot sell more SOL than current position"
)
ZERO_POSITION = LedgerError(
    "LEDGER_DATA_INVALID_TRADE_TIMELINE", "trades", "Cannot sell SOL with zero current position"
)
TOTAL_OFF = LedgerError(
    "LEDGER_DATA_INVALID_ENTITY",
    "trades[0].totalValue",
    "TOTAL_VALUE_MISMATCH: quantity × price is 1898, but totalValue is 1899",
)


def refused(*errors: LedgerError) -> Verdict:
    return Verdict(accepted=False, errors=errors)


ACCEPTED = Verdict(accepted=True, errors=())


# --- telling a holdings shortfall from everything else ----------------------


@pytest.mark.parametrize("error", [SHORTFALL, ZERO_POSITION])
def test_both_wordings_of_selling_more_than_is_held_count(error: LedgerError) -> None:
    assert is_holdings_shortfall(error)


@pytest.mark.parametrize(
    "error",
    [
        # Same code, other errors.
        LedgerError(
            "LEDGER_DATA_INVALID_TRADE_TIMELINE",
            "trades",
            "A BTC buy fee must be less than the bought quantity",
        ),
        LedgerError(
            "LEDGER_DATA_INVALID_TRADE_TIMELINE",
            "trades",
            "Cannot sell more BTC from exchange than available",
        ),
        LedgerError(
            "LEDGER_DATA_INVALID_TRADE_TIMELINE", "trades", "Mixed currencies are not supported"
        ),
        # Same wording, another code.
        LedgerError("LEDGER_DATA_INVALID_ENTITY", "trades[0].quantity", SHORTFALL.message),
        TOTAL_OFF,
    ],
)
def test_nothing_else_counts_as_selling_more_than_is_held(error: LedgerError) -> None:
    assert not is_holdings_shortfall(error)


# --- judging a verdict ------------------------------------------------------


def test_an_accepted_file_with_no_error_is_as_expected() -> None:
    assert judge(Accepted(), ACCEPTED) == []


def test_a_refused_file_is_not_accepted() -> None:
    problems = judge(Accepted(), refused(TOTAL_OFF))

    assert len(problems) == 1
    assert "TOTAL_VALUE_MISMATCH" in problems[0]


def test_only_holdings_errors_are_as_expected_when_only_those_are_allowed() -> None:
    assert judge(HoldingsOnly(), refused(SHORTFALL, ZERO_POSITION)) == []


def test_any_other_error_beside_the_holdings_is_reported() -> None:
    problems = judge(HoldingsOnly(), refused(SHORTFALL, TOTAL_OFF))

    assert len(problems) == 1
    assert "TOTAL_VALUE_MISMATCH" in problems[0]


@pytest.mark.parametrize("expected", [HoldingsOnly(), Refused((PlantedError("X", "y", "z"),))])
def test_a_file_meant_to_be_refused_must_be_refused(
    expected: HoldingsOnly | Refused,
) -> None:
    assert judge(expected, ACCEPTED) != []
    assert judge(expected, refused()) != []


def test_planted_errors_match_one_for_one() -> None:
    planted = PlantedError("LEDGER_DATA_INVALID_ENTITY", "trades[0].totalValue", "MISMATCH")

    assert judge(Refused((planted,)), refused(TOTAL_OFF)) == []


def test_a_planted_error_must_match_in_code_path_and_message() -> None:
    for planted in (
        PlantedError("LEDGER_DATA_INVALID_REFERENCE", "trades[0].totalValue", "MISMATCH"),
        PlantedError("LEDGER_DATA_INVALID_ENTITY", "trades[1].totalValue", "MISMATCH"),
        PlantedError("LEDGER_DATA_INVALID_ENTITY", "trades[0].totalValue", "Unknown fee"),
    ):
        problems = judge(Refused((planted,)), refused(TOTAL_OFF))

        assert any("not reported" in problem for problem in problems), planted
        assert any("not planted" in problem for problem in problems), planted


def test_an_error_beside_the_planted_ones_is_reported() -> None:
    planted = PlantedError("LEDGER_DATA_INVALID_ENTITY", "trades[0].totalValue", "MISMATCH")

    problems = judge(Refused((planted,)), refused(TOTAL_OFF, SHORTFALL))

    assert problems == [f"reported but not planted: {SHORTFALL}"]


def test_one_reported_error_cannot_stand_for_two_planted_ones() -> None:
    planted = PlantedError("LEDGER_DATA_INVALID_ENTITY", "trades[0].totalValue", "MISMATCH")

    problems = judge(Refused((planted, planted)), refused(TOTAL_OFF))

    assert len(problems) == 1
    assert "not reported" in problems[0]


@pytest.mark.parametrize("expected", [Accepted(), HoldingsOnly(), Refused(())])
def test_a_check_that_threw_is_never_as_expected(
    expected: Accepted | HoldingsOnly | Refused,
) -> None:
    verdict = Verdict(accepted=False, errors=(), thrown="RangeError: no offset")

    assert judge(expected, verdict) == [
        "the validator threw instead of answering: RangeError: no offset"
    ]


# --- reading what the validator printed -------------------------------------


def test_the_validator_report_is_read_into_typed_values() -> None:
    text = json.dumps(
        {
            "backupFormatVersion": 3,
            "ledgerSchemaVersion": 5,
            "results": [
                {"file": "a.json", "ok": True, "errors": []},
                {"file": "b.json", "ok": False, "errors": [vars(SHORTFALL)]},
                {"file": "c.json", "ok": False, "errors": [], "thrown": "Error: boom"},
            ],
        }
    )

    report = ledger_check.parse_report(text)

    assert report.backup_format_version == 3
    assert report.ledger_schema_version == 5
    thrown = Verdict(accepted=False, errors=(), thrown="Error: boom")
    assert report.verdicts == (ACCEPTED, refused(SHORTFALL), thrown)


# --- when the tier is skipped -----------------------------------------------


def test_without_a_ledger_named_the_tier_is_skipped_and_says_how_to_name_one() -> None:
    reason = locate_ledger(None, {})

    assert isinstance(reason, str)
    assert ledger_check.LEDGER_ENV in reason


def test_the_argument_comes_before_the_environment(tmp_path: Path) -> None:
    reason = locate_ledger(str(tmp_path / "given"), {ledger_check.LEDGER_ENV: str(tmp_path)})

    assert isinstance(reason, str)
    assert "given" in reason


@pytest.mark.parametrize(
    ("present", "named_in_reason"),
    [
        ((), str(ledger_check.LEDGER_ENTRY)),
        ((ledger_check.LEDGER_ENTRY,), str(ledger_check.LEDGER_TSX)),
    ],
)
def test_a_directory_that_lacks_the_validator_or_its_tool_is_skipped(
    tmp_path: Path, present: tuple[Path, ...], named_in_reason: str
) -> None:
    for relative in present:
        (tmp_path / relative).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / relative).write_text("", encoding="utf-8")

    reason = locate_ledger(None, {ledger_check.LEDGER_ENV: str(tmp_path)})

    assert isinstance(reason, str)
    assert named_in_reason in reason


def test_a_missing_ledger_skips_the_script_with_its_own_exit_status(tmp_path: Path) -> None:
    script = REPO_ROOT / "scripts" / "ledger_check.py"
    missing = tmp_path / "no-ledger-here"

    done = subprocess.run(
        [sys.executable, str(script), "--ledger", str(missing)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert done.returncode == ledger_check.Outcome.SKIPPED.value
    assert done.returncode not in (ledger_check.Outcome.PASSED.value, 1, 2)
    assert done.stdout == f"skipped: there is no directory at {missing}\n"


def test_a_missing_ledger_skips_the_ledger_tier_of_the_check_script(tmp_path: Path) -> None:
    missing = tmp_path / "no-ledger-here"
    environment = {"PATH": "/usr/bin:/bin", ledger_check.LEDGER_ENV: str(missing)}
    environment["LEDGER_HAND_PYTHON"] = sys.executable

    done = subprocess.run(
        ["bash", str(REPO_ROOT / "scripts" / "check.sh"), "ledger"],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )

    assert done.returncode == 3
    assert f"skipped: there is no directory at {missing}" in done.stdout
    assert done.stderr.strip().splitlines()[-1] == "SKIPPED: ledger"


# --- reading the checkout's Git files ---------------------------------------


def test_the_commit_is_read_from_a_branch_reference(tmp_path: Path) -> None:
    git = tmp_path / ".git"
    (git / "refs" / "heads").mkdir(parents=True)
    (git / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (git / "refs" / "heads" / "main").write_text("abc123\n", encoding="utf-8")

    assert ledger_check.ledger_commit(tmp_path) == "abc123 (refs/heads/main)"


def test_the_commit_is_read_from_packed_references(tmp_path: Path) -> None:
    git = tmp_path / ".git"
    git.mkdir()
    (git / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    packed = "# pack-refs with: peeled\ndef456 refs/heads/main\n"
    (git / "packed-refs").write_text(packed, encoding="utf-8")

    assert ledger_check.ledger_commit(tmp_path) == "def456 (refs/heads/main)"


def test_a_detached_head_is_its_own_commit(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").write_text("0123abcd\n", encoding="utf-8")

    assert ledger_check.ledger_commit(tmp_path) == "0123abcd"


def test_an_unreadable_checkout_has_an_unknown_commit(tmp_path: Path) -> None:
    assert ledger_check.ledger_commit(tmp_path) == "unknown"


# --- asking whether a checkout is clean -------------------------------------


def _git(directory: Path, *arguments: str) -> None:
    subprocess.run(["git", "-C", str(directory), *arguments], check=True, capture_output=True)


def test_a_checkout_with_no_change_is_clean_and_one_with_a_new_file_is_not(
    tmp_path: Path,
) -> None:
    _git(tmp_path, "init", "--quiet")

    assert ledger_check.checkout_state(tmp_path).clean

    (tmp_path / "new.txt").write_text("x\n", encoding="utf-8")
    state = ledger_check.checkout_state(tmp_path)

    assert not state.clean
    assert state.shown == "?? new.txt"


def test_a_directory_git_cannot_read_is_not_clean(tmp_path: Path) -> None:
    state = ledger_check.checkout_state(tmp_path / "missing")

    assert not state.clean
    assert state.shown.startswith("git could not tell:")


# --- the samples ------------------------------------------------------------


def test_every_sample_has_a_name_of_its_own_and_the_golden_one_is_read_from_its_file() -> None:
    chosen = ledger_check.light_samples()
    names = [sample.name for sample in chosen]

    assert len(set(names)) == len(names)
    golden = next(sample for sample in chosen if sample.name == GOLDEN_FILE.name)
    assert golden.text.encode("utf-8") == GOLDEN_FILE.read_bytes()
    assert golden.expected == Accepted()


def test_the_samples_cover_each_kind_of_expectation() -> None:
    kinds = {type(sample.expected) for sample in ledger_check.light_samples()}

    assert kinds == {Accepted, HoldingsOnly, Refused, ledger_check.AcceptedExceptZoneData}


def _changed_paths(before: object, after: object, path: str = "") -> list[str]:
    if isinstance(before, dict) and isinstance(after, dict):
        keys = sorted(set(before) | set(after))
        return [
            changed
            for key in keys
            for changed in _changed_paths(before.get(key), after.get(key), f"{path}.{key}")
        ]
    if isinstance(before, list) and isinstance(after, list) and len(before) == len(after):
        return [
            changed
            for index, (one, other) in enumerate(zip(before, after, strict=True))
            for changed in _changed_paths(one, other, f"{path}[{index}]")
        ]
    return [] if before == after else [path]


def test_each_planted_mistake_changes_exactly_one_field_of_the_golden_sample() -> None:
    golden = json.loads(golden_text())

    changed = {
        name: _changed_paths(golden, json.loads(text)) for name, text in broken_texts().items()
    }

    assert changed == {
        "total-off": [".ledgerData.trades[0].totalValue"],
        "fee-coin-missing": [".ledgerData.trades[0].feeCurrency"],
        "zone-disagrees": [".ledgerData.trades[2].occurredTimeZone"],
    }


def test_every_zone_name_the_machine_knows_is_taken_except_the_names_that_are_no_zone() -> None:
    candidates = set(zone_candidates())
    taken = set(zones_taken())

    assert candidates - taken <= NOT_ZONE_NAMES
    assert "Europe/Budapest" in taken
    assert "UTC" in taken
    assert len(taken) > 300


def test_every_case_has_a_name_of_its_own_and_heavy_ones_are_built_only_when_run() -> None:
    from tests.ledger_check import cases

    names = [case.name for case in [*cases.light_cases(), *cases.heavy_cases()]]
    refusals = [case.name for case in cases.limit_refusals()]

    assert len(set(names)) == len(names)
    assert len(set(refusals)) == len(refusals) == 3


def test_the_process_zones_are_the_machine_s_own_and_two_far_apart() -> None:
    assert ledger_check.PROCESS_ZONES[0] is None
    for zone in ledger_check.PROCESS_ZONES[1:]:
        assert zone is not None
        assert is_zone_name(zone)


# --- where the two time zone databases disagree -----------------------------


def offset_refused(place: int) -> LedgerError:
    """What the ledger says when a trade's offset is not its zone's at that instant."""
    return LedgerError(
        "LEDGER_DATA_INVALID_ENTITY",
        f"trades[{place}].occurredAt",
        f"trades[{place}].occurredAt offset must match occurredTimeZone at its instant",
    )


EXCEPT_ZONE_DATA = ledger_check.AcceptedExceptZoneData()


def test_only_refusals_where_the_databases_disagree_are_as_expected() -> None:
    verdict = refused(offset_refused(3), offset_refused(7))

    assert judge(EXCEPT_ZONE_DATA, verdict, frozenset({3, 7})) == []
    assert ledger_check.zone_data_errors(verdict, frozenset({3, 7})) == list(verdict.errors)


def test_any_other_error_beside_them_fails() -> None:
    verdict = refused(offset_refused(3), TOTAL_OFF)

    problems = judge(EXCEPT_ZONE_DATA, verdict, frozenset({3}))

    assert problems == [f"not explained by the two time zone databases: {TOTAL_OFF}"]


def test_an_offset_refused_where_the_databases_agree_fails() -> None:
    verdict = refused(offset_refused(5))

    problems = judge(EXCEPT_ZONE_DATA, verdict, frozenset({3}))

    assert f"not explained by the two time zone databases: {offset_refused(5)}" in problems
    assert "the time zone databases disagree on trades[3], yet the ledger did not object" in (
        problems
    )


def test_a_trade_the_databases_disagree_on_must_be_refused_for_it() -> None:
    assert judge(EXCEPT_ZONE_DATA, ACCEPTED, frozenset({3})) == [
        "the time zone databases disagree on trades[3], yet the ledger did not object"
    ]


def test_with_no_disagreement_the_file_must_simply_be_accepted() -> None:
    assert judge(EXCEPT_ZONE_DATA, ACCEPTED) == []
    assert judge(EXCEPT_ZONE_DATA, refused(offset_refused(0))) != []


def test_a_refusal_at_another_path_or_with_another_code_is_not_the_databases() -> None:
    elsewhere = LedgerError(
        "LEDGER_DATA_INVALID_ENTITY",
        "trades[4].occurredAt",
        "trades[3].occurredAt offset must match occurredTimeZone at its instant",
    )
    other_code = LedgerError(
        "LEDGER_DATA_INVALID_REFERENCE", "trades[3].occurredAt", offset_refused(3).message
    )

    assert ledger_check.zone_data_errors(refused(elsewhere, other_code), frozenset({3, 4})) == []


def test_the_offsets_of_timed_trades_are_probed_and_days_are_not() -> None:
    text = json.dumps(
        {
            "ledgerData": {
                "trades": [
                    {"occurredAt": "2026-10-02", "occurredTimeZone": "Europe/Budapest"},
                    {
                        "occurredAt": "2026-10-05T07:46:00+02:00",
                        "occurredTimeZone": "Europe/Budapest",
                    },
                    {"occurredAt": "2026-10-05T05:46:00+00:00", "occurredTimeZone": "UTC"},
                ]
            }
        }
    )

    assert ledger_check.offset_probes(text) == [
        (1, "2026-10-05T07:46:00+02:00", "Europe/Budapest"),
        (2, "2026-10-05T05:46:00+00:00", "UTC"),
    ]


@pytest.mark.parametrize(
    ("instant", "zone", "offset"),
    [
        ("2026-10-05T05:46:00+00:00", "UTC", "+00:00"),
        ("2026-10-05T07:46:00+02:00", "Europe/Budapest", "+02:00"),
        ("2026-01-05T07:46:00+00:00", "Europe/Budapest", "+01:00"),
        ("2026-10-05T05:46:00+00:00", "Asia/Kathmandu", "+05:45"),
        ("2026-01-05T05:46:00+00:00", "America/St_Johns", "-03:30"),
    ],
)
def test_our_offset_is_written_as_the_ledger_writes_it(
    instant: str, zone: str, offset: str
) -> None:
    assert ledger_check.our_offset(instant, zone) == offset


def test_gaps_are_the_probes_where_the_ledger_gives_another_offset() -> None:
    probes = [
        (0, "2026-10-05T05:46:00+00:00", "UTC"),
        (4, "2026-10-05T07:46:00+02:00", "Europe/Budapest"),
        (9, "2026-10-05T05:46:00+00:00", "UTC"),
    ]

    gaps = ledger_check.zone_gaps(probes, ["+01:00", "+02:00", None])

    assert gaps == {
        0: ledger_check.ZoneGap("UTC", "2026-10-05T05:46:00+00:00", "+00:00", "+01:00"),
        9: ledger_check.ZoneGap("UTC", "2026-10-05T05:46:00+00:00", "+00:00", None),
    }


def test_our_database_version_is_read_from_its_version_file(tmp_path: Path) -> None:
    (tmp_path / "+VERSION").write_text("2099z\n", encoding="utf-8")

    assert ledger_check.our_zone_data_version([str(tmp_path / "missing"), str(tmp_path)]) == (
        f"2099z (system, {tmp_path})"
    )


def test_the_notice_names_both_versions_the_zones_the_count_and_the_document() -> None:
    gap = ledger_check.ZoneGap("Africa/Casablanca", "2026-10-05T05:46:00+00:00", "+00:00", "+01:00")
    comparison = ledger_check.ZoneDataComparison(
        "2026c (system)", "tz 2026a, ICU 78.2", ({0: gap},)
    )

    lines = ledger_check.zone_data_notice(comparison, {"a.json": [gap, gap], "b.json": []})
    text = "\n".join(lines)

    assert all(line.startswith("!!!") for line in lines)
    assert "2026c (system)" in text
    assert "tz 2026a, ICU 78.2" in text
    assert "Africa/Casablanca" in text
    assert "2 (a.json: 2)" in text
    assert "pending" in text
    assert "docs/known-gaps.md" in text
    assert (REPO_ROOT / "docs" / "known-gaps.md").is_file()


def test_no_notice_when_the_ledger_refused_nothing_for_it() -> None:
    comparison = ledger_check.ZoneDataComparison("2026c", "tz 2026c", ({},))

    assert ledger_check.zone_data_notice(comparison, {"a.json": []}) == []
