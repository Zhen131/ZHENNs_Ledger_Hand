"""Tests of a rate compared with the ledger's own exchange rate, said aloud, one scenario each.

The trade: 2 shares of KO (priced in USD) bought on 2026-11-20 for 100 EUR
at 54 USD a share, so its rate is 2 × 54 ÷ 100 = 1.08 USD for 1 EUR; the
limit is ten in a hundred unless a test sets it. The ledgers are those of
``paid_apart_books`` (``jia``: its last trade paid in EUR is AAPL on
2026-11-03 at a rate of 1.0859), turned into ledgers with the tool for
exchange rates holding the rows each test gives. A scripted model stands
in for every call. Every rate, day and identifier is invented.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from ledger_hand.assistant.tools import tool_specs
from ledger_hand.core.cost_rate import RateNote
from ledger_hand.core.ledger_rate import LedgerRateOutcome, RateRow
from ledger_hand.core.ledger_records import AssetKind
from ledger_hand.core.marks import REASON_MOST, MarkKind, reason_length
from ledger_hand.core.trade_card import TradeCard
from ledger_hand.flows.conversation import AssistantChat, Said, say
from ledger_hand.flows.ledger_rates import looked_up
from ledger_hand.flows.recorded import RecordEnding
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ledger.invented_book import INVENTED_NOW, INVENTED_ZONE
from ledger_hand.ports import LedgerError, LedgerErrorKind, ToolCall, ToolReply
from tests.fakes.routed_model import RoutedModel
from tests.fakes.scripted_model import scripted_record
from tests.flows import paid_apart_books as books
from tests.flows.scripted_flow import row, screened, table

RECORD = ToolReply(
    text="", calls=(ToolCall(name="propose_trade_add", arguments={}),), record=scripted_record()
)
SAID = "11月20日15:30花了100欧元买了2股KO，一股54美元，换汇费0"
CELLS = {
    "side": "buy",
    "coin": "KO",
    "quantity": "2股",
    "price": "54美元",
    "total": "100欧元",
    "fee": "0",
    "time": "11月20日15:30",
}
NO_DAY_SAID = "花了100欧元买了2股KO，一股54美元，换汇费0"
NO_DAY_CELLS = {name: value for name, value in CELLS.items() if name != "time"}
EUR, USD = "asset-eur", "asset-usd"
WITHOUT_AAPL = tuple(trade for trade in books.JIA_TRADES if trade[0] != books.AAPL_EUR[0])


def rate(
    base: str, quote: str, value: str, day: str, source: str = "manual", online: str | None = None
) -> RateRow:
    return RateRow(
        base_id=base,
        base_code=base.removeprefix("asset-").upper(),
        quote_id=quote,
        quote_code=quote.removeprefix("asset-").upper(),
        rate=value,
        rate_date=day,
        source=source,
        online_source=online,
    )


def with_rates(
    *rows: RateRow,
    trades: tuple[tuple[str, object], ...] = books.JIA_TRADES,
    failure: LedgerError | None = None,
) -> FakeLedger:
    ledger = FakeLedger(
        assets=books.JIA_ASSETS,
        trades=trades,  # type: ignore[arg-type]
        prices=books.JIA_PRICES,
        rate_failure=failure,
    )
    return ledger.taking_cards().listing_rates(rows)


def said_to(
    ledger: FakeLedger,
    *,
    words: str = SAID,
    cells: dict[str, str] | None = None,
    rate_gap: Decimal = Decimal(10),
) -> Said:
    model = RoutedModel(
        tools=[RECORD],
        screen=[screened(("spot_trade", words[:6]))],
        extraction=[table(row(**(cells or CELLS)))],
        answers=[],
    )
    return say(
        AssistantChat(),
        words,
        model=model,
        ledger=ledger,
        now=INVENTED_NOW,
        zone=INVENTED_ZONE,
        max_steps=6,
        rate_gap=rate_gap,
    )


def sent_one(said: Said) -> tuple[TradeCard, RateNote]:
    recorded = said.recorded
    assert recorded is not None and recorded.ending is RecordEnding.SENT, said.reply
    (card,) = recorded.trades
    (marked,) = recorded.marked
    assert marked.rate is not None
    return card, marked.rate


def rate_mark(card: TradeCard) -> tuple[str, str]:
    (found,) = [(mark.kind, mark.reason) for mark in card.marks if mark.field == "costRate"]
    kind, reason = found
    assert reason is not None
    return kind, reason


def lines_with(said: Said, words: str) -> Sequence[str]:
    return [line for line in said.reply.splitlines() if words in line]


# 1
def test_the_same_rate_by_hand_on_the_day_is_not_marked_and_says_where_from() -> None:
    card, note = sent_one(said_to(with_rates(rate(EUR, USD, "1.08", "2026-11-20"))))

    assert card.cost_rate == Decimal("1.08")
    assert note.ledger is not None and note.ledger.outcome is LedgerRateOutcome.COMPARED
    assert not note.ledger.far and note.reference is None
    assert rate_mark(card)[0] != MarkKind.SUSPICIOUS.value


def test_the_reply_says_the_day_the_source_and_the_gap() -> None:
    said = said_to(with_rates(rate(EUR, USD, "1.08", "2026-11-20")))

    (line,) = lines_with(said, "compared with the ledger's exchange rate")
    assert "of 2026-11-20 (typed in by hand)" in line
    assert "1 EUR = 1.08 USD, which is 1.08 USD for 1 EUR" in line
    assert "They are 0.0% apart." in line
    assert "was not compared with one" not in said.reply


# 2
def test_a_row_the_other_way_round_is_said_as_stored_and_as_turned() -> None:
    online = rate(USD, EUR, "0.925", "2026-11-19", "online", "frankfurter")
    said = said_to(with_rates(online))
    card, note = sent_one(said)

    assert note.ledger is not None and note.ledger.picked is not None
    assert note.ledger.picked.inverted
    (line,) = lines_with(said, "compared with the ledger's exchange rate")
    assert "of 2026-11-19 (frankfurter): 1 USD = 0.925 EUR" in line
    assert "which is 1.0810810811 USD for 1 EUR" in line
    assert "They are 0.1% apart." in line
    assert rate_mark(card)[0] != MarkKind.SUSPICIOUS.value


# 3
def test_a_far_rate_is_marked_its_reason_the_ledgers_rate_and_day_then_source() -> None:
    said = said_to(with_rates(rate(EUR, USD, "1.30", "2026-11-20")))
    card, _ = sent_one(said)

    kind, reason = rate_mark(card)
    assert kind == MarkKind.SUSPICIOUS.value
    assert "far from the ledger's rate 1.3 USD for 1 EUR on 2026-11-20 (typed in by hand)" in (
        reason
    )
    (line,) = lines_with(said, "compared with the ledger's exchange rate")
    assert "They are 16.9% apart, more than 10%" in line
    assert "The rate is marked suspicious" in line


# 4
def test_about_eight_in_a_hundred_is_not_marked() -> None:
    card, note = sent_one(said_to(with_rates(rate(EUR, USD, "1.17", "2026-11-20"))))

    assert note.ledger is not None and not note.ledger.far
    assert rate_mark(card)[0] != MarkKind.SUSPICIOUS.value


# 5
def test_exactly_ten_in_a_hundred_is_not_marked_either_way_round() -> None:
    card, _ = sent_one(said_to(with_rates(rate(EUR, USD, "1.2", "2026-11-20"))))
    assert rate_mark(card)[0] != MarkKind.SUSPICIOUS.value

    # 2 × 62.5 ÷ 100 = 1.25, and 1.25 × 0.88 is exactly 1.1.
    cells = CELLS | {"price": "62.5美元"}
    words = SAID.replace("54美元", "62.5美元")
    said = said_to(with_rates(rate(USD, EUR, "0.88", "2026-11-20")), words=words, cells=cells)
    card, note = sent_one(said)
    assert card.cost_rate == Decimal("1.25")
    assert note.ledger is not None and note.ledger.gap == Decimal("0.1")
    assert rate_mark(card)[0] != MarkKind.SUSPICIOUS.value


# 6
def test_no_row_falls_back_to_the_last_trade_and_says_the_ledger_has_none() -> None:
    said = said_to(with_rates())
    _, note = sent_one(said)

    assert note.ledger is not None and note.ledger.outcome is LedgerRateOutcome.NONE_FITTING
    assert note.reference is not None and note.reference.trade_id == "t-aapl-eur"
    assert lines_with(said, "the ledger has no exchange rate between EUR and USD up to 2026-11-20")
    assert lines_with(said, "is close to 1.0859, the rate of the EUR trade on 2026-11-03")


def test_no_row_and_no_last_trade_is_not_compared() -> None:
    said = said_to(with_rates(trades=WITHOUT_AAPL))
    _, note = sent_one(said)

    assert note.reference is None
    assert lines_with(said, "the ledger has no exchange rate between EUR and USD")
    assert lines_with(said, "was not compared with one")


# 7
def test_only_a_later_row_is_none_fitting() -> None:
    said = said_to(with_rates(rate(EUR, USD, "1.5", "2026-11-25")))
    _, note = sent_one(said)

    assert note.ledger is not None and note.ledger.outcome is LedgerRateOutcome.NONE_FITTING
    assert lines_with(said, "the ledger has no exchange rate between EUR and USD")


# 8
def test_on_one_day_the_rate_typed_in_is_used() -> None:
    rows = (
        rate(USD, EUR, "0.70", "2026-11-20", "online", "frankfurter"),
        rate(EUR, USD, "1.08", "2026-11-20"),
    )
    _, note = sent_one(said_to(with_rates(*rows)))

    assert note.ledger is not None and note.ledger.picked is not None
    assert note.ledger.picked.row.by_hand and not note.ledger.far


def test_a_rate_long_before_is_still_compared_and_says_how_long() -> None:
    said = said_to(with_rates(rate(EUR, USD, "1.30", "2026-11-05")))
    card, note = sent_one(said)

    assert note.ledger is not None and note.ledger.days_apart == 15
    assert "15 days before the trade" in rate_mark(card)[1]
    assert lines_with(said, "the ledger's rate is 15 days older than the trade")


# 9
def test_a_ledger_with_no_tool_says_and_sends_what_it_did_before() -> None:
    old = books.jia()
    said = said_to(old)
    _, note = sent_one(said)

    assert note.ledger is not None and note.ledger.outcome is LedgerRateOutcome.NO_TOOL
    assert "exchange rate" not in said.reply
    assert "exchange_rates" not in old.calls


# 10
def test_a_ledger_that_kept_changing_is_said_and_the_trade_still_sent() -> None:
    changing = LedgerError(
        LedgerErrorKind.OTHER, "LEDGER_CHANGED_START_FROM_FIRST_PAGE", "Its own words."
    )
    said = said_to(with_rates(rate(EUR, USD, "1.30", "2026-11-20"), failure=changing))
    card, note = sent_one(said)

    assert note.ledger is not None and note.ledger.outcome is LedgerRateOutcome.NOT_READ
    (line,) = lines_with(said, "could not be read")
    assert "the ledger kept changing while they were read" in line
    assert "Its own words" not in said.reply
    assert note.reference is not None
    assert rate_mark(card)[0] != MarkKind.SUSPICIOUS.value


# 11
def test_a_refusal_for_a_money_that_is_not_cash_quotes_the_ledger_and_sends_the_card() -> None:
    refused = LedgerError(
        LedgerErrorKind.OTHER,
        "ASSET_IS_NOT_CURRENCY",
        "This id is a coin or a stock, not a cash currency.",
    )
    said = said_to(with_rates(failure=refused))
    _, note = sent_one(said)

    assert note.ledger is not None and note.ledger.outcome is LedgerRateOutcome.REFUSED
    (line,) = lines_with(said, "did not hand back its exchange rates")
    assert "(This id is a coin or a stock, not a cash currency)" in line


def test_a_money_that_is_not_cash_in_the_list_is_never_asked_about() -> None:
    assets = tuple(
        dataclasses.replace(one, kind=AssetKind.CRYPTO) if one.code == "USD" else one
        for one in books.JIA_ASSETS
    )
    ledger = FakeLedger(assets=assets, trades=books.JIA_TRADES, prices=books.JIA_PRICES)
    ledger = ledger.taking_cards().listing_rates([rate(EUR, USD, "1.30", "2026-11-20")])

    said = said_to(ledger)
    _, note = sent_one(said)

    assert "exchange_rates" not in ledger.calls
    assert note.ledger is not None and note.ledger.outcome is LedgerRateOutcome.NONE_FITTING
    assert lines_with(said, "the ledger has no exchange rate between EUR and USD")
    assert "ASSET_IS_NOT_CURRENCY" not in said.reply


def test_a_money_missing_from_the_list_or_shared_by_two_assets_is_never_asked_about() -> None:
    ledger = with_rates(rate(EUR, USD, "1.30", "2026-11-20"))
    held = {asset.code: asset for asset in books.JIA_ASSETS if asset.code != "USD"}

    found = looked_up(ledger, held, {("EUR", "USD"): [date(2026, 11, 20)]})

    assert found[("EUR", "USD")].outcome is LedgerRateOutcome.NONE_FITTING
    assert "exchange_rates" not in ledger.calls


# 12
def test_the_limit_comes_from_the_setting() -> None:
    rows = (rate(EUR, USD, "1.14", "2026-11-20"),)
    card, _ = sent_one(said_to(with_rates(*rows), rate_gap=Decimal(5)))
    assert rate_mark(card)[0] == MarkKind.SUSPICIOUS.value

    card, _ = sent_one(said_to(with_rates(*rows), rate_gap=Decimal(10)))
    assert rate_mark(card)[0] != MarkKind.SUSPICIOUS.value


# 13
def test_a_trade_with_no_day_is_compared_as_of_today_and_says_so() -> None:
    rows = (rate(EUR, USD, "1.30", "2026-11-24"), rate(EUR, USD, "1.08", "2026-11-23"))
    said = said_to(with_rates(*rows), words=NO_DAY_SAID, cells=NO_DAY_CELLS)
    recorded = said.recorded
    assert recorded is not None and recorded.ending is RecordEnding.SENT, said.reply
    (marked,) = recorded.marked
    note = marked.rate
    assert note is not None and note.ledger is not None
    assert not note.ledger.day_said and str(note.ledger.day) == "2026-11-24"
    assert note.ledger.picked is not None and note.ledger.picked.rate == Decimal("1.30")
    assert "no day was said, so it was compared as of today" in rate_mark(recorded.trades[0])[1]
    assert lines_with(said, "so it was compared as of today, 2026-11-24")


# 14
def test_a_ledger_rate_older_than_the_last_trade_is_not_used() -> None:
    yesterday = books.bought("AAPL", "EUR", (2026, 11, 19, 16, 0), "200", rate="1.0859")
    trades = (*WITHOUT_AAPL, ("t-aapl-eur-19", yesterday))
    said = said_to(with_rates(rate(EUR, USD, "1.5", "2025-10-16"), trades=trades))
    card, note = sent_one(said)

    assert note.ledger is not None
    assert note.ledger.outcome is LedgerRateOutcome.OLDER_THAN_TRADE
    assert note.reference is not None and note.reference.trade_id == "t-aapl-eur-19"
    assert rate_mark(card)[0] != MarkKind.SUSPICIOUS.value
    assert lines_with(said, "is of 2025-10-16, older than the EUR trade on 2026-11-19")


def test_a_ledger_rate_of_the_same_day_as_the_last_trade_is_used() -> None:
    same_day = books.bought("AAPL", "EUR", (2026, 11, 19, 16, 0), "200", rate="1.0859")
    trades = (*WITHOUT_AAPL, ("t-aapl-eur-19", same_day))
    _, note = sent_one(said_to(with_rates(rate(EUR, USD, "1.5", "2026-11-19"), trades=trades)))

    assert note.ledger is not None and note.ledger.outcome is LedgerRateOutcome.COMPARED
    assert note.ledger.far


# 15
def test_rows_that_do_not_read_are_passed_over_and_one_is_never_used() -> None:
    rows = tuple(
        rate(EUR, USD, text, "2026-11-20") for text in ("NaN", "Infinity", "0", "-1", "abc")
    )
    said = said_to(with_rates(*rows))
    _, note = sent_one(said)

    assert note.ledger is not None and note.ledger.outcome is LedgerRateOutcome.NONE_FITTING
    assert note.ledger.passed_over == 5


# 16
def test_out_of_time_says_so_and_the_trade_is_still_proposed() -> None:
    late = LedgerError(
        LedgerErrorKind.TIMED_OUT, "HAND_RATES_TIMED_OUT", "Out of time, as the plug says."
    )
    ledger = with_rates(rate(EUR, USD, "1.30", "2026-11-20"), failure=late)
    said = said_to(ledger)
    _, note = sent_one(said)

    assert note.ledger is not None and note.ledger.outcome is LedgerRateOutcome.NOT_READ
    assert lines_with(said, "could not be read (the ledger took too long to answer)")
    assert ledger.calls.index("exchange_rates") < ledger.calls.index("propose_add")


def test_both_far_keep_the_reason_within_the_ledgers_length_the_first_part_kept() -> None:
    cells = CELLS | {"price": "540美元", "total": "1000欧元"}
    words = SAID.replace("54美元", "540美元").replace("100欧元", "1000欧元")
    said = said_to(with_rates(rate(EUR, USD, "1.30", "2026-11-05")), words=words, cells=cells)
    card, note = sent_one(said)

    kind, reason = rate_mark(card)
    assert note.market_far and note.ledger is not None and note.ledger.far
    assert kind == MarkKind.SUSPICIOUS.value
    assert reason_length(reason) <= REASON_MOST
    assert "far from the ledger's rate 1.3 USD for 1 EUR on 2026-11-05" in reason


def test_the_rate_tool_is_never_handed_to_the_model_nor_its_words_sent_to_it() -> None:
    names = [spec.name for spec in tool_specs()]
    assert "list_exchange_rates" not in names
    assert not any("exchange" in name or "rate" in name for name in names)

    model = RoutedModel(
        tools=[RECORD],
        screen=[screened(("spot_trade", SAID[:6]))],
        extraction=[table(row(**CELLS))],
        answers=[],
    )
    say(
        AssistantChat(),
        SAID,
        model=model,
        ledger=with_rates(rate(EUR, USD, "1.30", "2026-11-20")),
        now=INVENTED_NOW,
        zone=INVENTED_ZONE,
        max_steps=6,
    )
    parts = (model.screen, model.extraction, model.tools, model.questions, model.answers)
    sent = json.dumps([repr(call) for part in parts for call in part.calls], ensure_ascii=False)
    assert model.tools.calls
    assert "list_exchange_rates" not in sent
    assert "far from the ledger's rate" not in sent
