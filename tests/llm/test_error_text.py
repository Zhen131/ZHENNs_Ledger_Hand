"""Tests of making a server's words safe to show: short, printable, and without the key."""

from __future__ import annotations

import pytest

from ledger_hand.llm.error_text import (
    DETAIL_CHARACTERS,
    HIDDEN,
    SNIPPET_CHARACTERS,
    detail,
    hide,
    snippet,
)
from ledger_hand.settings import Secret

KEY = Secret("sk-invented-abcdef0123456789")


def test_the_key_is_hidden_wherever_it_occurs() -> None:
    text = f"Bearer {KEY.reveal()} and again {KEY.reveal()}"

    assert hide(text, KEY) == f"Bearer {HIDDEN} and again {HIDDEN}"


def test_without_a_key_nothing_is_hidden() -> None:
    assert hide("plain text", None) == "plain text"
    assert hide("plain text", Secret("")) == "plain text"


def test_no_body_gives_no_snippet() -> None:
    assert snippet(b"", KEY) is None


def test_a_short_body_is_shown_whole() -> None:
    assert snippet(b'{"error": "busy"}', None) == '{"error": "busy"}'


def test_a_long_body_is_cut_short_and_says_so() -> None:
    shown = snippet(b"a" * (SNIPPET_CHARACTERS + 50), None)

    assert shown == "a" * SNIPPET_CHARACTERS + "..."


def test_a_key_straddling_the_cut_leaves_nothing_of_itself() -> None:
    value = KEY.reveal()
    body = ("x" * (SNIPPET_CHARACTERS - 10) + value + "y" * 50).encode("ascii")

    shown = snippet(body, KEY)

    assert shown is not None
    assert value[:10] not in shown
    assert value not in shown


@pytest.mark.parametrize(
    ("body", "shown"),
    [
        (b"clear\x1b[2Jscreen", "clear\\x1b[2Jscreen"),
        (b"line\nbreak\ttab\r", "line\\x0abreak\\x09tab\\x0d"),
        (b"bell\x07", "bell\\x07"),
        ("nul\x00".encode(), "nul\\x00"),
        ("right‮left".encode(), "right\\u202eleft"),
        ("中文 ok".encode(), "中文 ok"),
    ],
)
def test_characters_that_are_not_printable_are_written_as_escapes(body: bytes, shown: str) -> None:
    assert snippet(body, None) == shown


def test_bytes_that_are_not_utf8_are_replaced_not_refused() -> None:
    shown = snippet(b"\xff\xfe broken", None)

    assert shown is not None
    assert shown.endswith(" broken")


def test_a_detail_is_cut_and_hides_the_key() -> None:
    message = f"Illegal header value b'Bearer {KEY.reveal()}' " + "z" * DETAIL_CHARACTERS

    shown = detail(message, KEY)

    assert KEY.reveal() not in shown
    assert shown.endswith("...")
    assert HIDDEN in shown
