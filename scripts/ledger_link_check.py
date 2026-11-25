"""The ledger tier, second step: the real assistant link lists the tools this program expects.

    .venv/bin/python scripts/ledger_link_check.py [--ledger PATH]

It starts the ledger's own assistant link (``assistant-link/main.ts``) with
the program's link client, on a free port of 127.0.0.1, asks it for its
tools, and compares them with the table this program was built against
(``ledger_hand.ledger.link_tools``): each of the eight tools this program
uses is there; every field the ledger requires of one, this program sends;
every field this program sends, the tool takes (at the top and inside the
one trade). A tool the ledger has and this program does not use is no
failure; it is listed ("the ledger has, this program does not use: ...").
Nor is a field the ledger no longer requires that this program still
sends; it is listed too. No ledger page is needed and none is connected;
nothing is proposed or read from any ledger. It also reads the error table
of the ledger's ``assistant-link/README.md`` and checks that every code is on
one of the real ledger plug's two tables
(``ledger_hand.ledger.link_ledger.codes_on_no_table``). When the ledger's
tools or codes change, this step fails and says where.

Where the ledger is comes from ``--ledger PATH`` or else from the environment
variable ``LEDGER_HAND_LEDGER_DIR``, as for the first step of the tier. The
checkout is only read: the link is started inside it with its own ``tsx``,
with the cache off, and Git is asked before and after, in the way that
writes nothing, whether the checkout is clean.

Exit status: 0 the tools are as expected; 1 they are not, the checkout was
not clean, or the link could not be started; 3 skipped, because no ledger
checkout was named, the one named is missing or has no link, or Node.js or
Git is not on the PATH. The reason is always printed.
"""

from __future__ import annotations

import argparse
import enum
import os
import shutil
import socket
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path

from ledger_hand.ledger.link_client import LedgerLink
from ledger_hand.ledger.link_failures import LedgerLinkError
from ledger_hand.ledger.link_ledger import codes_on_no_table
from ledger_hand.ledger.link_tools import (
    EXPECTED_TOOLS,
    differences,
    no_longer_required,
    required_fields,
    unused,
)
from ledger_hand.settings import LEDGER_DIRECTORY_VARIABLE, load_ledger_link_settings
from ledger_hand.wiring import ledger_link

LINK_ENTRY = Path("assistant-link/main.ts")
LINK_TSX = Path("node_modules/tsx")


class Outcome(enum.Enum):
    """How the step ended; the value is the exit status."""

    PASSED = 0
    FAILED = 1
    SKIPPED = 3


def locate_ledger(argument: str | None, environ: Mapping[str, str]) -> Path | str:
    """The ledger checkout to use, or the reason the step is skipped."""
    named = argument or environ.get(LEDGER_DIRECTORY_VARIABLE, "")
    if not named.strip():
        return f"no ledger checkout named: pass --ledger PATH or set {LEDGER_DIRECTORY_VARIABLE}"
    ledger = Path(named.strip()).expanduser().resolve()
    if not ledger.is_dir():
        return f"there is no directory at {ledger}"
    if not (ledger / LINK_ENTRY).is_file():
        return f"{ledger} has no {LINK_ENTRY}, so it has no assistant link this step knows"
    if not (ledger / LINK_TSX).is_dir():
        return f"{ledger} has no {LINK_TSX}; the ledger's packages are not installed there"
    for tool in ("node", "git"):
        if shutil.which(tool) is None:
            return f"{tool} is not on the PATH"
    return ledger


def free_port() -> int:
    """A port of 127.0.0.1 that nothing listens on now."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def clean(ledger: Path, when: str) -> bool:
    """Whether Git sees no change in the checkout, asked in the way that writes nothing."""
    command = ["git", "--no-optional-locks", "-C", str(ledger), "status", "--porcelain"]
    done = subprocess.run(command, capture_output=True, text=True, check=False)
    if done.returncode == 0 and done.stdout == "":
        print(f"ledger checkout {when} the check: clean (git status --porcelain printed nothing)")
        return True
    print(f"ledger checkout {when} the check: NOT CLEAN\n{done.stdout}{done.stderr}")
    return False


def link_for(ledger: Path, environ: Mapping[str, str]) -> LedgerLink:
    """The link client for ``ledger`` on a free port, with the cache of ``tsx`` turned off."""
    read = load_ledger_link_settings({**environ, LEDGER_DIRECTORY_VARIABLE: str(ledger)})
    environment = {**read.environment, "TSX_DISABLE_CACHE": "1"}
    link = ledger_link(replace(read, link_port=free_port(), environment=environment))
    assert link is not None
    return link


def report(tools: Sequence[Mapping[str, object]]) -> list[str]:
    """Print each tool's required fields as the link lists them; the differences found."""
    for tool in tools:
        schema = tool.get("inputSchema")
        fields = required_fields(schema if isinstance(schema, dict) else {})
        shown = "; ".join(f"{where or 'top'}: {sorted(names)}" for where, names in fields.items())
        print(f"  {tool.get('name')}: {shown}")
    return differences(tools)


def check(ledger: Path, environ: Mapping[str, str]) -> Outcome:
    """Start the link in ``ledger``, compare its tools, and say whether all went as expected."""
    clean_before = clean(ledger, "before")
    try:
        with link_for(ledger, environ) as link:
            tools = link.tools()
    except LedgerLinkError as error:
        print(f"the assistant link could not be asked: {error}")
        return Outcome.FAILED
    print(f"the assistant link lists {len(tools)} tools (this program uses {len(EXPECTED_TOOLS)}):")
    found = report(tools)
    for difference in found:
        print(f"  DIFFERENT: {difference}")
    if not found:
        print("each tool this program uses is there; it sends every required field, all taken")
    extra = unused(tools)
    if extra:
        print(f"the ledger has, this program does not use: {', '.join(extra)}")
    for line in no_longer_required(tools):
        print(f"the ledger no longer requires, this program still sends: {line}")
    unsorted = codes_on_no_table(
        (ledger / "assistant-link" / "README.md").read_text(encoding="utf-8")
    )
    for code in unsorted:
        print(f"  NOT SORTED: the ledger's error code {code} is on neither of the plug's tables")
    if not unsorted:
        print("every error code of the ledger's README is on one of the plug's two tables")
    clean_after = clean(ledger, "after")
    passed = clean_before and clean_after and not found and not unsorted
    return Outcome.PASSED if passed else Outcome.FAILED


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare the ledger's link tools with ours.")
    parser.add_argument(
        "--ledger", help=f"the ledger checkout; default: ${LEDGER_DIRECTORY_VARIABLE}"
    )
    arguments = parser.parse_args(argv)
    located = locate_ledger(arguments.ledger, os.environ)
    if isinstance(located, str):
        print(f"skipped: {located}")
        return Outcome.SKIPPED.value
    return check(located, os.environ).value


if __name__ == "__main__":
    raise SystemExit(main())
