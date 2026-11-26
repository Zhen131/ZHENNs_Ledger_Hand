"""Tests of the set about cash balances and money moved, and of how its ruler judges.

No real model is called. The set holds what it was written to hold; the
sentences copied from ``cash.json`` are its words exactly; the program's
own readings, which come before the model, take each group as it should;
and the ruler judges a few sentences said with a scripted model.
"""

from __future__ import annotations

import json
from pathlib import Path

from evals.cash_balances_run import CASH_BALANCES_SET, judge, load_set
from evals.cash_run import CASH_SET
from ledger_hand.core.cash_words import held_names
from ledger_hand.core.ledger_table import names_of
from ledger_hand.core.money_asks import left_asked, statement
from ledger_hand.flows.cash_question import caught
from ledger_hand.flows.conversation import AssistantChat, say
from ledger_hand.ledger.demo_book import DEMO_ASSETS
from ledger_hand.ledger.demo_cash import demo_ledger_with_cash
from ledger_hand.ledger.invented_book import INVENTED_NOW, INVENTED_ZONE
from ledger_hand.ports import ToolCall, ToolReply
from tests.fakes.routed_model import RoutedModel
from tests.fakes.scripted_model import scripted_record

NOW, ZONE, SENTENCES = load_set()
HELD = (*(name for name, _ in names_of(()).built_in), *held_names(DEMO_ASSETS))


def group(name: str) -> list:  # type: ignore[type-arg]
    return [one for one in SENTENCES if one.group == name]


def test_the_set_holds_what_it_was_written_to_hold() -> None:
    named, manual, must = group("named"), group("manual"), group("must_pass")
    named_texts = {one.text for one in named}

    assert {"我还有多少美金", "我还有多少欧元", "我还剩多少EUR"} <= named_texts
    assert len(manual) >= 12
    for kind in ("deposit", "withdrawal", "exchange", "dividend"):
        assert sum(kind in one.kinds for one in manual) >= 2
    assert "我入了500美金" in {one.text for one in manual}
    assert sum(one.with_trade for one in manual) >= 2
    assert any(one.text.isascii() for one in manual)
    assert len(must) >= 36 + 8
    assert (NOW, ZONE) == (INVENTED_NOW, INVENTED_ZONE)
    assert CASH_BALANCES_SET.parent.name == "cash"


def test_the_sentences_copied_from_the_cash_set_are_its_words_exactly() -> None:
    cash = json.loads(CASH_SET.read_text(encoding="utf-8"))
    kept = json.loads(Path(CASH_BALANCES_SET).read_text(encoding="utf-8"))
    copied = [one for name in ("named", "must_pass") for one in kept[name] if "from" in one]
    for one in copied:
        _, source, number = one["from"].split()
        (original,) = [line for line in cash[source] if line["id"] == number]
        assert one["text"] == original["text"]
    every_must_pass = [
        line["text"]
        for name in ("must_pass", "must_pass_added", "must_pass_added_2")
        for line in cash[name]
    ]
    assert set(every_must_pass) <= {one.text for one in group("must_pass")}


def test_the_programs_readings_take_each_group_as_it_should() -> None:
    ledger = demo_ledger_with_cash()
    for one in group("named"):
        assert caught(one.text, ledger) is not None or left_asked(one.text), one.id
    for one in group("manual"):
        found = statement(one.text, HELD)
        assert found is not None, one.id
        assert tuple(kind.name.lower() for kind in found.kinds) == one.kinds, one.id
        assert found.with_trade == one.with_trade, one.id
    for one in group("must_pass"):
        assert statement(one.text, HELD) is None, one.id
        assert caught(one.text, ledger) is not None or not left_asked(one.text), one.id


def said(text: str, *tools: str):  # type: ignore[no-untyped-def]
    replies = [ToolReply(text=words, calls=(), record=scripted_record()) for words in tools]
    return say(
        AssistantChat(),
        text,
        model=RoutedModel(tools=replies),
        ledger=demo_ledger_with_cash().taking_cards(),
        now=NOW,
        zone=ZONE,
        max_steps=6,
    )


def test_the_ruler_judges_a_table_money_moved_and_a_figure_unheard() -> None:
    named = next(one for one in SENTENCES if one.text == "我还有多少USDT")
    manual = next(one for one in SENTENCES if one.text == "我今天入金了500 USDT")
    mixed = next(one for one in group("manual") if one.with_trade)
    near = next(one for one in group("must_pass") if one.text == "我现在还有多少BTC")

    assert judge(named, said(named.text)).right
    deposit = judge(manual, said(manual.text))
    assert deposit.right and not deposit.trouble
    unrecorded = judge(mixed, said(mixed.text, "好的。"))
    assert unrecorded.right and not unrecorded.trouble
    made_up = judge(near, said(near.text, "你还有 50 USDT 的现金。"))
    assert made_up.right
    assert made_up.trouble == ""


def test_a_figure_after_a_lookup_is_the_tables_and_no_trouble() -> None:
    near = next(one for one in group("must_pass") if one.text == "我现在还有多少BTC")
    looked = ToolReply(
        text="",
        calls=(ToolCall(name="get_positions", arguments={}),),
        record=scripted_record(),
    )
    after = ToolReply(
        text="You hold 1.0174765 BTC, 6919.6 USDT up.", calls=(), record=scripted_record()
    )
    done = say(
        AssistantChat(),
        near.text,
        model=RoutedModel(tools=[looked, after]),
        ledger=demo_ledger_with_cash().taking_cards(),
        now=NOW,
        zone=ZONE,
        max_steps=6,
    )

    assert judge(near, done).trouble == ""
