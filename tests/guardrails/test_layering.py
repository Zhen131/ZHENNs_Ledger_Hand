"""Tests of the layering check itself, run against throw-away packages.

Every rule gets a package that breaks it (and must be reported) and a package
that keeps it (and must pass). The expected answers below are written out by
hand, independently of the table inside the check, so that loosening the
check without touching these tests fails.
"""

from __future__ import annotations

import enum
import itertools
from collections.abc import Mapping
from pathlib import Path

import pytest

from tests.guardrails.layering import CORE_STDLIB, PORTS_STDLIB, Reason, Violation, check_package

PACKAGE = "fakepkg"

# One file per area of the package. "root" is the package's own __init__.
AREA_FILE = {
    "root": "__init__.py",
    "core": "core/rules.py",
    "ports": "ports.py",
    "extraction": "extraction/extractor.py",
    "asking": "asking/question_text.py",
    "export": "export/writer.py",
    "llm": "llm/client.py",
    "storage": "storage/store.py",
    "settings": "settings.py",
    "flows": "flows/record.py",
    "wiring": "wiring.py",
    "ui": "ui/app.py",
}
AREAS = tuple(AREA_FILE)

# The layering table: which other areas each area may import.
# An area may always import itself.
MAY_IMPORT = {
    "core": set(),
    "ports": {"core"},
    "extraction": {"core", "ports"},
    "asking": {"core", "ports"},
    "export": {"core", "ports"},
    "llm": {"core", "ports", "settings"},
    "storage": {"core", "ports", "settings"},
    "settings": set(),
    "flows": {
        "root",
        "core",
        "ports",
        "extraction",
        "asking",
        "export",
        "llm",
        "storage",
        "settings",
    },
    "ui": {
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
        "wiring",
    },
    "wiring": {
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
    },
    "root": set(),
}

# The only areas allowed to import each reserved module.
RESERVED_FOR = {
    "streamlit": {"ui"},
    "httpx": {"llm"},
    "sqlite3": {"storage"},
    "tzlocal": {"wiring"},
}

# Kinds of module the core must never be allowed to import.
NEVER_IN_CORE = {
    "files": ("os", "pathlib", "io", "shutil", "tempfile"),
    "network": ("socket", "ssl", "http", "urllib"),
    "database": ("sqlite3", "dbm", "shelve"),
    "processes": ("subprocess", "multiprocessing", "signal"),
    "randomness": ("random", "secrets", "uuid"),
    "clock": ("time",),
    "interface": ("tkinter", "curses"),
}

AREAS_WITH_ANY_STDLIB = (
    "root",
    "extraction",
    "export",
    "llm",
    "storage",
    "settings",
    "flows",
    "ui",
)


class Style(enum.Enum):
    """The spellings an import of another area can take."""

    ABSOLUTE = "import package.area.module"
    FROM_ABSOLUTE = "from package.area import module"
    RELATIVE = "from ..area import module"


def lines(*source_lines: str) -> str:
    """Source text of a throw-away file, one argument per line."""
    return "\n".join(source_lines) + "\n"


def build_package(root: Path, files: Mapping[str, str]) -> Path:
    """Write a throw-away package under ``root`` and return its directory."""
    package_dir = root / PACKAGE
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    for relative, source in files.items():
        path = package_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
    return package_dir


def check(root: Path, files: Mapping[str, str]) -> list[Violation]:
    return check_package(build_package(root, files))


def reasons(root: Path, files: Mapping[str, str]) -> list[Reason]:
    return [violation.reason for violation in check(root, files)]


def import_line(importer: str, target: str, style: Style) -> str:
    """An import statement, written in ``importer``'s file, that reaches ``target``."""
    head, _, name = AREA_FILE[target].removesuffix(".py").rpartition("/")
    if target == "root":
        name = "__version__"
    if style is Style.ABSOLUTE:
        module = name if target != "root" else ""
        return "import " + ".".join(part for part in (PACKAGE, head, module) if part)
    if style is Style.FROM_ABSOLUTE:
        return f"from {'.'.join(part for part in (PACKAGE, head) if part)} import {name}"
    dots = "." if "/" not in AREA_FILE[importer] else ".."
    return f"from {dots}{head} import {name}"


# --- the table: every area against every other area -------------------------


@pytest.mark.parametrize("style", list(Style))
@pytest.mark.parametrize(
    ("importer", "target"),
    [pair for pair in itertools.permutations(AREAS, 2) if pair[1] not in MAY_IMPORT[pair[0]]],
)
def test_import_the_table_forbids_is_reported(
    tmp_path: Path, importer: str, target: str, style: Style
) -> None:
    files = {AREA_FILE[target]: "", AREA_FILE[importer]: import_line(importer, target, style)}

    assert reasons(tmp_path, files) == [Reason.INTERNAL_IMPORT]


