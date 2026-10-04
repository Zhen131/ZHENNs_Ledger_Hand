"""Gate: the real package must obey the layering table."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.guardrails.layering import check_package

PACKAGE_DIR = Path(__file__).resolve().parents[2] / "src" / "ledger_hand"


def test_package_obeys_the_layering_table() -> None:
    violations = check_package(PACKAGE_DIR)

    if violations:
        report = "\n".join(str(violation) for violation in violations)
        pytest.fail(f"{len(violations)} layering violation(s):\n{report}", pytrace=False)
