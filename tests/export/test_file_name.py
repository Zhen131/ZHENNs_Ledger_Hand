"""Tests of the export file's name."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from ledger_hand.export.file_name import backup_file_name


def test_the_name_says_who_wrote_it_that_it_is_incremental_and_when() -> None:
    moment = datetime(2026, 10, 4, 8, 0, tzinfo=timezone.utc)

    assert backup_file_name(moment) == "ledger-hand-incremental-backup-v3-20261004-080000Z.json"


def test_the_moment_in_the_name_is_in_utc_to_the_second() -> None:
    moment = datetime(2026, 1, 1, 0, 30, 5, 999_999, tzinfo=ZoneInfo("Europe/Budapest"))

    assert backup_file_name(moment) == "ledger-hand-incremental-backup-v3-20251231-233005Z.json"


def test_the_name_has_no_character_a_file_system_might_refuse() -> None:
    name = backup_file_name(datetime(2026, 10, 4, 8, 0, tzinfo=timezone.utc))

    assert all(character.isalnum() or character in "-." for character in name)
    assert "incremental" in name


def test_an_export_moment_without_an_offset_is_refused() -> None:
    with pytest.raises(ValueError, match="needs a time zone offset"):
        backup_file_name(datetime(2026, 10, 4, 8, 0))