@pytest.mark.parametrize("style", list(Style))
@pytest.mark.parametrize(
    ("importer", "target"),
    [pair for pair in itertools.permutations(AREAS, 2) if pair[1] in MAY_IMPORT[pair[0]]],
)
def test_import_the_table_allows_passes(
    tmp_path: Path, importer: str, target: str, style: Style
) -> None:
    files = {AREA_FILE[target]: "", AREA_FILE[importer]: import_line(importer, target, style)}

    assert check(tmp_path, files) == []


@pytest.mark.parametrize("style", list(Style))
@pytest.mark.parametrize("area", AREAS)
def test_an_area_may_import_itself(tmp_path: Path, area: str, style: Style) -> None:
    assert check(tmp_path, {AREA_FILE[area]: import_line(area, area, style)}) == []


def test_every_row_of_the_table_has_a_forbidden_case_except_the_outermost() -> None:
    # Guards the tests above: a row with nothing forbidden would be exercised
    # one way only. ui is the outermost layer, so nothing is closed to it.
    rows_with_nothing_forbidden = [
        importer for importer in AREAS if not set(AREAS) - MAY_IMPORT[importer] - {importer}
    ]

    assert rows_with_nothing_forbidden == ["ui"]
    assert set(MAY_IMPORT) == set(AREAS)


# --- modules reserved for one area ------------------------------------------


@pytest.mark.parametrize(
    ("module", "area"),
    [
        (module, area)
        for module in RESERVED_FOR
        for area in AREAS
        if area not in RESERVED_FOR[module]
    ],
)
def test_reserved_module_outside_its_area_is_reported(
    tmp_path: Path, module: str, area: str
) -> None:
    assert reasons(tmp_path, {AREA_FILE[area]: f"import {module}"}) == [Reason.RESERVED_MODULE]


@pytest.mark.parametrize(
    ("module", "area"),
    [(module, area) for module, owners in RESERVED_FOR.items() for area in sorted(owners)],
)
@pytest.mark.parametrize("spelling", ["import {0}", "import {0} as alias", "from {0} import thing"])
def test_reserved_module_inside_its_area_passes(
    tmp_path: Path, module: str, area: str, spelling: str
) -> None:
    assert check(tmp_path, {AREA_FILE[area]: spelling.format(module)}) == []


@pytest.mark.parametrize("spelling", ["from {0} import thing", "import {0}.sub as alias"])
@pytest.mark.parametrize("module", list(RESERVED_FOR))
def test_reserved_module_is_reported_in_any_spelling(
    tmp_path: Path, module: str, spelling: str
) -> None:
    assert reasons(tmp_path, {"flows/record.py": spelling.format(module)}) == [
        Reason.RESERVED_MODULE
    ]


# --- third-party modules and repository-side code ---------------------------


@pytest.mark.parametrize("area", AREAS)
@pytest.mark.parametrize("module", ["requests", "pydantic", "langchain"])
def test_ungranted_third_party_module_is_reported(tmp_path: Path, area: str, module: str) -> None:
    assert reasons(tmp_path, {AREA_FILE[area]: f"import {module}"}) == [Reason.THIRD_PARTY_IMPORT]


@pytest.mark.parametrize("area", AREAS)
@pytest.mark.parametrize(
    "line",
    [
        "import tests.fakes",
        "from scripts import check",
        "import evals",
        "from evals.run import score",
    ],
)
def test_package_importing_repository_side_code_is_reported(
    tmp_path: Path, area: str, line: str
) -> None:
    assert reasons(tmp_path, {AREA_FILE[area]: line}) == [Reason.REPO_SIDE_IMPORT]


# --- the standard library ---------------------------------------------------


@pytest.mark.parametrize("module", sorted(CORE_STDLIB))
def test_core_may_import_its_allow_list(tmp_path: Path, module: str) -> None:
    assert check(tmp_path, {"core/rules.py": f"import {module}"}) == []


@pytest.mark.parametrize(
    "line",
    [
        "from decimal import Decimal",
        "from datetime import datetime, timedelta, timezone",
        "from collections.abc import Sequence",
        "from zoneinfo import ZoneInfo",
        "import dataclasses, enum, re",
    ],
)
def test_core_may_import_pure_modules_in_any_spelling(tmp_path: Path, line: str) -> None:
    assert check(tmp_path, {"core/rules.py": line}) == []


