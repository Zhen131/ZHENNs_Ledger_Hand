"""Tests of asking the ledger through the assistant, with a scripted model and the fake ledger.

The program turns the period the model copied into days, checks the asset
and the side against what the user said, asks the ledger, lays the table
out, and checks the model's words beside it. Every reply is invented.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

from ledger_hand.assistant.explanation import AFTER_A_TABLE, NO_TABLE
from ledger_hand.assistant.lookups import MOST_TRADES_SHOWN, Lookup, lookup_lines
from ledger_hand.assistant.outcome import (
    Chat,
    Ending,
    NotRunCall,
    RefusedCall,
    TakenCall,
    TurnResult,
)
from ledger_hand.assistant.tools import ToolName
from ledger_hand.core.ledger_records import (
    MoneyAmount,
    NotWorkedOut,
    PeriodRequest,
    TradeFacts,
    TradeFilter,
)
from ledger_hand.core.trade import Side
from ledger_hand.flows.assisting import take_turn
from ledger_hand.flows.conversation import AssistantChat, say
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ledger.invented_book import INVENTED_NOW, INVENTED_TRADES, INVENTED_ZONE
from ledger_hand.ports import (
    LedgerPort,
    Message,
    Role,
    ToolCall,
    ToolCallTurn,
    ToolReply,
    ToolResult,
)
from tests.fakes.scripted_model import ScriptedModel, Step, scripted_record


def calls(*pairs: tuple[str, dict[str, object]], text: str = "") -> ToolReply:
    return ToolReply(
        text=text,
        calls=tuple(ToolCall(name=name, arguments=arguments) for name, arguments in pairs),
        record=scripted_record(),
    )


def turn(
    steps: list[Step],
    said: str,
    *,
    chat: Chat | None = None,
    ledger: LedgerPort | None = None,
) -> tuple[TurnResult, ScriptedModel]:
    model = ScriptedModel(steps)
    result = take_turn(
        chat or Chat(),
        said,
        model=model,
        ledger=ledger or FakeLedger(),
        now=INVENTED_NOW,
        zone=INVENTED_ZONE,
        max_steps=6,
    )
    return result, model


def only_lookup(result: TurnResult) -> Lookup:
    (lookup,) = result.lookups
    return lookup


# --- the period ------------------------------------------------------------------


def test_the_trades_of_6_october_are_exactly_two_and_the_header_says_the_day() -> None:
    result, _ = turn(
        [calls(("list_trades", {"period": "10月6号"})), "10月6号你做了两笔交易。"],
        "10月6号那天我都做了什么交易",
    )

    lookup = only_lookup(result)
    assert [trade.id for trade in lookup.trades] == ["t-05", "t-06"]
    lines = lookup_lines(lookup)
    assert lines[0] == "Time: 2026-10-06"
    assert "Asset: all assets" in lines
    assert "Side: buys and sells" in lines
    assert "Trades: 2" in lines
    assert result.ending is Ending.ANSWERED
    assert result.reply == "10月6号你做了两笔交易。"
    assert result.withheld is None


def test_a_month_runs_from_its_first_to_its_last_day_in_the_header() -> None:
    result, _ = turn(
        [calls(("get_period_summary", {"period": "10月"})), "Done."],
        "我10月一共买了多少钱的币？",
    )

    lookup = only_lookup(result)
    assert lookup.conditions is not None and lookup.conditions.period is not None
    assert lookup.conditions.period.first_day == date(2026, 10, 1)
    assert lookup.conditions.period.last_day == date(2026, 10, 31)
    assert lookup_lines(lookup)[:2] == ("Time: 2026-10-01 to 2026-10-31", "Asset: all assets")


def test_no_period_is_all_time() -> None:
    result, _ = turn([calls(("list_trades", {})), "Done."], "我所有的交易")

    lookup = only_lookup(result)
    assert lookup.trade_count == len(INVENTED_TRADES)
    assert lookup_lines(lookup)[0] == "Time: all time"


def test_a_period_with_two_meanings_asks_nothing_of_the_ledger_and_says_which_words() -> None:
    ledger = FakeLedger()

    result, model = turn(
        [calls(("list_trades", {"period": "12月"}))], "12月我买了什么", ledger=ledger
    )

    assert ledger.calls == []
    assert result.ending is Ending.ANSWERED_BY_PROGRAM
    assert "'12月'" in result.reply
    assert "more than one stretch of time" in result.reply
    assert len(model.calls) == 1
    assert result.lookups == ()


def test_a_period_not_read_and_one_in_the_future_are_said_by_the_program() -> None:
    unread, _ = turn([calls(("list_trades", {"period": "很久以前"}))], "很久以前我买了什么")
    future, _ = turn([calls(("get_period_summary", {"period": "明年"}))], "明年我会赚多少")

    assert unread.ending is Ending.ANSWERED_BY_PROGRAM
    assert "could not read '很久以前'" in unread.reply
    assert future.ending is Ending.ANSWERED_BY_PROGRAM
    assert "'明年' lies in the future" in future.reply


def test_after_the_program_answers_every_call_of_the_step_has_a_result() -> None:
    result, _ = turn(
        [
            calls(
                ("list_assets", {}),
                ("list_trades", {"period": "12月"}),
                ("get_positions", {}),
            )
        ],
        "12月我买了什么",
    )

    items = result.chat.items
    (kept,) = [item for item in items if isinstance(item, ToolCallTurn)]
    results = [item for item in items if isinstance(item, ToolResult)]
    assert [item.name for item in results] == [call.name for call in kept.calls]
    assert json.loads(results[1].content)["status"] == "answered_by_program"
    assert json.loads(results[2].content)["status"] == "not_run"
    assert items[-1] == Message(Role.ASSISTANT, result.reply)
    step = result.steps[0]
    assert [type(call) for call in step.calls] == [TakenCall, TakenCall, NotRunCall]


def test_the_next_turn_after_the_program_answers_holds_no_call_without_a_result() -> None:
    first, _ = turn([calls(("list_trades", {"period": "12月"}))], "12月我买了什么")

    second, model = turn(
        [calls(("list_trades", {"period": "2025年12月"})), "No trades."],
        "2025年12月",
        chat=first.chat,
    )

    sent = model.calls[0].items
    asked = [call for item in sent if isinstance(item, ToolCallTurn) for call in item.calls]
    answered = [item for item in sent if isinstance(item, ToolResult)]
    assert len(asked) == len(answered)
    assert second.ending is Ending.ANSWERED


def test_a_date_the_model_wrote_itself_is_still_a_wrong_step() -> None:
    result, _ = turn(
        [calls(("list_trades", {"period": "2026-10-06"})), "Sorry."],
        "10月6号那天我都做了什么交易",
    )

    (refused,) = result.steps[0].calls
    assert isinstance(refused, RefusedCall)


def test_the_period_may_be_copied_from_what_the_user_said_before() -> None:
    first, _ = turn(
        [calls(("list_trades", {"period": "10月", "asset": "BTC"})), "Done."],
        "10月我买了哪些BTC",
    )

    second, _ = turn(
        [calls(("list_trades", {"period": "10月", "asset": "ETH"})), "Done."],
        "那ETH呢",
        chat=first.chat,
    )

    lookup = only_lookup(second)
    assert lookup.conditions is not None and lookup.conditions.period is not None
    assert lookup.conditions.period.first_day == date(2026, 10, 1)
    assert lookup.conditions.asset == "ETH"
    assert {trade.facts.asset for trade in lookup.trades} == {"ETH"}


# --- the asset -------------------------------------------------------------------------


def test_an_asset_the_user_did_not_name_is_not_used_and_the_header_says_so() -> None:
    result, _ = turn(
        [calls(("list_trades", {"period": "上个月", "asset": "BTC", "side": "sell"})), "Done."],
        "上个月哪几笔卖出最赚钱",
    )

    lookup = only_lookup(result)
    assert not result.steps[0].wrong
    assert lookup.conditions is not None
    assert lookup.conditions.asset is None
    assert lookup.conditions.side is Side.SELL
    assert [trade.id for trade in lookup.trades] == ["t-07", "t-08"]
    lines = lookup_lines(lookup)
    assert "Asset: all assets" in lines
    assert "Not narrowed to BTC: you did not name it." in lines


def test_the_users_bitcoin_and_the_models_btc_are_used_and_are_no_wrong_step() -> None:
    result, _ = turn(
        [calls(("list_trades", {"period": "上个月", "asset": "BTC"})), "Done."],
        "我上个月买了多少比特币",
    )

    lookup = only_lookup(result)
    assert not result.steps[0].wrong
    assert lookup.conditions is not None and lookup.conditions.asset == "BTC"
    assert {trade.facts.asset for trade in lookup.trades} == {"BTC"}


def test_the_word_coin_is_dropped_and_every_asset_is_looked_up() -> None:
    result, _ = turn(
        [calls(("get_period_summary", {"period": "10月", "asset": "币"})), "Done."],
        "我10月一共买了多少钱的币？",
    )

    lookup = only_lookup(result)
    assert lookup.conditions is not None and lookup.conditions.asset is None
    assert lookup.summary is not None and lookup.summary.request.asset is None
    assert "Not narrowed to '币': it names no asset." in lookup_lines(lookup)


def test_an_asset_the_ledger_lacks_asks_nothing_and_is_named() -> None:
    ledger = FakeLedger()

    result, _ = turn(
        [calls(("list_trades", {"period": "10月", "asset": "DOGE"}))],
        "10月我买了多少DOGE",
        ledger=ledger,
    )

    assert result.ending is Ending.ANSWERED_BY_PROGRAM
    assert result.reply == "The ledger has no asset called 'DOGE', so I looked nothing up."
    assert "list_trades" not in ledger.calls


def test_an_asset_named_the_time_before_is_kept_when_none_is_named_now() -> None:
    first, _ = turn(
        [calls(("list_trades", {"period": "10月", "asset": "BTC"})), "Done."],
        "10月我买了哪些比特币",
    )

    second, _ = turn(
        [calls(("list_trades", {"period": "上个月", "asset": "BTC"})), "Done."],
        "那上个月呢",
        chat=first.chat,
    )

    lookup = only_lookup(second)
    assert lookup.conditions is not None and lookup.conditions.asset == "BTC"


def test_an_asset_that_is_not_text_is_still_a_wrong_step() -> None:
    result, _ = turn([calls(("list_trades", {"asset": 7})), "Sorry."], "BTC")

    (refused,) = result.steps[0].calls
    assert isinstance(refused, RefusedCall)


# --- the side ----------------------------------------------------------------------------


def test_buy_and_sell_said_together_drop_the_side() -> None:
    result, _ = turn(
        [calls(("list_trades", {"period": "最近7天", "side": "buy"})), "Done."],
        "最近7天我有没有买卖过东西",
    )

    lookup = only_lookup(result)
    assert lookup.conditions is not None and lookup.conditions.side is None
    assert "Side: buys and sells" in lookup_lines(lookup)
    assert "Not narrowed to buys: what you said does not name buys alone." in lookup_lines(lookup)
    assert [trade.id for trade in lookup.trades] == ["t-11"]


# --- the table ------------------------------------------------------------------------------


def test_a_summary_in_two_moneys_has_two_rows_never_added_together() -> None:
    ledger = FakeLedger()

    result, _ = turn(
        [calls(("get_period_summary", {"period": "10月"})), "Done."], "10月的汇总", ledger=ledger
    )

    lookup = only_lookup(result)
    assert lookup.summary is not None
    by_currency = {totals.currency: totals for totals in lookup.summary.by_currency}
    assert set(by_currency) == {"USD", "USDT"}
    assert by_currency["USDT"].spent == MoneyAmount(currency="USDT", amount=Decimal("874.808"))
    assert by_currency["USD"].spent == MoneyAmount(currency="USD", amount=Decimal("1237.11"))
    rows = [line for line in lookup_lines(lookup) if "spent on buys" in line]
    assert rows == [
        "USD | spent on buys 1237.11 | received from sells 0 | realized 0 USD",
        "USDT | spent on buys 874.808 | received from sells 920.32 | realized 99.25813637 USDT",
    ]
    assert "2111.918" not in "\n".join(lookup_lines(lookup))
    assert "Trades in this time: 5" in lookup_lines(lookup)


def test_every_figure_of_a_summary_is_the_ledgers_own_value() -> None:
    ledger = FakeLedger()
    result, _ = turn([calls(("get_period_summary", {})), "Done."], "全部的汇总", ledger=ledger)

    lookup = only_lookup(result)
    assert lookup.summary == FakeLedger().period_summary(PeriodRequest())
    lines = "\n".join(lookup_lines(lookup))
    for totals in lookup.summary.by_currency:
        assert isinstance(totals.spent, MoneyAmount)
        assert isinstance(totals.received, MoneyAmount)
        assert format(totals.spent.amount, "f") in lines
        assert format(totals.received.amount, "f") in lines
        assert isinstance(totals.realized, MoneyAmount)
        assert format(totals.realized.amount, "f") in lines
    for fee in lookup.summary.fees:
        assert f"fees taken in {fee.currency}: {format(fee.amount, 'f')}" in lines


def test_every_figure_of_the_holdings_is_the_ledgers_own_value() -> None:
    result, _ = turn([calls(("get_positions", {})), "Done."], "我现在手里有哪些币")

    lookup = only_lookup(result)
    assert lookup.positions == FakeLedger().positions()
    lines = lookup_lines(lookup)
    for position, line in zip(lookup.positions, lines, strict=True):
        assert line.startswith(f"{position.asset} | {format(position.quantity, 'f')} | ")
        assert f"cost {format(position.cost.amount, 'f')} {position.currency}" in line
        if isinstance(position.unrealized, NotWorkedOut):
            assert position.unrealized.reason in line
        else:
            assert format(position.unrealized.amount, "f") in line


def test_nothing_found_is_an_empty_table_with_one_fixed_line() -> None:
    result, _ = turn(
        [calls(("list_trades", {"period": "今天"})), "今天没有交易。"], "今天我买了什么"
    )

    lookup = only_lookup(result)
    assert lookup.trades == ()
    assert lookup.trade_count == 0
    assert lookup_lines(lookup)[-1] == "Nothing in the ledger matches."


def test_a_long_list_shows_the_latest_trades_and_says_how_many_there_are() -> None:
    first = INVENTED_TRADES[0][1]
    many = tuple(
        (
            f"t-{number:03d}",
            TradeFacts(
                occurred=first.occurred.replace(day=1 + number % 28, hour=number % 24),
                side=Side.BUY,
                asset="BTC",
                quantity=Decimal("0.001"),
                price=Decimal(60000 + number),
                total=Decimal(60 + number),
                quote="USDT",
                fee=Decimal("0"),
                fee_asset="USDT",
                platform="OKX",
                note="",
                raw_text=f"invented trade {number}",
                zone=None,
                date_only=False,
                cost_rate=None,
            ),
        )
        for number in range(MOST_TRADES_SHOWN + 5)
    )
    ledger = FakeLedger(trades=many)

    result, model = turn([calls(("list_trades", {})), "Done."], "我所有的交易", ledger=ledger)

    lookup = only_lookup(result)
    assert lookup.trade_count == MOST_TRADES_SHOWN + 5
    assert len(lookup.trades) == MOST_TRADES_SHOWN
    everything = ledger.list_trades(TradeFilter()).trades
    assert lookup.trades == everything[-MOST_TRADES_SHOWN:]
    assert f"Trades: {MOST_TRADES_SHOWN + 5}; shown: the latest {MOST_TRADES_SHOWN}" in (
        lookup_lines(lookup)
    )
    handed = json.loads(model.calls[1].items[-1].content)  # type: ignore[union-attr]
    assert handed["trade_count"] == MOST_TRADES_SHOWN + 5
    assert handed["shown"] == MOST_TRADES_SHOWN
    assert len(handed["trades"]) == MOST_TRADES_SHOWN


def test_the_model_is_handed_the_conditions_with_the_trades() -> None:
    result, model = turn(
        [calls(("list_trades", {"period": "10月6号"})), "Done."], "10月6号那天我都做了什么交易"
    )

    handed = json.loads(model.calls[1].items[-1].content)  # type: ignore[union-attr]
    assert handed["conditions"] == {
        "from": "2026-10-06",
        "to": "2026-10-06",
        "asset": "all assets",
        "side": "buys and sells",
    }
    assert [trade["id"] for trade in handed["trades"]] == ["t-05", "t-06"]


def test_two_read_tools_in_one_turn_give_two_tables_in_order() -> None:
    result, _ = turn(
        [calls(("list_assets", {})), calls(("get_positions", {})), "Done."], "我有哪些资产"
    )

    assert [lookup.tool for lookup in result.lookups] == [
        ToolName.LIST_ASSETS,
        ToolName.GET_POSITIONS,
    ]


# --- the model's words -----------------------------------------------------------------------


def test_words_whose_numbers_are_in_the_table_are_used_thousands_commas_and_all() -> None:
    result, _ = turn(
        [
            calls(("get_period_summary", {"period": "10月"})),
            "你10月一共交易了5笔，买入共 1,237.11 USD 和 874.808 USDT",
        ],
        "我10月一共买了多少钱的币？",
    )

    assert result.withheld is None
    assert result.reply == "你10月一共交易了5笔，买入共 1,237.11 USD 和 874.808 USDT"


def test_a_number_not_in_the_table_gives_way_to_the_programs_words() -> None:
    said = "我10月一共买了多少钱的币？"
    result, _ = turn(
        [calls(("get_period_summary", {"period": "10月"})), "你10月一共买入了 874.809 USDT"],
        said,
    )

    assert result.ending is Ending.ANSWERED
    assert result.reply == AFTER_A_TABLE
    assert result.withheld is not None
    assert result.withheld.reason == "874.809 is not in what the ledger returned"
    assert result.steps[-1].text == "你10月一共买入了 874.809 USDT"
    assert result.chat.items[-1] == Message(Role.ASSISTANT, AFTER_A_TABLE)
    assert "874.809" not in repr(result.chat.items)


def test_the_example_of_61940_against_a_table_that_holds_it() -> None:
    trades = tuple(
        (key, facts) for key, facts in INVENTED_TRADES if key in ("t-01", "t-05", "t-08")
    )
    ledger = FakeLedger(trades=trades)
    asked = [calls(("list_trades", {"period": "10月6号"}))]

    good, _ = turn([*asked, "你10月6号买入了一笔，均价 61,940 USDT"], "10月6号", ledger=ledger)
    bad, _ = turn([*asked, "你10月6号买入了一笔，均价 61,950 USDT"], "10月6号", ledger=ledger)

    assert good.withheld is None
    assert bad.reply == AFTER_A_TABLE


def test_an_answer_with_no_lookup_and_a_price_gives_way_to_the_programs_words() -> None:
    result, _ = turn(["比特币明天大概会涨到 65000"], "比特币明天会涨吗")

    assert result.ending is Ending.ANSWERED
    assert result.reply == NO_TABLE
    assert result.withheld is not None
    assert result.chat.items[-1] == Message(Role.ASSISTANT, NO_TABLE)


def test_an_answer_with_no_lookup_and_no_amount_is_used() -> None:
    result, _ = turn(["我只能帮你查账本，比如你可以问我 10 月的交易。"], "你好，你能帮我做什么？")

    assert result.reply == "我只能帮你查账本，比如你可以问我 10 月的交易。"
    assert result.withheld is None


def test_the_programs_own_answer_counts_as_well_ended_in_the_conversation() -> None:
    said = say(
        AssistantChat(),
        "12月我买了什么",
        model=ScriptedModel([calls(("list_trades", {"period": "12月"}))]),
        ledger=FakeLedger(),
        now=INVENTED_NOW,
        zone=INVENTED_ZONE,
        max_steps=6,
    )

    assert said.well_ended
    assert said.turn is not None and said.turn.ending is Ending.ANSWERED_BY_PROGRAM
    assert said.reply == said.turn.reply


def test_a_side_said_the_time_before_is_kept_when_none_is_said_now() -> None:
    first, _ = turn(
        [calls(("list_trades", {"period": "10月", "asset": "BTC", "side": "sell"})), "Done."],
        "10月我卖了哪些BTC",
    )

    second, _ = turn(
        [calls(("list_trades", {"period": "10月", "asset": "ETH", "side": "sell"})), "Done."],
        "那ETH呢",
        chat=first.chat,
    )

    lookup = only_lookup(second)
    assert lookup.conditions is not None
    assert lookup.conditions.side is Side.SELL
    assert lookup.conditions.not_narrowed == ()
    assert [trade.id for trade in lookup.trades] == ["t-07"]


def test_a_period_not_copied_is_handed_back_with_the_users_own_words() -> None:
    said = "How much did I spend on ETH this year?"

    result, model = turn(
        [calls(("get_period_summary", {"period": "今年", "asset": "ETH"})), "Sorry."], said
    )

    (refused,) = result.steps[0].calls
    assert isinstance(refused, RefusedCall)
    assert refused.misstep.kind.value == "not_copied"
    handed = json.loads(model.calls[1].items[-1].content)  # type: ignore[union-attr]
    assert handed["status"] == "wrong_step"
    assert handed["problem"] == refused.misstep.detail
    assert handed["user_said"] == said
    assert "in the language the user wrote it in" in handed["how"]
    assert "2026" not in refused.result
    assert refused.result == model.calls[1].items[-1].content  # type: ignore[union-attr]


def test_other_wrong_steps_are_handed_back_as_before() -> None:
    result, model = turn(
        [calls(("list_trades", {"from_date": "2026-10-06"})), "Sorry."],
        "10月6号那天我都做了什么交易",
    )

    handed = json.loads(model.calls[1].items[-1].content)  # type: ignore[union-attr]
    assert set(handed) == {"status", "kind", "problem"}


def test_a_bare_year_the_model_copied_is_not_read() -> None:
    ledger = FakeLedger()

    result, _ = turn(
        [calls(("list_trades", {"period": "2446"}))], "Which ETH did I buy at 2446?", ledger=ledger
    )

    assert result.ending is Ending.ANSWERED_BY_PROGRAM
    assert "could not read '2446'" in result.reply
    assert "list_trades" not in ledger.calls


def test_may_copied_alone_is_not_read_as_a_month() -> None:
    result, _ = turn([calls(("list_trades", {"period": "May"}))], "May I see my trades?")

    assert result.ending is Ending.ANSWERED_BY_PROGRAM
    assert "could not read 'May'" in result.reply
