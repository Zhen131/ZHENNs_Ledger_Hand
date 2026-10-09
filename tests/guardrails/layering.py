"""Layering check: who may import whom inside the package.

Given the directory of a package, reads every Python file in it and reports
each import the layering table below does not allow. For ``core/`` it also
reports reads of the clock or of the machine's time zone, and builtins that
reach outside the program.
In ``core/`` it reports floating-point numbers as well.
For ``extraction/`` and ``asking/`` it reports reads of the clock and of the
machine's time zone too, including those through the ``time`` module, which
they may import for other uses.
Everywhere but ``settings.py`` it reports reads of environment variables.

It only reads source text; it never imports or runs the package under check,
and it judges nothing outside the directory it is given. Parts of the package
that do not exist yet are simply not visited.
"""

from __future__ import annotations

import ast
import enum
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path


class Area(enum.Enum):
    """A part of the package; the value is its directory or module name."""

    ROOT = "__init__"
    CORE = "core"
    PORTS = "ports"
    EXTRACTION = "extraction"
    ASKING = "asking"
    EXPORT = "export"
    LLM = "llm"
    STORAGE = "storage"
    SETTINGS = "settings"
    FLOWS = "flows"
    WIRING = "wiring"
    UI = "ui"


class Reason(enum.Enum):
    """Why a line was reported."""

    UNPARSEABLE_FILE = "file cannot be parsed"
    UNKNOWN_AREA = "not in the layering table"
    INTERNAL_IMPORT = "imports a part of the package it may not use"
    STDLIB_IMPORT = "imports a standard-library module outside its allow-list"
    RESERVED_MODULE = "imports a module reserved for another part"
    THIRD_PARTY_IMPORT = "imports a third-party module nobody was granted"
    REPO_SIDE_IMPORT = "imports repository-side code"
    DYNAMIC_IMPORT = "imports by name at run time"
    CLOCK_READ = "reads the current time or date"
    LOCAL_ZONE_READ = "reads the machine's time zone"
    OUTSIDE_WORLD_BUILTIN = "calls a builtin that reaches outside the program"
    FLOAT_USE = "uses a floating-point number"
    ENVIRONMENT_READ = "touches environment variables outside the settings module"


@dataclass(frozen=True)
class Violation:
    """One reported line; ``path`` starts at the package directory."""

    path: Path
    line: int
    reason: Reason
    detail: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.reason.value}: {self.detail}"


@dataclass(frozen=True)
class AreaRule:
    """What one area may import, besides itself."""

    areas: frozenset[Area]
    stdlib: frozenset[str]


ANY_STDLIB = frozenset(sys.stdlib_module_names)

# Modules that only compute and never touch the outside world. Files, network,
# databases, processes, randomness and the clock never belong here.
CORE_STDLIB = frozenset(
    {
        "__future__",
        "abc",
        "collections",
        "dataclasses",
        "datetime",
        "decimal",
        "enum",
        "fractions",
        "functools",
        "itertools",
        "math",
        "numbers",
        "operator",
        "re",
        "string",
        "typing",
        "unicodedata",
        "zoneinfo",
    }
)

# The ports file only declares shapes: annotations and plain data types.
PORTS_STDLIB = frozenset({"__future__", "abc", "collections", "dataclasses", "enum", "typing"})

_EVERY_AREA = frozenset(Area)
_CORE_AND_PORTS = frozenset({Area.CORE, Area.PORTS})
_PLUG_IMPORTS = frozenset({Area.CORE, Area.PORTS, Area.SETTINGS})
# Written out one by one, so that a new area is not open to the flows until
# it is added here. The wiring module reads the clock and the machine's zone
# and imports the flows; the flows never import it back.
_FLOWS_IMPORTS = frozenset(
    {
        Area.ROOT,
        Area.CORE,
        Area.PORTS,
        Area.EXTRACTION,
        Area.ASKING,
        Area.EXPORT,
        Area.LLM,
        Area.STORAGE,
        Area.SETTINGS,
    }
)