@pytest.mark.parametrize(
    "module", [module for modules in NEVER_IN_CORE.values() for module in modules]
)
@pytest.mark.parametrize("spelling", ["import {0}", "from {0} import thing"])
def test_core_importing_outside_world_module_is_reported(
    tmp_path: Path, module: str, spelling: str
) -> None:
    found = reasons(tmp_path, {"core/rules.py": spelling.format(module)})

    assert len(found) == 1
    assert found[0] in {Reason.STDLIB_IMPORT, Reason.RESERVED_MODULE}


@pytest.mark.parametrize("module", ["json", "logging", "sys", "importlib", "typing_extensions"])
def test_core_importing_anything_off_its_allow_list_is_reported(
    tmp_path: Path, module: str
) -> None:
    assert len(check(tmp_path, {"core/rules.py": f"import {module}"})) == 1


def test_core_allow_list_never_contains_outside_world_modules() -> None:
    never = {module for modules in NEVER_IN_CORE.values() for module in modules}

    assert never.isdisjoint(CORE_STDLIB)


@pytest.mark.parametrize("module", sorted(PORTS_STDLIB))
def test_ports_may_import_annotation_modules(tmp_path: Path, module: str) -> None:
    assert check(tmp_path, {"ports.py": f"import {module}"}) == []


@pytest.mark.parametrize(
    "line", ["from typing import Protocol", "from collections.abc import Iterator"]
)
def test_ports_may_import_annotation_names(tmp_path: Path, line: str) -> None:
    assert check(tmp_path, {"ports.py": line}) == []


@pytest.mark.parametrize(
    "line",
    [
        "import dataclasses",
        "import enum",
        "from dataclasses import dataclass",
        "from enum import Enum",
    ],
)
def test_ports_may_declare_data_classes_and_enumerations(tmp_path: Path, line: str) -> None:
    # Written out by hand: the ports file states shapes, and a shape may be a
    # data class or an enumeration.
    assert check(tmp_path, {"ports.py": line}) == []


@pytest.mark.parametrize("module", ["json", "os", "logging", "pathlib", "time"])
def test_ports_importing_other_stdlib_is_reported(tmp_path: Path, module: str) -> None:
    assert reasons(tmp_path, {"ports.py": f"import {module}"}) == [Reason.STDLIB_IMPORT]


@pytest.mark.parametrize("area", AREAS_WITH_ANY_STDLIB)
@pytest.mark.parametrize(
    "module", ["json", "os", "pathlib", "tomllib", "time", "importlib.resources"]
)
def test_other_areas_may_import_the_standard_library(
    tmp_path: Path, area: str, module: str
) -> None:
    assert check(tmp_path, {AREA_FILE[area]: f"import {module}"}) == []


# --- core: the clock and the machine's time zone ----------------------------

CLOCK_READS = [
    lines("from datetime import datetime", "stamp = datetime.now()"),
    lines("from datetime import datetime", "stamp = datetime.utcnow()"),
    lines("from datetime import datetime", "stamp = datetime.today()"),
    lines("from datetime import date", "day = date.today()"),
    lines("import datetime", "stamp = datetime.datetime.now(datetime.timezone.utc)"),
    lines("import datetime as dt", "day = dt.date.today()"),
    lines("from datetime import datetime as moment", "stamp = moment.now()"),
    lines("from datetime import datetime", "read_clock = datetime.now"),
    lines("def stamp(clock):", "    return clock.now()"),
]

LOCAL_ZONE_READS = [
    lines("def local(moment):", "    return moment.astimezone()"),
    lines("def local(moment):", "    return moment.astimezone(None)"),
    lines("def local(moment):", "    return moment.astimezone(tz=None)"),
    lines(
        "from datetime import datetime",
        "def local(seconds):",
        "    return datetime.fromtimestamp(seconds)",
    ),
    lines(
        "from datetime import date",
        "def local(seconds):",
        "    return date.fromtimestamp(seconds)",
    ),
    lines(
        "from datetime import datetime",
        "def local(seconds):",
        "    return datetime.fromtimestamp(seconds, tz=None)",
    ),
    lines("from zoneinfo import ZoneInfo", 'zone = ZoneInfo("localtime")'),
    lines("import zoneinfo", 'zone = zoneinfo.ZoneInfo("localtime")'),
]

