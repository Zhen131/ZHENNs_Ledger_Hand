"""The installed package can be imported and states a version."""

from __future__ import annotations

import re

import ledger_hand


def test_package_states_a_three_part_version() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", ledger_hand.__version__)
