"""Tests of how the ledger tier starts the checkout's own ``tsx``, by the system named.

Elsewhere than Windows it is ``node_modules/.bin/tsx`` itself, as before. On
Windows that file is a shell script Windows cannot start, so ``node`` runs
the entry the ``tsx`` package names (``bin``: one path, or one per command
name). Each test names its system, so all run on every system.
"""

from __future__ import annotations

import json
import subprocess
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from scripts import ledger_check
from scripts.ledger_check import LEDGER_TSX, LEDGER_TSX_PACKAGE, tsx_command


def _package(ledger: Path, bin_value: object, *, entry: str | None = "dist/cli.mjs") -> None:
    package = ledger / LEDGER_TSX_PACKAGE
    package.parent.mkdir(parents=True, exist_ok=True)
    package.write_text(json.dumps({"name": "tsx", "bin": bin_value}), encoding="utf-8")
    if entry is not None:
        (package.parent / entry).parent.mkdir(parents=True, exist_ok=True)
        (package.parent / entry).write_text("", encoding="utf-8")


@pytest.mark.parametrize("platform", ["darwin", "linux"])
def test_elsewhere_than_windows_the_script_in_bin_is_started_itself(
    tmp_path: Path, platform: str
) -> None:
    (tmp_path / LEDGER_TSX).parent.mkdir(parents=True)
    (tmp_path / LEDGER_TSX).write_text("", encoding="utf-8")
    _package(tmp_path, "./dist/cli.mjs")

    assert tsx_command(tmp_path, platform) == [str(tmp_path / LEDGER_TSX)]


def test_elsewhere_than_windows_a_missing_script_says_so(tmp_path: Path) -> None:
    _package(tmp_path, "./dist/cli.mjs")

    assert isinstance(tsx_command(tmp_path, "darwin"), str)


@pytest.mark.parametrize("bin_value", ["./dist/cli.mjs", {"tsx": "./dist/cli.mjs"}])
def test_on_windows_node_runs_the_entry_the_package_names(
    tmp_path: Path, bin_value: object
) -> None:
    _package(tmp_path, bin_value)

    command = tsx_command(tmp_path, "win32")

    assert command == ["node", str(tmp_path / "node_modules" / "tsx" / "./dist/cli.mjs")]


@pytest.mark.parametrize(
    ("bin_value", "entry"),
    [
        ("./dist/cli.mjs", None),
        ({"other": "./dist/cli.mjs"}, "dist/cli.mjs"),
        (None, "dist/cli.mjs"),
        ("", "dist/cli.mjs"),
    ],
)
def test_on_windows_no_entry_to_run_says_why(
    tmp_path: Path, bin_value: object, entry: str | None
) -> None:
    _package(tmp_path, bin_value, entry=entry)

    assert isinstance(tsx_command(tmp_path, "win32"), str)


def test_on_windows_no_package_says_why(tmp_path: Path) -> None:
    (tmp_path / LEDGER_TSX).parent.mkdir(parents=True)
    (tmp_path / LEDGER_TSX).write_text("", encoding="utf-8")

    assert isinstance(tsx_command(tmp_path, "win32"), str)


class _Ran:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def __call__(self, command: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        self.commands.append(command)
        return subprocess.CompletedProcess(command, 1, "", "stopped by the test")


def test_both_runs_start_with_the_tsx_command_then_the_same_arguments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ran = _Ran()
    monkeypatch.setattr(ledger_check, "tsx_command", lambda ledger: ["START", "TSX"])
    monkeypatch.setattr(ledger_check.subprocess, "run", ran)
    config = tmp_path / "tsconfig.json"

    ledger_check.run_validator(tmp_path, config, [tmp_path / "a.json"], date(2026, 11, 27))
    ledger_check.run_offsets(tmp_path, config, tmp_path, [("2026-11-27T00:00:00Z", "UTC")])

    validator, offsets = ran.commands
    assert validator == [
        "START",
        "TSX",
        "--no-cache",
        "--tsconfig",
        str(config),
        str(ledger_check.VALIDATOR),
        str(tmp_path),
        "2026-11-27",
        str(tmp_path / "a.json"),
    ]
    assert offsets == [
        "START",
        "TSX",
        "--no-cache",
        "--tsconfig",
        str(config),
        str(ledger_check.OFFSETS),
        str(tmp_path),
        str(tmp_path / "offset-probes.json"),
    ]


def test_no_tsx_to_run_is_said_and_nothing_is_started(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ran = _Ran()
    monkeypatch.setattr(ledger_check, "tsx_command", lambda ledger: "no entry")
    monkeypatch.setattr(ledger_check.subprocess, "run", ran)
    config = tmp_path / "tsconfig.json"

    said = ledger_check.run_validator(tmp_path, config, [], date(2026, 11, 27))
    asked = ledger_check.run_offsets(tmp_path, config, tmp_path, [])

    assert isinstance(said, str) and "no entry" in said
    assert isinstance(asked, str) and "no entry" in asked
    assert ran.commands == []
