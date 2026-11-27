"""Tests of a date the model put this year to, in a change or a deletion: let through or told.

One test for each line of the table of examples the rule was settled with,
numbered C1 to C19 as there. A scripted model stands in for every call;
"now" is 2026-11-27 18:00 in Budapest (C12 moves it to 2027-01-02). The
ledger holds two invented BTC buys, on 2026-08-03 and on 2025-08-03. Every
sentence is invented.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from ledger_hand.assistant.edit_calls import (
    EditCall,
    judge_edit,
    judge_edit_at,
    wrong_parts,
)
from ledger_hand.assistant.outcome import RefusedCall
from ledger_hand.core.ledger_records import Asset, AssetKind, Pricing, TradeFacts
from ledger_hand.core.trade import Side
from ledger_hand.flows.conversation import AssistantChat, Route, Said, say
from ledger_hand.flows.editing import EditEnding
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ports import Message, Role, ToolCall, ToolReply
from tests.fakes.scripted_model import ScriptedModel, Step, scripted_record

ZONE = "Europe/Budapest"
NOW = datetime(2026, 11, 27, 18, 0, tzinfo=ZoneInfo(ZONE))
THIS_YEAR = "read as this year"
NOT_AS_SAID = "Dates are taken only as you said them"


def _btc(year: int) -> TradeFacts:
    return TradeFacts(
        occurred=datetime(year, 8, 3, 10, 0, tzinfo=ZoneInfo(ZONE)),
        side=Side.BUY,
        asset="BTC",
        quantity=Decimal("0.01"),
        price=Decimal(60000),
        total=Decimal(600),
        quote="USDT",
        fee=Decimal(0),
        fee_asset="USDT",
        platform="Binance",
        note="",
        raw_text=None,
        zone=ZONE,
        date_only=False,
        cost_rate=None,
    )


def ledger() -> FakeLedger:
    return FakeLedger(
        assets=(
            Asset(
                id="a-usdt",
                code="USDT",
                name="USDT",
                kind=AssetKind.CASH,
                pricing=Pricing.CAN_PRICE,
            ),
            Asset(
                id="a-btc",
                code="BTC",
                name="BTC",
                kind=AssetKind.CRYPTO,
                pricing=Pricing.CANNOT_PRICE,
            ),
        ),  # fmt: skip
        trades=(("t-2026", _btc(2026)), ("t-2025", _btc(2025))),
        prices={},
    )


def _reply(*pairs: tuple[str, dict[str, object]]) -> ToolReply:
    return ToolReply(
        text="",
        calls=tuple(ToolCall(name=name, arguments=arguments) for name, arguments in pairs),
        record=scripted_record(),
    )


def update(period: str, new_value: str = "OKX") -> ToolReply:
    arguments = {"period": period, "asset": "BTC", "field": "platform", "new_value": new_value}
    return _reply(("propose_trade_update", arguments))


def delete(period: str) -> ToolReply:
    return _reply(("propose_trade_delete", {"period": period, "asset": "BTC"}))


def talk(said: str, steps: list[Step], now: datetime = NOW) -> tuple[Said, FakeLedger]:
    book = ledger()
    result = say(
        AssistantChat(),
        said,
        model=ScriptedModel(steps),
        ledger=book,
        now=now,
        zone=ZONE,
        max_steps=6,
    )
    return result, book


def proposed_on(book: FakeLedger) -> list[str]:
    return [call for call in book.calls if call.startswith("propose_")]


def told_not_as_said(said: Said, book: FakeLedger, written: str, yours: str) -> None:
    assert said.route is Route.TAKEOVER, said.reply
    assert NOT_AS_SAID in said.reply
    assert f'wrote "{written}"' in said.reply and f'you said "{yours}"' in said.reply
    assert THIS_YEAR not in said.reply
    assert proposed_on(book) == []


C1 = "把8月3号那笔BTC买入的平台改成OKX"
C5 = "把8月3号那笔BTC的平台改成OKX"


def test_c1_this_year_put_to_the_users_date_is_let_through() -> None:
    said, book = talk(C1, [update("2026年8月3号")])

    assert said.edited is not None and said.edited.ending is EditEnding.SENT, said.reply
    assert said.edit_sent is not None and said.edit_sent.trade == "t-2026"
    assert "read as this year (2026)" in said.reply


def test_c2_a_deletion_the_same() -> None:
    said, book = talk("把8月3号那笔BTC删掉", [delete("2026年8月3号")])

    assert said.edit_sent is not None and said.edit_sent.trade == "t-2026"
    assert "read as this year (2026)" in said.reply


def test_c3_the_users_words_copied_say_nothing_of_a_year() -> None:
    said, _ = talk(C1, [update("8月3号")])

    assert said.edit_sent is not None and said.edit_sent.trade == "t-2026"
    assert THIS_YEAR not in said.reply


def test_c4_the_users_own_year_copied_says_nothing_of_a_year() -> None:
    said, _ = talk("把2025年8月3号那笔BTC的平台改成OKX", [update("2025年8月3号")])

    assert said.edit_sent is not None and said.edit_sent.trade == "t-2025"
    assert THIS_YEAR not in said.reply


def test_c5_another_year_is_held_back_and_said() -> None:
    said, book = talk(C5, [update("2025年8月3号"), update("2025年8月3号")])

    told_not_as_said(said, book, "2025年8月3号", "8月3号")


def test_c6_last_year_said_holds_back_this_year() -> None:
    said, book = talk(
        "把去年8月3号那笔BTC的平台改成OKX", [update("2026年8月3号"), update("2026年8月3号")]
    )

    told_not_as_said(said, book, "2026年8月3号", "8月3号")


def test_c7_a_year_said_right_before_holds_it_back() -> None:
    said, book = talk(
        "把2025年8月3号那笔BTC的平台改成OKX", [update("2026年8月3号"), update("2026年8月3号")]
    )

    told_not_as_said(said, book, "2026年8月3号", "8月3号")


def test_c8_another_day_is_held_back_with_the_whole_sentence() -> None:
    said, book = talk(C5, [update("2026年8月4号"), update("2026年8月4号")])

    told_not_as_said(said, book, "2026年8月4号", C5)


def test_c9_a_date_written_another_way_is_held_back() -> None:
    said, book = talk(C5, [update("2026-8-3"), update("2026-8-3")])

    told_not_as_said(said, book, "2026-8-3", C5)


def test_c10_a_month_with_this_year_is_cut_as_before() -> None:
    said, book = talk(C5, [update("2026年8月")])

    assert said.edited is not None and said.edited.ending is EditEnding.TOLD
    assert said.reply.startswith("I could not tell which day's trade you mean")
    assert THIS_YEAR not in said.reply and NOT_AS_SAID not in said.reply
    assert proposed_on(book) == []


def test_c11_asking_the_ledger_is_not_let_through() -> None:
    said, book = talk(
        "我8月3号买了哪些BTC",
        [
            _reply(("list_trades", {"period": "2026年8月3号", "asset": "BTC"})),
            ToolReply(text="好的。", calls=(), record=scripted_record()),
        ],
    )

    assert said.turn is not None
    refused = said.turn.steps[0].calls[0]
    assert isinstance(refused, RefusedCall)
    assert NOT_AS_SAID not in said.reply and THIS_YEAR not in said.reply


def test_c12_a_year_not_this_one_is_held_back() -> None:
    later = datetime(2027, 1, 2, 18, 0, tzinfo=ZoneInfo(ZONE))
    said, book = talk(C1, [update("2026年8月3号"), update("2026年8月3号")], now=later)

    told_not_as_said(said, book, "2026年8月3号", "8月3号")


def test_c13_the_parts_of_a_call_let_through_are_not_wrong() -> None:
    call = ToolCall(
        name="propose_trade_update",
        arguments={"period": "2026年8月3号", "asset": "BTC", "field": "platform",
                   "new_value": "OKX"},
    )  # fmt: skip
    said = (C1,)
    taken = judge_edit(call, said, now=NOW, zone=ZONE)
    at = judge_edit_at(call, said, now=NOW, zone=ZONE)
    parts = wrong_parts(call, said, now=NOW, zone=ZONE)

    assert isinstance(taken, EditCall) and isinstance(at, EditCall)
    assert (taken.period, taken.this_year) == ("8月3号", 2026)
    assert at == taken
    assert not parts.period_wrong and not parts.new_value_wrong
    assert not isinstance(judge_edit(call, said), EditCall)


def test_c14_a_day_not_come_yet_this_year_is_held_back() -> None:
    said, book = talk("把12月5号那笔BTC删掉", [delete("2026年12月5号"), delete("2026年12月5号")])

    told_not_as_said(said, book, "2026年12月5号", "12月5号")
    assert '"2025年12月5号"' in said.reply


def test_c15_a_day_this_year_has_not_is_held_back() -> None:
    said, book = talk("把2月29号那笔BTC删掉", [delete("2026年2月29号"), delete("2026年2月29号")])

    told_not_as_said(said, book, "2026年2月29号", "2月29号")
    assert "list_trades" not in book.calls


def test_c16_last_years_said_apart_holds_it_back() -> None:
    said, book = talk(
        "把去年的8月3号那笔BTC的平台改成OKX", [update("2026年8月3号"), update("2026年8月3号")]
    )

    told_not_as_said(said, book, "2026年8月3号", "8月3号")


def test_c17_last_years_in_english_holds_it_back() -> None:
    sentence = "change the platform of last year's August 3 BTC trade to OKX"
    said, book = talk(sentence, [update("August 3, 2026"), update("August 3, 2026")])

    told_not_as_said(said, book, "August 3, 2026", "August 3")


def test_c18_another_year_in_english_is_held_back() -> None:
    sentence = "change the August 3, 2025 BTC trade's platform to OKX"
    said, book = talk(sentence, [update("August 3, 2026"), update("August 3, 2026")])

    told_not_as_said(said, book, "August 3, 2026", "August 3")


def test_c19_a_new_value_not_copied_is_still_a_wrong_step() -> None:
    said, book = talk(
        C1, [update("2026年8月3号", new_value="Okx交易所"), update("2026年8月3号", "Okx交易所")]
    )

    assert said.route is Route.TAKEOVER
    assert said.reply.startswith("I could not tell what you want it changed to")
    assert THIS_YEAR not in said.reply and NOT_AS_SAID not in said.reply
    assert proposed_on(book) == []


def test_the_model_ending_in_its_own_words_gets_the_line_added() -> None:
    said, _ = talk(
        C5,
        [
            update("2025年8月3号"),
            ToolReply(text="请再说一次。", calls=(), record=scripted_record()),
        ],
    )

    assert said.route is Route.MODEL
    assert said.reply.startswith("请再说一次。\n")
    assert NOT_AS_SAID in said.reply and 'you said "8月3号"' in said.reply
    assert said.state.chat.items[-1] == Message(Role.ASSISTANT, said.reply)
