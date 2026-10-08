"""Tests of writing an export file: a new file, whole, or nothing; never a file replaced."""

from __future__ import annotations

from pathlib import Path

import pytest

from ledger_hand.flows import export_file
from ledger_hand.flows.export_file import NotWritten, WriteProblem, write_new_file

TEXT = '{\n  "invented": "日本語 and English",\n  "number": "0.02"\n}\n'


def test_the_text_is_written_as_utf8_under_its_name_and_nothing_else_is_left(
    tmp_path: Path,
) -> None:
    written = write_new_file(tmp_path / "exports", "file.json", TEXT)

    assert written == tmp_path / "exports" / "file.json"
    assert written.read_bytes() == TEXT.encode("utf-8")
    assert [path.name for path in (tmp_path / "exports").iterdir()] == ["file.json"]


def test_missing_folders_are_made(tmp_path: Path) -> None:
    written = write_new_file(tmp_path / "a" / "b" / "c", "file.json", TEXT)

    assert isinstance(written, Path)
    assert written.is_file()


def test_a_file_of_that_name_is_left_as_it_is(tmp_path: Path) -> None:
    (tmp_path / "file.json").write_bytes(b"kept")

    outcome = write_new_file(tmp_path, "file.json", TEXT)

    assert outcome == NotWritten(WriteProblem.NAME_TAKEN, str(tmp_path / "file.json"))
    assert (tmp_path / "file.json").read_bytes() == b"kept"
    assert [path.name for path in tmp_path.iterdir()] == ["file.json"]


def test_a_folder_that_is_a_file_cannot_be_written_into(tmp_path: Path) -> None:
    (tmp_path / "exports").write_text("a file", encoding="utf-8")

    outcome = write_new_file(tmp_path / "exports", "file.json", TEXT)

    assert isinstance(outcome, NotWritten)
    assert outcome.problem is WriteProblem.CANNOT_WRITE
    assert [path.name for path in tmp_path.iterdir()] == ["exports"]


def test_a_folder_that_cannot_be_written_into_gets_nothing(tmp_path: Path) -> None:
    folder = tmp_path / "exports"
    folder.mkdir()
    folder.chmod(0o500)
    try:
        outcome = write_new_file(folder, "file.json", TEXT)
    finally:
        folder.chmod(0o700)

    assert isinstance(outcome, NotWritten)
    assert outcome.problem is WriteProblem.CANNOT_WRITE
    assert list(folder.iterdir()) == []


@pytest.mark.parametrize("failing", ["fsync", "link"])
def test_a_failure_half_way_removes_the_temporary_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failing: str
) -> None:
    def fails(*_arguments: object) -> None:
        raise OSError(28, "No space left on device (staged)")

    monkeypatch.setattr(export_file.os, failing, fails)

    outcome = write_new_file(tmp_path, "file.json", TEXT)

    assert isinstance(outcome, NotWritten)
    assert outcome.problem is WriteProblem.CANNOT_WRITE
    assert "staged" in outcome.detail
    assert list(tmp_path.iterdir()) == []
