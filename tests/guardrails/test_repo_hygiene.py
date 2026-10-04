"""Gate: no file Git tracks or would add may contain forbidden text."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.guardrails.hygiene import scan_repository

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_repository_files_are_clean() -> None:
    findings = scan_repository(REPO_ROOT)

    if findings:
        report = "\n".join(str(finding) for finding in findings)
        pytest.fail(f"{len(findings)} hygiene finding(s):\n{report}", pytrace=False)