LAYERING_TABLE: dict[Area, AreaRule] = {
    Area.CORE: AreaRule(areas=frozenset(), stdlib=CORE_STDLIB),
    Area.PORTS: AreaRule(areas=frozenset({Area.CORE}), stdlib=PORTS_STDLIB),
    Area.EXTRACTION: AreaRule(areas=_CORE_AND_PORTS, stdlib=ANY_STDLIB),
    Area.ASKING: AreaRule(areas=_CORE_AND_PORTS, stdlib=ANY_STDLIB),
    Area.EXPORT: AreaRule(areas=_CORE_AND_PORTS, stdlib=ANY_STDLIB),
    Area.LLM: AreaRule(areas=_PLUG_IMPORTS, stdlib=ANY_STDLIB),
    Area.STORAGE: AreaRule(areas=_PLUG_IMPORTS, stdlib=ANY_STDLIB),
    Area.SETTINGS: AreaRule(areas=frozenset(), stdlib=ANY_STDLIB),
    Area.FLOWS: AreaRule(areas=_FLOWS_IMPORTS, stdlib=ANY_STDLIB),
    Area.WIRING: AreaRule(areas=_EVERY_AREA - {Area.UI}, stdlib=ANY_STDLIB),
    Area.UI: AreaRule(areas=_EVERY_AREA, stdlib=ANY_STDLIB),
    Area.ROOT: AreaRule(areas=frozenset(), stdlib=ANY_STDLIB),
}

# Modules only the named areas may import, whatever their other rules say.
# An empty set means no part of the package may import the module.
RESERVED_MODULES: dict[str, frozenset[Area]] = {
    "streamlit": frozenset({Area.UI}),
    "httpx": frozenset({Area.LLM}),
    "sqlite3": frozenset({Area.STORAGE}),
    "tzlocal": frozenset({Area.WIRING}),
}

# Top-level directories that may import the package but never the reverse.
REPO_SIDE_DIRECTORIES = frozenset({"scripts", "evals", "tests"})

_AREA_BY_NAME = {area.value: area for area in Area}
_CLOCK_METHODS = frozenset({"now", "utcnow", "today"})
_CLOCK_OWNERS = frozenset({"datetime", "date"})
_OUTSIDE_WORLD_BUILTINS = frozenset(
    {"open", "input", "print", "breakpoint", "eval", "exec", "compile"}
)
_DYNAMIC_IMPORTERS = frozenset({"__import__", "import_module"})
# The two ways of building a zone from its name: the cached constructor and the uncached one.
_ZONE_CONSTRUCTORS = frozenset({"ZoneInfo", "no_cache"})
_FLOAT_MAKERS = frozenset({"float", "complex", "__float__", "__complex__", "from_float"})
# Settings are read in one place: only that area may touch the environment.
ENVIRONMENT_AREAS = frozenset({Area.SETTINGS})
# Areas that are handed the current moment and the zone and never read them
# from the machine.
CLOCK_FREE_AREAS = frozenset({Area.CORE, Area.EXTRACTION, Area.ASKING})
# The clock-free areas that may import the time module for other uses, and
# so are checked for its reads of the clock and the zone. The core may not
# import the module at all, which is reported as such.
TIME_MODULE_AREAS = CLOCK_FREE_AREAS - {Area.CORE}
# What the time module offers that reads the clock, and what reads the
# machine's time zone.
_TIME_MODULE_CLOCK = frozenset(
    {
        "time",
        "time_ns",
        "monotonic",
        "monotonic_ns",
        "perf_counter",
        "perf_counter_ns",
        "process_time",
        "process_time_ns",
        "thread_time",
        "thread_time_ns",
        "clock_gettime",
        "clock_gettime_ns",
        "gmtime",
        "asctime",
    }
)
_TIME_MODULE_ZONE = frozenset(
    {"localtime", "ctime", "mktime", "strftime", "tzname", "timezone", "altzone", "daylight"}
)
# How Python code reaches environment variables: the mapping, its bytes twin,
# and the functions that read, set or remove one variable.
_ENVIRONMENT_NAMES = frozenset({"environ", "environb", "getenv", "getenvb", "putenv", "unsetenv"})
# The modules that offer them: ``os`` and the platform modules behind it.
_ENVIRONMENT_MODULES = frozenset({"os", "posix", "nt"})

