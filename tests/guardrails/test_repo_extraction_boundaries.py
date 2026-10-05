"""Gate: extraction's boundaries in the real package, checked a second way.

The layering check already enforces these through its table. Here they are
checked again straight from the source of ``extraction/``, without the
table, so that a change to the table alone cannot quietly open them:
extraction imports only the standard library, the core and the ports file;
it does not import the time module at all; it calls no method that reads
the clock or the machine's zone; and it names no environment variable.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

EXTRACTION_DIR = Path(__file__).resolve().parents[2] / "src" / "ledger_hand" / "extraction"
ALLOWED_PARTS = {"core", "ports", "extraction"}
CLOCK_CALLS = {"now", "utcnow", "today", "timestamp", "fromtimestamp", "from_file"}
ENVIRONMENT_NAMES = {"environ", "environb", "getenv", "getenvb", "putenv", "unsetenv"}


def extraction_files() -> list[Path]:
    files = sorted(EXTRACTION_DIR.rglob("*.py"))
    assert files, "extraction is expected to exist"
    return files


def imported_modules(path: Path) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, f"{path.name}: relative imports are not expected here"
            found.add(node.module or "")
    return found


def test_extraction_imports_only_the_standard_library_the_core_and_the_ports() -> None:
    for path in extraction_files():
        for module in imported_modules(path):
            top, _, rest = module.partition(".")
            if top == "ledger_hand":
                assert rest.split(".")[0] in ALLOWED_PARTS, (path.name, module)
            else:
                assert top in sys.stdlib_module_names, (path.name, module)
                assert top != "time", (path.name, module)


def test_extraction_calls_nothing_that_reads_the_clock_or_the_machines_zone() -> None:
    for path in extraction_files():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                name = node.func.attr
                assert name not in CLOCK_CALLS, (path.name, node.lineno, name)
                if name == "astimezone":
                    assert node.args or node.keywords, (path.name, node.lineno)
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert node.value != "localtime", (path.name, node.lineno)


def test_extraction_names_no_environment_variable() -> None:
    for path in extraction_files():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Attribute):
                assert node.attr not in ENVIRONMENT_NAMES, (path.name, node.lineno)
            if isinstance(node, ast.Name):
                assert node.id not in ENVIRONMENT_NAMES, (path.name, node.lineno)
