"""Tests of the link client against a stand-in for the ledger's assistant link.

The stand-in (``fake_link.py``) plays Node.js and the link by a script, so
every way of failing is reached without the ledger: Node.js missing or too
old, the ledger's folder wrong, the port taken, the handshake refused, no
answer in time, the link gone in the middle, an answer that is not JSON.
The last tests run every failing path with one fixed, invented token and
look for it in every place it must not be.
"""

from __future__ import annotations

import logging
import stat
import subprocess
import sys
import time
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from ledger_hand.ledger.link_client import (
    CLIENT_NAME,
    AnswerKind,
    LedgerLink,
    LinkSetup,
    PageState,
)
from ledger_hand.ledger.link_failures import LedgerLinkError, LinkFailure, LinkToken

FAKE_LINK = Path(__file__).resolve().parent / "fake_link.py"
# An invented token, the same in every test, so that it can be looked for.
TOKEN = "InventedTokenForTheLinkTests_0123456789"
PORT = 47999


@pytest.fixture
def ledger_folder(tmp_path: Path) -> Path:
    folder = tmp_path / "ledger"
    (folder / "assistant-link").mkdir(parents=True)
    (folder / "assistant-link" / "main.ts").write_text("// stand-in\n", encoding="utf-8")
    (folder / "node_modules" / "tsx").mkdir(parents=True)
    return folder


@pytest.fixture
def node(tmp_path: Path) -> str:
    """A stand-in for Node.js: a shell script that runs the fake link with this Python."""
    path = tmp_path / "node"
    path.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{FAKE_LINK}" "$@"\n', encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return str(path)


def setup(folder: Path, node: str, scenario: str = "normal", **extra: str) -> LinkSetup:
    return LinkSetup(
        ledger_directory=folder,
        token=LinkToken(TOKEN),
        hand_version="0.1.0",
        port=PORT,
        page_port=3068,
        environment={"FAKE_LINK_SCENARIO": scenario, **extra},
        node=node,
        start_seconds=5.0,
        answer_seconds=1.0,
    )


@pytest.fixture
def started(ledger_folder: Path, node: str) -> Iterator[LedgerLink]:
    link = LedgerLink(setup(ledger_folder, node))
    link.start()
    yield link
    link.close()


def failure_of(link: LedgerLink, act: str = "start") -> LedgerLinkError:
    with pytest.raises(LedgerLinkError) as raised:
        if act == "start":
            link.start()
        else:
            link.start()
            link.call("list_assets", {})
    link.close()
    return raised.value


# --- when everything works -------------------------------------------------------


def test_it_lists_the_tools_the_link_lists(started: LedgerLink) -> None:
    names = [tool["name"] for tool in started.tools()]

    assert names[0] == "list_assets"
    assert len(names) == 8


def test_a_result_comes_back_as_the_ledger_gave_it(started: LedgerLink) -> None:
    answer = started.call("list_assets", {})

    assert answer.kind is AnswerKind.RESULT
    assert answer.content == {"kind": "asset-list", "assets": []}


def test_the_ledgers_error_comes_back_as_it_came(started: LedgerLink) -> None:
    answer = started.call("get_positions", {})

    assert answer.kind is AnswerKind.ERROR
    assert answer.content["code"] == "LEDGER_PAGE_NOT_CONNECTED"
    assert set(answer.content) == {"code", "category", "message"}


def soon(link: LedgerLink, state: PageState) -> bool:
    """Whether ``link`` is in ``state`` within two seconds; its lines come on their own thread."""
    for _ in range(40):
        if link.page_state() is state:
            return True
        time.sleep(0.05)
    return False


def test_it_knows_when_the_page_connects_and_leaves(started: LedgerLink) -> None:
    assert soon(started, PageState.CONNECTED)

    started.call("drop_page", {})

    assert soon(started, PageState.DISCONNECTED)


def test_closing_twice_is_harmless_and_a_closed_link_says_so(started: LedgerLink) -> None:
    started.close()
    started.close()

    with pytest.raises(LedgerLinkError) as raised:
        started.call("list_assets", {})

    assert raised.value.failure is LinkFailure.NOT_STARTED


def test_the_token_is_there_to_show_and_nowhere_in_the_repr(started: LedgerLink) -> None:
    assert started.token_to_show() == TOKEN
    assert TOKEN not in repr(started)
    assert CLIENT_NAME == "Ledger Hand"


# --- every way of failing ----------------------------------------------------------


def test_no_node(ledger_folder: Path, tmp_path: Path) -> None:
    error = failure_of(LedgerLink(setup(ledger_folder, str(tmp_path / "missing-node"))))

    assert error.failure is LinkFailure.NODE_MISSING