PURE_TIME_CODE = [
    lines(
        "from datetime import datetime, timezone",
        "fixed = datetime(2026, 1, 2, 3, 4, tzinfo=timezone.utc)",
    ),
    lines("def shift(moment, zone):", "    return moment.astimezone(zone)"),
    lines("def shift(moment, zone):", "    return moment.astimezone(tz=zone)"),
    lines(
        "from datetime import datetime",
        "def at(seconds, zone):",
        "    return datetime.fromtimestamp(seconds, zone)",
    ),
    lines(
        "from datetime import datetime",
        "def at(seconds, zone):",
        "    return datetime.fromtimestamp(seconds, tz=zone)",
    ),
    lines("from zoneinfo import ZoneInfo", 'zone = ZoneInfo("Europe/Budapest")'),
    lines(
        "from datetime import datetime",
        "def parse(text):",
        "    return datetime.fromisoformat(text)",
    ),
    lines("def day_of(now):", "    return now.date()"),
    lines("def day_of(context):", "    return context.now.date()"),
    lines(
        "from datetime import timedelta",
        "def yesterday(today):",
        "    return today - timedelta(days=1)",
    ),
]


@pytest.mark.parametrize("source", CLOCK_READS)
def test_core_reading_the_clock_is_reported(tmp_path: Path, source: str) -> None:
    assert reasons(tmp_path, {"core/rules.py": source}) == [Reason.CLOCK_READ]


def test_core_reading_the_clock_through_the_time_module_is_reported(tmp_path: Path) -> None:
    # The time module is not on the core's allow-list, so the import itself
    # is what gets reported; without it none of the calls below can run.
    source = lines("import time", "stamp = time.time()", "local = time.localtime()")

    assert reasons(tmp_path, {"core/rules.py": source}) == [Reason.STDLIB_IMPORT]


@pytest.mark.parametrize("line", ["from time import time", "from time import localtime, tzname"])
def test_core_importing_names_from_the_time_module_is_reported(tmp_path: Path, line: str) -> None:
    assert reasons(tmp_path, {"core/rules.py": line}) == [Reason.STDLIB_IMPORT]


@pytest.mark.parametrize("source", LOCAL_ZONE_READS)
def test_core_reading_the_local_zone_is_reported(tmp_path: Path, source: str) -> None:
    assert reasons(tmp_path, {"core/rules.py": source}) == [Reason.LOCAL_ZONE_READ]


@pytest.mark.parametrize("source", PURE_TIME_CODE)
def test_core_handling_time_passed_in_from_outside_passes(tmp_path: Path, source: str) -> None:
    assert check(tmp_path, {"core/rules.py": source}) == []


@pytest.mark.parametrize("source", CLOCK_READS + LOCAL_ZONE_READS)
def test_clock_and_zone_rules_apply_to_core_only(tmp_path: Path, source: str) -> None:
    assert check(tmp_path, {"ui/app.py": source}) == []


# More ways of reaching the machine's zone: the zone's name given by keyword or
# to the uncached constructor, a zone loaded from a file (which is how the
# machine's own zone file is read), and a moment's timestamp (which takes a
# time without a zone to be in the machine's zone).
MORE_LOCAL_ZONE_READS = [
    pytest.param(
        lines("from zoneinfo import ZoneInfo", 'zone = ZoneInfo(key="localtime")'),
        id="name-by-keyword",
    ),
    pytest.param(
        lines("from zoneinfo import ZoneInfo", 'zone = ZoneInfo.no_cache("localtime")'),
        id="uncached",
    ),
    pytest.param(
        lines("import zoneinfo", 'zone = zoneinfo.ZoneInfo.no_cache(key="localtime")'),
        id="uncached-name-by-keyword",
    ),
    pytest.param(
        lines(
            "from zoneinfo import ZoneInfo",
            "def load(handle):",
            "    return ZoneInfo.from_file(handle)",
        ),
        id="from-a-file",
    ),
    pytest.param(
        lines("def seconds(moment):", "    return moment.timestamp()"),
        id="timestamp",
    ),
]

MORE_PURE_ZONE_CODE = [
    pytest.param(
        lines("from zoneinfo import ZoneInfo", 'zone = ZoneInfo(key="Europe/Budapest")'),
        id="named-zone-by-keyword",
    ),
    pytest.param(
        lines("from zoneinfo import ZoneInfo", 'zone = ZoneInfo.no_cache("Asia/Shanghai")'),
        id="named-zone-uncached",
    ),
]


@pytest.mark.parametrize("source", MORE_LOCAL_ZONE_READS)
def test_core_reaching_the_local_zone_another_way_is_reported(tmp_path: Path, source: str) -> None:
    assert reasons(tmp_path, {"core/rules.py": source}) == [Reason.LOCAL_ZONE_READ]


