"""Tests of a card (a trade with cells left empty) sent to the fake ledger and to the real plug.

The fake ledger takes cards the way the ledger's ``propose_trade_add``
does since 2026-11-25 (``allowUnfinished``, ``fieldMarks``): a whole card
is checked as before; a card with an empty cell is kept, cannot be saved,
and says its empty cells (in the ledger's order) and what the cells given
show; its marks are checked by the ledger's rules, split as the ledger
splits them. The real plug's answers are written from the ledger's
``assistant-link/README.md`` ("Unfinished trades and field marks"), as no
answer with cells left empty was captured and no test connects to the
ledger page. Every figure is invented.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from ledger_hand.core.marks import SentMark
from ledger_hand.core.proposals import CheckOutcome, ProposalStatus
from ledger_hand.core.trade import Side
from ledger_hand.core.trade_card import EMPTY_ALLOWED, TradeCard
from ledger_hand.ledger.demo_book import demo_ledger
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ledger.link_client import AnswerKind, ToolAnswer
from ledger_hand.ledger.link_ledger import LinkLedger
from ledger_hand.ports import LedgerError
from tests.ledger.test_link_ledger import ASSETS, MODEL, SAID, TODAY, SampleLink, plug

_BUDAPEST = ZoneInfo("Europe/Budapest")
TEN = datetime(2026, 11, 24, 10, 0, tzinfo=_BUDAPEST)


def eth(**changes: object) -> TradeCard:
    """A buy of 0.1 ETH at 2600 USDT, total 260, fee 0, on 2026-11-24 at 10:00; changes made."""
    values: dict[str, object] = {
        "occurred": TEN,
        "side": Side.BUY,
        "asset": "ETH",
        "quantity": Decimal("0.1"),
        "price": Decimal("2600"),
        "total": Decimal("260"),
        "quote": "USDT",
        "fee": Decimal("0"),
        "fee_asset": "USDT",
        "platform": "",
        "note": "",
        "raw_text": "invented",
        "zone": "Europe/Budapest",
        "date_only": False,
    }
    values.update(changes)
    return TradeCard(**values)  # type: ignore[arg-type]


def mark(field: str, kind: str, reason: str | None = None) -> SentMark:
    return SentMark(field, kind, reason)


def taking() -> FakeLedger:
    return demo_ledger().taking_cards()


# --- the card itself ---------------------------------------------------------------------------


def test_a_card_names_its_empty_cells_in_the_ledgers_order_and_is_never_0() -> None:
    card = eth(quantity=None, fee=None, fee_asset=None, occurred=None, zone=None)

    assert card.missing == ("occurredDate", "quantity", "fee", "feeAssetId")
    assert set(card.missing) <= set(EMPTY_ALLOWED)
    assert card.facts is None
    with pytest.raises(ValueError, match="empty text"):
        eth(quote="")
    with pytest.raises(ValueError, match="above 0"):
        eth(price=Decimal(0))
    with pytest.raises(ValueError, match="no time"):
        eth(occurred=None)


# --- the fake ledger ---------------------------------------------------------------------------


def test_a_whole_card_is_taken_ready_and_its_marks_kept_as_they_came() -> None:
    ledger = taking()
    marks = (mark("totalValue", "computed", "worked out"),)

    (check,) = ledger.propose_cards((eth(marks=marks),), SAID).checks

    assert check.outcome is CheckOutcome.PASSED and check.ready is True and check.missing == ()
    assert check.proposal_id is not None
    assert ledger.marks_of(check.proposal_id) == marks
    assert ledger.calls == ["propose_add"]


def test_a_card_with_an_empty_cell_waits_unready_and_cannot_be_saved() -> None:
    ledger = taking()
    before = ledger.positions()

    (check,) = ledger.propose_cards((eth(fee=None, fee_asset=None),), SAID).checks

    assert check.ready is False and check.missing == ("fee", "feeAssetId")
    assert check.problem is None
    assert check.proposal_id is not None
    with pytest.raises(LedgerError, match="fee, feeAssetId"):
        ledger.save(check.proposal_id)
    assert ledger.proposal_status(check.proposal_id).status is ProposalStatus.PENDING
    assert ledger.positions() == before


def test_a_card_with_an_empty_cell_says_a_total_that_does_not_agree() -> None:
    ledger = taking()

    (check,) = ledger.propose_cards(
        (eth(total=Decimal("200"), fee=None, fee_asset=None),), SAID
    ).checks

    assert check.problem is not None and check.problem.code == "TOTAL_VALUE_MISMATCH"


def test_selling_more_than_held_is_found_only_when_day_figures_and_money_are_given() -> None:
    ledger = taking()
    sell = eth(side=Side.SELL, quantity=Decimal("500"), total=Decimal("1300000"))

    found, not_found = ledger.propose_cards(
        (
            dataclasses.replace(sell, fee=None, fee_asset=None),
            dataclasses.replace(sell, price=None, total=None, fee=None, fee_asset=None),
        ),
        SAID,
    ).checks

    assert found.problem is not None and found.problem.code == "INSUFFICIENT_HOLDINGS"
    assert not_found.problem is None and not_found.ready is False


def test_a_ledger_from_before_takes_no_card() -> None:
    ledger = demo_ledger()

    assert not ledger.takes_unfinished()
    with pytest.raises(LedgerError, match="allowUnfinished"):
        ledger.propose_cards((eth(),), SAID)
    assert ledger.takes_unfinished() is False and taking().takes_unfinished() is True


# The ledger's split (72C1): these refuse the whole call ...
WHOLE_CALL = {
    "an unknown cell": mark("colour", "suspicious", "why"),
    "an unknown kind": mark("price", "guessed", "why"),
    "a reason over 256": mark("price", "suspicious", "x" * 257),
    "a reason of 129 emoji": mark("price", "suspicious", "😀" * 129),
}


@pytest.mark.parametrize("bad", WHOLE_CALL.values(), ids=WHOLE_CALL.keys())
def test_a_mark_the_ledger_cannot_read_refuses_the_whole_call(bad: SentMark) -> None:
    ledger = taking()

    with pytest.raises(LedgerError) as raised:
        ledger.propose_cards((eth(), eth(marks=(bad,))), SAID)
    assert raised.value.code == "INVALID_ARGUMENTS"
    with pytest.raises(LedgerError, match="no proposal"):
        ledger.proposal_status("proposal-1")


# ... and these turn down that one card alone.
ONE_CARD = {
    "suspicious with no reason": (mark("price", "suspicious"),),
    "suspicious with a blank reason": (mark("price", "suspicious", "  "),),
    "two marks on one cell": (mark("price", "computed"), mark("price", "inferred")),
    "worked out on an empty cell": (mark("fee", "computed", "why"),),
    "assumed on an empty cell": (mark("feeAssetId", "inferred", "why"),),
}


@pytest.mark.parametrize("bad", ONE_CARD.values(), ids=ONE_CARD.keys())
def test_a_mark_against_the_rules_turns_down_that_card_alone(bad: tuple[SentMark, ...]) -> None:
    ledger = taking()

    good, wrong = ledger.propose_cards(
        (eth(), eth(fee=None, fee_asset=None, marks=bad)), SAID
    ).checks

    assert good.outcome is CheckOutcome.PASSED
    assert wrong.outcome is CheckOutcome.FAILED and wrong.code == "INVALID_ARGUMENTS"


def test_an_empty_cell_marked_suspicious_is_taken() -> None:
    ledger = taking()
    marks = (mark("price", "suspicious", "you said the price was 0, which is not above zero"),)

    (check,) = ledger.propose_cards((eth(price=None, total=None, marks=marks),), SAID).checks

    assert check.outcome is CheckOutcome.PASSED and check.missing == ("price", "totalValue")


# --- the real ledger's plug ---------------------------------------------------------------------


# A propose_trade_add answer for one card, as the README writes it.
def taken(
    missing: list[str], problem: dict[str, Any] | None = None, *, ready: bool = False
) -> ToolAnswer:
    return ToolAnswer(
        kind=AnswerKind.RESULT,
        content={
            "results": [
                {
                    "ok": True,
                    "proposalId": "p-1",
                    "readyToSave": ready,
                    "missingFields": missing,
                    "ledgerProblem": problem,
                }
            ]
        },
    )


def sent_trade(link: SampleLink) -> tuple[dict[str, Any], dict[str, Any]]:
    name, arguments = link.asked[-1]
    assert name == "propose_trade_add"
    (trade,) = arguments["trades"]
    return arguments, trade


def test_a_card_missing_its_fee_is_sent_with_nulls_and_the_switch() -> None:
    ledger, link = plug(ASSETS, ("propose_trade_add", taken(["fee", "feeAssetId"])))

    (check,) = ledger.propose_cards((eth(fee=None, fee_asset=None),), SAID).checks

    arguments, trade = sent_trade(link)
    assert arguments["allowUnfinished"] is True
    assert trade["fee"] is None and trade["feeAssetId"] is None
    assert trade["quantity"] == "0.1" and trade["quoteAssetId"] == "asset-usdt"
    assert check.ready is False and check.missing == ("fee", "feeAssetId")


def test_a_card_missing_its_price_carries_its_suspicious_mark() -> None:
    marks = (mark("price", "suspicious", "you said the price was 0, which is not above zero"),)
    ledger, link = plug(ASSETS, ("propose_trade_add", taken(["price", "totalValue"])))

    ledger.propose_cards((eth(price=None, total=None, marks=marks),), SAID)

    _, trade = sent_trade(link)
    assert trade["price"] is None and trade["totalValue"] is None
    assert trade["fieldMarks"] == [
        {"field": "price", "kind": "suspicious", "reason": marks[0].reason}
    ]


def test_a_whole_card_with_marks_is_ready() -> None:
    marks = (mark("totalValue", "computed", "worked out as quantity × price"),)
    ledger, link = plug(ASSETS, ("propose_trade_add", taken([], ready=True)))

    (check,) = ledger.propose_cards((eth(marks=marks),), SAID).checks

    _, trade = sent_trade(link)
    assert trade["occurredTime"] == "10:00" and trade["fieldMarks"][0]["kind"] == "computed"
    assert check.ready is True and check.missing == ()


def test_a_card_the_ledger_finds_oversold_carries_the_ledgers_words() -> None:
    problem = {
        "code": "INSUFFICIENT_HOLDINGS",
        "category": "check-failed",
        "message": "卖出数量超过当时持仓。",
        "field": "quantity",
    }
    ledger, _ = plug(ASSETS, ("propose_trade_add", taken(["fee", "feeAssetId"], problem)))

    (check,) = ledger.propose_cards(
        (eth(side=Side.SELL, quantity=Decimal("500"), total=Decimal("1300000"), fee=None,
             fee_asset=None),),
        SAID,
    ).checks  # fmt: skip

    assert check.problem is not None
    assert (check.problem.code, check.problem.message, check.problem.field) == (
        "INSUFFICIENT_HOLDINGS",
        "卖出数量超过当时持仓。",
        "quantity",
    )


def test_a_card_with_no_day_sends_no_time_and_no_zone() -> None:
    ledger, link = plug(ASSETS, ("propose_trade_add", taken(["occurredDate"])))

    ledger.propose_cards((eth(occurred=None, zone=None),), SAID)

    _, trade = sent_trade(link)
    assert not {"occurredDate", "occurredTime", "occurredTimeZone"} & set(trade)


def test_a_fee_of_0_with_no_money_has_no_fee_money_either() -> None:
    ledger, link = plug(ASSETS, ("propose_trade_add", taken(["quoteAssetId", "feeAssetId"])))

    ledger.propose_cards((eth(quote=None, fee_asset=None),), SAID)

    _, trade = sent_trade(link)
    assert trade["fee"] == "0" and trade["feeAssetId"] is None and trade["quoteAssetId"] is None


class ListingLink(SampleLink):
    """A stand-in that also lists the ledger's tools, ``propose_trade_add`` taking ``fields``."""

    def __init__(self, fields: list[str]) -> None:
        super().__init__()
        self.fields = fields

    def tools(self) -> list[dict[str, Any]]:
        properties = {name: {"type": "boolean"} for name in self.fields}
        schema = {"type": "object", "properties": properties}
        return [{"name": "propose_trade_add", "inputSchema": schema}]


def test_the_plug_reads_once_whether_the_ledger_takes_cards() -> None:
    now = LinkLedger(
        ListingLink(["trades", "allowUnfinished"]), model_name=MODEL, today=lambda: TODAY
    )
    before = LinkLedger(ListingLink(["trades"]), model_name=MODEL, today=lambda: TODAY)
    unlisted, _ = plug()

    assert now.takes_unfinished() is True
    assert before.takes_unfinished() is False
    assert unlisted.takes_unfinished() is False