def test_node_too_old(ledger_folder: Path, node: str) -> None:
    link = LedgerLink(setup(ledger_folder, node, FAKE_NODE_VERSION="v18.19.0"))

    error = failure_of(link)

    assert error.failure is LinkFailure.NODE_TOO_OLD
    assert "v18.19.0" in error.detail


def test_node_that_says_no_version(ledger_folder: Path, node: str) -> None:
    error = failure_of(LedgerLink(setup(ledger_folder, node, FAKE_NODE_VERSION="hello")))

    assert error.failure is LinkFailure.NODE_MISSING


@pytest.mark.parametrize("missing", ["assistant-link/main.ts", "node_modules/tsx"])
def test_a_folder_that_is_not_the_ledger(ledger_folder: Path, node: str, missing: str) -> None:
    target = ledger_folder / missing
    if target.is_dir():
        target.rmdir()
    else:
        target.unlink()

    error = failure_of(LedgerLink(setup(ledger_folder, node)))

    assert error.failure is LinkFailure.LEDGER_FOLDER_WRONG


def test_port_in_use(ledger_folder: Path, node: str) -> None:
    error = failure_of(LedgerLink(setup(ledger_folder, node, "port_in_use")))

    assert error.failure is LinkFailure.PORT_IN_USE
    assert f"127.0.0.1:{PORT}" in error.detail


def test_any_other_refusal_to_start(ledger_folder: Path, node: str) -> None:
    error = failure_of(LedgerLink(setup(ledger_folder, node, "bad_option")))

    assert error.failure is LinkFailure.CANNOT_START
    assert "--page-port" in error.detail


def test_a_link_that_listens_on_another_port(ledger_folder: Path, node: str) -> None:
    error = failure_of(LedgerLink(setup(ledger_folder, node, "wrong_port")))

    assert error.failure is LinkFailure.CANNOT_START


def test_handshake_refused(ledger_folder: Path, node: str) -> None:
    error = failure_of(LedgerLink(setup(ledger_folder, node, "refuse_handshake")))

    assert error.failure is LinkFailure.HANDSHAKE_REFUSED


def test_a_link_that_never_listens_times_out(ledger_folder: Path, node: str) -> None:
    link = LedgerLink(replace(setup(ledger_folder, node, "never_listens"), start_seconds=1.0))

    error = failure_of(link)

    assert error.failure is LinkFailure.TIMED_OUT


def test_no_answer_in_time(ledger_folder: Path, node: str) -> None:
    error = failure_of(LedgerLink(setup(ledger_folder, node, "silent")), act="call")

    assert error.failure is LinkFailure.TIMED_OUT


def test_the_link_gone_in_the_middle(ledger_folder: Path, node: str) -> None:
    error = failure_of(LedgerLink(setup(ledger_folder, node, "die")), act="call")

    assert error.failure is LinkFailure.LINK_GONE


def test_an_answer_that_is_not_json(ledger_folder: Path, node: str) -> None:
    error = failure_of(LedgerLink(setup(ledger_folder, node, "garbage")), act="call")

    assert error.failure is LinkFailure.REPLY_NOT_JSON


def test_an_answer_without_the_ledgers_content(ledger_folder: Path, node: str) -> None:
    error = failure_of(LedgerLink(setup(ledger_folder, node, "no_structured")), act="call")

    assert error.failure is LinkFailure.REPLY_UNEXPECTED


def spawned(monkeypatch: pytest.MonkeyPatch) -> list[subprocess.Popen[str]]:
    """Every child process the client starts, kept so a test can see it has left."""
    made: list[subprocess.Popen[str]] = []
    real = subprocess.Popen

    def keeping(*args: Any, **kwargs: Any) -> subprocess.Popen[str]:
        process = real(*args, **kwargs)
        made.append(process)
        return process

    monkeypatch.setattr(subprocess, "Popen", keeping)
    return made


