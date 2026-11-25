"""Tests of the shapes the ledger port uses: no money is assumed, and none is mixed.

Every trade names the money it is priced in and what its fee was taken in,
with no default for either, and nothing new in the package leans on the
old single money of the extraction (``core.ledger_limits.QUOTE_CURRENCY``).
Amounts are exact decimals; moments carry an offset; a buy carries no
profit of its own and a sell does.
"""

from __future__ import annotations

import dataclasses
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from ledger_hand.core import ledger_records, proposals
from ledger_hand.core.ledger_records import (
    CurrencyTotals,
    LedgerTrade,
    MoneyAmount,
    NotWorkedOut,
    PeriodRequest,
    PeriodSummary,
    Position,
    TradeFacts,
    TradeFilter,
)
from ledger_hand.core.proposals import CheckOutcome, ProposalResult, TradeCheck
from ledger_hand.core.trade import Side

PACKAGE = Path(ledger_records.__file__).resolve().parents[1]
# The parts this change added; none of them may name the old single money.
NEW_PARTS = (
    PACKAGE / "core" / "ledger_records.py",
    PACKAGE / "core" / "proposals.py",
    PACKAGE / "ledger",
    PACKAGE / "assistant",
    PACKAGE / "flows" / "assisting.py",
    PACKAGE / "flows" / "conversation.py",
    PACKAGE / "flows" / "recorded.py",
    PACKAGE / "flows" / "record_words.py",
    PACKAGE / "flows" / "proposing.py",
)
# No new part may name it any more.
OLD_MONEY_ALLOWED: dict[Path, int] = {}
WHEN = datetime(2026, 10, 6, 11, 48, tzinfo=timezone.utc)


def a_trade(**changed: object) -> TradeFacts:
    fields: dict[str, object] = {
        "occurred": WHEN,
        "side": Side.BUY,
        "asset": "BTC",
        "quantity": Decimal("0.0082"),
        "price": Decimal("61940"),
        "total": Decimal("507.908"),
        "quote": "USDT",
        "fee": Decimal("0.0000082"),
        "fee_asset": "BTC",
        "platform": "OKX",
        "note": "",
        "raw_text": "10月6号11:48在OKX买了0.0082 BTC，均价61940",
        "zone": "Europe/Budapest",
        "date_only": False,
        "cost_rate": None,
    }
    fields.update(changed)
    return TradeFacts(**fields)  # type: ignore[arg-type]


def test_a_trade_has_no_default_money_and_no_default_fee_asset() -> None:
    for shape in (TradeFacts, CurrencyTotals, Position, MoneyAmount):
        for field in dataclasses.fields(shape):
            assert field.default is dataclasses.MISSING, (shape.__name__, field.name)
            assert field.default_factory is dataclasses.MISSING, (shape.__name__, field.name)
    with pytest.raises(TypeError):
        TradeFacts(**{k: v for k, v in a_trade().__dict__.items() if k != "quote"})


def test_nothing_new_names_the_old_single_money() -> None:
    files = [
        path
        for part in NEW_PARTS
        for path in ([part] if part.is_file() else sorted(part.rglob("*.py")))
    ]

    assert files
    for path in files:
        lines = path.read_text(encoding="utf-8").splitlines()
        naming = [line for line in lines if "QUOTE_CURRENCY" in line]
        assert len(naming) == OLD_MONEY_ALLOWED.get(path, 0), (path, naming)


@pytest.mark.parametrize(
    "changed",
    [
        {"quantity": 0.5},
        {"quantity": Decimal("0")},
        {"fee": Decimal("-1")},
        {"price": Decimal("NaN")},
        {"occurred": datetime(2026, 10, 6)},
        {"quote": " "},
        {"side": "buy"},
    ],
    ids=[
        "a float",
        "nothing bought",
        "a fee below zero",
        "not a number",
        "no offset",
        "no money",
        "a bare word",
    ],
)
def test_a_trade_refuses_what_it_cannot_be(changed: dict[str, object]) -> None:
    with pytest.raises((TypeError, ValueError)):
        a_trade(**changed)


def test_a_buy_has_no_profit_and_a_sell_has_one_or_a_reason() -> None:
    with pytest.raises(ValueError):
        LedgerTrade(
            id="t",
            facts=a_trade(),
            realized=MoneyAmount(currency="USDT", amount=Decimal(1)),
            realized_unreliable=None,
            dated_after_today=False,
        )
    with pytest.raises(ValueError):
        LedgerTrade(
            id="t",
            facts=a_trade(side=Side.SELL),
            realized=None,
            realized_unreliable=None,
            dated_after_today=False,
        )

    assert LedgerTrade(
        id="t",
        facts=a_trade(side=Side.SELL),
        realized=NotWorkedOut(reason="why"),
        realized_unreliable=None,
        dated_after_today=False,
    )


