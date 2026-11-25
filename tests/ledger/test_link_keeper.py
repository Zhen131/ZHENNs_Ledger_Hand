"""Tests of the link keeper: the program's one assistant link, started and stopped on request.

The link is the stand-in of ``fake_link.py``, played by a stand-in for
Node.js, so every state is reached without the ledger: started and
connected, the page disconnected, the link gone by itself, stopped, a
start that fails. The keeper builds a fresh link, so a fresh token, at
each start.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from ledger_hand.ledger.link_client import LedgerLink
from ledger_hand.ledger.link_failures import LinkFailure, LinkToken
from ledger_hand.ledger.link_keeper import LinkKeeper, LinkState
from ledger_hand.ledger.link_ledger import LinkLedger, ToolCaller
from ledger_hand.ports import LedgerError, LedgerErrorKind, LedgerPort
from tests.ledger.test_link_client import ledger_folder, node, setup

__all__ = ["ledger_folder", "node"]  # the stand-in link's fixtures, used below


def tokens() -> Iterator[str]:
    number = 0
    while True:
        number += 1
        yield f"InventedKeeperToken_{number:04d}_0123456789abcdef"


class Built:
    """Counts the links built, each with its own invented token."""

    def __init__(self, folder: Path, node: str, scenario: str = "normal") -> None:
        self.links: list[LedgerLink] = []
        self._setup = setup(folder, node, scenario)
        self._tokens = tokens()

    def link(self) -> LedgerLink:
        built = LedgerLink(replace(self._setup, token=LinkToken(next(self._tokens))))
        self.links.append(built)
        return built


def plug_for(caller: ToolCaller, model_name: str) -> LedgerPort:
    return LinkLedger(caller, model_name=model_name, today=lambda: date(2026, 11, 25))


@pytest.fixture
def built(ledger_folder: Path, node: str) -> Built:
    return Built(ledger_folder, node)


@pytest.fixture
def keeper(built: Built) -> Iterator[LinkKeeper]:
    kept = LinkKeeper(built.link, plug_for)
    yield kept
    kept.stop()


def wait_for(keeper: LinkKeeper, state: LinkState) -> LinkState:
    for _ in range(100):
        if keeper.state() is state:
            break
        time.sleep(0.05)
    return keeper.state()


def test_before_any_start_it_is_not_started_and_shows_no_port_or_token(
    keeper: LinkKeeper,
) -> None:
    assert keeper.state() is LinkState.NOT_STARTED
    assert (keeper.port, keeper.token_to_show()) == (None, None)


def test_a_start_connects_and_a_second_start_starts_nothing(
    keeper: LinkKeeper, built: Built
) -> None:
    assert keeper.start() is None
    assert keeper.start() is None

    assert len(built.links) == 1
    assert wait_for(keeper, LinkState.CONNECTED) is LinkState.CONNECTED
    assert keeper.port == 47999
    assert keeper.page_port == 3068
    assert keeper.token_to_show() == "InventedKeeperToken_0001_0123456789abcdef"


def test_a_stop_is_seen_as_stopped_and_a_new_start_brings_a_new_token(
    keeper: LinkKeeper, built: Built
) -> None:
    keeper.start()
    keeper.stop()

    assert keeper.state() is LinkState.STOPPED
    assert not built.links[0].running()
    assert keeper.token_to_show() is None
    keeper.start()
    assert keeper.token_to_show() == "InventedKeeperToken_0002_0123456789abcdef"


def test_the_page_disconnecting_is_seen(keeper: LinkKeeper, built: Built) -> None:
    keeper.start()
    wait_for(keeper, LinkState.CONNECTED)

    built.links[0].call("drop_page", {})

    assert wait_for(keeper, LinkState.DISCONNECTED) is LinkState.DISCONNECTED


def test_a_link_killed_in_the_middle_is_seen_as_gone(keeper: LinkKeeper, built: Built) -> None:
    keeper.start()
    process = built.links[0]._process  # noqa: SLF001 - the test kills the child itself
    assert process is not None
    process.kill()
    process.wait()

    assert keeper.state() is LinkState.GONE
    assert keeper.port is None


def test_a_start_that_fails_hands_back_why_and_leaves_nothing_running(
    ledger_folder: Path, node: str
) -> None:
    built = Built(ledger_folder, node, "port_in_use")
    keeper = LinkKeeper(built.link, plug_for)

    failure = keeper.start()

    assert failure is not None and failure.failure is LinkFailure.PORT_IN_USE
    assert keeper.state() is LinkState.NOT_STARTED
    assert not built.links[0].running()


def test_one_plug_for_each_model_until_the_next_start(keeper: LinkKeeper) -> None:
    first = keeper.plug("qwen2.5:7b")

    assert keeper.plug("qwen2.5:7b") is first
    assert keeper.plug("another-model") is not first
    keeper.start()
    assert keeper.plug("qwen2.5:7b") is not first


def test_a_plug_over_no_running_link_says_the_ledger_cannot_be_reached(
    keeper: LinkKeeper,
) -> None:
    with pytest.raises(LedgerError) as raised:
        keeper.plug("qwen2.5:7b").list_assets()

    assert raised.value.kind is LedgerErrorKind.UNREACHABLE


def test_a_plug_reaches_the_running_link(keeper: LinkKeeper) -> None:
    keeper.start()

    assert keeper.plug("qwen2.5:7b").list_assets() == ()
