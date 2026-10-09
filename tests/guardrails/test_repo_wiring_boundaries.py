"""Gate: the wiring module's boundaries in the real package, checked a second way.

The layering check already enforces these through its table. Here they are
checked again straight from the source, without the table, so that a change
to the table alone cannot quietly open them: inside the package only
``wiring.py`` imports tzlocal, and only the interface imports the wiring
module; the flows never do.
"""

from __future__ import annotations

import ast
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parents[2] / "src" / "ledger_hand"
WIRING = "ledger_hand.wiring"


def imported(path: Path) -> set[str]:
    """Every module ``path`` imports, with ``from package import name`` as ``package.name``."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, f"{path.name}: relative imports are not expected here"
            module = node.module or ""
            found.add(module)
            found.update(f"{module}.{alias.name}" for alias in node.names)
    return found


def relative(path: Path) -> str:
    return path.relative_to(PACKAGE_DIR).as_posix()


def package_files() -> list[Path]:
    return sorted(PACKAGE_DIR.rglob("*.py"))


def test_only_the_wiring_module_imports_tzlocal() -> None:
    importers = [
        relative(path)
        for path in package_files()
        if any(module.partition(".")[0] == "tzlocal" for module in imported(path))
    ]

    assert importers == ["wiring.py"]


def test_only_the_interface_imports_the_wiring_module() -> None:
    importers = [
        relative(path)
        for path in package_files()
        if any(module == WIRING or module.startswith(WIRING + ".") for module in imported(path))
    ]

    assert all(name.startswith("ui/") for name in importers), importers


def test_the_flows_import_neither_the_wiring_module_nor_the_interface() -> None:
    files = sorted((PACKAGE_DIR / "flows").rglob("*.py"))
    assert files, "flows is expected to exist"
    for path in files:
        for module in imported(path):
            assert not module.startswith((WIRING, "ledger_hand.ui")), (relative(path), module)