def usdt_group(**changed: object) -> CurrencyTotals:
    zero = MoneyAmount(currency="USDT", amount=Decimal(0))
    fields: dict[str, object] = {
        "currency": "USDT",
        "buy_count": 3,
        "sell_count": 1,
        "spent": MoneyAmount(currency="USDT", amount=Decimal("13007.5")),
        "received": MoneyAmount(currency="USDT", amount=Decimal("2797")),
        "fees": (MoneyAmount(currency="USDT", amount=Decimal("10.5")),),
        "realized": MoneyAmount(currency="USDT", amount=Decimal("195")),
        "realized_from_sells": MoneyAmount(currency="USDT", amount=Decimal("195")),
        "realized_from_transfers": zero,
        "by_asset": (),
    }
    fields.update(changed)
    return CurrencyTotals(**fields)  # type: ignore[arg-type]


def test_one_money_is_summed_once() -> None:
    usdt = usdt_group()

    with pytest.raises(ValueError):
        PeriodSummary(request=PeriodRequest(), by_currency=(usdt, usdt))


def test_the_count_of_a_summary_is_every_groups_buys_and_sells_and_fees_add_by_asset() -> None:
    # Invented, as the ledger's all-time sample has it: 3 + 1 trades in USDT,
    # 2 + 1 in USD; 10.5 USDT of fees in the one group and 0.2 USDT in the other.
    usd = usdt_group(
        currency="USD",
        buy_count=2,
        sell_count=1,
        spent=MoneyAmount(currency="USD", amount=Decimal("2952")),
        received=MoneyAmount(currency="USD", amount=Decimal("1199")),
        fees=(
            MoneyAmount(currency="USD", amount=Decimal("3")),
            MoneyAmount(currency="USDT", amount=Decimal("0.2")),
        ),
        realized=MoneyAmount(currency="USD", amount=Decimal("48")),
        realized_from_sells=MoneyAmount(currency="USD", amount=Decimal("48")),
        realized_from_transfers=MoneyAmount(currency="USD", amount=Decimal(0)),
    )
    summary = PeriodSummary(request=PeriodRequest(), by_currency=(usd, usdt_group()))

    assert summary.trade_count == 7
    assert summary.fees == (
        MoneyAmount(currency="USD", amount=Decimal("3")),
        MoneyAmount(currency="USDT", amount=Decimal("10.7")),
    )


def test_a_sum_that_was_not_worked_out_is_its_reason_and_a_spent_sum_is_never_below_zero() -> None:
    assert usdt_group(spent=NotWorkedOut(reason="a buy's money could not be added")).spent
    with pytest.raises(ValueError):
        usdt_group(spent=MoneyAmount(currency="USDT", amount=Decimal("-1")))


def test_a_holding_is_costed_in_the_money_it_was_bought_with() -> None:
    with pytest.raises(ValueError):
        Position(
            asset="MSFT",
            currency="USD",
            quantity=Decimal(2),
            cost=MoneyAmount(currency="USDT", amount=Decimal(800)),
            unrealized=NotWorkedOut(reason="no market price"),
            cost_unreliable=None,
        )


def test_a_filter_ends_after_it_starts_and_counts_both_its_days() -> None:
    with pytest.raises(ValueError):
        TradeFilter(first_day=date(2026, 11, 2), last_day=date(2026, 11, 1))
    with pytest.raises(TypeError):
        TradeFilter(first_day=WHEN)  # type: ignore[arg-type]

    one_day = TradeFilter(first_day=WHEN.date(), last_day=WHEN.date())
    # 23:30 on 6 October in New York is 7 October in UTC; the trade's own day counts.
    late = a_trade(occurred=datetime(2026, 10, 6, 23, 30, tzinfo=ZoneInfo("America/New_York")))
    assert one_day.holds(a_trade()) and one_day.holds(late)
    assert not TradeFilter(first_day=date(2026, 10, 7)).holds(late)


def test_a_trade_known_only_to_its_day_holds_the_start_of_it() -> None:
    day_only = a_trade(occurred=datetime(2026, 11, 14, tzinfo=timezone.utc), date_only=True)

    assert day_only.day == date(2026, 11, 14)
    with pytest.raises(ValueError):
        a_trade(date_only=True)


def test_a_trade_with_no_words_of_the_user_holds_none_never_made_up_words() -> None:
    assert a_trade(raw_text=None).raw_text is None
    with pytest.raises(ValueError):
        a_trade(raw_text="  ")


def test_a_failed_check_has_a_code_and_a_sentence_and_a_passed_one_has_neither() -> None:
    with pytest.raises(ValueError):
        TradeCheck(outcome=CheckOutcome.FAILED, code="unknown_asset")
    with pytest.raises(ValueError):
        TradeCheck(outcome=CheckOutcome.PASSED, code="unknown_asset", message="No.")

    with pytest.raises(ValueError):
        TradeCheck(outcome=CheckOutcome.PASSED)
    with pytest.raises(ValueError):
        TradeCheck(outcome=CheckOutcome.FAILED, proposal_id="p-1", code="x", message="No.")

    result = ProposalResult(
        checks=(
            TradeCheck(outcome=CheckOutcome.PASSED, proposal_id="p-1"),
            TradeCheck(outcome=CheckOutcome.FAILED, code="unknown_asset", message="No DOGE."),
            TradeCheck(outcome=CheckOutcome.PASSED, proposal_id="p-2"),
        ),
    )
    assert not result.all_passed and not result.none_passed
    assert result.proposal_ids == ("p-1", "p-2")
    assert proposals.ProposalStatus.VOID.value == "void"
