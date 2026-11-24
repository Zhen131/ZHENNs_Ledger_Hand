"""Tests of the edit set: its gold answers are what the program does for a model that copies right.

Each sentence is run through the ruler with a scripted model that makes the
one call a careful model would make; every sentence must then come out
right. A gold answer the program cannot reach even then is wrong, or the
program is. The judging of what came of a sentence is tested on its own
too. No real model is asked.
"""

from __future__ import annotations

import dataclasses
from decimal import Decimal

import pytest

from evals.edit_run import _one, outcome_of
from evals.edit_set import (
    EditGold,
    EditSentence,
    Outcome,
    Verdict,
    expected_trade,
    judge_edit,
    load_edit_set,
    passes,
)
from ledger_hand.ledger.invented_book import INVENTED_TRADES
from ledger_hand.ports import ToolCall, ToolReply
from tests.fakes.scripted_model import ScriptedModel, scripted_record

SET = load_edit_set()


def update(
    period: str | None, asset: str | None, field: str, value: str, side: str | None = None
) -> tuple[str, dict[str, object]]:
    arguments: dict[str, object] = {"field": field, "new_value": value}
    for name, given in (("period", period), ("asset", asset), ("side", side)):
        if given is not None:
            arguments[name] = given
    return "propose_trade_update", arguments


def delete(
    period: str | None, asset: str | None = None, side: str | None = None
) -> tuple[str, dict[str, object]]:
    arguments = {
        name: given
        for name, given in (("period", period), ("asset", asset), ("side", side))
        if given
    }
    return "propose_trade_delete", dict(arguments)


CAREFUL = {
    "E1": update("10月6号", "BTC", "quantity", "0.0081"),
    "E2": delete("9月25号", "ADA"),
    "E3": update("10月6号", None, "fee", "0.000009"),
    "N1": update("10月21号", "BTC", "price", "66150", side="sell"),
    "N2": update("2 October", "MSFT", "total", "1237.12"),
    "N3": update("9月25号", "ADA", "platform", "Binance"),
    "N4": update("11月3号", "ADA", "note", "补仓"),
    "N5": update("10月2号", "MSFT", "time", "10月2号上午9:25"),
    "N6": update("14 October", "ETH", "fee", "0.52 USDT", side="sell"),
    "N7": delete("October 6"),
    "N8": delete("10月", side="sell"),
    "N9": delete("October 21", "BTC", "sell"),
    "N10": update(None, "ADA", "platform", "Binance"),
    "N11": update("October", "ETH", "price", "2450"),
    "N12": delete("10月30号", "BTC"),
    "N13": delete("November 20", "ETH"),
    "N14": update("9月25号", "ADA", "time", "9月24号"),
}


def test_the_set_holds_what_it_must() -> None:
    sentences = {sentence.id: sentence for sentence in SET.sentences}
    golds = [sentence.gold for sentence in SET.sentences]
    assert set(sentences) == set(CAREFUL)
    assert len(sentences) >= 15
    fields = {gold.field for gold in golds if gold.kind == "change"}
    assert {"quantity", "price", "total", "fee", "time", "platform", "note"} <= fields
    assert sum(gold.kind == "delete" for gold in golds) >= 3
    one = [g for g in golds if g.expect == "send" and g.pick is None]
    assert len(one) >= 4
    assert sum(gold.pick is not None for gold in golds) >= 4
    assert sum(gold.expect == "not_found" for gold in golds) >= 1
    assert any(sentence.text.isascii() for sentence in SET.sentences)


@pytest.mark.parametrize("sentence", SET.sentences, ids=lambda sentence: sentence.id)
def test_a_careful_model_gets_every_sentence_right(sentence: object) -> None:
    assert isinstance(sentence, EditSentence)
    name, arguments = CAREFUL[sentence.id]
    reply = ToolReply(
        text="", calls=(ToolCall(name=name, arguments=arguments),), record=scripted_record()
    )

    said = _one(sentence, ScriptedModel([reply]), 6, SET.now, SET.zone)

    outcome = outcome_of([one for _, one in said])
    assert judge_edit(sentence.gold, outcome) is Verdict.RIGHT, said[-1][1].reply


GOLD = EditGold(
    expect="send", kind="change", trade="t-06", field="fee", value="0.000009", pick="第二笔"
)


def test_sent_without_asking_first_is_silently_wrong() -> None:
    after = expected_trade(GOLD)
    sent = Outcome(sent_kind="change", sent_trade="t-06", after=after, ending="sent")
    assert judge_edit(GOLD, sent) is Verdict.SILENTLY_WRONG
    asked = dataclasses.replace(sent, asked_pick=True)
    assert judge_edit(GOLD, asked) is Verdict.RIGHT


def test_another_trade_or_another_value_is_silently_wrong() -> None:
    after = expected_trade(GOLD)
    assert after is not None
    other = Outcome(asked_pick=True, sent_kind="change", sent_trade="t-05", after=after)
    value = Outcome(
        asked_pick=True,
        sent_kind="change",
        sent_trade="t-06",
        after=dataclasses.replace(after, fee=Decimal("0.00009")),
    )
    assert judge_edit(GOLD, other) is Verdict.SILENTLY_WRONG
    assert judge_edit(GOLD, value) is Verdict.SILENTLY_WRONG


def test_nothing_sent_is_not_done_and_a_send_where_nothing_should_be_is_silently_wrong() -> None:
    assert judge_edit(GOLD, Outcome(asked_pick=True, ending="picking")) is Verdict.NOT_DONE
    not_found = EditGold(expect="not_found")
    assert judge_edit(not_found, Outcome(ending="not_found")) is Verdict.RIGHT
    assert judge_edit(not_found, Outcome(ending="told")) is Verdict.NOT_DONE
    assert (
        judge_edit(not_found, Outcome(sent_kind="delete", sent_trade="t-05"))
        is Verdict.SILENTLY_WRONG
    )


def test_the_gold_change_keeps_every_other_part_of_the_trade() -> None:
    after = expected_trade(GOLD)
    assert after == dataclasses.replace(dict(INVENTED_TRADES)["t-06"], fee=Decimal("0.000009"))


def test_the_pass_lines() -> None:
    right = {f"N{number}": Verdict.RIGHT for number in range(1, 8)}
    all_right = {"E1": Verdict.RIGHT, "E2": Verdict.RIGHT, "E3": Verdict.RIGHT, **right}
    assert all(passes(all_right).values())
    one_silent = {**all_right, "N1": Verdict.SILENTLY_WRONG}
    assert passes(one_silent)["nothing silently wrong"] is False
    e3_not_done = {**all_right, "E3": Verdict.NOT_DONE}
    assert passes(e3_not_done)["E1 to E3 right"] is False
    three_not_done = {
        **all_right,
        "N1": Verdict.NOT_DONE,
        "N2": Verdict.NOT_DONE,
        "N3": Verdict.NOT_DONE,
    }
    assert passes(three_not_done)["at least 80% right"] is False
