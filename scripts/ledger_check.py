"""The ledger tier: sample files checked by the ledger's own validator.

    .venv/bin/python scripts/ledger_check.py [--ledger PATH]

The ledger is the Local-First Trading Ledger, a separate TypeScript project,
and its function ``parseBackupJson`` decides whether a backup file is
accepted. This script writes a set of sample files into a fresh temporary
directory, has that function judge each one, and compares every verdict with
what the sample is expected to get. A sample is expected to be one of:

- accepted, with no error at all;
- refused only because a sale exceeds what is held, which this program
  cannot know: it does not see what the ledger already holds;
- refused with exactly the errors that were planted in it, one for one.

What is checked is said in ``tests/ledger_check/cases.py``, beside the
invented trades the samples are exported from: a file written by hand, the
committed golden sample, edge cases and batches of awkward trades, and copies
with mistakes planted in them. Each sample is judged on a given today, handed
to the ledger, and in three process time zones (the machine's own,
Los Angeles and Kiritimati), so that no verdict depends on the clock or on
where the ledger runs. Before any of that, the export itself must refuse
inputs one past each of the ledger's limits of one file. The tier also fails
when the ledger's format versions are no longer the ones this program writes.

Where the ledger is comes from ``--ledger PATH`` or else from the environment
variable ``LEDGER_HAND_LEDGER_DIR``. Nothing in this repository names a path
on any machine.

The ledger checkout is only ever read. The validator runs from inside it, with
the checkout's own ``tsx`` (with ``--no-cache``, so nothing is cached either)
and a configuration file that extends the checkout's own. That file has to
name the checkout, so it is generated in the temporary directory. Before and
after, the script asks Git whether the checkout is clean, in the one way that
writes nothing into it, and fails when it is not.

Exit status: 0 every sample got what it should; 1 something did not, the
checkout was not clean, or the validator could not be run; 3 skipped, because
no ledger checkout was named, the one named is missing, or a tool needed to
run its validator is missing. The reason is always printed.
"""

from __future__ import annotations

import argparse
import enum
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from types import ModuleType
from typing import Any

from ledger_hand.export.backup import BACKUP_FORMAT_VERSION, LEDGER_SCHEMA_VERSION

REPO_ROOT = Path(__file__).resolve().parent.parent
LEDGER_ENV = "LEDGER_HAND_LEDGER_DIR"
VALIDATOR = REPO_ROOT / "scripts" / "ledger_validate.ts"

# Inside a ledger checkout.
LEDGER_ENTRY = Path("src/features/backup/backupEnvelope.ts")
LEDGER_TSX = Path("node_modules/.bin/tsx")
LEDGER_CONFIG = Path("tsconfig.json")

# The line on which the validator prints its findings starts with this.
MARKER = "LEDGER_HAND_RESULT "
VALIDATOR_TIMEOUT_SECONDS = 600

# The time zones the validator's process is run in: the machine's own, and
# two far apart, so that no verdict depends on where the ledger happens to be.
PROCESS_ZONES = (None, "America/Los_Angeles", "Pacific/Kiritimati")

# How the ledger says that a sale exceeds what is held: this code, with one of
# these two messages. The same code is also used for other errors, so both
# have to match.
HOLDINGS_CODE = "LEDGER_DATA_INVALID_TRADE_TIMELINE"
HOLDINGS_MESSAGE = re.compile(
    r"Cannot sell (?:more \S+ than current position|\S+ with zero current position)"
)


class Outcome(enum.Enum):
    """How the tier ended; the value is the exit status."""

    PASSED = 0
    FAILED = 1
    SKIPPED = 3


# --- what a sample is expected to get ---------------------------------------


@dataclass(frozen=True)
class Accepted:
    """The ledger accepts the file and reports no error."""

    def __str__(self) -> str:
        return "accepted with no error"


@dataclass(frozen=True)
class HoldingsOnly:
    """The ledger refuses the file, and every error says a sale exceeds what is held."""

    def __str__(self) -> str:
        return "refused only for selling more than is held"


@dataclass(frozen=True)
class PlantedError:
    """An error put into a sample on purpose: its code, its path and a piece of its message."""

    code: str
    path: str
    says: str

    def matches(self, error: LedgerError) -> bool:
        return error.code == self.code and error.path == self.path and self.says in error.message


@dataclass(frozen=True)
class Refused:
    """The ledger refuses the file with exactly these errors, one for one."""

    errors: tuple[PlantedError, ...]

    def __str__(self) -> str:
        planted = "; ".join(f"{error.code} at {error.path}" for error in self.errors)
        return f"refused with exactly: {planted}"


Expectation = Accepted | HoldingsOnly | Refused


