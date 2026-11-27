"""Tests of a time said with another time zone named: the time cell marked, never converted.

One test for each line of the table of examples the rule was settled with,
numbered A1 to A20 as there. A scripted model stands in for every call;
"now" is 2026-11-27 18:00 in Budapest, the ledger's zone. Every sentence,
reply and number is invented.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from ledger_hand.core.ledger_records import Asset, AssetKind, Pricing
from ledger_hand.core.marks import Field, MarkKind
from ledger_hand.core.other_zone import (
    PLACE_ZONES,
    other_zone_words,
    own_zone_names,
)
from ledger_hand.core.spoken_text import SPOKEN_ZONES, tidy_spoken
from ledger_hand.flows.conversation import AssistantChat, Said, say
from ledger_hand.flows.recorded import RecordEnding
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ports import ToolCall, ToolReply
from tests.fakes.routed_model import RoutedModel
from tests.fakes.scripted_model import scripted_record
from tests.flows.scripted_flow import row, screened, table

ZONE = "Europe/Budapest"
NOW = datetime(2026, 11, 27, 18, 0, tzinfo=ZoneInfo(ZONE))
RECORD = ToolReply(
    text="", calls=(ToolCall(name="propose_trade_add", arguments={}),), record=scripted_record()
)
NOT_CONVERTED = "was not converted"

ETH = {"side": "buy", "coin": "ETH", "quantity": "0.1个ETH"}


def _asset(code: str, kind: AssetKind, pricing: Pricing = Pricing.CANNOT_PRICE) -> Asset:
    return Asset(id=f"asset-{code.lower()}", code=code, name=code, kind=kind, pricing=pricing)


def ledger(*, cards: bool = True) -> FakeLedger:
    """USDT prices trades; ETH and ADA have market prices in USDT on the day of "now"."""
    return FakeLedger(
        assets=(
            _asset("USDT", AssetKind.CASH, Pricing.CAN_PRICE),
            _asset("ETH", AssetKind.CRYPTO),
            _asset("ADA", AssetKind.CRYPTO),
        ),
        trades=(),
        prices={("ETH", "USDT"): Decimal("2701"), ("ADA", "USDT"): Decimal("0.5")},
        prices_on=date(2026, 11, 27),
        takes_unfinished=cards,
    )


def talk(
    said: str, rows: Sequence[dict[str, str]], *, cards: bool = True, book: FakeLedger | None = None
) -> Said:
    model = RoutedModel(
        tools=[RECORD],
        screen=[screened(("spot_trade", said[:6]))],
        extraction=[table(*(row(**cells) for cells in rows))],
    )
    return say(
        AssistantChat(),
        said,
        model=model,
        ledger=book if book is not None else ledger(cards=cards),
        now=NOW,
        zone=ZONE,
        max_steps=6,
    )


def sent(said: Said) -> Said:
    assert said.recorded is not None and said.recorded.ending is RecordEnding.SENT, said.reply
    return said


def time_mark(said: Said, place: int = 0, field: Field = Field.OCCURRED_TIME) -> tuple[str, str]:
    assert said.recorded is not None
    mark = said.recorded.marked[place].marks.on(field)
    assert mark is not None and mark.reason is not None, said.reply
    return mark.kind.value, mark.reason


def no_zone_mark(said: Said, place: int = 0) -> None:
    assert said.recorded is not None
    marks = said.recorded.marked[place].marks
    for field in (Field.OCCURRED_TIME, Field.OCCURRED_DATE):
        mark = marks.on(field)
        assert mark is None or "another time zone" not in (mark.reason or ""), mark
    assert NOT_CONVERTED not in said.reply


def suspicious_for(said: Said, words: str, place: int = 0, field: Field = Field.OCCURRED_TIME):
    kind, reason = time_mark(said, place, field)
    assert kind == MarkKind.SUSPICIOUS.value
    assert f'"{words}"' in reason and ZONE in reason, reason
    assert NOT_CONVERTED in said.reply


def sent_time(said: Said, place: int = 0) -> object:
    assert said.recorded is not None
    return said.recorded.trades[place].occurred


A1 = "按北京时间算，2026年11月20号下午3点在OKX买了0.1个ETH，成交价2700 USDT，手续费0.1 USDT"
A1_ROW = ETH | {
    "time": "2026年11月20号下午3点",
    "price": "2700 USDT",
    "fee": "0.1 USDT",
    "platform": "OKX",
}
A2 = (
    "按北京时间算，二零二六年十一月二十号下午三点在OKX买了0.1个ETH，成交价2700 USDT，手续费0.1 USDT"
)
A14 = "按北京时间算，下午3点买了0.1个ETH，2700 USDT，手续费0；下午4点买了1个ADA，0.5 USDT，手续费0"
TIME_1500 = datetime(2026, 11, 20, 15, 0, tzinfo=ZoneInfo(ZONE))


def test_a1_a_place_with_time_marks_the_time_and_sends_it_as_said() -> None:
    said = sent(talk(A1, [A1_ROW]))

    suspicious_for(said, "北京时间")
    assert sent_time(said) == TIME_1500
    assert said.recorded is not None
    sent_mark = [mark for mark in said.recorded.trades[0].marks if mark.field == "occurredTime"]
    assert sent_mark and sent_mark[0].kind == "suspicious"
    assert said.reply.count(NOT_CONVERTED) == 1
    assert 'you said "北京时间", another time zone' in said.reply


def test_a2_a_time_in_chinese_numerals_is_marked_too() -> None:
    a2 = A2
    said = sent(talk(a2, [A1_ROW | {"time": "二零二六年十一月二十号下午三点"}]))

    suspicious_for(said, "北京时间")
    assert sent_time(said) == TIME_1500


def test_a3_east_eight_is_marked() -> None:
    a3 = "东八区2026年11月20号15:00买了0.1个ETH，2700 USDT，手续费0"
    said = sent(talk(a3, [ETH | {"time": "2026年11月20号15:00", "price": "2700 USDT", "fee": "0"}]))

    suspicious_for(said, "东八区")


def test_a4_an_english_sentence_with_an_offset_is_marked() -> None:
    a4 = "Bought 0.1 ETH at 2700 USDT on 20 Nov 2026 at 15:00 UTC+8, fee 0"
    cells = {
        "side": "buy",
        "coin": "ETH",
        "quantity": "0.1 ETH",
        "price": "2700 USDT",
        "time": "20 Nov 2026 at 15:00",
        "fee": "0",
    }
    said = sent(talk(a4, [cells]))

    suspicious_for(said, "UTC+8")
    assert sent_time(said) == TIME_1500


def test_a5_words_between_the_place_and_time() -> None:
    a5 = "按纽约那个时间，2026年11月20号上午9点买了0.1个ETH，2700 USDT，手续费0"
    said = sent(
        talk(a5, [ETH | {"time": "2026年11月20号上午9点", "price": "2700 USDT", "fee": "0"}])
    )

    suspicious_for(said, "纽约那个时间")


def test_a6_us_shares_hours_count_as_new_york() -> None:
    a6 = "美股交易时间2026年11月20号上午10点买了0.1个ETH，2700 USDT，手续费0"
    said = sent(
        talk(a6, [ETH | {"time": "2026年11月20号上午10点", "price": "2700 USDT", "fee": "0"}])
    )

    suspicious_for(said, "美股交易时间")


def test_a7_a_place_before_the_time_of_the_trade() -> None:
    a7 = "北京的成交时间是2026年11月20号15:00，买了0.1个ETH，2700 USDT，手续费0"
    said = sent(talk(a7, [ETH | {"time": "2026年11月20号15:00", "price": "2700 USDT", "fee": "0"}]))

    suspicious_for(said, "北京的成交时间")


def test_a8_the_ledgers_own_zone_is_not_marked() -> None:
    a8 = "按匈牙利时间算，2026年11月20号下午3点买了0.1个ETH，2700 USDT，手续费0"
    said = sent(
        talk(a8, [ETH | {"time": "2026年11月20号下午3点", "price": "2700 USDT", "fee": "0"}])
    )

    no_zone_mark(said)


def test_a9_time_with_no_place_is_not_marked() -> None:
    a9 = "成交时间是2026年11月20号15:00，买了0.1个ETH，2700 USDT，手续费0"
    said = sent(talk(a9, [ETH | {"time": "2026年11月20号15:00", "price": "2700 USDT", "fee": "0"}]))

    no_zone_mark(said)


def test_a10_nothing_said_is_not_marked() -> None:
    a10 = "2026年11月20号下午3点买了0.1个ETH，2700 USDT，手续费0"
    said = sent(
        talk(a10, [ETH | {"time": "2026年11月20号下午3点", "price": "2700 USDT", "fee": "0"}])
    )

    no_zone_mark(said)


def test_a11_a_place_with_no_time_word_is_not_found() -> None:
    a11 = "按国内算，2026年11月20号下午3点买了0.1个ETH，2700 USDT，手续费0"
    said = sent(
        talk(a11, [ETH | {"time": "2026年11月20号下午3点", "price": "2700 USDT", "fee": "0"}])
    )

    no_zone_mark(said)


def test_a12_a_day_alone_has_its_day_marked() -> None:
    a12 = "北京时间2026年11月20号买了0.1个ETH，2700 USDT，手续费0"
    said = sent(talk(a12, [ETH | {"time": "2026年11月20号", "price": "2700 USDT", "fee": "0"}]))

    suspicious_for(said, "北京时间", field=Field.OCCURRED_DATE)
    assert said.recorded is not None
    assert said.recorded.marked[0].marks.on(Field.OCCURRED_TIME) is None
    fields = {mark.field for mark in said.recorded.trades[0].marks}
    assert "occurredDate" in fields and "occurredTime" not in fields


def test_a13_no_time_copied_gets_no_zone_mark() -> None:
    a13 = "按北京时间，成交价2700 USDT买了0.1个ETH，手续费0"
    said = sent(talk(a13, [ETH | {"price": "2700 USDT", "fee": "0"}]))

    no_zone_mark(said)
    assert said.recorded is not None
    assert Field.OCCURRED_DATE in said.recorded.marked[0].marks.empty
    assert "occurredDate" in said.recorded.trades[0].missing
    assert said.recorded.trades[0].occurred is None


def test_a14_every_trade_of_the_passage_is_marked() -> None:
    a14 = A14
    rows = [
        ETH | {"time": "下午3点", "price": "2700 USDT", "fee": "0"},
        {
            "side": "buy",
            "coin": "ADA",
            "quantity": "1个ADA",
            "time": "下午4点",
            "price": "0.5 USDT",
            "fee": "0",
        },
    ]
    said = sent(talk(a14, rows))

    suspicious_for(said, "北京时间", place=0)
    suspicious_for(said, "北京时间", place=1)
    assert said.reply.count(NOT_CONVERTED) == 2
    assert "Trade 1: you said" in said.reply and "Trade 2: you said" in said.reply


def test_a15_a_ledger_that_takes_no_cards_is_told_too() -> None:
    book = ledger(cards=False)
    said = sent(talk(A1, [A1_ROW], book=book))

    suspicious_for(said, "北京时间")
    assert "propose_add" in book.calls and "propose_cards" not in book.calls


def test_a16_a_price_far_off_keeps_its_own_mark() -> None:
    a16 = "按北京时间算，2026年11月20号下午3点买了0.1个ETH，成交价27 USDT，手续费0"
    said = sent(
        talk(a16, [ETH | {"time": "2026年11月20号下午3点", "price": "27 USDT", "fee": "0"}])
    )

    suspicious_for(said, "北京时间")
    assert said.recorded is not None
    price = said.recorded.marked[0].marks.on(Field.PRICE)
    assert price is not None and price.kind is MarkKind.SUSPICIOUS
    assert "far from the market price" in (price.reason or "")


def test_a17_a_place_with_no_time_word_after_it_is_not_marked() -> None:
    a17 = "在美股买的苹果股票，2026年11月20号15:00，成交价2700 USDT买了0.1个ETH，手续费0"
    said = sent(
        talk(a17, [ETH | {"time": "2026年11月20号15:00", "price": "2700 USDT", "fee": "0"}])
    )

    no_zone_mark(said)


def test_a18_a_place_four_characters_before_time_is_a_name() -> None:
    a18 = "中国平安成交时间是2026年11月20号9:30买了0.1个ETH成交价2700 USDT手续费0"
    said = sent(talk(a18, [ETH | {"time": "2026年11月20号9:30", "price": "2700 USDT", "fee": "0"}]))

    no_zone_mark(said)


def test_a19_the_ledgers_own_latin_name_is_not_marked() -> None:
    a19 = "2026年11月20号15:00 CET买了0.1个ETH，2700 USDT，手续费0"
    said = sent(
        talk(a19, [ETH | {"time": "2026年11月20号15:00", "price": "2700 USDT", "fee": "0"}])
    )

    no_zone_mark(said)


def test_a20_local_time_is_marked() -> None:
    a20 = "按当地时间2026年11月20号下午3点买了0.1个ETH，2700 USDT，手续费0"
    said = sent(
        talk(a20, [ETH | {"time": "2026年11月20号下午3点", "price": "2700 USDT", "fee": "0"}])
    )

    suspicious_for(said, "当地时间")


# --- the table of places, and the tidying left as it was ------------------------------


def test_every_place_the_tidying_knows_is_in_the_table_with_the_same_zone() -> None:
    for said, zone in SPOKEN_ZONES.items():
        place = said.removesuffix("时间")
        assert PLACE_ZONES.get(place) == zone, place


def test_the_ledgers_own_names_are_those_of_winter_and_summer() -> None:
    assert own_zone_names(ZONE, 2026) == frozenset({"CET", "CEST"})


@pytest.mark.parametrize(
    ("said", "found"),
    [
        ("at 3 pm Beijing local time bought 1 ETH", "Beijing local time"),
        ("give us time to buy 1 ETH", None),
        ("bought 1 ETH for 2000 USDT at 10:00", None),
        ("按布达佩斯的时间和北京时间", "北京时间"),
        ("按我那边的时区", "时区"),
        ("按布达佩斯当地时间", None),
        ("2026年11月20号15:00 CEST", None),
        ("2026年11月20号15:00 CET+1", "CET+1"),
    ],
)
def test_more_sayings(said: str, found: str | None) -> None:
    assert other_zone_words(said, ZONE, own_zone_names(ZONE, 2026)) == found


# What ``tidy_spoken`` gave for each sentence of the table before the marks were
# added (measured on the code before this rule): each sentence as it was said.
TIDIED_BEFORE = (
    A1,
    A2,
    "东八区2026年11月20号15:00买了0.1个ETH，2700 USDT，手续费0",
    "Bought 0.1 ETH at 2700 USDT on 20 Nov 2026 at 15:00 UTC+8, fee 0",
    "按纽约那个时间，2026年11月20号上午9点买了0.1个ETH，2700 USDT，手续费0",
    "美股交易时间2026年11月20号上午10点买了0.1个ETH，2700 USDT，手续费0",
    "北京的成交时间是2026年11月20号15:00，买了0.1个ETH，2700 USDT，手续费0",
    "按匈牙利时间算，2026年11月20号下午3点买了0.1个ETH，2700 USDT，手续费0",
    "成交时间是2026年11月20号15:00，买了0.1个ETH，2700 USDT，手续费0",
    "2026年11月20号下午3点买了0.1个ETH，2700 USDT，手续费0",
    "按国内算，2026年11月20号下午3点买了0.1个ETH，2700 USDT，手续费0",
    "北京时间2026年11月20号买了0.1个ETH，2700 USDT，手续费0",
    "按北京时间，成交价2700 USDT买了0.1个ETH，手续费0",
    A14,
    "按北京时间算，2026年11月20号下午3点买了0.1个ETH，成交价27 USDT，手续费0",
    "在美股买的苹果股票，2026年11月20号15:00，成交价2700 USDT买了0.1个ETH，手续费0",
    "中国平安成交时间是2026年11月20号9:30买了0.1个ETH成交价2700 USDT手续费0",
    "2026年11月20号15:00 CET买了0.1个ETH，2700 USDT，手续费0",
    "按当地时间2026年11月20号下午3点买了0.1个ETH，2700 USDT，手续费0",
)


@pytest.mark.parametrize("said", TIDIED_BEFORE)
def test_the_tidying_of_each_sentence_is_as_before(said: str) -> None:
    assert tidy_spoken(said, ZONE).text == said
