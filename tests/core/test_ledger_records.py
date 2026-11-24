"""Tests of the shapes the ledger port uses: no money is assumed, and none is mixed.

Every trade names the money it is priced in and what its fee was taken in,
with no default for either, and nothing new in the package leans on the
old single money of the extraction (``core.ledger_limits.QUOTE_CURRENCY``).
Amounts are exact decimals; moments carry an offset; a buy carries no
profit of its own and a sell does.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

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
)
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
        assert "QUOTE_CURRENCY" not in path.read_text(encoding="utf-8"), path


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
            id="t", facts=a_trade(), realized=MoneyAmount(currency="USDT", amount=Decimal(1))
        )
    with pytest.raises(ValueError):
        LedgerTrade(id="t", facts=a_trade(side=Side.SELL), realized=None)

    assert LedgerTrade(id="t", facts=a_trade(side=Side.SELL), realized=NotWorkedOut(reason="why"))


def test_one_money_is_summed_once() -> None:
    usdt = CurrencyTotals(
        currency="USDT",
        spent=Decimal(1),
        received=Decimal(0),
        realized=MoneyAmount(currency="USDT", amount=Decimal(0)),
    )

    with pytest.raises(ValueError):
        PeriodSummary(request=PeriodRequest(), trade_count=1, by_currency=(usdt, usdt), fees=())


def test_a_holding_is_costed_in_the_money_it_was_bought_with() -> None:
    with pytest.raises(ValueError):
        Position(
            asset="MSFT",
            quote="USD",
            quantity=Decimal(2),
            cost=MoneyAmount(currency="USDT", amount=Decimal(800)),
            unrealized=NotWorkedOut(reason="no market price"),
        )


def test_a_filter_ends_after_it_starts() -> None:
    with pytest.raises(ValueError):
        TradeFilter(start=WHEN, end=WHEN)


def test_a_failed_check_has_a_code_and_a_sentence_and_a_passed_one_has_neither() -> None:
    with pytest.raises(ValueError):
        TradeCheck(outcome=CheckOutcome.FAILED, code="unknown_asset")
    with pytest.raises(ValueError):
        TradeCheck(outcome=CheckOutcome.PASSED, code="unknown_asset", message="No.")

    result = ProposalResult(
        checks=(
            TradeCheck(outcome=CheckOutcome.PASSED),
            TradeCheck(outcome=CheckOutcome.FAILED, code="unknown_asset", message="No DOGE."),
        ),
        proposal_id=None,
    )
    assert not result.all_passed
    assert proposals.ProposalStatus.VOID.value == "void"
