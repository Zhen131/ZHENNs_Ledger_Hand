"""Tests of the real plug against the ledger's answers about three figures that do not agree.

The samples whose names end in ``3f4223e`` were made by this program's
``LinkLedger`` sending to the ledger's own tool-call code at its dev 3f4223e,
run on that code's stand-in page (each sample's ``_source`` says how; none
was captured through the ledger page in a browser). A card whose total is
not quantity times price, sent with ``allowUnfinished``, is taken, not
ready, nothing missing, ``TOTAL_VALUE_MISMATCH`` on the total; sent whole, or
selling more than was held as well, it is turned down. The rejection of a
trade paid in another money with no rate no longer says the half sentence
about holdings. The program's own sentence for such a card is chosen by the
code alone, so it is the same whatever words the ledger uses. Every figure
is invented.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from ledger_hand.core.marks import SentMark
from ledger_hand.core.proposals import CheckOutcome, ProposalResult
from ledger_hand.core.trade import Side
from ledger_hand.core.trade_card import TradeCard
from ledger_hand.flows.record_words import FIX_FIGURES_WORDS
from ledger_hand.ledger.demo_book import DEMO_ASSETS, DEMO_MARKET_PRICES, DEMO_TRADES
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ledger.link_client import AnswerKind, ToolAnswer
from ledger_hand.ledger.link_ledger import LinkLedger
from tests.flows.test_cards_examples import SOL_200, card, one
from tests.ledger.test_link_ledger import ASSETS, SampleLink

SAMPLES = Path(__file__).parent / "samples"
HOLDINGS_HALF = "卖出数量超过该时间点的可用持仓"
SOL_WORDS = "今天上午8:25花了200 USDT买入了0.094326个SOL，均价212.03 USDT，手续费0"
DISAGREE = (
    "you said the total was 6000 USDT, but quantity × price is 6500 USDT; "
    "the program does not guess which is wrong"
)


def document(name: str) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads((SAMPLES / f"{name}.json").read_text(encoding="utf-8"))
    return loaded


def answer(name: str) -> ToolAnswer:
    found = document(name)["answer"]
    return ToolAnswer(kind=AnswerKind(found["kind"]), content=found["content"])


def btc(**changes: Any) -> TradeCard:
    """The card the samples were made with: 0.1 BTC at 65000 USDT for 6000, on 2026-11-24."""
    values: dict[str, Any] = {
        "occurred": datetime(2026, 11, 24, tzinfo=ZoneInfo("Europe/Budapest")),
        "side": Side.BUY,
        "asset": "BTC",
        "quantity": Decimal("0.1"),
        "price": Decimal("65000"),
        "total": Decimal("6000"),
        "quote": "USDT",
        "fee": Decimal("5"),
        "fee_asset": "USDT",
        "platform": "",
        "note": "",
        "raw_text": "invented",
        "zone": None,
        "date_only": True,
        "marks": tuple(
            SentMark(field, "suspicious", DISAGREE) for field in ("quantity", "price", "totalValue")
        ),
    }
    values.update(changes)
    return TradeCard(**values)


def plug_of(name: str) -> tuple[LinkLedger, SampleLink]:
    link = SampleLink(ASSETS, ("propose_trade_add", answer(name)))
    link_tools: list[dict[str, Any]] = [
        {
            "name": "propose_trade_add",
            "inputSchema": {"type": "object", "properties": {"allowUnfinished": {}}},
        }
    ]
    link.tools = lambda: link_tools  # type: ignore[attr-defined]
    return LinkLedger(link, model_name="no model (sample)", today=lambda: date(2026, 11, 24)), link


@pytest.mark.parametrize(
    "name",
    ["propose-add-card-mismatch-3f4223e", "propose-add-card-mismatch-page-in-english-3f4223e"],
)
def test_the_card_is_sent_as_said_and_read_back_taken_not_ready_with_the_code(name: str) -> None:
    plug, link = plug_of(name)

    (check,) = plug.propose_cards((btc(),), "invented").checks

    (_, sent) = link.asked[-1]
    assert sent == document(name)["arguments"]
    (trade,) = sent["trades"]
    assert (trade["quantity"], trade["price"], trade["totalValue"]) == ("0.1", "65000", "6000")
    assert sent["allowUnfinished"] is True
    assert check.outcome is CheckOutcome.PASSED
    assert (check.ready, check.missing) == (False, ())
    assert check.problem is not None
    assert (check.problem.code, check.problem.field) == ("TOTAL_VALUE_MISMATCH", "totalValue")


def test_a_card_with_the_fee_empty_names_the_fee_missing_and_the_mismatch() -> None:
    plug, _ = plug_of("propose-add-card-mismatch-fee-empty-3f4223e")

    (check,) = plug.propose_cards((btc(fee=None, fee_asset=None),), "invented").checks

    assert (check.ready, check.missing) == (False, ("fee", "feeAssetId"))
    assert check.problem is not None and check.problem.code == "TOTAL_VALUE_MISMATCH"


def test_sent_whole_without_the_switch_it_is_turned_down() -> None:
    plug, link = plug_of("propose-add-mismatch-no-switch-3f4223e")
    facts = btc(marks=()).facts
    assert facts is not None

    (check,) = plug.propose_add((facts,), "invented").checks

    assert "allowUnfinished" not in link.asked[-1][1]
    assert (check.outcome, check.code) == (CheckOutcome.FAILED, "TOTAL_VALUE_MISMATCH")


def test_selling_more_than_held_as_well_it_is_turned_down_whole_saying_both() -> None:
    plug, _ = plug_of("propose-add-card-mismatch-oversold-3f4223e")
    sell = btc(side=Side.SELL, quantity=Decimal("0.5"), total=Decimal("3250"))

    (check,) = plug.propose_cards((sell,), "invented").checks

    assert (check.outcome, check.code) == (CheckOutcome.FAILED, "TOTAL_VALUE_MISMATCH")
    assert check.message is not None and HOLDINGS_HALF in check.message


def test_another_money_with_no_rate_no_longer_says_the_holdings_half() -> None:
    (result,) = answer("propose-add-other-money-no-rate-3f4223e").content["results"]

    assert result["error"]["code"] == "CURRENCY_MISMATCH"
    assert HOLDINGS_HALF not in result["error"]["message"]


class _ReadFromSample(FakeLedger):
    """The demo ledger taking cards, whose check of each card is the plug's reading of a sample."""

    def __init__(self, name: str, message: str | None = None) -> None:
        super().__init__(
            assets=DEMO_ASSETS, trades=DEMO_TRADES, prices=DEMO_MARKET_PRICES, takes_unfinished=True
        )
        self.name = name
        self.message = message

    def propose_cards(self, cards: tuple[TradeCard, ...], said: str) -> ProposalResult:
        name = self.name
        if self.message is not None:
            changed = document(name)
            problem = changed["answer"]["content"]["results"][0]["ledgerProblem"]
            problem["message"] = self.message
            sampled = ToolAnswer(kind=AnswerKind.RESULT, content=changed["answer"]["content"])
        else:
            sampled = answer(name)
        link = SampleLink(ASSETS, ("propose_trade_add", sampled))
        link.tools = lambda: [  # type: ignore[attr-defined]
            {"name": "propose_trade_add", "inputSchema": {"properties": {"allowUnfinished": {}}}}
        ]
        plug = LinkLedger(link, model_name="m", today=lambda: date(2026, 11, 24))
        return plug.propose_cards((btc(),), said)


@pytest.mark.parametrize(
    "message",
    [
        None,
        "The execution amount does not match quantity × average execution price",
        "成交金额与数量 × 成交均价不一致；卖出数量超过该时间点的可用持仓",
        "完全不同的一句话",
    ],
)
def test_the_programs_sentence_from_the_sample_is_the_same_whatever_the_message(
    message: str | None,
) -> None:
    ledger = _ReadFromSample("propose-add-card-mismatch-3f4223e", message)

    said = one(SOL_WORDS, SOL_200, ledger)

    card(said)
    lines = said.reply.splitlines()
    assert FIX_FIGURES_WORDS.format(number=1) in lines
    shown = message if message is not None else "成交金额与数量 × 成交均价不一致"
    assert f"Trade 1: the ledger says: {shown}" in lines
