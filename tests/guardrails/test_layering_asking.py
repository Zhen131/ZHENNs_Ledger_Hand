"""Tests of the layering check for ``asking/``: handed the facts, never reading the clock.

``asking/`` may import only the core and the ports file, like extraction,
and reads neither the clock nor the machine's time zone. Every rule gets a
throw-away package that breaks it (and must be reported) and one that keeps
it (and must pass). The expected answers are written out by hand.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.guardrails.layering import Reason
from tests.guardrails.test_layering import (
    AREA_FILE,
    CLOCK_READS,
    ENVIRONMENT_READS,
    LOCAL_ZONE_READS,
    MORE_LOCAL_ZONE_READS,
    MORE_PURE_ZONE_CODE,
    PURE_TIME_CODE,
    TIME_MODULE_CLOCK_READS,
    TIME_MODULE_HARMLESS,
    TIME_MODULE_ZONE_READS,
    Style,
    check,
    import_line,
    reasons,
)

ASKING_FILE = AREA_FILE["asking"]
# Written out by hand: what asking may import besides itself.
ASKING_MAY_IMPORT = {"core", "ports"}


@pytest.mark.parametrize("source", CLOCK_READS + TIME_MODULE_CLOCK_READS)
def test_asking_reading_the_clock_is_reported(tmp_path: Path, source: str) -> None:
    assert reasons(tmp_path, {ASKING_FILE: source}) == [Reason.CLOCK_READ]


@pytest.mark.parametrize("source", LOCAL_ZONE_READS + MORE_LOCAL_ZONE_READS)
def test_asking_reading_the_local_zone_is_reported(tmp_path: Path, source: str) -> None:
    assert reasons(tmp_path, {ASKING_FILE: source}) == [Reason.LOCAL_ZONE_READ]


@pytest.mark.parametrize("source", TIME_MODULE_ZONE_READS)
def test_asking_reading_the_local_zone_through_the_time_module_is_reported(
    tmp_path: Path, source: str
) -> None:
    found = reasons(tmp_path, {ASKING_FILE: source})

    assert found and set(found) == {Reason.LOCAL_ZONE_READ}


@pytest.mark.parametrize("source", TIME_MODULE_HARMLESS + PURE_TIME_CODE + MORE_PURE_ZONE_CODE)
def test_asking_handling_time_passed_in_passes(tmp_path: Path, source: str) -> None:
    assert check(tmp_path, {ASKING_FILE: source}) == []


@pytest.mark.parametrize("source", ENVIRONMENT_READS)
def test_asking_reading_the_environment_is_reported(tmp_path: Path, source: str) -> None:
    assert Reason.ENVIRONMENT_READ in reasons(tmp_path, {ASKING_FILE: source})


@pytest.mark.parametrize("module", ["httpx", "tzlocal", "sqlite3", "streamlit"])
def test_asking_importing_a_reserved_module_is_reported(tmp_path: Path, module: str) -> None:
    assert reasons(tmp_path, {ASKING_FILE: f"import {module}"}) == [Reason.RESERVED_MODULE]


@pytest.mark.parametrize(
    "target", ["extraction", "export", "llm", "storage", "settings", "flows", "ui", "root"]
)
def test_asking_importing_anything_but_the_core_and_the_ports_is_reported(
    tmp_path: Path, target: str
) -> None:
    files = {AREA_FILE[target]: "", ASKING_FILE: import_line("asking", target, Style.FROM_ABSOLUTE)}

    assert reasons(tmp_path, files) == [Reason.INTERNAL_IMPORT]


@pytest.mark.parametrize("target", sorted(ASKING_MAY_IMPORT))
@pytest.mark.parametrize("style", list(Style))
def test_asking_importing_the_core_and_the_ports_passes(
    tmp_path: Path, target: str, style: Style
) -> None:
    files = {AREA_FILE[target]: "", ASKING_FILE: import_line("asking", target, style)}

    assert check(tmp_path, files) == []


@pytest.mark.parametrize("importer", ["flows", "ui"])
def test_flows_and_the_interface_may_import_asking(tmp_path: Path, importer: str) -> None:
    files = {ASKING_FILE: "", AREA_FILE[importer]: import_line(importer, "asking", Style.RELATIVE)}

    assert check(tmp_path, files) == []


@pytest.mark.parametrize("importer", ["core", "ports", "extraction", "export", "llm", "storage"])
def test_the_inner_parts_may_not_import_asking(tmp_path: Path, importer: str) -> None:
    line = import_line(importer, "asking", Style.FROM_ABSOLUTE)

    assert reasons(tmp_path, {ASKING_FILE: "", AREA_FILE[importer]: line}) == [
        Reason.INTERNAL_IMPORT
    ]
