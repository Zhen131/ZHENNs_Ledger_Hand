"""Gate: the storage's boundaries in the real package, checked a second way.

The layering check already enforces these through its table. Here they are
checked again straight from the source, without the table, so that a change
to the table alone cannot quietly open them: only ``storage/`` imports
sqlite3, ``storage/`` imports nothing of the package but the core, the ports
file, the settings and itself, and the ports file still imports only the
standard library and the core.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parents[2] / "src" / "ledger_hand"
STORAGE_MAY_IMPORT = {"core", "ports", "settings", "storage"}


def imported(path: Path) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, f"{path.name}: relative imports are not expected here"
            found.add(node.module or "")
    return found


def relative(path: Path) -> str:
    return path.relative_to(PACKAGE_DIR).as_posix()


def test_only_the_storage_plug_imports_sqlite3() -> None:
    importers = [
        relative(path)
        for path in sorted(PACKAGE_DIR.rglob("*.py"))
        if any(module.partition(".")[0] == "sqlite3" for module in imported(path))
    ]

    assert importers, "the storage plug is expected to use sqlite3"
    assert all(name.startswith("storage/") for name in importers), importers


def test_the_storage_plug_imports_only_the_core_the_ports_the_settings_and_itself() -> None:
    files = sorted((PACKAGE_DIR / "storage").rglob("*.py"))
    assert files, "storage is expected to exist"
    for path in files:
        for module in imported(path):
            top, _, rest = module.partition(".")
            if top == "ledger_hand":
                assert rest.split(".")[0] in STORAGE_MAY_IMPORT, (relative(path), module)
            else:
                assert top in sys.stdlib_module_names, (relative(path), module)


def test_the_ports_file_names_the_storage_shapes_from_the_core_only() -> None:
    for module in imported(PACKAGE_DIR / "ports.py"):
        top, _, rest = module.partition(".")
        if top == "ledger_hand":
            assert rest.startswith("core."), module
        else:
            assert module in {"__future__", "enum", "collections.abc", "dataclasses", "typing"}
