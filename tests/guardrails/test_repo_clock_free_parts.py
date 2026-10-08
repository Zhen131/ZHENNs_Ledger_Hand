"""Gate: ``asking/`` and ``flows/`` in the real package read no clock and no machine zone.

The current moment and the zone are handed in to every step of recording a
passage. Here the source of the two parts is checked straight, without the
layering table: neither imports the ``time`` module, calls a method that
reads the clock or the machine's zone (``astimezone`` only with a zone),
names the zone "localtime", or names an environment variable. ``asking/``
also imports only the standard library, the core and the ports file.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

PACKAGE_DIR = Path(__file__).resolve().parents[2] / "src" / "ledger_hand"
PARTS = ("asking", "flows")
CLOCK_CALLS = {"now", "utcnow", "today", "timestamp", "fromtimestamp", "from_file"}
ENVIRONMENT_NAMES = {"environ", "environb", "getenv", "getenvb", "putenv", "unsetenv"}
ASKING_MAY_IMPORT = {"core", "ports", "asking"}


def files_of(part: str) -> list[Path]:
    files = sorted((PACKAGE_DIR / part).rglob("*.py"))
    assert files, f"{part} is expected to exist"
    return files


def imported(path: Path) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, f"{path.name}: relative imports are not expected here"
            found.add(node.module or "")
    return found


@pytest.mark.parametrize("part", PARTS)
def test_the_part_does_not_import_the_time_module(part: str) -> None:
    for path in files_of(part):
        assert all(module.partition(".")[0] != "time" for module in imported(path)), path.name


def test_asking_imports_only_the_standard_library_the_core_and_the_ports() -> None:
    for path in files_of("asking"):
        for module in imported(path):
            top, _, rest = module.partition(".")
            if top == "ledger_hand":
                assert rest.split(".")[0] in ASKING_MAY_IMPORT, (path.name, module)
            else:
                assert top in sys.stdlib_module_names, (path.name, module)


@pytest.mark.parametrize("part", PARTS)
def test_the_part_calls_nothing_that_reads_the_clock_or_the_machines_zone(part: str) -> None:
    for path in files_of(part):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                name = node.func.attr
                assert name not in CLOCK_CALLS, (path.name, node.lineno, name)
                if name == "astimezone":
                    assert node.args or node.keywords, (path.name, node.lineno)
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert node.value != "localtime", (path.name, node.lineno)


@pytest.mark.parametrize("part", PARTS)
def test_the_part_names_no_environment_variable(part: str) -> None:
    for path in files_of(part):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Attribute):
                assert node.attr not in ENVIRONMENT_NAMES, (path.name, node.lineno)
            if isinstance(node, ast.Name):
                assert node.id not in ENVIRONMENT_NAMES, (path.name, node.lineno)
