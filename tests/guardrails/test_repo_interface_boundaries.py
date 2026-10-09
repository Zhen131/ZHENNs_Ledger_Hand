"""Gate: the interface's boundaries in the real package, checked a second way.

The layering check already enforces the imports through its table. Here
they are checked again straight from the source, without the table, so that
a change to the table alone cannot quietly open them: only ``ui/`` imports
Streamlit; ``ui/`` imports nothing third-party but Streamlit itself (not
what Streamlit brings along, such as pandas or numpy); and what lasts
between reruns, ``session_state``, is named nowhere but in ``ui/``.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parents[2] / "src" / "ledger_hand"


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


def package_files() -> list[Path]:
    return sorted(PACKAGE_DIR.rglob("*.py"))


def names_session_state(path: Path) -> bool:
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Attribute) and node.attr == "session_state":
            return True
        if isinstance(node, ast.Name) and node.id == "session_state":
            return True
        if isinstance(node, ast.alias) and node.name == "session_state":
            return True
    return False


def test_only_the_interface_imports_streamlit() -> None:
    importers = [
        relative(path)
        for path in package_files()
        if any(module.partition(".")[0] == "streamlit" for module in imported(path))
    ]

    assert importers, "the interface is expected to use Streamlit"
    assert all(name.startswith("ui/") for name in importers), importers


def test_the_interface_imports_nothing_third_party_but_streamlit() -> None:
    files = sorted((PACKAGE_DIR / "ui").rglob("*.py"))
    assert files, "ui is expected to exist"
    for path in files:
        for module in imported(path):
            top = module.partition(".")[0]
            allowed = top in sys.stdlib_module_names or top in {"ledger_hand", "streamlit"}
            assert allowed, (relative(path), module)


def test_what_lasts_between_reruns_is_named_only_in_the_interface() -> None:
    namers = [relative(path) for path in package_files() if names_session_state(path)]

    assert namers, "the interface is expected to keep its state"
    assert all(name.startswith("ui/") for name in namers), namers
