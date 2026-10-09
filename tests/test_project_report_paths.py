"""Every path the project report names is a file or folder of the repository.

``docs/project-report.md`` points its reader at files, in code spans
(`` `src/...` ``) and in links (``[...](../src/...)``). This test finds each
one and checks that Git tracks it, or that it is a folder holding a file Git
tracks, so the report cannot name a file that was renamed, moved or never
there.

A code span is taken for a path when it starts with the name of a top-level
folder of the repository or ends with the extension of a common kind of
file, and holds neither ``://`` nor whitespace. So an address
(``http://127.0.0.1:11434``), a time zone (``Europe/Budapest``), a date
written as ``10/2``, an endpoint (``/chat/completions``), a model's name or a
number is not taken for one. A link is checked when its target is neither an
address nor an anchor; it is read from the report's own folder.

The few spans taken for paths that are not in Git on purpose are listed in
``NOT_IN_GIT``, each with its reason; each must still be in the report, so
that the list cannot outlive what it excuses.

Only the report is checked. The README names files relative to the package
(``core/stored.py``) and with placeholders, by its own convention.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from types import MappingProxyType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
REPORT = REPO_ROOT / "docs" / "project-report.md"

# The top-level folders of the repository that hold tracked files.
TOP_LEVEL_FOLDERS = ("src/", "tests/", "evals/", "docs/", "scripts/", ".streamlit/")
# The extensions of the kinds of file a path in the report may end in.
FILE_EXTENSIONS = (
    ".py",
    ".md",
    ".json",
    ".jsonl",
    ".toml",
    ".txt",
    ".sh",
    ".ts",
    ".sql",
    ".sqlite3",
    ".cfg",
    ".ini",
    ".yaml",
    ".yml",
    ".csv",
    ".html",
    ".lock",
)

NOT_IN_GIT: Mapping[str, str] = MappingProxyType(
    {
        "data/ledger-hand-book.sqlite3": (
            "the book in the default data folder: the ignore file keeps data/ out of Git, "
            "and the book is made the first time a passage is recorded with it"
        ),
    }
)

_FENCED_BLOCK = re.compile(r"^```.*?^```[^\n]*$", re.MULTILINE | re.DOTALL)
_CODE_SPAN = re.compile(r"`([^`]+)`")
_LINK = re.compile(r"\]\(([^)\s]+)\)")


def code_spans(text: str) -> list[str]:
    """The text of every code span outside fenced blocks, in order."""
    return _CODE_SPAN.findall(_FENCED_BLOCK.sub("", text))


def link_targets(text: str) -> list[str]:
    """The target of every Markdown link outside fenced blocks, in order."""
    return _LINK.findall(_FENCED_BLOCK.sub("", text))


def is_path(span: str) -> bool:
    """Whether a code span is taken for a path of the repository."""
    if "://" in span or any(character.isspace() for character in span):
        return False
    return span.startswith(TOP_LEVEL_FOLDERS) or span.endswith(FILE_EXTENSIONS)


def is_checked_link(target: str) -> bool:
    """Whether a link's target names something in the repository."""
    return "://" not in target and not target.startswith(("#", "mailto:"))


def tracked_files(repo_root: Path) -> frozenset[str]:
    """The paths, relative to ``repo_root`` and with forward slashes, that Git tracks."""
    done = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "-z"], capture_output=True, check=True
    )
    return frozenset(name for name in done.stdout.decode("utf-8").split("\0") if name)


def is_in_repository(relative: str, tracked: frozenset[str]) -> bool:
    """Whether ``relative`` is a tracked file, or a folder holding one."""
    path = PurePosixPath(relative).as_posix()
    if path in tracked:
        return True
    folder = path.rstrip("/") + "/"
    return any(name.startswith(folder) for name in tracked)


def link_path(target: str) -> str | None:
    """A link's target as a path relative to the repository, or ``None`` outside it."""
    resolved = (REPORT.parent / target.split("#", 1)[0]).resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return None