@pytest.mark.parametrize("source", MORE_PURE_ZONE_CODE)
def test_core_naming_a_zone_another_way_passes(tmp_path: Path, source: str) -> None:
    assert check(tmp_path, {"core/rules.py": source}) == []


@pytest.mark.parametrize("source", MORE_LOCAL_ZONE_READS)
def test_more_zone_rules_apply_to_core_only(tmp_path: Path, source: str) -> None:
    assert check(tmp_path, {"ui/app.py": source}) == []


# --- core: builtins that reach outside --------------------------------------

OUTSIDE_WORLD_CALLS = [
    'text = open("coins.txt").read()',
    'answer = input("amount? ")',
    'print("bought")',
    "breakpoint()",
    'value = eval("1 + 1")',
    'exec("x = 1")',
    'code = compile("1", "<s>", "eval")',
]


@pytest.mark.parametrize("source", OUTSIDE_WORLD_CALLS)
def test_core_calling_outside_world_builtin_is_reported(tmp_path: Path, source: str) -> None:
    assert reasons(tmp_path, {"core/rules.py": source}) == [Reason.OUTSIDE_WORLD_BUILTIN]


@pytest.mark.parametrize("source", OUTSIDE_WORLD_CALLS)
def test_outside_world_builtins_are_fine_outside_core(tmp_path: Path, source: str) -> None:
    assert check(tmp_path, {"flows/record.py": source}) == []


def test_core_using_pure_builtins_passes(tmp_path: Path) -> None:
    source = lines("def total(amounts):", "    return sum(sorted(amounts), start=0)")

    assert check(tmp_path, {"core/rules.py": source}) == []


# --- core: floating-point numbers -------------------------------------------

FLOAT_USES = [
    "rate = 0.1",
    "fee = 1e-3",
    "big = 1E5",
    "half = .5",
    "two = 2.",
    "debt = -0.5",
    "turn = 1j",
    lines("def scale(amount):", "    return amount * 1.5"),
    lines("def scale(amount, rate=0.0):", "    return amount"),
    "value = float(text)",
    'value = float("0.1")',
    "value = complex(text)",
    "value = number.__float__()",
    lines("from decimal import Decimal", "value = Decimal.from_float(number)"),
    lines("from fractions import Fraction", "value = Fraction.from_float(number)"),
    'value = float.fromhex("0x1p-3")',
]

EXACT_NUMBER_CODE = [
    lines("from decimal import Decimal", 'rate = Decimal("0.1")'),
    lines("from fractions import Fraction", "third = Fraction(1, 3)"),
    "count = 10",
    "big = 10**18",
    "half = 5 // 2",
    'text = "0.1"',
    'note = "1e5 is not accepted"',
    'raw = bytes.fromhex("ff")',
    lines("def total(amounts):", "    return sum(amounts)"),
]


@pytest.mark.parametrize("source", FLOAT_USES)
def test_core_using_a_floating_point_number_is_reported(tmp_path: Path, source: str) -> None:
    assert reasons(tmp_path, {"core/rules.py": source}) == [Reason.FLOAT_USE]


def test_every_floating_point_use_on_a_line_is_reported(tmp_path: Path) -> None:
    found = check(tmp_path, {"core/rules.py": lines("count = 1", "rate = float(0.5) + 0.25")})

    assert [(violation.line, violation.reason) for violation in found] == [
        (2, Reason.FLOAT_USE),
        (2, Reason.FLOAT_USE),
        (2, Reason.FLOAT_USE),
    ]


@pytest.mark.parametrize("source", EXACT_NUMBER_CODE)
def test_core_calculating_with_exact_numbers_passes(tmp_path: Path, source: str) -> None:
    assert check(tmp_path, {"core/rules.py": source}) == []


@pytest.mark.parametrize("source", FLOAT_USES)
def test_floating_point_rule_applies_to_core_only(tmp_path: Path, source: str) -> None:
    assert check(tmp_path, {"flows/record.py": source}) == []


# --- imports hidden from the reader -----------------------------------------


@pytest.mark.parametrize("area", AREAS)
@pytest.mark.parametrize(
    "source",
    [
        'client = __import__("httpx")',
        lines("import importlib", 'client = importlib.import_module("httpx")'),
        lines("from importlib import import_module", 'client = import_module("httpx")'),
    ],
)
def test_import_by_name_at_run_time_is_reported(tmp_path: Path, area: str, source: str) -> None:
    assert Reason.DYNAMIC_IMPORT in reasons(tmp_path, {AREA_FILE[area]: source})


