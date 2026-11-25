"""Tests of how the wiring module builds the client of the ledger's assistant link.

It is built, not started; without a ledger folder there is none; and each
one gets a fresh token of 32 characters that no ``repr`` shows.
"""

from __future__ import annotations

from pathlib import Path

from ledger_hand import __version__
from ledger_hand.settings import LedgerLinkSettings
from ledger_hand.wiring import ledger_link, make_link_token


def test_without_a_ledger_folder_there_is_no_link() -> None:
    assert ledger_link(LedgerLinkSettings(directory=None)) is None


def test_the_link_is_built_from_the_settings_and_not_started(tmp_path: Path) -> None:
    settings = LedgerLinkSettings(
        directory=tmp_path, link_port=47668, page_port=3068, environment={"PATH": "/usr/bin"}
    )

    link = ledger_link(settings)

    assert link is not None
    assert repr(link) == "LedgerLink(port=47668, running=False)"
    setup = link._setup  # noqa: SLF001
    assert (setup.ledger_directory, setup.port, setup.page_port) == (tmp_path, 47668, 3068)
    assert setup.hand_version == __version__
    assert dict(setup.environment) == {"PATH": "/usr/bin"}


def test_every_link_gets_a_fresh_token_of_32_characters(tmp_path: Path) -> None:
    first = ledger_link(LedgerLinkSettings(directory=tmp_path))
    second = ledger_link(LedgerLinkSettings(directory=tmp_path))

    assert first is not None and second is not None
    assert len(first.token_to_show()) == 32
    assert first.token_to_show() != second.token_to_show()
    assert first.token_to_show() not in repr(first._setup)  # noqa: SLF001


def test_a_made_token_shows_only_a_placeholder() -> None:
    token = make_link_token()

    assert len(token.reveal()) == 32
    assert token.reveal() not in f"{token} {token!r}"
