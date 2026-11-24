"""Tests of the ask set, of judging one answer against it, and of its runner."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from evals import ask_run
from evals.ask_set import (
    FIRST_SIX,
    AskSentence,
    Found,
    Gold,
    Verdict,
    judge_answer,
    load_ask_set,
    markdown,
    passes,
)
from evals.run import Backend
from evals.tool_set import load_tool_set
from ledger_hand.ports import ToolCall, ToolReply
from tests.fakes.scripted_model import ScriptedModel, scripted_record

SET = load_ask_set()
OCT_1, OCT_31 = date(2026, 10, 1), date(2026, 10, 31)


def sentence(*gold: Gold) -> AskSentence:
    return AskSentence(id="X", text="x", gold=gold)


TRADES_OCT_SELLS = Gold(tool="list_trades", first_day=OCT_1, last_day=OCT_31, side="sell")


def test_the_set_holds_q1_to_q6_with_their_first_words_and_new_sentences() -> None:
    first = {one.id: one.text for one in load_tool_set().sentences}
    ids = [one.id for one in SET.sentences]

    assert ids[:6] == list(FIRST_SIX)
    for one in SET.sentences[:6]:
        assert one.text == first[one.id]
    assert len(SET.sentences) - 6 >= 12
    assert SET.now.isoformat() == "2026-11-24T23:55:00+01:00"
    assert SET.zone == "Europe/Budapest"


def test_the_set_covers_every_tool_both_languages_a_follow_up_and_what_cannot_be_answered() -> None:
    tools = {gold.tool for one in SET.sentences for gold in one.gold}
    texts = [one.text for one in SET.sentences]

    assert {"list_trades", "get_period_summary", "get_positions", "list_assets"} <= tools
    assert sum(gold.tool == "no_tool" for one in SET.sentences for gold in one.gold) >= 2
    assert any(gold.tool == "no_such_asset" for one in SET.sentences for gold in one.gold)
    assert any(len(group.sentences) == 2 for group in SET.groups)
    assert any(text.isascii() for text in texts)
    assert any(not text.isascii() for text in texts)
    assert any("买卖" in text for text in texts)


def test_the_same_tool_and_conditions_are_right() -> None:
    found = Found(tool="list_trades", first_day=OCT_1, last_day=OCT_31, side="sell")

    assert judge_answer(sentence(TRADES_OCT_SELLS), found) is Verdict.RIGHT


def test_both_sides_where_one_was_asked_is_wider() -> None:
    found = Found(tool="list_trades", first_day=OCT_1, last_day=OCT_31)

    assert judge_answer(sentence(TRADES_OCT_SELLS), found) is Verdict.WIDER


def test_all_time_or_days_that_hold_the_gold_days_are_wider() -> None:
    gold = sentence(TRADES_OCT_SELLS)

    assert judge_answer(gold, Found(tool="list_trades", side="sell")) is Verdict.WIDER
    assert (
        judge_answer(
            gold,
            Found(
                tool="list_trades",
                first_day=date(2026, 9, 1),
                last_day=OCT_31,
                side="sell",
            ),
        )
        is Verdict.WIDER
    )


@pytest.mark.parametrize(
    "found",
    [
        Found(tool="list_trades", first_day=date(2026, 9, 1), last_day=date(2026, 9, 30)),
        Found(tool="list_trades", first_day=OCT_1, last_day=date(2026, 10, 15), side="sell"),
        Found(tool="list_trades", first_day=OCT_1, last_day=OCT_31, side="sell", asset="BTC"),
        Found(tool="list_trades", first_day=OCT_1, last_day=OCT_31, side="buy"),
        Found(tool="get_positions"),
    ],
    ids=["other days", "fewer days", "an asset not asked", "the other side", "another tool"],
)
def test_narrower_different_or_another_tool_is_off(found: Found) -> None:
    assert judge_answer(sentence(TRADES_OCT_SELLS), found) is Verdict.OFF


def test_no_table_where_one_was_wanted_is_no_table() -> None:
    assert judge_answer(sentence(TRADES_OCT_SELLS), Found()) is Verdict.NO_TABLE
    assert (
        judge_answer(sentence(TRADES_OCT_SELLS), Found(program_words="I could not read"))
        is Verdict.NO_TABLE
    )


def test_a_question_without_a_table_is_right_without_one_and_off_with_one() -> None:
    gold = sentence(Gold(tool="no_tool"))

    assert judge_answer(gold, Found()) is Verdict.RIGHT
    assert judge_answer(gold, Found(tool="get_positions")) is Verdict.OFF


def test_an_asset_the_ledger_lacks_is_right_when_the_program_names_it() -> None:
    gold = sentence(Gold(tool="no_such_asset", word="DOGE"))
    said = "The ledger has no asset called 'DOGE', so I looked nothing up."

    assert judge_answer(gold, Found(program_words=said)) is Verdict.RIGHT
    assert judge_answer(gold, Found()) is Verdict.NO_TABLE
    assert judge_answer(gold, Found(tool="list_trades")) is Verdict.WIDER
    assert judge_answer(gold, Found(tool="list_trades", asset="BTC")) is Verdict.OFF


def test_either_of_two_gold_tools_may_be_right() -> None:
    gold = (
        Gold(tool="get_period_summary", first_day=OCT_1, last_day=OCT_31),
        Gold(tool="list_trades", first_day=OCT_1, last_day=OCT_31, side="buy"),
    )

    found = Found(tool="list_trades", first_day=OCT_1, last_day=OCT_31, side="buy")
    assert judge_answer(sentence(*gold), found) is Verdict.RIGHT
    summary = Found(tool="get_period_summary", first_day=OCT_1, last_day=OCT_31)
    assert judge_answer(sentence(*gold), summary) is Verdict.RIGHT


def test_the_three_pass_lines() -> None:
    every_right = dict.fromkeys([*FIRST_SIX, *(f"N{n}" for n in range(14))], Verdict.RIGHT)

    assert all(passes(every_right).values())
    assert not passes({**every_right, "N1": Verdict.OFF})["nothing narrower or off"]
    assert not passes({**every_right, "Q6": Verdict.WIDER})["Q1 to Q6 all right"]
    five_short = {**every_right, **dict.fromkeys(["N1", "N2", "N3", "N4", "N5"], Verdict.WIDER)}
    assert not passes(five_short)["at least 80% right"]
    four_short = {**every_right, **dict.fromkeys(["N1", "N2", "N3", "N4"], Verdict.WIDER)}
    assert passes(four_short)["at least 80% right"]


def test_the_runner_runs_each_group_as_one_chat_and_writes_a_line_a_sentence(
    tmp_path: Path,
) -> None:
    group = [
        {"id": "Q4", "text": "10月6号那天我都做了什么交易", "gold": [_gold_oct_6()]},
        {"id": "F2", "text": "那ETH呢", "gold": [_gold_oct_6("ETH")]},
    ]
    set_file = tmp_path / "asks.json"
    data = {"now": SET.now.isoformat(), "zone": SET.zone, "groups": [group]}
    set_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def asks(**arguments: object) -> ToolReply:
        return ToolReply(
            text="",
            calls=(ToolCall(name="list_trades", arguments=arguments),),
            record=scripted_record(),
        )

    model = ScriptedModel(
        [
            asks(period="10月6号"),
            "两笔。",
            asks(period="10月6号", asset="ETH"),
            "一笔 ETH。",
        ]
    )
    backend = Backend(
        model=model,
        name="scripted",
        fingerprint="f",
        server_version="v",
        base_url="b",
        parameters={},
    )
    path = tmp_path / "run.jsonl"

    rows = ask_run.run(backend, set_file, path, 6)

    assert [verdict for _, _, verdict, _ in rows] == [Verdict.RIGHT, Verdict.RIGHT]
    assert "10月6号那天我都做了什么交易" in repr(model.calls[2].items)
    lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert [line["id"] for line in lines] == ["Q4", "F2"]
    assert lines[1]["found"] == {
        "tool": "list_trades",
        "from": "2026-10-06",
        "to": "2026-10-06",
        "asset": "ETH",
        "side": None,
    }
    assert lines[0]["words_by"] == "the model"
    table = markdown(rows, {"model": "scripted", "prompt": "p"})
    assert "looked up right on 2 of 2 sentences" in table


def _gold_oct_6(asset: str | None = None) -> dict[str, object]:
    return {
        "tool": "list_trades",
        "from": "2026-10-06",
        "to": "2026-10-06",
        "asset": asset,
        "side": None,
    }


def test_a_set_with_a_gold_answer_of_one_day_only_is_refused(tmp_path: Path) -> None:
    broken = {
        "now": SET.now.isoformat(),
        "zone": SET.zone,
        "groups": [
            [{"id": "X", "text": "x", "gold": [{"tool": "list_trades", "from": "2026-10-01"}]}]
        ],
    }
    path = tmp_path / "asks.json"
    path.write_text(json.dumps(broken), encoding="utf-8")

    with pytest.raises(ValueError, match="both days or neither"):
        load_ask_set(path)