def test_reading_packaged_files_is_not_a_hidden_import(tmp_path: Path) -> None:
    source = lines(
        "from importlib import resources",
        'text = resources.files("fakepkg").joinpath("p.txt").read_text()',
    )

    assert check(tmp_path, {"extraction/extractor.py": source}) == []


# --- areas the table does not know ------------------------------------------


@pytest.mark.parametrize("relative", ["voice/recorder.py", "assembly.py", "__main__.py"])
def test_code_outside_the_table_is_reported(tmp_path: Path, relative: str) -> None:
    assert reasons(tmp_path, {relative: ""}) == [Reason.UNKNOWN_AREA]


@pytest.mark.parametrize(
    "line", ["import fakepkg.voice", "from fakepkg import voice", "from ..voice import mic"]
)
def test_importing_an_area_outside_the_table_is_reported(tmp_path: Path, line: str) -> None:
    files = {"voice/__init__.py": "", "ui/app.py": line}

    # One report for the import in ui, one for the unknown area's own file.
    assert reasons(tmp_path, files) == [Reason.INTERNAL_IMPORT, Reason.UNKNOWN_AREA]


@pytest.mark.parametrize(
    ("relative", "line"),
    [
        ("ports.py", "from .. import other"),
        ("ports.py", "from ..other import thing"),
        ("llm/client.py", "from ... import other"),
        ("llm/client.py", "from ...other import thing"),
    ],
)
def test_relative_import_climbing_out_of_the_package_is_reported(
    tmp_path: Path, relative: str, line: str
) -> None:
    assert reasons(tmp_path, {relative: line}) == [Reason.INTERNAL_IMPORT]


# --- imports that are not at the top of a file ------------------------------


@pytest.mark.parametrize(
    "source",
    [
        lines("def load():", "    import socket", "    return socket"),
        lines("from typing import TYPE_CHECKING", "if TYPE_CHECKING:", "    import socket"),
        lines("try:", "    import socket", "except ImportError:", "    socket = None"),
        lines("class Reader:", "    def load(self):", "        from socket import socket"),
    ],
)
def test_import_tucked_inside_a_block_is_still_reported(tmp_path: Path, source: str) -> None:
    assert reasons(tmp_path, {"core/rules.py": source}) == [Reason.STDLIB_IMPORT]


def test_forbidden_internal_import_inside_a_function_is_reported(tmp_path: Path) -> None:
    files = {
        "ui/app.py": "",
        "flows/record.py": lines("def show():", "    from ..ui import app", "    return app"),
    }

    assert reasons(tmp_path, files) == [Reason.INTERNAL_IMPORT]


# --- what the check is given ------------------------------------------------


def test_parts_that_do_not_exist_are_not_demanded(tmp_path: Path) -> None:
    assert check(tmp_path, {"core/__init__.py": '"""Pure rules."""'}) == []


@pytest.mark.parametrize("directory", ["scripts", "evals", "tests"])
def test_code_outside_the_package_is_free_to_import_it(tmp_path: Path, directory: str) -> None:
    package_dir = build_package(tmp_path, {"core/rules.py": "", "ui/app.py": ""})
    outside = tmp_path / directory
    outside.mkdir()
    (outside / "tool.py").write_text(
        lines("import tzlocal", "import fakepkg.core.rules", "from fakepkg.ui import app"),
        encoding="utf-8",
    )

    assert check_package(package_dir) == []


def test_package_using_every_allowed_edge_passes(tmp_path: Path) -> None:
    plug_imports = ("from .. import ports, settings", "from ..core import trade")
    files = {
        "core/__init__.py": "",
        "core/trade.py": lines("from decimal import Decimal", "from .coins import KNOWN"),
        "core/coins.py": lines("import enum", "KNOWN = ()"),
        "ports.py": lines("from typing import Protocol", "from .core.trade import Decimal"),
        "settings.py": lines("import os", "import tomllib"),
        "extraction/extractor.py": lines(
            "import json", "from ..core import trade", "from .. import ports"
        ),
        "export/writer.py": lines(
            "import json", "from fakepkg.core import trade", "from fakepkg import ports"
        ),
        "llm/client.py": lines("import httpx", *plug_imports),
        "storage/store.py": lines("import sqlite3", *plug_imports),
        "flows/record.py": lines(
            "from ..extraction import extractor",
            "from ..export import writer",
            "from ..llm import client",
            "from ..storage import store",
            "from .. import ports, settings, __version__",
        ),
        "ui/app.py": lines(
            "import streamlit as st", "from ..flows import record", "from ..core import trade"
        ),
    }

    assert check(tmp_path, files) == []