_Found = tuple[int, Reason, str]


@dataclass(frozen=True)
class _SourceFile:
    package_dir: Path
    relative: Path
    area: Area

    @property
    def package_name(self) -> str:
        return self.package_dir.name

    @property
    def shown(self) -> Path:
        return Path(self.package_name) / self.relative

    @property
    def context(self) -> tuple[str, ...]:
        """The package that this file's relative imports are resolved against."""
        return (self.package_name, *self.relative.parts[:-1])


def check_package(package_dir: Path) -> list[Violation]:
    """Return every layering violation found under ``package_dir``."""
    if not (package_dir / "__init__.py").is_file():
        raise ValueError(f"not a package directory: {package_dir}")
    violations: list[Violation] = []
    for path in package_dir.rglob("*.py"):
        violations.extend(_check_file(package_dir, path.relative_to(package_dir)))
    return sorted(violations, key=lambda found: (found.path, found.line, found.reason.name))


def _check_file(package_dir: Path, relative: Path) -> list[Violation]:
    shown = Path(package_dir.name) / relative
    area_name = relative.stem if len(relative.parts) == 1 else relative.parts[0]
    area = _AREA_BY_NAME.get(area_name)
    if area is None:
        detail = f"add a row for {area_name!r} before putting code there"
        return [Violation(shown, 1, Reason.UNKNOWN_AREA, detail)]
    try:
        tree = ast.parse((package_dir / relative).read_text(encoding="utf-8"))
    except (SyntaxError, ValueError) as error:
        return [Violation(shown, 1, Reason.UNPARSEABLE_FILE, str(error))]
    file = _SourceFile(package_dir, relative, area)
    found = [*_import_findings(file, tree), *_dynamic_import_findings(tree)]
    if area not in ENVIRONMENT_AREAS:
        found.extend(_environment_findings(tree))
    if area in CLOCK_FREE_AREAS:
        found.extend(_clock_findings(tree))
        found.extend(_local_zone_findings(tree))
    if area in TIME_MODULE_AREAS:
        found.extend(_time_module_findings(tree))
    if area is Area.CORE:
        found.extend(_outside_world_findings(tree))
        found.extend(_float_findings(tree))
    return [Violation(shown, line, reason, detail) for line, reason, detail in found]


