"""Hygiene scan: text that must never be committed to this repository.

Looks through the files Git tracks, and the new files Git would pick up, for
machine-specific absolute paths, private work-log identifiers, and assistant
names or authorship trailers. Both file names and file contents are scanned.
It reports what it finds and changes nothing.

Each pattern is spelled so that its own source text does not match it (a
one-character class is enough), so this file needs no exemption from its own
scan, and neither does any other file.
"""

from __future__ import annotations

import enum
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


class Kind(enum.Enum):
    """What sort of text was found."""

    LOCAL_PATH = "machine-specific absolute path"
    PRIVATE_LOG_ID = "private work-log identifier"
    TOOL_ATTRIBUTION = "assistant name or authorship trailer"


@dataclass(frozen=True)
class Finding:
    """One hit; ``line`` is 0 when the hit is in the file's name."""

    path: Path
    line: int
    kind: Kind
    text: str

    def __str__(self) -> str:
        where = f"{self.path}:{self.line}" if self.line else f"{self.path} (file name)"
        return f"{where}: {self.kind.value}: {self.text!r}"


class NotAGitCheckoutError(RuntimeError):
    """There is no Git checkout here, so there is no list of files to scan."""


_PATTERNS: tuple[tuple[Kind, re.Pattern[str]], ...] = (
    # Home directories on macOS, Linux and Windows.
    (Kind.LOCAL_PATH, re.compile(r"/Users[/]")),
    (Kind.LOCAL_PATH, re.compile(r"(?<![\w.])/home[/]")),
    (Kind.LOCAL_PATH, re.compile(r"[A-Z]:\\Users[\\]", re.IGNORECASE)),
    # Work-log file stems, week folders and branch names.
    (Kind.PRIVATE_LOG_ID, re.compile(r"\b\d{2,3}[A-Z]?(?:-[A-Z])?_W\d{1,2}\b", re.IGNORECASE)),
    (Kind.PRIVATE_LOG_ID, re.compile(r"\bweek\d{1,2}_\d{6}\b", re.IGNORECASE)),
    (Kind.PRIVATE_LOG_ID, re.compile(r"\bw\d{2}-\d{2}-[a-z]", re.IGNORECASE)),
    # Assistant and vendor names, and the trailers such tools append.
    (Kind.TOOL_ATTRIBUTION, re.compile(r"Cl[a]ude", re.IGNORECASE)),
    (Kind.TOOL_ATTRIBUTION, re.compile(r"Anthr[o]pic", re.IGNORECASE)),
    (Kind.TOOL_ATTRIBUTION, re.compile(r"Co-Auth[o]red-By", re.IGNORECASE)),
    (Kind.TOOL_ATTRIBUTION, re.compile(r"Gener[a]ted with", re.IGNORECASE)),
)


def scan_text(path: Path, text: str) -> list[Finding]:
    """Findings in one file: its name (reported as line 0) and each line of its text."""
    numbered = [(0, path.as_posix()), *enumerate(text.splitlines(), start=1)]
    findings: list[Finding] = []
    for number, line in numbered:
        for kind, pattern in _PATTERNS:
            match = pattern.search(line)
            if match is not None:
                findings.append(Finding(path, number, kind, match.group()))
    return findings


def scan_repository(repo_root: Path) -> list[Finding]:
    """Findings in every file Git tracks or would add under ``repo_root``."""
    findings: list[Finding] = []
    for relative in listed_files(repo_root):
        findings.extend(scan_text(relative, _text_of(repo_root / relative)))
    return findings


def listed_files(repo_root: Path) -> list[Path]:
    """Paths, relative to ``repo_root``, that Git tracks or would add.

    Ignored files are left out; new files that are not ignored are included,
    so a problem is caught before the file is committed rather than after.
    """
    command = ["git", "-C", str(repo_root), "ls-files", "-z"]
    command += ["--cached", "--others", "--exclude-standard"]
    try:
        done = subprocess.run(command, capture_output=True, check=False)
    except FileNotFoundError as error:
        raise NotAGitCheckoutError("git is not installed") from error
    if done.returncode != 0:
        raise NotAGitCheckoutError(done.stderr.decode("utf-8", "replace").strip())
    names = done.stdout.decode("utf-8").split("\0")
    return sorted({Path(name) for name in names if name})


def _text_of(path: Path) -> str:
    """The file's text; empty when the file is gone from disk or is not text."""
    try:
        return path.read_text(encoding="utf-8")
    except (FileNotFoundError, IsADirectoryError, UnicodeDecodeError):
        return ""
