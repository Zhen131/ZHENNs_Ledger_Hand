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
committed golden sample, edge cases and batches of awkward trades, a file the
export flow wrote from a book, and copies with mistakes planted in them.
Two samples hold a trade in every time zone and allow for the known gap
between the two time zone databases; once both sides have been asked where
they disagree, the same trades without those are exported again as two more
samples, and these must be accepted with no error at all.

Each sample is judged on a given today, handed to the ledger, and in three
process time zones (the machine's own, Los Angeles and Kiritimati), so that
no verdict depends on the clock or on where the ledger runs. Before any of
that, the export itself must refuse inputs one past each of the ledger's
limits of one file. The tier also fails when the ledger's format versions are
no longer the ones this program writes.

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
import zoneinfo
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from types import ModuleType
from typing import Any
from zoneinfo import ZoneInfo

from ledger_hand.export.backup import BACKUP_FORMAT_VERSION, LEDGER_SCHEMA_VERSION

REPO_ROOT = Path(__file__).resolve().parent.parent
LEDGER_ENV = "LEDGER_HAND_LEDGER_DIR"
VALIDATOR = REPO_ROOT / "scripts" / "ledger_validate.ts"
OFFSETS = REPO_ROOT / "scripts" / "ledger_offsets.ts"
# Where the known, pending gap between the two time zone databases is described.
ZONE_DATA_DOC = 'docs/known-gaps.md, section "Time zone database versions"'

# Inside a ledger checkout.
LEDGER_ENTRY = Path("src/features/backup/backupEnvelope.ts")
LEDGER_TSX = Path("node_modules/.bin/tsx")
LEDGER_CONFIG = Path("tsconfig.json")

# The lines on which the two TypeScript scripts print their findings start with these.
MARKER = "LEDGER_HAND_RESULT "
OFFSETS_MARKER = "LEDGER_HAND_OFFSETS "
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

# How the ledger says that a trade's offset is not its zone's offset at that
# instant, which it also says when its time zone database differs from ours.
ZONE_DATA_CODE = "LEDGER_DATA_INVALID_ENTITY"
ZONE_DATA_MESSAGE = re.compile(
    r"trades\[(\d+)\]\.occurredAt offset must match occurredTimeZone at its instant"
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


@dataclass(frozen=True)
class AcceptedExceptZoneData:
    """Accepted, except that the ledger may refuse the offset of a trade whose zone, at
    that instant, has another offset in the ledger's time zone database than in ours.

    Which trades those are is worked out when the tier runs, by asking both sides.
    """

    def __str__(self) -> str:
        return "accepted, except offsets where the two time zone databases disagree"


Expectation = Accepted | HoldingsOnly | Refused | AcceptedExceptZoneData


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


def judge(expected: Expectation, verdict: Verdict, gaps: frozenset[int] = frozenset()) -> list[str]:
    """How ``verdict`` differs from ``expected``; an empty list when it does not.

    ``gaps`` are the places of the trades whose offset the two time zone
    databases disagree on; only ``AcceptedExceptZoneData`` looks at them.
    """
    if verdict.thrown is not None:
        return [f"the validator threw instead of answering: {verdict.thrown}"]
    if isinstance(expected, AcceptedExceptZoneData):
        return _beyond_zone_data(verdict, gaps)
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


def zone_data_errors(verdict: Verdict, gaps: frozenset[int]) -> list[LedgerError]:
    """The errors in ``verdict`` that only say the two time zone databases disagree."""
    return [error for error in verdict.errors if _zone_data_place(error) in gaps]


def _zone_data_place(error: LedgerError) -> int | None:
    found = ZONE_DATA_MESSAGE.fullmatch(error.message)
    if error.code != ZONE_DATA_CODE or found is None:
        return None
    place = int(found.group(1))
    return place if error.path == f"trades[{place}].occurredAt" else None


def _beyond_zone_data(verdict: Verdict, gaps: frozenset[int]) -> list[str]:
    tolerated = zone_data_errors(verdict, gaps)
    problems = [
        f"not explained by the two time zone databases: {error}"
        for error in verdict.errors
        if error not in tolerated
    ]
    objected = {_zone_data_place(error) for error in tolerated}
    problems.extend(
        f"the time zone databases disagree on trades[{place}], yet the ledger did not object"
        for place in sorted(gaps - objected)
    )
    return problems


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
    elif case.expect is cases.Expect.ACCEPTED_EXCEPT_ZONE_DATA:
        expected = AcceptedExceptZoneData()
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


# --- where the two time zone databases disagree ------------------------------


@dataclass(frozen=True)
class ZoneGap:
    """One trade whose zone has two different offsets at its instant, ours and the ledger's."""

    zone: str
    instant: str
    ours: str
    ledgers: str | None


@dataclass(frozen=True)
class ZoneDataComparison:
    """Both sides' time zone databases, and per sample the trades they disagree on, by place."""

    ours: str
    ledgers: str
    gaps: tuple[dict[int, ZoneGap], ...]


def offset_probes(text: str) -> list[tuple[int, str, str]]:
    """Each trade in ``text`` known to the minute or second: its place, instant and zone."""
    trades = json.loads(text)["ledgerData"]["trades"]
    return [
        (place, trade["occurredAt"], trade["occurredTimeZone"])
        for place, trade in enumerate(trades)
        if len(trade["occurredAt"]) > len("YYYY-MM-DD") and "occurredTimeZone" in trade
    ]


def our_offset(instant: str, zone: str) -> str:
    """The offset of ``zone`` at ``instant`` by our time zone database, as ``+01:00``."""
    offset = datetime.fromisoformat(instant).astimezone(ZoneInfo(zone)).utcoffset()
    assert offset is not None
    minutes = int(offset.total_seconds()) // 60
    sign = "-" if minutes < 0 else "+"
    return f"{sign}{abs(minutes) // 60:02}:{abs(minutes) % 60:02}"


def zone_gaps(
    probes: Sequence[tuple[int, str, str]], ledgers: Sequence[str | None]
) -> dict[int, ZoneGap]:
    """The probed trades whose offset the ledger's database gives otherwise than ours."""
    gaps = {}
    for (place, instant, zone), theirs in zip(probes, ledgers, strict=True):
        ours = our_offset(instant, zone)
        if theirs != ours:
            gaps[place] = ZoneGap(zone, instant, ours, theirs)
    return gaps


def our_zone_data_version(tzpath: Sequence[str] = zoneinfo.TZPATH) -> str:
    """The version of the time zone database Python reads, as its files name it."""
    for directory in tzpath:
        version = Path(directory) / "+VERSION"
        if version.is_file():
            return f"{version.read_text(encoding='utf-8').strip()} (system, {directory})"
    try:
        # Only where the system has no database of its own.
        import tzdata
    except ImportError:
        return "unknown"
    return f"{tzdata.IANA_VERSION} (tzdata package)"


def zone_data_notice(
    comparison: ZoneDataComparison, refused: Mapping[str, Sequence[ZoneGap]]
) -> list[str]:
    """The lines that announce the known, pending gap; none when the ledger refused nothing for it.

    ``refused`` maps each sample's name to the trades the ledger refused only
    because the two databases disagree.
    """
    count = sum(len(gaps) for gaps in refused.values())
    if not count:
        return []
    zones = sorted({gap.zone for gaps in refused.values() for gap in gaps})
    per_sample = ", ".join(f"{name}: {len(gaps)}" for name, gaps in refused.items() if gaps)
    rule = "!!! " + "=" * 72
    return [
        rule,
        "!!! KNOWN AND PENDING: the two time zone databases disagree",
        f"!!!   ours (Python zoneinfo):        {comparison.ours}",
        f"!!!   the ledger's (its Node runtime): {comparison.ledgers}",
        f"!!!   zones where they disagree:     {', '.join(zones)}",
        f"!!!   trades the ledger refused for it: {count} ({per_sample})",
        "!!!   The ledger computes another offset for these zones at these moments,",
        "!!!   so it refuses trades this program exports there to the minute or second.",
        f"!!!   This is a decision still pending, not a pass. See {ZONE_DATA_DOC}.",
        "!!!   It is not counted as a failure of this tier; anything else would be.",
        rule,
    ]


def compare_zone_data(
    ledger: Path, config: Path, directory: Path, chosen: Sequence[Sample]
) -> ZoneDataComparison | str:
    """Ask both sides for the offsets of the samples that allow for the gap; compare them."""
    probes = [
        offset_probes(sample.text) if isinstance(sample.expected, AcceptedExceptZoneData) else []
        for sample in chosen
    ]
    flat = [(instant, zone) for found in probes for _, instant, zone in found]
    answer = run_offsets(ledger, config, directory, flat)
    if isinstance(answer, str):
        return answer
    versions, ledgers = answer
    gaps: list[dict[int, ZoneGap]] = []
    start = 0
    for found in probes:
        gaps.append(zone_gaps(found, ledgers[start : start + len(found)]))
        start += len(found)
    return ZoneDataComparison(our_zone_data_version(), versions, tuple(gaps))


def run_offsets(
    ledger: Path, config: Path, directory: Path, probes: Sequence[tuple[str, str]]
) -> tuple[str, list[str | None]] | str:
    """The ledger's versions and its offset for each (instant, zone), or why it could not tell."""
    probes_file = directory / "offset-probes.json"
    probes_file.write_text(json.dumps([list(probe) for probe in probes]), encoding="utf-8")
    command = [str(ledger / LEDGER_TSX), "--no-cache", "--tsconfig", str(config), str(OFFSETS)]
    command += [str(ledger), str(probes_file)]
    try:
        done = subprocess.run(
            command,
            cwd=ledger,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=VALIDATOR_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return f"the ledger's offsets could not be asked for: {error}"
    lines = [line for line in done.stdout.splitlines() if line.startswith(OFFSETS_MARKER)]
    if done.returncode != 0 or len(lines) != 1:
        return f"asking the ledger for offsets failed (exit {done.returncode}):\n{done.stderr}"
    report = json.loads(lines[0].removeprefix(OFFSETS_MARKER))
    if len(report["offsets"]) != len(probes):
        return f"the ledger gave {len(report['offsets'])} offsets for {len(probes)} moments"
    return f"tz {report['tz']}, ICU {report['icu']}", report["offsets"]


# --- the whole tier ---------------------------------------------------------


def run(ledger: Path, chosen: Sequence[Sample]) -> Outcome:
    """Check ``chosen`` with the ledger at ``ledger``, printing the evidence as it goes.

    The samples where the two time zone databases agree are added to
    ``chosen`` once both sides have been asked (``agreed_samples``).
    """
    print(f"ledger checkout: {ledger}")
    print(f"ledger commit: {ledger_commit(ledger)}")
    if not _reported_clean(ledger, "before"):
        return Outcome.FAILED
    with tempfile.TemporaryDirectory(prefix="ledger-hand-check-") as scratch:
        directory = Path(scratch)
        config = write_config(directory, ledger)
        judged = _judged(ledger, config, directory, chosen)
    clean_after = _reported_clean(ledger, "after")
    if isinstance(judged, str):
        print(judged)
        return Outcome.FAILED
    everything, report, verdicts, comparison = judged
    versions_match = _reported_versions(report)
    all_as_expected = _reported_verdicts(everything, verdicts, comparison.gaps)
    _announce_zone_data(everything, verdicts, comparison)
    return Outcome.PASSED if all_as_expected and versions_match and clean_after else Outcome.FAILED


def _judged(
    ledger: Path, config: Path, directory: Path, chosen: Sequence[Sample]
) -> tuple[list[Sample], ValidatorReport, list[list[Verdict]], ZoneDataComparison] | str:
    """Every sample's verdicts, those where the databases agree included; or why not."""
    comparison = compare_zone_data(ledger, config, directory, chosen)
    if isinstance(comparison, str):
        return comparison
    agreed, left_out = agreed_samples(chosen, comparison)
    print("\n== trades left out where the two time zone databases disagree ==")
    print("\n".join(left_out) if left_out else "(no sample to derive)")
    everything = [*chosen, *agreed]
    files = write_samples(directory, everything)
    answers = _validate_everywhere(ledger, config, everything, files)
    if isinstance(answers, str):
        return answers
    gaps = (*comparison.gaps, *({} for _ in agreed))
    report, verdicts = answers
    return (
        everything,
        report,
        verdicts,
        ZoneDataComparison(comparison.ours, comparison.ledgers, gaps),
    )


def agreed_samples(
    chosen: Sequence[Sample], comparison: ZoneDataComparison
) -> tuple[list[Sample], list[str]]:
    """The samples of the same trades without those the two databases disagree on.

    For each such case whose source is among ``chosen``: the trades the two
    time zone databases give different offsets, found when both sides were
    asked, are left out, and the rest are exported again; the sample must be
    accepted with no error. Also gives the lines that say which trades were
    left out.
    """
    gaps_of = {
        sample.name: (sample, gaps) for sample, gaps in zip(chosen, comparison.gaps, strict=True)
    }
    cases = _cases()
    derived: list[Sample] = []
    lines: list[str] = []
    for case in cases.zone_agreed_cases():
        if case.source not in gaps_of:
            continue
        source, gaps = gaps_of[case.source]
        written = json.loads(source.text)["ledgerData"]["trades"]
        left_out = {written[place]["id"]: gaps[place] for place in sorted(gaps)}
        kept = [trade for trade in case.trades() if trade.id not in left_out]
        derived.append(
            Sample(case.name, cases.text_of(kept, case.coins, case.today), Accepted(), case.today)
        )
        lines.append(
            f"{case.name}: {len(kept)} of the {len(written)} trades of {case.source}; "
            f"left out {len(left_out)}"
        )
        lines.extend(
            f"  {identifier}: {gap.zone} at {gap.instant}: "
            f"ours {gap.ours}, the ledger's {gap.ledgers}"
            for identifier, gap in left_out.items()
        )
    return derived, lines


def _announce_zone_data(
    chosen: Sequence[Sample], verdicts: Sequence[Sequence[Verdict]], comparison: ZoneDataComparison
) -> None:
    refused = {}
    for sample, answers, gaps in zip(chosen, verdicts, comparison.gaps, strict=True):
        places = {
            _zone_data_place(error) for error in zone_data_errors(answers[0], frozenset(gaps))
        }
        refused[sample.name] = [gaps[place] for place in sorted(gaps) if place in places]
    lines = zone_data_notice(comparison, refused)
    if lines:
        print("\n" + "\n".join(lines))


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


def _reported_verdicts(
    chosen: Sequence[Sample],
    verdicts: Sequence[Sequence[Verdict]],
    gaps: Sequence[Mapping[int, ZoneGap]],
) -> bool:
    failures = 0
    for sample, answers, sample_gaps in zip(chosen, verdicts, gaps, strict=True):
        problems = {
            _zone_label(zone): judge(sample.expected, verdict, frozenset(sample_gaps))
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