def missing_paths(text: str, tracked: frozenset[str]) -> list[str]:
    """Every path the text names in a code span or a link that is not in the repository."""
    missing = [
        span
        for span in code_spans(text)
        if is_path(span) and span not in NOT_IN_GIT and not is_in_repository(span, tracked)
    ]
    for target in link_targets(text):
        if not is_checked_link(target):
            continue
        path = link_path(target)
        if path is None or not is_in_repository(path, tracked):
            missing.append(target)
    return missing


@pytest.fixture(scope="module")
def tracked() -> frozenset[str]:
    return tracked_files(REPO_ROOT)


@pytest.fixture(scope="module")
def report() -> str:
    return REPORT.read_text(encoding="utf-8")


def test_every_path_the_report_names_is_in_the_repository(
    report: str, tracked: frozenset[str]
) -> None:
    missing = missing_paths(report, tracked)

    assert missing == [], f"the report names what the repository does not hold: {missing}"


def test_the_report_names_paths_at_all(report: str) -> None:
    assert sum(is_path(span) for span in code_spans(report)) >= 50
    assert sum(is_checked_link(target) for target in link_targets(report)) >= 20


def test_every_path_excused_is_in_the_report_and_not_in_git(
    report: str, tracked: frozenset[str]
) -> None:
    spans = code_spans(report)
    for path, reason in NOT_IN_GIT.items():
        assert path in spans, f"{path} is excused but the report no longer names it"
        assert is_path(path)
        assert not is_in_repository(path, tracked)
        assert reason.strip()


def test_no_code_span_is_broken_over_two_lines(report: str) -> None:
    # A span broken over two lines holds whitespace, so a path in it would
    # never be checked.
    assert [span for span in code_spans(report) if "\n" in span] == []


@pytest.mark.parametrize(
    "span",
    [
        "src/ledger_hand/ui/app.py",
        "tests/ui/",
        "evals/RESULTS.md",
        "docs/known-gaps.md",
        "scripts/check.sh",
        ".streamlit/config.toml",
        "pyproject.toml",
        "first.py",
        "data/ledger-hand-book.sqlite3",
    ],
)
def test_these_are_taken_for_paths(span: str) -> None:
    assert is_path(span)


@pytest.mark.parametrize(
    "span",
    [
        "http://127.0.0.1:11434",
        "https://api.example.com/v1",
        "Europe/Budapest",
        "10/2",
        "/chat/completions",
        "qwen2.5:7b",
        "0.02 94900",
        "64.80",
        "1.2k",
        "--final-exam",
        "ABOUT",
        "LEDGER_HAND_MODEL_TEMPERATURE",
        '{"trades": [...]}',
        "data/",
    ],
)
def test_these_are_not_taken_for_paths(span: str) -> None:
    assert not is_path(span)


def test_a_path_that_is_not_there_is_reported(tracked: frozenset[str]) -> None:
    text = (
        "The entry is `src/ledger_hand/ui/app.py`, the old one `src/ledger_hand/ui/main.py`; "
        "see [the record](../evals/RESULTS.md) and [the old notes](../docs/notes.md), "
        "`first.py`, `tests/nowhere/` and `http://127.0.0.1:8501`."
    )

    assert missing_paths(text, tracked) == [
        "src/ledger_hand/ui/main.py",
        "first.py",
        "tests/nowhere/",
        "../docs/notes.md",
    ]


def test_a_link_out_of_the_repository_is_reported(tracked: frozenset[str]) -> None:
    assert missing_paths("[up](../../somewhere/else.md)", tracked) == ["../../somewhere/else.md"]


def test_addresses_and_anchors_are_not_links_to_check(tracked: frozenset[str]) -> None:
    text = "[site](https://example.com/a.md), [above](#2-how-it-works), [mail](mailto:a@b.c)"

    assert missing_paths(text, tracked) == []


def test_spans_in_a_fenced_block_are_left_alone() -> None:
    text = "before\n```text\n`src/nowhere.py`\n```\nafter `src/ledger_hand/ports.py`\n"

    assert code_spans(text) == ["src/ledger_hand/ports.py"]
