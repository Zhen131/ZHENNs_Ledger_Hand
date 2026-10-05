"""Gate: the model's boundaries in the real package, checked a second way.

The layering check already enforces these through its table. Here they are
checked again straight from the source, without the table, so that a change
to the table alone cannot quietly open them: only ``llm/`` imports httpx,
the ports file imports no third-party library, and only the settings module
reads environment variables.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parents[2] / "src" / "ledger_hand"
ENVIRONMENT_NAMES = {"environ", "environb", "getenv", "getenvb", "putenv", "unsetenv"}


def package_files() -> list[Path]:
    return sorted(PACKAGE_DIR.rglob("*.py"))


def top_level_imports(path: Path) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.add(node.module.split(".")[0])
    return found


def reads_the_environment(path: Path) -> bool:
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Attribute) and node.attr in ENVIRONMENT_NAMES:
            return True
        if (
            isinstance(node, ast.ImportFrom)
            and node.module == "os"
            and any(alias.name in ENVIRONMENT_NAMES | {"*"} for alias in node.names)
        ):
            return True
    return False


def relative(path: Path) -> str:
    return path.relative_to(PACKAGE_DIR).as_posix()


def test_only_the_model_plugs_import_httpx() -> None:
    importers = [relative(path) for path in package_files() if "httpx" in top_level_imports(path)]

    assert importers, "the model plug is expected to use httpx"
    assert all(name.startswith("llm/") for name in importers), importers


def test_the_ports_file_imports_only_the_standard_library_and_the_core() -> None:
    imports = top_level_imports(PACKAGE_DIR / "ports.py")

    assert imports <= set(sys.stdlib_module_names) | {"ledger_hand"}, imports


def test_only_the_settings_module_reads_the_environment() -> None:
    readers = [relative(path) for path in package_files() if reads_the_environment(path)]

    assert readers == ["settings.py"]
