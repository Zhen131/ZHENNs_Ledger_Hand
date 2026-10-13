"""Tests of the layering check for ``flows/``: handed the moment and the zone, never reading them.

The flows are handed the current moment and the zone by the wiring module and
read neither from the machine, like extraction and asking. A throw-away
package that reads the clock or the machine's zone in ``flows/`` must be
reported, with the same reasons as in extraction and asking; one that only
handles time passed in must pass. The expected answers are written out by
hand.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.guardrails.layering import Reason
from tests.guardrails.test_layering import (
    AREA_FILE,
    CLOCK_READS,
    LOCAL_ZONE_READS,
    MORE_LOCAL_ZONE_READS,
    MORE_PURE_ZONE_CODE,
    PURE_TIME_CODE,
    TIME_MODULE_CLOCK_READS,
    TIME_MODULE_HARMLESS,
    TIME_MODULE_ZONE_READS,
    check,
    reasons,
)

FLOWS_FILE = AREA_FILE["flows"]
EVERY_READ = (
    CLOCK_READS
    + LOCAL_ZONE_READS
    + MORE_LOCAL_ZONE_READS
    + TIME_MODULE_CLOCK_READS
    + TIME_MODULE_ZONE_READS
)


@pytest.mark.parametrize("source", CLOCK_READS + TIME_MODULE_CLOCK_READS)
def test_flows_reading_the_clock_is_reported(tmp_path: Path, source: str) -> None:
    assert reasons(tmp_path, {FLOWS_FILE: source}) == [Reason.CLOCK_READ]


@pytest.mark.parametrize("source", LOCAL_ZONE_READS + MORE_LOCAL_ZONE_READS)
def test_flows_reading_the_local_zone_is_reported(tmp_path: Path, source: str) -> None:
    assert reasons(tmp_path, {FLOWS_FILE: source}) == [Reason.LOCAL_ZONE_READ]


@pytest.mark.parametrize("source", TIME_MODULE_ZONE_READS)
def test_flows_reading_the_local_zone_through_the_time_module_is_reported(
    tmp_path: Path, source: str
) -> None:
    found = reasons(tmp_path, {FLOWS_FILE: source})

    assert found and set(found) == {Reason.LOCAL_ZONE_READ}


@pytest.mark.parametrize("source", EVERY_READ)
@pytest.mark.parametrize("other", ["extraction", "asking"])
def test_flows_are_told_the_same_as_extraction_and_asking(
    tmp_path: Path, source: str, other: str
) -> None:
    (tmp_path / "flows").mkdir()
    (tmp_path / other).mkdir()
    in_flows = reasons(tmp_path / "flows", {FLOWS_FILE: source})
    in_other = reasons(tmp_path / other, {AREA_FILE[other]: source})

    assert in_flows and in_flows == in_other


@pytest.mark.parametrize("source", TIME_MODULE_HARMLESS + PURE_TIME_CODE + MORE_PURE_ZONE_CODE)
def test_flows_handling_time_passed_in_passes(tmp_path: Path, source: str) -> None:
    assert check(tmp_path, {FLOWS_FILE: source}) == []
