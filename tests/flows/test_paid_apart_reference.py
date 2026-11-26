"""Tests of what the rate of a trade paid in another money is compared with, and how far is far.

The reference is the latest trade in the ledger paid in the same money for
an asset priced in the same money: first among the asset's own trades as
listed when its money was looked up, then among the ledger's trades asked
once with no condition; with neither, nothing is compared and the reply
says so. Far is more than ten in a hundred by default, the setting
``LEDGER_HAND_RATE_GAP_PERCENT`` changes it, and exactly that share is not
far. Every sentence and number is invented.
"""

from __future__ import annotations

from decimal import Decimal

from ledger_hand.core.marks import MarkKind
from ledger_hand.flows.conversation import AssistantChat, Said, say
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ledger.invented_book import INVENTED_NOW, INVENTED_ZONE
from ledger_hand.settings import DEFAULT_RATE_GAP_PERCENT
from tests.fakes.routed_model import RoutedModel
from tests.flows import paid_apart_books as books
from tests.flows.scripted_flow import row, screened, table
from tests.flows.test_paid_apart_examples import E1, E1_ROW, KO, NO_REFERENCE, RECORD

# 2 shares at 55 USD for 100 EUR: a rate of exactly 1.1.
ONE_POINT_ONE = "今天15:30花了100欧元买了2股KO，一股55美元，手续费0"
ONE_POINT_ONE_ROW = KO | {"price": "55美元", "total": "100欧元", "fee": "0"}


def said_with(
    words: str, cells: dict[str, str], ledger: FakeLedger, gap: Decimal = DEFAULT_RATE_GAP_PERCENT
) -> Said:
    model = RoutedModel(
        tools=[RECORD],
        screen=[screened(("spot_trade", words[:6]))],
        extraction=[table(row(**cells))],
    )
    return say(
        AssistantChat(),
        words,
        model=model,
        ledger=ledger,
        now=INVENTED_NOW,
        zone=INVENTED_ZONE,
        max_steps=6,
        rate_gap=gap,
    )


def ko_paid_in_euros(rate: str) -> FakeLedger:
    """The ``jia`` ledger with one more KO buy, paid in euros at ``rate``, on 1 November."""
    own = ("t-ko-eur", books.bought("KO", "EUR", (2026, 11, 1, 16, 0), "60", rate=rate))
    return books.jia((*books.JIA_TRADES, own))


def _rate_mark(said: Said) -> tuple[str, str]:
    assert said.recorded is not None
    (card,) = said.recorded.trades
    (mark,) = [mark for mark in card.marks if mark.field == "costRate"]
    return mark.kind, mark.reason or ""


def test_the_assets_own_trade_paid_in_euros_is_the_reference_and_nothing_more_is_asked() -> None:
    ledger = ko_paid_in_euros("1.0859")

    said = said_with(E1, E1_ROW, ledger)

    assert said.recorded is not None
    (marked,) = said.recorded.marked
    assert marked.rate is not None and marked.rate.reference is not None
    assert (marked.rate.reference.trade_id, marked.rate.reference.asset) == ("t-ko-eur", "KO")
    assert ledger.calls.count("list_trades") == 1


def test_another_asset_priced_in_dollars_is_the_reference_after_one_more_call() -> None:
    ledger = books.jia()

    said = said_with(E1, E1_ROW, ledger)

    assert said.recorded is not None
    (marked,) = said.recorded.marked
    assert marked.rate is not None and marked.rate.reference is not None
    assert (marked.rate.reference.trade_id, marked.rate.reference.asset) == ("t-aapl-eur", "AAPL")
    assert ledger.calls.count("list_trades") == 2
    assert NO_REFERENCE not in said.reply


def test_with_no_such_trade_nothing_is_compared_and_the_reply_says_so() -> None:
    trades = tuple(pair for pair in books.JIA_TRADES if pair[0] != books.AAPL_EUR[0])

    said = said_with(E1, E1_ROW, books.jia(trades))

    assert NO_REFERENCE in said.reply
    assert _rate_mark(said)[0] == MarkKind.COMPUTED.value


def test_by_default_a_rate_nine_and_a_half_in_a_hundred_away_is_not_far() -> None:
    # 1.0859375 against 1.2: about 9.5 in a hundred below.
    said = said_with(E1, E1_ROW, ko_paid_in_euros("1.2"))

    assert _rate_mark(said)[0] == MarkKind.COMPUTED.value
    assert "is far from" not in said.reply


def test_with_the_setting_at_five_the_same_rate_is_far() -> None:
    said = said_with(E1, E1_ROW, ko_paid_in_euros("1.2"), gap=Decimal(5))

    kind, reason = _rate_mark(said)
    assert kind == MarkKind.SUSPICIOUS.value
    assert "1.0859375 is far from 1.2 of the EUR trade on 2026-11-01" in reason
    assert "is far from 1.2" in said.reply


def test_exactly_ten_in_a_hundred_is_not_far() -> None:
    said = said_with(ONE_POINT_ONE, ONE_POINT_ONE_ROW, ko_paid_in_euros("1"))

    assert said.recorded is not None
    (card,) = said.recorded.trades
    assert card.cost_rate == Decimal("1.1")
    assert _rate_mark(said)[0] == MarkKind.COMPUTED.value


def test_a_little_more_than_ten_in_a_hundred_is_far() -> None:
    said = said_with(ONE_POINT_ONE, ONE_POINT_ONE_ROW, ko_paid_in_euros("0.999"))

    assert _rate_mark(said)[0] == MarkKind.SUSPICIOUS.value
