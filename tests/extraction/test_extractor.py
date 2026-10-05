"""Tests of extraction as a whole, with the scripted model playing the replies.

These are the scenarios the extraction has to get right whatever the model
does: what comes back, and how often the model is asked. Every passage and
every reply below is invented; no test talks to a real model.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from ledger_hand.core.coins import BUILT_IN_TABLE
from ledger_hand.core.ledger_limits import RAW_TEXT_MAX_LENGTH
from ledger_hand.core.numbers import Caution, Doubt
from ledger_hand.core.timeparse import Refusal, TimeCaution
from ledger_hand.core.trade import Side, TimePrecision, TradeDraft
from ledger_hand.core.validation import DraftProblems, Missing, Violation, check_draft
from ledger_hand.extraction.extractor import (
    DEFAULT_ASKS_AGAIN,
    MAX_ASKS_AGAIN,
    Extracted,
    ModelFailed,
    PassageProblem,
    PassageRefused,
    ReplyUnreadable,
)
from ledger_hand.extraction.issues import Issue, IssueKind
from ledger_hand.extraction.prompts.first import FIRST_PROMPT
from ledger_hand.extraction.reply_parser import ReplyProblem
from ledger_hand.extraction.reply_table import REPLY_TABLE, Field
from ledger_hand.ports import (
    FinishReason,
    ModelError,
    ModelErrorKind,
    ModelParameters,
    ModelReply,
    ReplyRecord,
    Role,
)
from tests.extraction.scripted_runs import NOW, ZONE, row, run, table

ONE_TRADE = "昨天晚上 9 点 40 在币安买了 0.02 个比特币，价格 94,900，手续费 2 USDT，我觉得要涨"
ONE_ROW = row(
    side="buy",
    coin="比特币",
    quantity="0.02 个比特币",
    price="94,900",
    fee="2 USDT",
    time="昨天晚上 9 点 40",
    platform="币安",
    opinion="我觉得要涨",
)
THREE_TRADES = (
    "今天下午 3 点在 OKX 买了 0.5 ETH，价格 3,420；"
    "sold 120 SOL at 182.4 yesterday, fee 0.3 USDT；"
    "还花 200U 买了 DOGE"
)
THREE_ROWS = (
    row(
        side="buy",
        coin="ETH",
        quantity="0.5 ETH",
        price="3,420",
        time="今天下午 3 点",
        platform="OKX",
    ),
    row(
        side="sell",
        coin="SOL",
        quantity="120 SOL",
        price="182.4",
        fee="0.3 USDT",
        time="yesterday",
    ),
    row(side="buy", coin="DOGE", total="200U"),
)


def extracted(passage: str, *steps: object, **options: object) -> Extracted:
    result, _ = run(passage, *steps, **options)  # type: ignore[arg-type]
    assert isinstance(result, Extracted), result
    return result


def issues_of(result: Extracted, kind: IssueKind) -> list[Issue]:
    return [issue for issue in result.issues if issue.kind is kind]


# --- X-1: one trade ------------------------------------------------------------


def test_one_trade_becomes_one_draft_with_every_field_converted() -> None:
    result = extracted(ONE_TRADE, table(ONE_ROW))

    (draft,) = result.drafts
    assert draft.side is Side.BUY
    assert draft.coin == "BTC"
    assert draft.quantity == Decimal("0.02")
    assert draft.price == Decimal("94900")
    assert draft.total is None
    assert draft.fee == Decimal("2")
    assert draft.fee_coin == "USDT"
    assert draft.quote is None
    assert draft.occurred is not None
    assert draft.occurred.value == datetime(2026, 10, 4, 21, 40, tzinfo=ZoneInfo(ZONE))
    assert draft.occurred.precision is TimePrecision.MINUTE
    assert draft.occurred.time_zone == ZONE
    assert draft.platform == "币安"
    assert draft.note == "我觉得要涨"
    assert draft.raw_text == ONE_TRADE
    assert draft.derived == frozenset()
    assert result.issues == ()


def test_the_draft_of_one_full_trade_passes_the_check() -> None:
    (draft,) = extracted(ONE_TRADE, table(ONE_ROW)).drafts

    record = check_draft(draft, BUILT_IN_TABLE, NOW)

    assert not isinstance(record, DraftProblems), record
    assert record.total == Decimal("1898")


# --- X-2: three trades -----------------------------------------------------------


def test_three_trades_become_three_drafts_that_keep_to_their_own_fields() -> None:
    result = extracted(THREE_TRADES, table(*THREE_ROWS))

    first, second, third = result.drafts
    assert (first.side, first.coin, first.quantity, first.price) == (
        Side.BUY,
        "ETH",
        Decimal("0.5"),
        Decimal("3420"),
    )
    assert first.fee is None and first.fee_coin is None and first.total is None
    assert first.platform == "OKX"
    assert first.occurred is not None and first.occurred.value.hour == 15
    assert (second.side, second.coin, second.quantity, second.price) == (
        Side.SELL,
        "SOL",
        Decimal("120"),
        Decimal("182.4"),
    )
    assert (second.fee, second.fee_coin, second.platform) == (Decimal("0.3"), "USDT", None)
    assert second.occurred is not None and second.occurred.value == date(2026, 10, 4)
    assert (third.side, third.coin, third.total, third.quote) == (
        Side.BUY,
        "DOGE",
        Decimal("200"),
        "U",
    )
    assert third.quantity is None and third.price is None and third.occurred is None
    assert all(draft.raw_text == THREE_TRADES for draft in result.drafts)
    assert result.issues == ()


# --- X-3: a phrase that is not in the passage ------------------------------------


def test_a_number_the_passage_does_not_hold_leaves_only_that_field_empty() -> None:
    rows = list(THREE_ROWS)
    rows[1] = {**rows[1], "price": "185.0"}

    result = extracted(THREE_TRADES, table(*rows))

    assert result.drafts[1].price is None
    assert result.drafts[1].quantity == Decimal("120")
    assert result.drafts[1].fee == Decimal("0.3")
    assert result.drafts[0].price == Decimal("3420")
    assert result.drafts[2].total == Decimal("200")
    assert issues_of(result, IssueKind.NOT_IN_PASSAGE) == [
        Issue(kind=IssueKind.NOT_IN_PASSAGE, draft=1, field=Field.PRICE, phrase="185.0")
    ]


@pytest.mark.parametrize(
    ("field", "phrase"),
    [
        ("coin", "Bitcoin"),
        ("quantity", "0.020"),
        ("price", "94900"),
        ("fee", "2.0"),
        ("time", "昨天 21:40"),
        ("platform", "Binance"),
        ("opinion", "看涨"),
        ("price_currency", "dollars"),
        ("fee_currency", "美元"),
    ],
)
def test_any_field_written_differently_from_the_passage_is_left_empty(
    field: str, phrase: str
) -> None:
    result = extracted(ONE_TRADE, table({**ONE_ROW, field: phrase}))

    issues = [issue for issue in result.issues if issue.field is Field(field)]
    assert [issue.kind for issue in issues] in (
        [IssueKind.NOT_IN_PASSAGE],
        [IssueKind.CUTS_A_NUMBER],
    )
    assert issues[0].draft == 0
    assert issues[0].phrase == phrase


def test_a_phrase_that_cuts_a_number_is_left_empty() -> None:
    result = extracted(ONE_TRADE, table({**ONE_ROW, "price": "94"}))

    assert result.drafts[0].price is None
    assert issues_of(result, IssueKind.CUTS_A_NUMBER) == [
        Issue(kind=IssueKind.CUTS_A_NUMBER, draft=0, field=Field.PRICE, phrase="94")
    ]


# --- X-4: empty, missing and extra fields ------------------------------------------


def test_empty_text_missing_fields_and_extra_fields_are_all_read() -> None:
    reply = table(
        {"side": "buy", "coin": "比特币", "price": "", "fee": "   ", "leverage": "10x"},
        {"coin": "ETH"},
    )
    passage = "买了比特币，也看了看 ETH"

    result = extracted(passage, reply)

    first, second = result.drafts
    assert (first.side, first.coin, first.price, first.fee) == (Side.BUY, "BTC", None, None)
    assert (second.side, second.coin) == (None, "ETH")
    assert result.issues == ()


# --- X-5: a reply that is not the table ---------------------------------------------


def test_a_bad_first_reply_is_asked_again_and_the_second_is_used() -> None:
    result, model = run(ONE_TRADE, "this is not JSON", table(ONE_ROW))

    assert isinstance(result, Extracted)
    assert result.drafts[0].coin == "BTC"
    assert len(model.calls) == 2
    assert len(result.calls) == 2


def test_two_bad_replies_give_a_clear_answer_and_nothing_raised() -> None:
    result, model = run(ONE_TRADE, "not JSON", '{"trades": [')

    assert result == ReplyUnreadable(
        (ReplyProblem.NOT_JSON, ReplyProblem.NOT_JSON),
        tuple(call.record for call in [_reply(), _reply()]),
    )
    assert len(model.calls) == 1 + DEFAULT_ASKS_AGAIN


def test_asking_again_says_what_was_wrong_and_keeps_everything_else() -> None:
    _, model = run(ONE_TRADE, '{"trades": {}}', table(ONE_ROW))

    first, second = model.calls
    assert second.messages[:-1] == first.messages
    note = second.messages[-1]
    assert note.role is Role.USER
    assert ReplyProblem.NO_TRADES_LIST.value in note.content
    assert second.reply_schema == first.reply_schema == REPLY_TABLE


@pytest.mark.parametrize("asks_again", [0, 1, 2, MAX_ASKS_AGAIN])
def test_the_caller_says_how_often_to_ask_again(asks_again: int) -> None:
    steps = ["no"] * (asks_again + 1)

    result, model = run(ONE_TRADE, *steps, asks_again=asks_again)

    assert isinstance(result, ReplyUnreadable)
    assert len(result.problems) == len(model.calls) == asks_again + 1
    assert model.steps_left == 0


def test_a_reply_cut_off_at_the_length_limit_is_asked_again() -> None:
    cut = ModelReply(text=table(ONE_ROW), record=_record(FinishReason.LENGTH_LIMIT))

    result, model = run(ONE_TRADE, cut, table(ONE_ROW))

    assert isinstance(result, Extracted)
    assert len(model.calls) == 2


@pytest.mark.parametrize("asks_again", [-1, MAX_ASKS_AGAIN + 1])
def test_asking_again_out_of_range_is_a_mistake_of_the_caller(asks_again: int) -> None:
    with pytest.raises(ValueError, match="asks_again"):
        run(ONE_TRADE, asks_again=asks_again)


@pytest.mark.parametrize("asks_again", [True, 1.0, "1", None])
def test_asking_again_must_be_a_whole_number(asks_again: object) -> None:
    with pytest.raises(TypeError, match="asks_again"):
        run(ONE_TRADE, asks_again=asks_again)


# --- X-6: no trade ------------------------------------------------------------------


def test_chatter_with_an_empty_list_gives_no_drafts_and_no_issues() -> None:
    result, model = run("今天行情好无聊，啥也没做，晚上看会儿书", '{"trades": []}')

    assert result == Extracted((), (), (_reply().record,))
    assert len(model.calls) == 1


def test_chatter_with_numbers_and_no_trade_names_the_numbers() -> None:
    result = extracted("BTC hit 70k today, not touching it", '{"trades": []}')

    assert result.drafts == ()
    assert result.issues == (Issue(kind=IssueKind.NUMBERS_LEFT_OVER, numbers=("70k",)),)


# --- X-7: a trade the model missed ----------------------------------------------------


def test_numbers_of_a_trade_the_model_missed_are_reported() -> None:
    passage = "买了 0.1 BTC，价格 60,000；又买了 2 ETH，价格 3,000"
    only_first = row(side="buy", coin="BTC", quantity="0.1 BTC", price="60,000")

    result = extracted(passage, table(only_first))

    assert len(result.drafts) == 1
    assert issues_of(result, IssueKind.NUMBERS_LEFT_OVER) == [
        Issue(kind=IssueKind.NUMBERS_LEFT_OVER, numbers=("2", "3,000"))
    ]


def test_a_number_written_twice_needs_two_trades_to_account_for_it() -> None:
    passage = "买了 0.1 BTC 和 0.1 ETH"
    btc = row(side="buy", coin="BTC", quantity="0.1 BTC")
    eth = row(side="buy", coin="ETH", quantity="0.1 ETH")

    one = extracted(passage, table(btc))
    both = extracted(passage, table(btc, eth))

    assert issues_of(one, IssueKind.NUMBERS_LEFT_OVER)[0].numbers == ("0.1",)
    assert issues_of(both, IssueKind.NUMBERS_LEFT_OVER) == []


def test_numbers_inside_a_copied_phrase_count_as_used_even_when_not_converted() -> None:
    passage = "大概 9 点多买了 1,5 个 ETH"
    reply = table(row(side="buy", coin="ETH", quantity="1,5 个 ETH", time="大概 9 点多"))

    result = extracted(passage, reply)

    assert issues_of(result, IssueKind.NUMBERS_LEFT_OVER) == []
    assert result.drafts[0].quantity is None and result.drafts[0].occurred is None


# --- X-8: a phrase the core cannot pin down ----------------------------------------


def test_a_number_the_core_is_unsure_of_is_left_empty_with_its_reason() -> None:
    passage = "买了 1,5 个 ETH"

    result = extracted(passage, table(row(side="buy", coin="ETH", quantity="1,5 个 ETH")))

    assert result.drafts[0].quantity is None
    assert result.issues == (
        Issue(
            kind=IssueKind.NUMBER_UNSURE,
            draft=0,
            field=Field.QUANTITY,
            phrase="1,5 个 ETH",
            cause=Doubt.AMBIGUOUS_SEPARATOR,
        ),
    )


def test_a_time_the_core_refuses_is_left_empty_with_its_reason() -> None:
    passage = "晚上 12 点买了 0.1 BTC"

    result = extracted(passage, table(row(side="buy", coin="BTC", time="晚上 12 点")))

    assert result.drafts[0].occurred is None
    assert issues_of(result, IssueKind.TIME_REFUSED) == [
        Issue(
            kind=IssueKind.TIME_REFUSED,
            draft=0,
            field=Field.TIME,
            phrase="晚上 12 点",
            cause=Refusal.AMBIGUOUS,
        )
    ]


@pytest.mark.parametrize(
    ("phrase", "reason"),
    [("明天", Refusal.IN_THE_FUTURE), ("差不多那会儿", Refusal.UNKNOWN_WORDING)],
)
def test_a_time_in_the_future_or_in_unknown_words_is_left_empty(
    phrase: str, reason: Refusal
) -> None:
    passage = f"{phrase}买 BTC"

    result = extracted(passage, table(row(side="buy", coin="BTC", time=phrase)))

    assert result.drafts[0].occurred is None
    assert result.issues[0].cause is reason


def test_a_number_that_is_not_a_number_is_left_empty() -> None:
    passage = "price was high, bought ETH"

    result = extracted(passage, table(row(side="buy", coin="ETH", price="high")))

    assert result.drafts[0].price is None
    assert result.issues == (
        Issue(kind=IssueKind.NOT_A_NUMBER, draft=0, field=Field.PRICE, phrase="high"),
    )


def test_a_unit_the_core_does_not_know_leaves_the_number_empty() -> None:
    passage = "bought 5000 sats worth of BTC"

    result = extracted(passage, table(row(side="buy", coin="BTC", quantity="5000 sats")))

    assert result.drafts[0].quantity is None
    assert result.issues[0].cause is Doubt.UNKNOWN_UNIT


# --- X-8b: read, with a caution ------------------------------------------------------


def test_a_time_read_with_a_caution_keeps_its_value() -> None:
    passage = "9:40 买了 0.1 BTC"

    result = extracted(passage, table(row(side="buy", coin="BTC", time="9:40")))

    occurred = result.drafts[0].occurred
    assert occurred is not None
    assert occurred.value == datetime(2026, 10, 5, 9, 40, tzinfo=ZoneInfo(ZONE))
    assert issues_of(result, IssueKind.TIME_CAUTION) == [
        Issue(
            kind=IssueKind.TIME_CAUTION,
            draft=0,
            field=Field.TIME,
            phrase="9:40",
            cause=TimeCaution.NO_HALF_OF_DAY,
        )
    ]


def test_a_half_of_the_day_without_a_clock_time_keeps_the_day() -> None:
    passage = "昨天晚上买了 BTC"

    result = extracted(passage, table(row(side="buy", coin="BTC", time="昨天晚上")))

    occurred = result.drafts[0].occurred
    assert occurred is not None and occurred.value == date(2026, 10, 4)
    assert result.issues[0].cause is TimeCaution.ONLY_A_HALF_OF_DAY


def test_a_number_read_with_a_caution_keeps_its_value() -> None:
    passage = "以 94.900 的价格买了 BTC"

    result = extracted(passage, table(row(side="buy", coin="BTC", price="94.900")))

    assert result.drafts[0].price == Decimal("94.900")
    assert result.issues == (
        Issue(
            kind=IssueKind.NUMBER_CAUTION,
            draft=0,
            field=Field.PRICE,
            phrase="94.900",
            cause=Caution.POINT_MAY_BE_THOUSANDS_SEPARATOR,
        ),
    )


# --- X-8c: the hour the clocks showed twice ------------------------------------------


def test_a_time_the_clocks_showed_twice_is_left_empty_with_both_candidates() -> None:
    passage = "10 月 25 号凌晨 2 点 30 卖了 1 ETH"
    after_the_change = datetime(2026, 10, 26, 12, 0, tzinfo=ZoneInfo(ZONE))
    reply = table(row(side="sell", coin="ETH", quantity="1 ETH", time="10 月 25 号凌晨 2 点 30"))

    result = extracted(passage, reply, now=after_the_change)

    assert result.drafts[0].occurred is None
    (issue,) = issues_of(result, IssueKind.TWO_TIMES)
    assert (issue.draft, issue.field) == (0, Field.TIME)
    earlier, later = issue.candidates
    assert earlier.value.utcoffset() == timedelta(hours=2)
    assert later.value.utcoffset() == timedelta(hours=1)
    assert earlier.value.replace(tzinfo=None) == later.value.replace(tzinfo=None)


# --- X-8d, X-8e: the unit that stood with a number ------------------------------------


def test_a_coin_as_the_unit_of_the_price_becomes_the_pricing_currency() -> None:
    passage = "用 0.05 BTC 一个的价格买了 2 ETH"
    reply = table(row(side="buy", coin="ETH", quantity="2 ETH", price="0.05 BTC"))

    (draft,) = extracted(passage, reply).drafts
    problems = check_draft(draft, BUILT_IN_TABLE, NOW)

    assert draft.quote == "BTC"
    assert draft.price == Decimal("0.05")
    assert isinstance(problems, DraftProblems)
    assert Violation.UNSUPPORTED_QUOTE in problems.violations


def test_a_word_for_usdt_as_the_unit_of_the_fee_becomes_the_fee_coin() -> None:
    passage = "买了 0.1 BTC，手续费 2 USDT"
    reply = table(row(side="buy", coin="BTC", quantity="0.1 BTC", fee="2 USDT"))

    (draft,) = extracted(passage, reply).drafts

    assert draft.fee == Decimal("2")
    assert draft.fee_coin == "USDT"


# --- X-8f: a coin the table does not know ---------------------------------------------


@pytest.mark.parametrize("written", ["BONK", "bonk", "Bonk"])
def test_a_coin_outside_the_table_becomes_a_capital_candidate_to_confirm(written: str) -> None:
    passage = f"买了 500 {written}，价格 0.00002"
    reply = table(row(side="buy", coin=written, quantity=f"500 {written}", price="0.00002"))

    result = extracted(passage, reply)
    (draft,) = result.drafts
    problems = check_draft(draft, BUILT_IN_TABLE, NOW)

    assert draft.coin == "BONK"
    assert draft.quantity == Decimal("500")
    assert isinstance(problems, DraftProblems)
    assert Missing.COIN_CONFIRMATION in problems.missing
    assert result.issues == ()


# --- X-9: passages that are not sent ----------------------------------------------------


@pytest.mark.parametrize(
    "passage",
    ["", " ", "\n\t", "\N{IDEOGRAPHIC SPACE}", "\N{BYTE ORDER MARK}", "\N{NO-BREAK SPACE}"],
)
def test_an_empty_passage_is_not_sent(passage: str) -> None:
    result, model = run(passage)

    assert result == PassageRefused(PassageProblem.EMPTY)
    assert model.calls == []


@pytest.mark.parametrize(
    "passage",
    [
        "买" * (RAW_TEXT_MAX_LENGTH + 1),
        "a" * (RAW_TEXT_MAX_LENGTH + 1),
        "\N{GRINNING FACE}" * (RAW_TEXT_MAX_LENGTH // 2 + 1),
        "x" * 5_000_000,
    ],
)
def test_a_passage_longer_than_the_ledger_keeps_is_not_sent(passage: str) -> None:
    result, model = run(passage)

    assert result == PassageRefused(PassageProblem.TOO_LONG)
    assert model.calls == []


def test_a_passage_just_within_the_limit_is_sent() -> None:
    passage = "买" * RAW_TEXT_MAX_LENGTH

    result, model = run(passage, '{"trades": []}')

    assert isinstance(result, Extracted)
    assert len(model.calls) == 1


@pytest.mark.parametrize("passage", ["买了 BTC \ud800", "\udc80", "ok\udfffok"])
def test_a_passage_that_is_not_valid_text_is_not_sent(passage: str) -> None:
    result, model = run(passage)

    assert result == PassageRefused(PassageProblem.NOT_VALID_TEXT)
    assert model.calls == []


# --- X-10: the model port's errors -------------------------------------------------------


@pytest.mark.parametrize("kind", list(ModelErrorKind))
def test_an_error_of_the_port_is_handed_back_as_raised_and_not_asked_again(
    kind: ModelErrorKind,
) -> None:
    error = ModelError(kind, "invented failure", status=503, snippet="oops")

    result, model = run(ONE_TRADE, error, table(ONE_ROW))

    assert isinstance(result, ModelFailed)
    assert result.error is error
    assert result.error.kind is kind
    assert result.calls == ()
    assert len(model.calls) == 1
    assert model.steps_left == 1


def test_an_error_after_a_bad_reply_is_handed_back_with_the_record_of_that_reply() -> None:
    error = ModelError(ModelErrorKind.TIMED_OUT, "invented")

    result, model = run(ONE_TRADE, "not JSON", error, table(ONE_ROW), asks_again=2)

    assert isinstance(result, ModelFailed)
    assert result.error is error
    assert len(result.calls) == 1
    assert len(model.calls) == 2


# --- what is sent ------------------------------------------------------------------------


def test_the_passage_is_sent_unchanged_with_the_table_and_the_callers_parameters() -> None:
    parameters = ModelParameters(
        temperature=0.0, top_p=1.0, max_reply_tokens=1024, context_tokens=8192, timeout_seconds=5
    )
    passage = "  买了 ０.１ BTC\n\n价格 6万  "

    _, model = run(passage, '{"trades": []}', parameters=parameters)

    (call,) = model.calls
    assert call.messages[-1].role is Role.USER
    assert call.messages[-1].content == passage
    assert call.messages[0].role is Role.SYSTEM
    assert call.messages[0].content == FIRST_PROMPT.instructions
    assert call.reply_schema == REPLY_TABLE
    assert call.parameters is parameters


def test_without_parameters_the_plugs_defaults_are_left_in_place() -> None:
    _, model = run(ONE_TRADE, table(ONE_ROW))

    assert model.calls[0].parameters is None


# --- rows the model gave oddly ---------------------------------------------------------


def test_a_row_with_every_field_empty_is_left_out_and_noted() -> None:
    empty = row()

    result = extracted(ONE_TRADE, table(empty, ONE_ROW, empty))

    assert len(result.drafts) == 1
    assert issues_of(result, IssueKind.EMPTY_ROW) == [
        Issue(kind=IssueKind.EMPTY_ROW),
        Issue(kind=IssueKind.EMPTY_ROW),
    ]


def test_a_row_given_twice_is_kept_twice_and_noted() -> None:
    result = extracted(ONE_TRADE, table(ONE_ROW, ONE_ROW, ONE_ROW))

    assert len(result.drafts) == 3
    assert issues_of(result, IssueKind.SAME_AS_ANOTHER) == [
        Issue(kind=IssueKind.SAME_AS_ANOTHER, draft=1, same_as=0),
        Issue(kind=IssueKind.SAME_AS_ANOTHER, draft=2, same_as=0),
    ]


def test_a_side_alone_is_a_row_and_stays() -> None:
    result = extracted("卖了", table(row(side="sell")))

    assert result.drafts == (TradeDraft(side=Side.SELL, raw_text="卖了"),)


def test_contradicting_fields_go_into_the_draft_as_they_are() -> None:
    passage = "0.5 ETH"
    reply = table(row(coin="ETH", quantity="0.5 ETH", price="0.5 ETH"))

    (draft,) = extracted(passage, reply).drafts

    assert draft.quantity == draft.price == Decimal("0.5")


# --- mistakes of the calling code ------------------------------------------------------


@pytest.mark.parametrize(
    "now", [datetime(2026, 10, 5, 22, 0), "2026-10-05T22:00:00+02:00", date(2026, 10, 5)]
)
def test_a_current_moment_without_an_offset_is_a_mistake_of_the_caller(now: object) -> None:
    with pytest.raises(ValueError, match="current moment"):
        run(ONE_TRADE, now=now)


@pytest.mark.parametrize("zone", ["europe/budapest", "localtime", "Factory", "", "UTC+2", None])
def test_a_zone_that_is_not_a_zone_name_is_a_mistake_of_the_caller(zone: object) -> None:
    with pytest.raises(ValueError, match="time zone"):
        run(ONE_TRADE, zone=zone)


def test_a_passage_that_is_not_text_is_a_mistake_of_the_caller() -> None:
    with pytest.raises(TypeError):
        run(b"bought BTC")  # type: ignore[arg-type]


def test_the_current_moment_may_be_given_in_any_zone() -> None:
    in_utc = NOW.astimezone(timezone.utc)

    (draft,) = extracted(ONE_TRADE, table(ONE_ROW), now=in_utc).drafts

    assert draft.occurred is not None
    assert draft.occurred.value == datetime(2026, 10, 4, 21, 40, tzinfo=ZoneInfo(ZONE))


def _record(finish: FinishReason = FinishReason.STOPPED) -> ReplyRecord:
    return ReplyRecord(
        model="scripted",
        elapsed_seconds=0.0,
        prompt_tokens=None,
        reply_tokens=None,
        finish=finish,
    )


def _reply() -> ModelReply:
    return ModelReply(text="", record=_record())
