"""Tests of the layering check for the wiring module: the one place that assembles the program.

``wiring.py`` sits at the top of the package, beside the settings and the
ports file. It builds the plugs from the settings and reads the clock and
the machine's time zone, so it may import every part of the package but the
interface, and it is the only part that may import ``tzlocal``. Only the
interface may import it: the flows are handed what it builds and never
import it back. Every rule gets a throw-away package that breaks it (and
must be reported) and one that keeps it (and must pass). The expected
answers are written out by hand.
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
    TIME_MODULE_CLOCK_READS,
    TIME_MODULE_ZONE_READS,
    Style,
    check,
    import_line,
    reasons,
)

WIRING_FILE = "wiring.py"
# Written out by hand: what the wiring module may import besides itself.
WIRING_MAY_IMPORT = {
    "root",
    "core",
    "ports",
    "extraction",
    "asking",
    "export",
    "llm",
    "storage",
    "settings",
    "flows",
}
# Written out by hand: the only area that may import the wiring module.
IMPORTS_WIRING = {"ui"}
OTHER_AREAS = sorted(set(AREA_FILE) - {"wiring"})


def test_the_wiring_module_is_an_area_of_its_own() -> None:
    assert AREA_FILE["wiring"] == WIRING_FILE


def test_the_wiring_module_is_not_an_unknown_area(tmp_path: Path) -> None:
    assert check(tmp_path, {WIRING_FILE: ""}) == []


@pytest.mark.parametrize("target", sorted(WIRING_MAY_IMPORT))
@pytest.mark.parametrize("style", list(Style))
def test_wiring_importing_every_part_but_the_interface_passes(
    tmp_path: Path, target: str, style: Style
) -> None:
    files = {AREA_FILE[target]: "", WIRING_FILE: import_line("wiring", target, style)}

    assert check(tmp_path, files) == []


@pytest.mark.parametrize("style", list(Style))
def test_wiring_importing_the_interface_is_reported(tmp_path: Path, style: Style) -> None:
    files = {AREA_FILE["ui"]: "", WIRING_FILE: import_line("wiring", "ui", style)}

    assert reasons(tmp_path, files) == [Reason.INTERNAL_IMPORT]


@pytest.mark.parametrize("style", list(Style))
def test_the_flows_importing_the_wiring_module_is_reported(tmp_path: Path, style: Style) -> None:
    files = {WIRING_FILE: "", AREA_FILE["flows"]: import_line("flows", "wiring", style)}

    assert reasons(tmp_path, files) == [Reason.INTERNAL_IMPORT]


def test_the_flows_importing_the_wiring_module_inside_a_function_is_reported(
    tmp_path: Path,
) -> None:
    source = "\n".join(["def parts():", "    from .. import wiring", "    return wiring", ""])

    assert reasons(tmp_path, {WIRING_FILE: "", AREA_FILE["flows"]: source}) == [
        Reason.INTERNAL_IMPORT
    ]


@pytest.mark.parametrize("importer", sorted(set(OTHER_AREAS) - IMPORTS_WIRING))
@pytest.mark.parametrize("style", list(Style))
def test_every_part_but_the_interface_importing_the_wiring_module_is_reported(
    tmp_path: Path, importer: str, style: Style
) -> None:
    files = {WIRING_FILE: "", AREA_FILE[importer]: import_line(importer, "wiring", style)}

    assert reasons(tmp_path, files) == [Reason.INTERNAL_IMPORT]


@pytest.mark.parametrize("style", list(Style))
def test_the_interface_importing_the_wiring_module_passes(tmp_path: Path, style: Style) -> None:
    files = {WIRING_FILE: "", AREA_FILE["ui"]: import_line("ui", "wiring", style)}

    assert check(tmp_path, files) == []


@pytest.mark.parametrize(
    "spelling",
    ["import tzlocal", "import tzlocal as zone_names", "from tzlocal import get_localzone_name"],
)
def test_wiring_may_import_tzlocal(tmp_path: Path, spelling: str) -> None:
    assert check(tmp_path, {WIRING_FILE: spelling}) == []


@pytest.mark.parametrize("area", OTHER_AREAS)
@pytest.mark.parametrize("spelling", ["import tzlocal", "from tzlocal import get_localzone_name"])
def test_tzlocal_anywhere_else_in_the_package_is_reported(
    tmp_path: Path, area: str, spelling: str
) -> None:
    assert reasons(tmp_path, {AREA_FILE[area]: spelling}) == [Reason.RESERVED_MODULE]


@pytest.mark.parametrize("module", ["streamlit", "httpx", "sqlite3"])
def test_wiring_importing_a_module_reserved_for_another_part_is_reported(
    tmp_path: Path, module: str
) -> None:
    assert reasons(tmp_path, {WIRING_FILE: f"import {module}"}) == [Reason.RESERVED_MODULE]


@pytest.mark.parametrize("module", ["pandas", "numpy", "requests", "pydantic"])
def test_wiring_importing_an_ungranted_third_party_module_is_reported(
    tmp_path: Path, module: str
) -> None:
    assert reasons(tmp_path, {WIRING_FILE: f"import {module}"}) == [Reason.THIRD_PARTY_IMPORT]


@pytest.mark.parametrize("source", ENVIRONMENT_READS)
def test_wiring_reading_the_environment_is_reported(tmp_path: Path, source: str) -> None:
    # The settings are read through the settings module, here as everywhere.
    assert Reason.ENVIRONMENT_READ in reasons(tmp_path, {WIRING_FILE: source})


@pytest.mark.parametrize(
    "source",
    CLOCK_READS
    + LOCAL_ZONE_READS
    + MORE_LOCAL_ZONE_READS
    + TIME_MODULE_CLOCK_READS
    + TIME_MODULE_ZONE_READS,
)
def test_wiring_may_read_the_clock_and_the_machines_zone(tmp_path: Path, source: str) -> None:
    # Reading them is its job: it hands them to the flows, which never read them.
    found = reasons(tmp_path, {WIRING_FILE: source})

    assert Reason.CLOCK_READ not in found and Reason.LOCAL_ZONE_READ not in found


# --- what the interface may import, now that Streamlit brings its own dependencies


@pytest.mark.parametrize("module", ["pandas", "numpy", "altair", "pyarrow", "pydeck", "PIL"])
def test_the_interface_importing_what_streamlit_brings_along_is_reported(
    tmp_path: Path, module: str
) -> None:
    # Only streamlit itself is granted; what it installs beside it is not.
    assert reasons(tmp_path, {AREA_FILE["ui"]: f"import {module}"}) == [Reason.THIRD_PARTY_IMPORT]


@pytest.mark.parametrize(
    "spelling", ["import streamlit as st", "from streamlit.testing.v1 import AppTest"]
)
def test_the_interface_may_import_streamlit(tmp_path: Path, spelling: str) -> None:
    assert check(tmp_path, {AREA_FILE["ui"]: spelling}) == []