def _import_findings(file: _SourceFile, tree: ast.AST) -> Iterator[_Found]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            targets = [tuple(alias.name.split(".")) for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            targets = _from_import_targets(file, node)
        else:
            continue
        for target in targets:
            problem = _judge_import(file, target)
            if problem is not None:
                yield (node.lineno, *problem)


def _from_import_targets(file: _SourceFile, node: ast.ImportFrom) -> list[tuple[str, ...]]:
    """Resolve ``from X import a, b`` to absolute dotted paths.

    An empty tuple stands for a relative import that climbs out of the package.
    """
    module = tuple(node.module.split(".")) if node.module else ()
    if node.level:
        climbed = node.level - 1
        if climbed >= len(file.context):
            return [()]
        module = (*file.context[: len(file.context) - climbed], *module)
    if module != (file.package_name,):
        return [module]
    # ``from package import name``: the name is either a part of the package
    # or something defined in the package's own ``__init__``.
    return [
        (*module, alias.name) if _is_part_of_package(file, alias.name) else module
        for alias in node.names
    ]


def _is_part_of_package(file: _SourceFile, name: str) -> bool:
    if name in _AREA_BY_NAME:
        return True
    return (file.package_dir / name).is_dir() or (file.package_dir / f"{name}.py").is_file()


def _judge_import(file: _SourceFile, target: tuple[str, ...]) -> tuple[Reason, str] | None:
    if not target:
        return Reason.INTERNAL_IMPORT, "relative import climbs out of the package"
    if target[0] == file.package_name:
        return _judge_internal_import(file, target)
    return _judge_external_import(file, target[0])


def _judge_internal_import(file: _SourceFile, target: tuple[str, ...]) -> tuple[Reason, str] | None:
    dotted = ".".join(target)
    target_name = target[1] if len(target) > 1 else Area.ROOT.value
    target_area = _AREA_BY_NAME.get(target_name)
    if target_area is None:
        return Reason.INTERNAL_IMPORT, f"{dotted}: {target_name!r} is not in the layering table"
    if target_area is file.area or target_area in LAYERING_TABLE[file.area].areas:
        return None
    return Reason.INTERNAL_IMPORT, f"{file.area.value} may not import {dotted}"


def _judge_external_import(file: _SourceFile, top: str) -> tuple[Reason, str] | None:
    here = file.area.value
    if top in REPO_SIDE_DIRECTORIES:
        return Reason.REPO_SIDE_IMPORT, f"the package may not import {top}"
    if top in RESERVED_MODULES:
        if file.area in RESERVED_MODULES[top]:
            return None
        owners = sorted(area.value for area in RESERVED_MODULES[top])
        where = ", ".join(owners) if owners else "code outside the package"
        return Reason.RESERVED_MODULE, f"{top} is reserved for {where}; found in {here}"
    if top in ANY_STDLIB:
        if top in LAYERING_TABLE[file.area].stdlib:
            return None
        return Reason.STDLIB_IMPORT, f"{here} may not import {top}"
    return Reason.THIRD_PARTY_IMPORT, f"{top} has not been granted to {here}"


def _dynamic_import_findings(tree: ast.AST) -> Iterator[_Found]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _called_name(node) in _DYNAMIC_IMPORTERS:
            yield node.lineno, Reason.DYNAMIC_IMPORT, f"{_called_name(node)}() hides an import"


def _environment_findings(tree: ast.AST) -> Iterator[_Found]:
    """``os.environ``, ``os.getenv()`` and the like in any spelling: as an
    attribute of anything, imported by name, or fetched with ``getattr``."""
    for node in ast.walk(tree):
        name = _environment_name(node)
        if name is not None:
            detail = f"{name} reads the environment; read settings through the settings module"
            yield getattr(node, "lineno", 1), Reason.ENVIRONMENT_READ, detail


def _environment_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Attribute) and node.attr in _ENVIRONMENT_NAMES:
        return node.attr
    if isinstance(node, ast.ImportFrom) and (node.module or "") in _ENVIRONMENT_MODULES:
        for alias in node.names:
            if alias.name in _ENVIRONMENT_NAMES or alias.name == "*":
                return f"from {node.module} import {alias.name}"
    if isinstance(node, ast.Call) and _called_name(node) == "getattr" and len(node.args) >= 2:
        named = node.args[1]
        if isinstance(named, ast.Constant) and named.value in _ENVIRONMENT_NAMES:
            return f"getattr(..., {named.value!r})"
    return None


def _clock_findings(tree: ast.AST) -> Iterator[_Found]:
    """Calls to ``.now()``, ``.utcnow()``, ``.today()`` on anything, and any
    mention of those methods on the datetime classes even when not called."""
    called = {id(node.func) for node in ast.walk(tree) if isinstance(node, ast.Call)}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute) or node.attr not in _CLOCK_METHODS:
            continue
        if id(node) in called or _last_name(node.value) in _CLOCK_OWNERS:
            detail = f".{node.attr} asks the machine; take the moment as an argument instead"
            yield node.lineno, Reason.CLOCK_READ, detail


def _local_zone_findings(tree: ast.AST) -> Iterator[_Found]:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        detail = _local_zone_detail(node)
        if detail is not None:
            yield node.lineno, Reason.LOCAL_ZONE_READ, detail


