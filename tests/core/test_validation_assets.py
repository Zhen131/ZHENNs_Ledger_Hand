"""Tests of the check of a draft against an asset table other than the built-in one.

With the table made for the tests (two moneys to price in, one that cannot,
a share, unseen assets refused), the check says which money a trade is
priced in, asks when it is not clear, and refuses what the table does not
hold. With the built-in table, the problems added for other tables never
come up, whatever is said. Every trade below is invented.
"""

from __future__ import annotations

import dataclasses
import itertools
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from ledger_hand.core.assets import BUILT_IN_ASSETS
from ledger_hand.core.coins import USDT_WORDS
from ledger_hand.core.followup import AskCell, Cell, next_follow_up
from ledger_hand.core.trade import OccurredTime, Side, TimePrecision, TradeDraft, TradeRecord
from ledger_hand.core.validation import DraftProblems, Missing, Violation, check_draft
from tests.core.two_moneys import TWO_MONEYS

BUDAPEST = "Europe/Budapest"
NOW = datetime(2026, 10, 4, 12, 0, tzinfo=ZoneInfo(BUDAPEST))
MORNING = OccurredTime(
    datetime(2026, 10, 4, 9, 40, tzinfo=ZoneInfo(BUDAPEST)), TimePrecision.MINUTE, BUDAPEST
)
# The problems only a table other than the built-in one can bring up.
NEW_PROBLEMS: frozenset[Missing | Violation] = frozenset(
    {
        Missing.QUOTE,
        Violation.COIN_IS_PRICING_MONEY,
        Violation.QUOTE_CANNOT_PRICE,
        Violation.ASSET_NOT_IN_LEDGER,
        Violation.FEE_ASSET_NOT_IN_LEDGER,
    }
)


def share(**changes: object) -> TradeDraft:
    """Two shares bought at 400 in USD, fee 1 USD: sound with the test table."""
    draft = TradeDraft(
        side=Side.BUY,
        coin="微软",
        quantity=Decimal("2"),
        price=Decimal("400"),
        quote="USD",
        fee=Decimal("1"),
        fee_coin="$",
        occurred=MORNING,
        raw_text="买了 2 股微软，400 美元一股，手续费 1 美元",
    )
    return dataclasses.replace(draft, **changes)  # type: ignore[arg-type]


def record_of(outcome: TradeRecord | DraftProblems) -> TradeRecord:
    assert isinstance(outcome, TradeRecord), outcome
    return outcome


def problems_of(outcome: TradeRecord | DraftProblems) -> DraftProblems:
    assert isinstance(outcome, DraftProblems), outcome
    return outcome


def check(draft: TradeDraft) -> TradeRecord | DraftProblems:
    return check_draft(draft, TWO_MONEYS, NOW)


# --- the money a trade is priced in -----------------------------------------


def test_a_share_priced_in_usd_is_recorded_priced_in_usd() -> None:
    built = record_of(check(share()))

    assert (built.coin, built.quote, built.fee_coin) == ("MSFT", "USD", "USD")
    assert built.total == Decimal("800")


def test_a_fee_of_zero_is_recorded_in_the_money_the_trade_is_priced_in() -> None:
    assert record_of(check(share(fee=Decimal("0"), fee_coin=None))).fee_coin == "USD"
    assert record_of(check(share(quote="U", fee=Decimal("0")))).fee_coin == "USDT"


@pytest.mark.parametrize("quote", [None, "", "  ", "刀"])
def test_no_money_said_or_one_both_moneys_go_by_asks_which(quote: str | None) -> None:
    problems = problems_of(check(share(quote=quote)))

    assert problems.missing == (Missing.QUOTE,)
    assert problems.violations == ()
    assert next_follow_up(share(quote=quote), problems) == AskCell(Cell.QUOTE, Missing.QUOTE)


@pytest.mark.parametrize("quote", ["欧元", "EUR", "BTC", "日元"])
def test_a_trade_priced_in_money_the_table_does_not_price_in_cannot_be_recorded(
    quote: str,
) -> None:
    assert problems_of(check(share(quote=quote))).violations == (Violation.QUOTE_CANNOT_PRICE,)


# --- the asset traded ---------------------------------------------------------


@pytest.mark.parametrize("coin", ["USD", "美元", "U", "刀"])
def test_a_money_trades_are_priced_in_cannot_be_the_asset_traded(coin: str) -> None:
    problems = problems_of(check(share(coin=coin, fee_coin="USD")))

    assert problems.violations == (Violation.COIN_IS_PRICING_MONEY,)
    assert problems.missing == ()


def test_an_asset_the_table_does_not_hold_cannot_be_recorded_and_is_not_offered() -> None:
    problems = problems_of(check(share(coin="SOL")))

    assert problems.violations == (Violation.ASSET_NOT_IN_LEDGER,)
    assert Missing.COIN_CONFIRMATION not in problems.missing


def test_a_word_that_cannot_be_a_symbol_is_still_asked_again() -> None:
    assert problems_of(check(share(coin="某某币"))).violations == (Violation.COIN_NOT_A_SYMBOL,)


# --- the fee's coin -----------------------------------------------------------


def test_a_fee_paid_in_a_word_both_moneys_go_by_asks_for_the_fee_s_coin() -> None:
    problems = problems_of(check(share(fee_coin="刀")))

    assert problems.missing == (Missing.FEE_COIN,)
    assert next_follow_up(share(fee_coin="刀"), problems) == AskCell(
        Cell.FEE_COIN, Missing.FEE_COIN
    )


def test_a_fee_paid_in_the_other_money_or_an_asset_of_the_table_passes() -> None:
    assert record_of(check(share(fee_coin="泰达币"))).fee_coin == "USDT"
    assert record_of(check(share(fee_coin="BTC", fee=Decimal("0.00001")))).fee_coin == "BTC"


def test_a_fee_paid_in_an_asset_the_table_does_not_hold_cannot_be_recorded() -> None:
    problems = problems_of(check(share(fee_coin="BNB")))

    assert problems.violations == (Violation.FEE_ASSET_NOT_IN_LEDGER,)
    assert Missing.FEE_COIN_CONFIRMATION not in problems.missing


# --- the built-in table never brings them up ------------------------------------

_QUOTES = [None, "", *sorted(USDT_WORDS), "u", "刀", "BTC", "欧元", "EUR", "日元", "PIKA"]
_COINS = [None, "BTC", "比特币", "PIKA", "某某币", "USDT", "美元", "刀", "U", "USD"]
_FEE_COINS = [None, "USDT", "U", "刀", "美元", "BTC", "BNB", "PIKA", "某某币"]
_FEES = [None, Decimal("0"), Decimal("0.5")]


@pytest.mark.parametrize("quote", _QUOTES)
def test_the_built_in_table_never_asks_the_money_or_gives_the_new_reasons(
    quote: str | None,
) -> None:
    for coin, fee_coin, fee in itertools.product(_COINS, _FEE_COINS, _FEES):
        draft = share(quote=quote, coin=coin, fee_coin=fee_coin, fee=fee)
        outcome = check_draft(draft, BUILT_IN_ASSETS, NOW)
        if isinstance(outcome, TradeRecord):
            assert outcome.quote == "USDT"
            continue
        found = set(outcome.missing) | set(outcome.violations)
        assert not found & NEW_PROBLEMS, (draft, found)
        assert next_follow_up(draft, outcome) != AskCell(Cell.QUOTE, Missing.QUOTE)
