"""A check with no model: no sentence of the sets is read as money moved, or as a balance asked.

Every sentence said in every set of ``evals/sets/`` (the hidden halves left
out, never opened) and in ``tests/live/demo_sentences.json`` goes through
the two readings that come before the model, in the order the
conversation reads them: money moved that the assistant does not record
(``money_asks.statement``), and, only when the question about cash finds
none, how much of any money is still had (``money_asks.left_asked``). None
may be caught: the sets hold trades, questions about trades and questions
about cash, which the question about cash keeps as before.

The set written to be caught by them (``cash/cash-balances.json``) is
read for its ``must_pass`` sentences alone: its ``named`` and ``manual``
sentences are caught on purpose, and measured by its own ruler.

A sentence of the practice halves not yet in use (``enabled`` false) that
waits for cash balances or dividends would be read on purpose; such
sentences are listed apart, and there are none today.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from ledger_hand.core.cash_words import held_names
from ledger_hand.core.ledger_table import names_of
from ledger_hand.core.money_asks import left_asked, statement
from ledger_hand.flows.cash_question import caught
from ledger_hand.ledger.demo_book import DEMO_ASSETS, demo_ledger

REPO = Path(__file__).resolve().parents[2]
SETS = [
    path for path in sorted((REPO / "evals" / "sets").rglob("*.json")) if "hidden" not in path.name
]
DEMO_SENTENCES = REPO / "tests" / "live" / "demo_sentences.json"
HELD = (*(name for name, _ in names_of(()).built_in), *held_names(DEMO_ASSETS))
# What a sentence not yet in use waits for that these readings would catch on purpose.
_ON_PURPOSE = frozenset({"cash_balance", "dividend"})


def _sentences(found: Any) -> Iterator[dict[str, Any] | str]:
    """Every sentence said: each ``text`` or ``said``, the gold answers left out."""
    if isinstance(found, dict):
        for key, value in found.items():
            if key == "gold":
                continue
            if key in ("text", "said") and isinstance(value, str):
                yield found if "enabled" in found else value
            else:
                yield from _sentences(value)
    elif isinstance(found, list):
        for value in found:
            yield from _sentences(value)


def _all() -> list[tuple[str, str, bool]]:
    """Each sentence, the file it is in, and whether it waits on purpose."""
    found = []
    for path in (*SETS, DEMO_SENTENCES):
        data = json.loads(path.read_text(encoding="utf-8"))
        if path.name == "cash-balances.json":
            data = data["must_pass"]
        for one in _sentences(data):
            if isinstance(one, str):
                found.append((path.name, one, False))
                continue
            waits = not one.get("enabled", True) and one.get("wait_for") in _ON_PURPOSE
            found.append((path.name, str(one.get("text") or one.get("said")), waits))
    return found


def _read(said: str) -> str | None:
    """Which reading catches ``said``, in the conversation's order, or ``None``."""
    if statement(said, HELD) is not None:
        return "money moved, said"
    if caught(said, demo_ledger()) is None and left_asked(said):
        return "a balance asked"
    return None


def test_the_sets_and_the_demo_sentences_are_all_read() -> None:
    sentences = _all()
    names = {name for name, _, _ in sentences}

    assert len(sentences) >= 300
    assert {"cash.json", "final.json", "stocks.json", "demo_sentences.json"} <= names
    assert {"spoken-r100-practice.json", "spoken-r80-practice.json"} <= names
    assert not any("hidden" in name for name in names)


def test_no_sentence_in_use_is_caught_by_either_reading() -> None:
    caught_now = [
        (name, said, reading)
        for name, said, on_purpose in _all()
        if not on_purpose and (reading := _read(said)) is not None
    ]

    assert caught_now == []


def test_the_sentences_waiting_on_purpose_are_listed_apart() -> None:
    waiting = [(name, said, _read(said)) for name, said, on_purpose in _all() if on_purpose]

    print(f"waiting on purpose: {waiting}")
    assert waiting == []