def _local_zone_detail(call: ast.Call) -> str | None:
    """Why ``call`` reaches the machine's time zone; ``None`` when it does not."""
    name = _called_name(call)
    if name == "astimezone" and _zone_argument(call, position=0) is None:
        return "astimezone() without a zone uses the machine's zone"
    if name == "fromtimestamp" and _zone_argument(call, position=1) is None:
        return "fromtimestamp() without a zone uses the machine's zone"
    if name in _ZONE_CONSTRUCTORS and _zone_key_is(call, "localtime"):
        return f'{name}("localtime") is the machine\'s zone'
    if name == "from_file":
        return "from_file() loads a zone from a file, which is how the machine's zone is read"
    if name == "timestamp":
        return "timestamp() takes a time without a zone to be in the machine's zone"
    return None


def _time_module_findings(tree: ast.AST) -> Iterator[_Found]:
    """What reads the clock or the machine's zone through the ``time`` module.

    Its functions used by name after ``from time import ...``, or as an
    attribute of the module under any name it was imported as.
    """
    module_names = {
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
        if alias.name == "time"
    }
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.ImportFrom) and node.module == "time" and node.level == 0:
            names = [alias.name for alias in node.names]
        elif (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id in module_names
        ):
            names = [node.attr]
        for name in names:
            finding = _time_module_finding(name)
            if finding is not None:
                yield node.lineno, *finding


def _time_module_finding(name: str) -> tuple[Reason, str] | None:
    if name in _TIME_MODULE_CLOCK or name == "*":
        return Reason.CLOCK_READ, f"time.{name} asks the machine; take the moment as an argument"
    if name in _TIME_MODULE_ZONE:
        return (
            Reason.LOCAL_ZONE_READ,
            f"time.{name} reads the machine's zone; take it as an argument",
        )
    return None


def _outside_world_findings(tree: ast.AST) -> Iterator[_Found]:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        if node.func.id in _OUTSIDE_WORLD_BUILTINS:
            yield node.lineno, Reason.OUTSIDE_WORLD_BUILTIN, f"{node.func.id}() is not pure"


def _float_findings(tree: ast.AST) -> Iterator[_Found]:
    """Floating-point constants, and calls that turn something into such a number.

    Amounts are exact decimals built from text. What this cannot see has to be
    caught by reading the code: a division of two whole numbers with ``/``,
    for one, gives a floating-point number without any of these signs.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, float | complex):
            detail = f"{node.value!r} is not exact; build a decimal from text instead"
        elif isinstance(node, ast.Call) and _makes_a_float(node):
            detail = f"{_called_name(node)}() gives a number that is not exact"
        else:
            continue
        yield node.lineno, Reason.FLOAT_USE, detail


def _makes_a_float(call: ast.Call) -> bool:
    name = _called_name(call)
    if name in _FLOAT_MAKERS:
        return True
    return (
        name == "fromhex"
        and isinstance(call.func, ast.Attribute)
        and _last_name(call.func.value) == "float"
    )


def _called_name(call: ast.Call) -> str | None:
    return _last_name(call.func)


def _last_name(node: ast.expr) -> str | None:
    """The final name in ``a.b.c`` or ``c``; ``None`` for anything else."""
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return None


def _zone_argument(call: ast.Call, *, position: int) -> ast.expr | None:
    """The time-zone argument of a call, or ``None`` when it is missing or ``None``."""
    zone: ast.expr | None = None
    if len(call.args) > position:
        zone = call.args[position]
    for keyword in call.keywords:
        if keyword.arg == "tz":
            zone = keyword.value
    if isinstance(zone, ast.Constant) and zone.value is None:
        return None
    return zone


def _zone_key_is(call: ast.Call, text: str) -> bool:
    """Whether the zone's name, given first or by the keyword ``key``, is ``text``."""
    given = [*call.args[:1], *(keyword.value for keyword in call.keywords if keyword.arg == "key")]
    return any(isinstance(key, ast.Constant) and key.value == text for key in given)