def test_file_that_cannot_be_parsed_is_reported(tmp_path: Path) -> None:
    assert reasons(tmp_path, {"core/rules.py": "def broken(:\n"}) == [Reason.UNPARSEABLE_FILE]


def test_directory_that_is_not_a_package_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not a package directory"):
        check_package(tmp_path)


def test_violation_names_the_file_the_line_and_the_rule(tmp_path: Path) -> None:
    source = lines('"""Rules."""', "", "import enum", "import socket")

    (violation,) = check(tmp_path, {"core/rules.py": source})

    assert violation.path == Path(PACKAGE, "core", "rules.py")
    assert violation.line == 4
    assert str(violation).startswith(f"{PACKAGE}/core/rules.py:4: ")
    assert "socket" in str(violation)


def test_violations_come_back_in_file_and_line_order(tmp_path: Path) -> None:
    files = {
        "ui/app.py": "import httpx",
        "core/rules.py": lines("import enum", "import os", "import socket"),
    }

    found = [(violation.path.as_posix(), violation.line) for violation in check(tmp_path, files)]

    assert found == [
        (f"{PACKAGE}/core/rules.py", 2),
        (f"{PACKAGE}/core/rules.py", 3),
        (f"{PACKAGE}/ui/app.py", 1),
    ]


# --- environment variables ---------------------------------------------------

# Written out by hand: the only area that may touch the environment.
READS_THE_ENVIRONMENT = {"settings"}

ENVIRONMENT_READS = [
    lines("import os", 'value = os.environ["NAME"]'),
    lines("import os", 'value = os.environ.get("NAME")'),
    lines("import os", 'value = os.getenv("NAME")'),
    lines("import os", 'value = os.environb[b"NAME"]'),
    lines("import os", 'value = os.getenvb(b"NAME")'),
    lines("import os", 'os.putenv("NAME", "x")'),
    lines("import os", 'os.unsetenv("NAME")'),
    lines("import os as system", "everything = dict(system.environ)"),
    "from os import environ",
    "from os import getenv as read",
    "from os import path, environ",
    "from os import *",
    lines("import posix", "everything = posix.environ"),
    lines("import os", 'everything = getattr(os, "environ")'),
    lines("def setting():", "    import os", '    return os.environ.get("NAME")'),
]

NOT_ENVIRONMENT_READS = [
    "from os import path",
    lines("import os", "here = os.sep"),
    lines("from collections.abc import Mapping", "def load(environ: Mapping[str, str]): ..."),
    'note = "os.environ is read in one place"',
]


@pytest.mark.parametrize("source", ENVIRONMENT_READS)
@pytest.mark.parametrize("area", sorted(set(AREAS) - READS_THE_ENVIRONMENT))
def test_reading_the_environment_outside_settings_is_reported(
    tmp_path: Path, area: str, source: str
) -> None:
    assert Reason.ENVIRONMENT_READ in reasons(tmp_path, {AREA_FILE[area]: source})


@pytest.mark.parametrize("source", ENVIRONMENT_READS)
@pytest.mark.parametrize("area", sorted(READS_THE_ENVIRONMENT))
def test_settings_may_read_the_environment(tmp_path: Path, area: str, source: str) -> None:
    assert check(tmp_path, {AREA_FILE[area]: source}) == []


@pytest.mark.parametrize("source", NOT_ENVIRONMENT_READS)
@pytest.mark.parametrize("area", ["llm", "extraction", "flows", "ui"])
def test_other_uses_of_os_are_not_environment_reads(tmp_path: Path, area: str, source: str) -> None:
    assert Reason.ENVIRONMENT_READ not in reasons(tmp_path, {AREA_FILE[area]: source})


def test_an_environment_read_names_the_line(tmp_path: Path) -> None:
    source = lines("import os", "", 'value = os.getenv("NAME")')

    (violation,) = check(tmp_path, {"llm/client.py": source})

    assert violation.reason is Reason.ENVIRONMENT_READ
    assert violation.line == 3


# --- extraction: handed the moment and the zone, never reading them ----------

# Written out by hand: the areas that read neither the clock nor the
# machine's time zone. The core is checked above; extraction is checked here.
CLOCK_FREE = {"core", "extraction", "asking", "flows"}
EXTRACTION_FILE = AREA_FILE["extraction"]

TIME_MODULE_CLOCK_READS = [
    lines("import time", "stamp = time.time()"),
    lines("import time", "started = time.monotonic()"),
    lines("import time", "started = time.perf_counter_ns()"),
    lines("import time as clock", "stamp = clock.time()"),
    lines("import time", "read = time.time"),
    "from time import time",
    "from time import perf_counter as tick",
    "from time import *",
    lines("import time", "parts = time.gmtime()"),
]