def test_a_handshake_never_answered_times_out_and_the_link_is_closed(
    ledger_folder: Path, node: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    made = spawned(monkeypatch)
    link = LedgerLink(setup(ledger_folder, node, "silent_hello"))

    error = failure_of(link)

    assert error.failure is LinkFailure.TIMED_OUT
    *_, process = made  # the version check runs first
    # Closed, so its port is free for the next try (68D, finding 1).
    assert process.poll() is not None
    assert "running=False" in repr(link)


def test_a_link_slow_to_leave_after_it_refused_is_stopped_and_said_in_words(
    ledger_folder: Path, node: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    made = spawned(monkeypatch)
    the_setup = replace(
        setup(ledger_folder, node, "linger", FAKE_LINK_LINGER="30"), close_seconds=0.5
    )
    started_at = time.monotonic()

    error = failure_of(LedgerLink(the_setup))

    assert error.failure is LinkFailure.TIMED_OUT
    assert str(error) == f"{LinkFailure.TIMED_OUT.value} waiting for the link to leave"
    assert time.monotonic() - started_at < 10
    *_, process = made  # the version check runs first
    assert process.poll() is not None


def test_a_call_the_link_refuses(started: LedgerLink) -> None:
    with pytest.raises(LedgerLinkError) as raised:
        started.call("no_such_tool", {})

    assert raised.value.failure is LinkFailure.CALL_REFUSED
    assert "no_such_tool" in raised.value.detail


def test_every_failure_has_a_sentence() -> None:
    for failure in LinkFailure:
        assert failure.value.endswith(".")
        assert len(failure.value.split()) >= 5


# --- the token stays in memory -----------------------------------------------------

FAILING = [
    ("port_in_use", "start"),
    ("bad_option", "start"),
    ("refuse_handshake", "start"),
    ("wrong_port", "start"),
    ("silent", "call"),
    ("die", "call"),
    ("garbage", "call"),
    ("no_structured", "call"),
]


@pytest.mark.parametrize(("scenario", "act"), FAILING)
def test_the_token_is_in_no_error_repr_log_output_or_file(
    ledger_folder: Path,
    node: str,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
    scenario: str,
    act: str,
) -> None:
    caplog.set_level(logging.DEBUG)
    the_setup = setup(ledger_folder, node, scenario)
    link = LedgerLink(the_setup)

    error = failure_of(link, act)
    logging.getLogger("test").error("link failed: %s %r", error, error)
    captured = capsys.readouterr()

    seen = [str(error), repr(error), error.detail, repr(link), repr(the_setup), str(the_setup)]
    seen += [caplog.text, captured.out, captured.err]
    assert all(TOKEN not in text for text in seen)
    files = [path for path in tmp_path.rglob("*") if path.is_file()]
    assert all(TOKEN.encode() not in path.read_bytes() for path in files)


def test_the_token_in_the_links_own_line_is_hidden(ledger_folder: Path, node: str) -> None:
    error = failure_of(LedgerLink(setup(ledger_folder, node, "port_in_use")))

    assert "<token>" in error.detail


def test_a_token_too_short_or_with_other_characters_is_refused() -> None:
    for bad in ["short", "x" * 31, "a" * 31 + "!", "a" * 40 + " "]:
        with pytest.raises(ValueError) as raised:
            LinkToken(bad)
        assert bad not in str(raised.value)


# --- one call on its way at a time (68B3, part two, 7) -------------------------


def test_calls_from_many_threads_at_once_each_get_their_own_answer(
    ledger_folder: Path, node: str
) -> None:
    import threading

    link = LedgerLink(replace(setup(ledger_folder, node), answer_seconds=5.0))
    link.start()
    got: dict[int, object] = {}
    failed: list[BaseException] = []

    def ask(number: int) -> None:
        try:
            for round_ in range(5):
                answer = link.call("echo", {"caller": number, "round": round_})
                got[number * 10 + round_] = answer.content["echoed"]
        except BaseException as error:  # noqa: BLE001 - every failure is reported below
            failed.append(error)

    threads = [threading.Thread(target=ask, args=(n,)) for n in range(8)]
    try:
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
    finally:
        link.close()

    assert failed == []
    assert got == {n * 10 + r: {"caller": n, "round": r} for n in range(8) for r in range(5)}


def test_a_ledger_whose_packages_were_not_all_installed_is_said_so(
    ledger_folder: Path, node: str
) -> None:
    (ledger_folder / "package.json").write_text(
        '{"dependencies": {"tsx": "4", "@modelcontextprotocol/server": "1"}}', encoding="utf-8"
    )

    error = failure_of(LedgerLink(setup(ledger_folder, node)))

    assert error.failure is LinkFailure.PACKAGES_MISSING
    assert error.detail == "@modelcontextprotocol/server"


def test_a_ledger_with_every_package_installed_starts(ledger_folder: Path, node: str) -> None:
    (ledger_folder / "package.json").write_text('{"dependencies": {"tsx": "4"}}', encoding="utf-8")

    with LedgerLink(setup(ledger_folder, node)) as link:
        assert link.running()
    assert not link.running()


def test_a_package_node_cannot_find_is_said_as_packages_missing(
    ledger_folder: Path, node: str
) -> None:
    error = failure_of(LedgerLink(setup(ledger_folder, node, "missing_module")))

    assert error.failure is LinkFailure.PACKAGES_MISSING
    assert error.detail == "@modelcontextprotocol/server/stdio"
