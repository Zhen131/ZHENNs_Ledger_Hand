"""Shared set-up of the interface tests that build the real parts: a bare machine.

``bare_machine`` clears every model setting from the environment, puts the
data folder in the test's temporary folder, names the machine's zone
Europe/Budapest and works from the temporary folder, so that the wiring
module builds the same parts on every machine and writes nowhere else. The
tests that hand in parts of their own do not need it.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import tzlocal

from ledger_hand.settings import DATA_DIRECTORY_VARIABLE, ENV_PREFIX


@pytest.fixture
def bare_machine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The data folder of a machine in Europe/Budapest with no model setting; not made yet."""
    for name in list(os.environ):
        if name.startswith(ENV_PREFIX):
            monkeypatch.delenv(name)
    data = tmp_path / "data"
    monkeypatch.setenv(DATA_DIRECTORY_VARIABLE, str(data))
    monkeypatch.setattr(tzlocal, "get_localzone_name", lambda: "Europe/Budapest")
    monkeypatch.chdir(tmp_path)
    return data