TIME_MODULE_ZONE_READS = [
    lines("import time", "parts = time.localtime()"),
    lines("import time", "names = time.tzname"),
    lines("import time", "offset = time.timezone"),
    lines("import time", "text = time.strftime('%H')"),
    lines("import time", "text = time.ctime()"),
    "from time import localtime",
    "from time import altzone, daylight",
]

TIME_MODULE_HARMLESS = [
    "import time",
    lines("import time", "time.sleep(0)"),
    "from time import sleep",
    lines("import time", "kind = time.struct_time"),
]


@pytest.mark.parametrize("source", CLOCK_READS)
def test_extraction_reading_the_clock_is_reported(tmp_path: Path, source: str) -> None:
    assert reasons(tmp_path, {EXTRACTION_FILE: source}) == [Reason.CLOCK_READ]


@pytest.mark.parametrize("source", LOCAL_ZONE_READS + MORE_LOCAL_ZONE_READS)
def test_extraction_reading_the_local_zone_is_reported(tmp_path: Path, source: str) -> None:
    assert reasons(tmp_path, {EXTRACTION_FILE: source}) == [Reason.LOCAL_ZONE_READ]


@pytest.mark.parametrize("source", TIME_MODULE_CLOCK_READS)
def test_extraction_reading_the_clock_through_the_time_module_is_reported(
    tmp_path: Path, source: str
) -> None:
    assert reasons(tmp_path, {EXTRACTION_FILE: source}) == [Reason.CLOCK_READ]


@pytest.mark.parametrize("source", TIME_MODULE_ZONE_READS)
def test_extraction_reading_the_local_zone_through_the_time_module_is_reported(
    tmp_path: Path, source: str
) -> None:
    found = reasons(tmp_path, {EXTRACTION_FILE: source})

    assert found and set(found) == {Reason.LOCAL_ZONE_READ}


@pytest.mark.parametrize("source", TIME_MODULE_HARMLESS + PURE_TIME_CODE + MORE_PURE_ZONE_CODE)
def test_extraction_handling_time_passed_in_passes(tmp_path: Path, source: str) -> None:
    assert check(tmp_path, {EXTRACTION_FILE: source}) == []


@pytest.mark.parametrize("source", ENVIRONMENT_READS)
def test_extraction_reading_the_environment_is_reported(tmp_path: Path, source: str) -> None:
    assert Reason.ENVIRONMENT_READ in reasons(tmp_path, {EXTRACTION_FILE: source})


@pytest.mark.parametrize("module", ["httpx", "tzlocal", "sqlite3", "streamlit"])
@pytest.mark.parametrize("spelling", ["import {0}", "from {0} import thing", "import {0} as alias"])
def test_extraction_importing_a_reserved_module_is_reported(
    tmp_path: Path, module: str, spelling: str
) -> None:
    assert reasons(tmp_path, {EXTRACTION_FILE: spelling.format(module)}) == [Reason.RESERVED_MODULE]


@pytest.mark.parametrize("target", ["llm", "settings", "storage", "export", "flows", "ui"])
def test_extraction_importing_the_plugs_or_the_settings_is_reported(
    tmp_path: Path, target: str
) -> None:
    line = import_line("extraction", target, Style.FROM_ABSOLUTE)

    assert reasons(tmp_path, {EXTRACTION_FILE: line}) == [Reason.INTERNAL_IMPORT]


@pytest.mark.parametrize("area", sorted(set(AREAS) - CLOCK_FREE))
@pytest.mark.parametrize("source", TIME_MODULE_CLOCK_READS + TIME_MODULE_ZONE_READS)
def test_the_time_module_rules_apply_to_extraction_only(
    tmp_path: Path, area: str, source: str
) -> None:
    found = reasons(tmp_path, {AREA_FILE[area]: source})

    assert Reason.CLOCK_READ not in found and Reason.LOCAL_ZONE_READ not in found


@pytest.mark.parametrize("area", sorted(set(AREAS) - CLOCK_FREE))
@pytest.mark.parametrize("source", CLOCK_READS + LOCAL_ZONE_READS)
def test_the_clock_and_zone_rules_spare_every_area_but_the_clock_free_ones(
    tmp_path: Path, area: str, source: str
) -> None:
    found = reasons(tmp_path, {AREA_FILE[area]: source})

    assert Reason.CLOCK_READ not in found and Reason.LOCAL_ZONE_READ not in found
