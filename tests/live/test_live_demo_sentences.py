"""The live check of the sentences for a demo: a real model, the fake ledger. Run only by hand.

Marked ``live_model``, so ordinary runs leave it out. ``scripts/check.sh
live`` runs it with the settings read from the environment. Each sentence of
``tests/live/demo_sentences.json`` is said once, in a chat of its own, to the
whole assistant, with a new fake ledger and the invented book's fixed moment
as now, and what came of it is held to what the file says it must come to:

- a trade recorded: the trades sent, every figure, the money, the time and
  the platform;
- money said where the quantity goes: nothing sent, and the reply says why;
- a question: the tool of the last table, its header's time, asset and side,
  how many rows it has and which trades or assets they are;
- a change or a deletion: which trade, and for a change the part and its new
  value.

Each also checks whether a reminder line is in the reply. Only what the
program did is checked, never the model's wording. Each prints what
happened, so the run itself is the record. The README lists the same
sentences under "Sentences for a demo"; a test that needs no model keeps
the two the same (``tests/live/test_demo_sentences_readme.py``).
"""

from __future__ import annotations

import io
import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from ledger_hand.assistant.lookups import Lookup, header_lines, lookup_lines
from ledger_hand.flows.conversation import AssistantChat, Said, say
from ledger_hand.flows.recording import tuning_from
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ledger.invented_book import INVENTED_NOW, INVENTED_ZONE
from ledger_hand.llm.local import connect_local_model
from ledger_hand.settings import load_assistant_steps, load_model_settings
from scripts.try_assistant import show_said

pytestmark = pytest.mark.live_model

SENTENCES_FILE = Path(__file__).with_name("demo_sentences.json")
SENTENCES: list[dict[str, Any]] = json.loads(SENTENCES_FILE.read_text(encoding="utf-8"))[
    "sentences"
]
REMINDER = "Reminder:"


def said_once(words: str) -> Said:
    settings = load_model_settings()
    said = say(
        AssistantChat(),
        words,
        model=connect_local_model(settings),
        ledger=FakeLedger(),
        now=INVENTED_NOW,
        zone=INVENTED_ZONE,
        max_steps=load_assistant_steps(),
        tuning=tuning_from(settings),
    )
    shown = io.StringIO()
    show_said(words, said, shown)
    print("\n" + shown.getvalue())
    return said


def check_recorded(said: Said, expect: dict[str, Any]) -> None:
    assert said.sent is not None, f"nothing was sent: {said.reply}"
    assert said.recorded is not None
    trades = said.recorded.trades
    assert len(trades) == len(expect["trades"]), f"sent {len(trades)} trade(s)"
    for trade, gold in zip(trades, expect["trades"], strict=True):
        assert trade.side.value == gold["side"]
        assert trade.asset == gold["asset"]
        for part in ("quantity", "price", "total", "fee"):
            assert getattr(trade, part) == Decimal(gold[part]), part
        assert trade.quote == gold["quote"]
        assert trade.fee_asset == gold["fee_asset"]
        assert trade.occurred == datetime.fromisoformat(gold["occurred"])
        assert trade.platform == gold["platform"]


def check_held_back(said: Said, expect: dict[str, Any]) -> None:
    assert said.sent is None, f"something was sent: {said.reply}"
    assert expect["reply_holds"] in said.reply, said.reply


def check_asked(said: Said, expect: dict[str, Any]) -> None:
    assert said.turn is not None and said.turn.lookups, f"no table: {said.reply}"
    lookup = said.turn.lookups[-1]
    assert lookup.tool.value == expect["tool"]
    header = header_lines(lookup)
    for part in ("time", "asset", "side"):
        if part in expect:
            assert expect[part] in header, f"{expect[part]!r} not in {header}"
    rows = len(lookup_lines(lookup)) - len(header)
    assert rows == expect["rows"], f"{rows} row(s)"
    if "items" in expect:
        assert table_items(lookup) == expect["items"]


def table_items(lookup: Lookup) -> list[str]:
    """Which things the table lists: trades by the ledger's number, else assets by code."""
    if lookup.trades:
        return [trade.id for trade in lookup.trades]
    if lookup.positions:
        return [position.asset for position in lookup.positions]
    return [asset.code for asset in lookup.assets]


def check_edited(said: Said, expect: dict[str, Any]) -> None:
    sent = said.edit_sent
    assert sent is not None, f"no change or deletion was sent: {said.reply}"
    assert sent.kind.value == expect["edit"]
    assert sent.trade == expect["trade"]
    if expect["edit"] == "change":
        assert said.edited is not None and said.edited.after is not None
        assert str(getattr(said.edited.after, expect["field"])) == expect["value"]


CHECKS = {
    "record": check_recorded,
    "held_back": check_held_back,
    "ask": check_asked,
    "change": check_edited,
}


@pytest.mark.parametrize("sentence", SENTENCES, ids=[s["id"] for s in SENTENCES])
def test_a_sentence_for_a_demo_comes_to_what_the_file_says(sentence: dict[str, Any]) -> None:
    said = said_once(sentence["said"])

    CHECKS[sentence["kind"]](said, sentence["expect"])
    if "reminder_line" in sentence["expect"]:
        assert (REMINDER in said.reply) is sentence["expect"]["reminder_line"], said.reply
