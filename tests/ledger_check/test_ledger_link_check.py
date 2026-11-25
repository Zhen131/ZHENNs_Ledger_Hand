"""Tests of the second step of the ledger tier, with no ledger and no link started.

What the real link lists is checked by the tier (``scripts/check.sh ledger``),
not here. These tests pin down when the step skips, and that it starts the
link on a free port with the cache of ``tsx`` off.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts import ledger_link_check
from scripts.ledger_link_check import Outcome, locate_ledger

VARIABLE = "LEDGER_HAND_LEDGER_DIR"


def ledger(tmp_path: Path) -> Path:
    folder = tmp_path / "ledger"
    (folder / "assistant-link").mkdir(parents=True)
    (folder / "assistant-link" / "main.ts").write_text("", encoding="utf-8")
    (folder / "node_modules" / "tsx").mkdir(parents=True)
    return folder


def test_nothing_named_is_skipped_saying_how_to_name_it() -> None:
    reason = locate_ledger(None, {})

    assert isinstance(reason, str)
    assert VARIABLE in reason


def test_a_missing_folder_is_skipped(tmp_path: Path) -> None:
    assert isinstance(locate_ledger(str(tmp_path / "nowhere"), {}), str)


def test_a_folder_without_the_link_or_its_packages_is_skipped(tmp_path: Path) -> None:
    folder = ledger(tmp_path)
    (folder / "node_modules" / "tsx").rmdir()

    assert "not installed" in str(locate_ledger(str(folder), {}))

    (folder / "assistant-link" / "main.ts").unlink()

    assert "assistant-link" in str(locate_ledger(str(folder), {}))


def test_a_ledger_named_by_the_variable_is_found(tmp_path: Path) -> None:
    folder = ledger(tmp_path)

    assert locate_ledger(None, {VARIABLE: str(folder)}) == folder.resolve()


def test_main_skips_with_status_3_without_a_ledger(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(VARIABLE, raising=False)

    assert ledger_link_check.main([]) == Outcome.SKIPPED.value == 3


def test_the_link_is_built_on_a_free_port_with_the_cache_off(tmp_path: Path) -> None:
    link = ledger_link_check.link_for(tmp_path, {"PATH": "bin"})
    setup = link._setup  # noqa: SLF001

    assert setup.ledger_directory == tmp_path
    assert setup.environment["TSX_DISABLE_CACHE"] == "1"
    assert setup.port != 47651