@dataclass(frozen=True)
class Sample:
    """One file for the ledger to judge, the date it is to take as today, and what it should get."""

    name: str
    text: str
    expected: Expectation
    today: date


# --- what the ledger said ---------------------------------------------------


@dataclass(frozen=True)
class LedgerError:
    """One error as the ledger reports it."""

    code: str
    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.code} at {self.path}: {self.message}"


@dataclass(frozen=True)
class Verdict:
    """The ledger's answer for one file. ``thrown`` is set when the check threw instead."""

    accepted: bool
    errors: tuple[LedgerError, ...]
    thrown: str | None = None


@dataclass(frozen=True)
class ValidatorReport:
    """Everything the validator printed: the ledger's format versions and one verdict per file."""

    backup_format_version: object
    ledger_schema_version: object
    verdicts: tuple[Verdict, ...]


@dataclass(frozen=True)
class CheckoutState:
    """Whether the ledger checkout is clean; ``shown`` is what Git printed, or why it could not."""

    clean: bool
    shown: str


def is_holdings_shortfall(error: LedgerError) -> bool:
    """Whether ``error`` is the ledger saying that a sale exceeds what is held."""
    return error.code == HOLDINGS_CODE and HOLDINGS_MESSAGE.fullmatch(error.message) is not None


def judge(expected: Expectation, verdict: Verdict) -> list[str]:
    """How ``verdict`` differs from ``expected``; an empty list when it does not."""
    if verdict.thrown is not None:
        return [f"the validator threw instead of answering: {verdict.thrown}"]
    if isinstance(expected, Accepted):
        if verdict.accepted and not verdict.errors:
            return []
        return [f"should have been accepted; reported: {error}" for error in verdict.errors] or [
            "should have been accepted"
        ]
    if verdict.accepted or not verdict.errors:
        return ["should have been refused with errors, but was not"]
    if isinstance(expected, HoldingsOnly):
        return [
            f"not about selling more than is held: {error}"
            for error in verdict.errors
            if not is_holdings_shortfall(error)
        ]
    return _unmatched(expected.errors, verdict.errors)


def _unmatched(planted: Sequence[PlantedError], reported: Sequence[LedgerError]) -> list[str]:
    left = list(reported)
    problems: list[str] = []
    for error in planted:
        found = next((candidate for candidate in left if error.matches(candidate)), None)
        if found is None:
            problems.append(f"planted error not reported: {error.code} at {error.path}")
        else:
            left.remove(found)
    problems.extend(f"reported but not planted: {error}" for error in left)
    return problems


# --- the samples ------------------------------------------------------------


def _cases() -> ModuleType:
    """The module that says what to check; it lives with the tests and their invented trades."""
    # This script runs from its own directory, so the repository has to be put
    # on the path to reach the tests.
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from tests.ledger_check import cases

    return cases


def light_samples() -> list[Sample]:
    """Every sample but the very large one, in the order they are reported."""
    return [_sample(case) for case in _cases().light_cases()]


def heavy_samples() -> list[Sample]:
    """The sample exactly as large as the ledger reads, about 128 MiB."""
    return [_sample(case) for case in _cases().heavy_cases()]


def _sample(case: Any) -> Sample:
    cases = _cases()
    if case.expect is cases.Expect.ACCEPTED:
        expected: Expectation = Accepted()
    elif case.expect is cases.Expect.HOLDINGS_ONLY:
        expected = HoldingsOnly()
    else:
        expected = Refused(tuple(PlantedError(*planted) for planted in case.planted))
    return Sample(case.name, case.build(), expected, case.today)


def check_limit_refusals() -> bool:
    """Whether the export refuses one past each of the ledger's limits, as it should."""
    all_refused = True
    for case in _cases().limit_refusals():
        result = case.build()
        issues = getattr(result, "issues", None)
        expected = [(case.problem, case.subject)]
        found = None if issues is None else [(issue.problem, issue.subject) for issue in issues]
        as_expected = found == expected
        all_refused = all_refused and as_expected
        verdict = "as expected" if as_expected else "NOT AS EXPECTED"
        outcome = (
            "exported"
            if found is None
            else "refused: " + ", ".join(f"{problem.name} {subject}" for problem, subject in found)
        )
        print(f"{verdict}: export of {case.name}: {outcome}")
    return all_refused


# --- finding the ledger -----------------------------------------------------


