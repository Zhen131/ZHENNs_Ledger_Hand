"""Tests that every browser tab shares one keeper, built once for the program, and one link.

The keeper is built by the wiring module's ``link_keeper``, replaced here by
one that counts how often it is called and hands back a keeper over the
stand-in link of ``test_page_assistant_link``. The page keeps it with
Streamlit's process-wide cache, so ten reruns and a second tab still build
it once, and Start pressed in either tab starts one link. Every sentence
table about the link is walked against its enumeration.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
import streamlit as st

from ledger_hand import wiring
from ledger_hand.ledger.link_failures import LinkFailure
from ledger_hand.ledger.link_keeper import LinkKeeper, LinkState
from ledger_hand.ui.assistant_ledger import KEEPER_KEY
from ledger_hand.ui.assistant_link_panel import START_KEY
from ledger_hand.ui.assistant_link_words import (
    NO_LINK_WORDS,
    START_FAILURES,
    STATE_WORDS,
    not_connected,
)
from ledger_hand.wiring import LinkNotSet
from tests.fakes.routed_model import RoutedModel
from tests.ui.test_page_assistant_link import TOKEN, Fixture, open_page, state_line


class Counted:
    def __init__(self) -> None:
        self.fixture = Fixture()
        self.built = 0

    def __call__(self) -> LinkKeeper:
        self.built += 1
        return self.fixture.keeper


@pytest.fixture
def counted(monkeypatch: pytest.MonkeyPatch) -> Iterator[Counted]:
    made = Counted()
    monkeypatch.setattr(wiring, "link_keeper", made)
    st.cache_resource.clear()
    yield made
    st.cache_resource.clear()


def shared_page(model: RoutedModel) -> object:
    """A tab that uses the process's keeper, not a test's own."""
    page = open_page(model, Fixture())
    del page.session_state[KEEPER_KEY]
    return page.run()


def test_ten_reruns_build_the_keeper_once_and_start_one_link(counted: Counted) -> None:
    page = shared_page(RoutedModel())
    page = page.button(key=START_KEY).click().run()  # type: ignore[attr-defined]

    for _ in range(10):
        page = page.run()

    assert counted.built == 1
    assert len(counted.fixture.links) == 1
    assert state_line(page) == f"Assistant link: {STATE_WORDS[LinkState.CONNECTED]}"


def test_two_tabs_see_the_same_keeper_and_the_same_link(counted: Counted) -> None:
    one = shared_page(RoutedModel())
    other = shared_page(RoutedModel())

    one = one.button(key=START_KEY).click().run()  # type: ignore[attr-defined]
    other = other.run()  # type: ignore[attr-defined]

    assert counted.built == 1
    assert len(counted.fixture.links) == 1
    assert state_line(other) == f"Assistant link: {STATE_WORDS[LinkState.CONNECTED]}"
    assert other.button(key=START_KEY).disabled


def test_every_state_every_failed_start_and_every_reason_has_its_sentence() -> None:
    assert set(STATE_WORDS) == set(LinkState)
    assert set(START_FAILURES) == set(LinkFailure)
    assert set(NO_LINK_WORDS) == set(LinkNotSet)
    for sentence in [*STATE_WORDS.values(), *START_FAILURES.values(), *NO_LINK_WORDS.values()]:
        assert sentence.endswith(".")
        assert TOKEN not in sentence


def test_not_connected_names_the_port_and_the_page_port_and_asks_nothing_of_the_model() -> None:
    said = not_connected(LinkState.WAITING, 47668, 3068)

    assert said.startswith(
        "Your ledger page is not connected yet, so nothing was sent and the model was not asked."
    )
    assert "http://127.0.0.1:3068" in said
    assert "Enter port 47668" in said
