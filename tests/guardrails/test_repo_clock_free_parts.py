"""Gate: ``asking/`` and ``flows/`` in the real package read no clock and no machine zone.

The current moment and the zone are handed in to every step of recording a
passage. The layering check already holds both parts to that; this gate is a
second guard that checks their source straight, without the layering table:
neither imports the ``time`` module, calls a method that reads the clock or
the machine's zone (``astimezone`` only with a zone other than ``None``),
hands over ``now``, ``utcnow`` or ``today`` of ``datetime`` or ``date``
without calling it, names the zone "localtime", or names an environment
variable. ``asking/`` also imports only the standard library, the core and
the ports file. The judging of the time module and of the clock and the zone
is one function, ``clock_problems``, which the gate's own tests feed directly.
"""

from __future__ import annotations

import ast
import enum
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

PACKAGE_DIR = Path(__file__).resolve().parents[2] / "src" / "ledger_hand"
PARTS = ("asking", "flows")
CLOCK_CALLS = {"now", "utcnow", "today", "timestamp", "fromtimestamp", "from_file"}
# Mentioned without being called, these still hand the clock to whoever calls
# them later. The owners are the same as in the layering check.
CLOCK_METHODS = {"now", "utcnow", "today"}
CLOCK_OWNERS = {"datetime", "date"}
ENVIRONMENT_NAMES = {"environ", "environb", "getenv", "getenvb", "putenv", "unsetenv"}
ASKING_MAY_IMPORT = {"core", "ports", "asking"}


class Rule(enum.Enum):
    """Which of the gate's two rules a problem breaks."""

    TIME_MODULE = "imports the time module"
    CLOCK_OR_ZONE = "reads the clock or the machine's zone"


@dataclass(frozen=True)
class Problem:
    """One thing the gate found in a piece of source."""

    line: int
    rule: Rule
    detail: str


def clock_problems(source: str) -> list[Problem]:
    """Every import of the time module and every read of the clock or the
    machine's zone in ``source``; an empty list when there is none."""
    tree = ast.parse(source)
    called = {id(node.func) for node in ast.walk(tree) if isinstance(node, ast.Call)}
    problems: list[Problem] = []
    for node in ast.walk(tree):
        for rule, detail in (
            (Rule.TIME_MODULE, _time_module_import(node)),
            (Rule.CLOCK_OR_ZONE, _clock_or_zone_read(node, called)),
        ):
            if detail is not None:
                problems.append(Problem(getattr(node, "lineno", 1), rule, detail))
    return problems


def _time_module_import(node: ast.AST) -> str | None:
    if isinstance(node, ast.Import):
        modules = [alias.name for alias in node.names]
    elif isinstance(node, ast.ImportFrom):
        if node.level:
            # What a relative import reaches cannot be told from its text.
            return "relative imports are not expected here"
        modules = [node.module or ""]
    else:
        return None
    if any(module.partition(".")[0] == "time" for module in modules):
        return "imports the time module"
    return None


def _clock_or_zone_read(node: ast.AST, called: set[int]) -> str | None:
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        name = node.func.attr
        if name in CLOCK_CALLS:
            return f"calls .{name}()"
        if name == "astimezone" and _zone_given(node) is None:
            return "astimezone() without a zone uses the machine's zone"
    if (
        isinstance(node, ast.Attribute)
        and node.attr in CLOCK_METHODS
        and id(node) not in called
        and _last_name(node.value) in CLOCK_OWNERS
    ):
        return f"hands over .{node.attr} of {_last_name(node.value)} without calling it"
    if isinstance(node, ast.Constant) and node.value == "localtime":
        return 'names the zone "localtime"'
    return None


def _zone_given(call: ast.Call) -> ast.expr | None:
    """The zone handed to ``astimezone``, or ``None`` when it is missing or ``None``."""
    zone: ast.expr | None = call.args[0] if call.args else None
    for keyword in call.keywords:
        if keyword.arg == "tz":
            zone = keyword.value
    if isinstance(zone, ast.Constant) and zone.value is None:
        return None
    return zone


def _last_name(node: ast.expr) -> str | None:
    """The final name in ``a.b.c`` or ``c``; ``None`` for anything else."""
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return None


def problems_in(path: Path, rule: Rule) -> list[Problem]:
    return [
        problem
        for problem in clock_problems(path.read_text(encoding="utf-8"))
        if problem.rule is rule
    ]


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
        assert problems_in(path, Rule.TIME_MODULE) == [], path.name


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
        assert problems_in(path, Rule.CLOCK_OR_ZONE) == [], path.name


@pytest.mark.parametrize("part", PARTS)
def test_the_part_names_no_environment_variable(part: str) -> None:
    for path in files_of(part):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Attribute):
                assert node.attr not in ENVIRONMENT_NAMES, (path.name, node.lineno)
            if isinstance(node, ast.Name):
                assert node.id not in ENVIRONMENT_NAMES, (path.name, node.lineno)