def locate_ledger(argument: str | None, environ: Mapping[str, str]) -> Path | str:
    """The ledger checkout to use, or the reason the tier is skipped."""
    named = argument or environ.get(LEDGER_ENV, "")
    if not named:
        return f"no ledger checkout named: pass --ledger PATH or set {LEDGER_ENV}"
    ledger = Path(named).expanduser().resolve()
    if not ledger.is_dir():
        return f"there is no directory at {ledger}"
    if not (ledger / LEDGER_ENTRY).is_file():
        return f"{ledger} has no {LEDGER_ENTRY}, so it is not a ledger checkout this tier knows"
    if not (ledger / LEDGER_TSX).is_file():
        return f"{ledger} has no {LEDGER_TSX}; the ledger's packages are not installed there"
    for tool in ("node", "git"):
        if shutil.which(tool) is None:
            return f"{tool} is not on the PATH"
    return ledger


def checkout_state(ledger: Path) -> CheckoutState:
    """Whether Git sees any change in the checkout, asked in the way that writes nothing."""
    command = ["git", "--no-optional-locks", "-C", str(ledger), "status", "--porcelain"]
    done = subprocess.run(command, capture_output=True, text=True, check=False)
    if done.returncode != 0:
        return CheckoutState(clean=False, shown=f"git could not tell: {done.stderr.strip()}")
    return CheckoutState(clean=done.stdout == "", shown=done.stdout.rstrip("\n"))


def ledger_commit(ledger: Path) -> str:
    """The commit the checkout is on, read from its Git files; ``unknown`` when unreadable."""
    git = ledger / ".git"
    try:
        head = (git / "HEAD").read_text(encoding="utf-8").strip()
        if not head.startswith("ref: "):
            return head
        ref = head.removeprefix("ref: ")
        loose = git / ref
        if loose.is_file():
            return f"{loose.read_text(encoding='utf-8').strip()} ({ref})"
        for line in (git / "packed-refs").read_text(encoding="utf-8").splitlines():
            commit, _, name = line.partition(" ")
            if name == ref:
                return f"{commit} ({ref})"
    except OSError:
        pass
    return "unknown"


# --- running the validator --------------------------------------------------


def write_config(directory: Path, ledger: Path) -> Path:
    """A configuration that extends the ledger's own, with JSX compiled the React way.

    Without the JSX setting the validator fails with "React is not defined":
    it reaches some of the ledger's interface files through its imports.
    """
    config = directory / "tsconfig.json"
    document = {"extends": str(ledger / LEDGER_CONFIG), "compilerOptions": {"jsx": "react-jsx"}}
    config.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return config


def write_samples(directory: Path, chosen: Sequence[Sample]) -> list[Path]:
    """Each sample written to its own file, byte for byte as UTF-8."""
    files = []
    for sample in chosen:
        file = directory / sample.name
        file.write_bytes(sample.text.encode("utf-8"))
        files.append(file)
    return files


def run_validator(
    ledger: Path, config: Path, files: Sequence[Path], today: date, zone: str | None = None
) -> ValidatorReport | str:
    """What the ledger's validator says about each file, or why it could not be run.

    ``today`` is handed to the ledger as its today. ``zone``, when given, is
    the time zone the validator's process runs in, in place of the machine's.
    """
    command = [str(ledger / LEDGER_TSX), "--no-cache", "--tsconfig", str(config), str(VALIDATOR)]
    command += [str(ledger), today.isoformat(), *map(str, files)]
    environment = dict(os.environ) if zone is None else {**os.environ, "TZ": zone}
    try:
        done = subprocess.run(
            command,
            cwd=ledger,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=VALIDATOR_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return f"the validator could not be run: {error}"
    lines = [line for line in done.stdout.splitlines() if line.startswith(MARKER)]
    if done.returncode != 0 or len(lines) != 1:
        return f"the validator failed (exit status {done.returncode}):\n{done.stderr.strip()}"
    return parse_report(lines[0].removeprefix(MARKER))


def parse_report(text: str) -> ValidatorReport:
    """The validator's printed document as typed values."""
    document = json.loads(text)
    verdicts = tuple(
        Verdict(
            accepted=bool(result["ok"]),
            errors=tuple(
                LedgerError(error["code"], error["path"], error["message"])
                for error in result["errors"]
            ),
            thrown=result.get("thrown"),
        )
        for result in document["results"]
    )
    return ValidatorReport(
        backup_format_version=document["backupFormatVersion"],
        ledger_schema_version=document["ledgerSchemaVersion"],
        verdicts=verdicts,
    )


# --- the whole tier ---------------------------------------------------------


def run(ledger: Path, chosen: Sequence[Sample]) -> Outcome:
    """Check ``chosen`` with the ledger at ``ledger``, printing the evidence as it goes."""
    print(f"ledger checkout: {ledger}")
    print(f"ledger commit: {ledger_commit(ledger)}")
    if not _reported_clean(ledger, "before"):
        return Outcome.FAILED
    with tempfile.TemporaryDirectory(prefix="ledger-hand-check-") as scratch:
        directory = Path(scratch)
        config = write_config(directory, ledger)
        files = write_samples(directory, chosen)
        answers = _validate_everywhere(ledger, config, chosen, files)
    clean_after = _reported_clean(ledger, "after")
    if isinstance(answers, str):
        print(answers)
        return Outcome.FAILED
    report, verdicts = answers
    versions_match = _reported_versions(report)
    all_as_expected = _reported_verdicts(chosen, verdicts)
    return Outcome.PASSED if all_as_expected and versions_match and clean_after else Outcome.FAILED


def _validate_everywhere(
    ledger: Path, config: Path, chosen: Sequence[Sample], files: Sequence[Path]
) -> tuple[ValidatorReport, list[list[Verdict]]] | str:
    """Each sample's verdict in each process time zone, judged on the sample's own today."""
    verdicts: list[list[Verdict]] = [[] for _ in chosen]
    report: ValidatorReport | None = None
    for zone in PROCESS_ZONES:
        for today in sorted({sample.today for sample in chosen}):
            places = [place for place, sample in enumerate(chosen) if sample.today == today]
            answer = run_validator(ledger, config, [files[place] for place in places], today, zone)
            if isinstance(answer, str):
                return answer
            if len(answer.verdicts) != len(places):
                return f"the validator answered for {len(answer.verdicts)} of {len(places)} files"
            report = report or answer
            for place, verdict in zip(places, answer.verdicts, strict=True):
                verdicts[place].append(verdict)
    assert report is not None
    return report, verdicts


def _reported_versions(report: ValidatorReport) -> bool:
    found = (report.backup_format_version, report.ledger_schema_version)
    written = (BACKUP_FORMAT_VERSION, LEDGER_SCHEMA_VERSION)
    print(f"ledger format versions: backup format {found[0]}, ledger schema {found[1]}")
    if found != written:
        print(
            f"NOT the versions this program writes: backup format {written[0]}, schema {written[1]}"
        )
    return found == written


def _reported_clean(ledger: Path, when: str) -> bool:
    state = checkout_state(ledger)
    if state.clean:
        print(f"ledger checkout {when} the check: clean (git status --porcelain printed nothing)")
    else:
        print(f"ledger checkout {when} the check: NOT CLEAN\n{state.shown}")
    return state.clean


def _reported_verdicts(chosen: Sequence[Sample], verdicts: Sequence[Sequence[Verdict]]) -> bool:
    failures = 0
    for sample, answers in zip(chosen, verdicts, strict=True):
        problems = {
            _zone_label(zone): judge(sample.expected, verdict)
            for zone, verdict in zip(PROCESS_ZONES, answers, strict=True)
        }
        failed = any(problems.values())
        failures += failed
        print(f"\n{'NOT AS EXPECTED' if failed else 'as expected'}: {sample.name}")
        print(f"  expected: {sample.expected}, judged on {sample.today.isoformat()}")
        if all(answer == answers[0] for answer in answers):
            zones = ", ".join(_zone_label(zone) for zone in PROCESS_ZONES)
            _print_verdict(f"ledger, in each process time zone ({zones})", answers[0])
        else:
            for zone, answer in zip(PROCESS_ZONES, answers, strict=True):
                _print_verdict(f"ledger, in {_zone_label(zone)}", answer)
        for zone, found in problems.items():
            for problem in found:
                print(f"  problem ({zone}): {problem}")
    print(f"\n{len(chosen) - failures} of {len(chosen)} samples got what they should")
    return failures == 0


def _print_verdict(where: str, verdict: Verdict) -> None:
    print(f"  {where}: {'accepted' if verdict.accepted else 'refused'}")
    for error in verdict.errors:
        print(f"    {error}")


def _zone_label(zone: str | None) -> str:
    return "the machine's own" if zone is None else zone


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check sample files with the ledger's validator.")
    parser.add_argument("--ledger", help=f"the ledger checkout; default: ${LEDGER_ENV}")
    arguments = parser.parse_args(argv)
    located = locate_ledger(arguments.ledger, os.environ)
    if isinstance(located, str):
        print(f"skipped: {located}")
        return Outcome.SKIPPED.value
    print("== the export's own refusals at the ledger's limits ==")
    refused_as_expected = check_limit_refusals()
    print("\n== sample files judged by the ledger ==")
    outcome = run(located, light_samples() + heavy_samples())
    passed = outcome is Outcome.PASSED and refused_as_expected
    return (Outcome.PASSED if passed else Outcome.FAILED).value


if __name__ == "__main__":
    raise SystemExit(main())
