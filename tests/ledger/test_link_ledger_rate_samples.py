"""Tests of the real ledger's plug against the exchange rates the ledger really handed back.

The answers in ``samples/list-exchange-rates-*-050e7dd.json`` were captured
on 2026-11-27 through the ledger's assistant link and its page, at its dev
050e7dd, from an invented ledger. A stand-in plays them in order and keeps
what the plug asked. Every figure is invented.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from ledger_hand.core.ledger_rate import RateRequest, pick, rate_gap
from ledger_hand.ledger.link_client import AnswerKind, ToolAnswer
from ledger_hand.ledger.link_ledger import LinkLedger
from ledger_hand.ports import LedgerError
from tests.ledger.test_link_ledger_rates import RateLink, plug

SAMPLES = Path(__file__).resolve().parent / "samples"


def sample(name: str) -> dict[str, Any]:
    found: dict[str, Any] = json.loads(
        (SAMPLES / f"list-exchange-rates-{name}-050e7dd.json").read_text(encoding="utf-8")
    )
    return found


def answer(name: str) -> ToolAnswer:
    kept = sample(name)["answer"]
    return ToolAnswer(kind=AnswerKind(kept["kind"]), content=kept["content"])


def request(name: str, enough: date) -> RateRequest:
    asked = sample(name)["arguments"]
    return RateRequest(
        currency_id=asked["currencyAssetId"],
        other_id=asked["otherCurrencyAssetId"],
        last_day=date(2026, 11, 27),
        enough_day=enough,
    )


def ledger(*names: str) -> tuple[LinkLedger, RateLink]:
    return plug(*((answer(name), 0.1) for name in names))


def test_both_ways_round_read_as_stored_and_compared_without_assuming_a_direction() -> None:
    found, _ = ledger("both-ways")

    listed = found.exchange_rates(request("both-ways", date(2026, 11, 19)))

    assert [(row.base_code, row.rate, row.rate_date) for row in listed.rows] == [
        ("EUR", "1.08", "2026-11-20"),
        ("USD", "0.925", "2026-11-19"),
    ]
    assert listed.today == date(2026, 11, 27)
    on_the_20th, _ = pick(listed.rows, "asset-eur", "asset-usd", date(2026, 11, 20))
    on_the_19th, _ = pick(listed.rows, "asset-eur", "asset-usd", date(2026, 11, 19))
    assert on_the_20th is not None and not on_the_20th.inverted
    assert on_the_19th is not None and on_the_19th.inverted
    assert str(on_the_19th.converted) == "1.0810810811"
    assert rate_gap(Decimal("1.08"), on_the_19th) == Decimal("0.001")


def test_a_pair_with_no_rate_is_an_empty_list() -> None:
    found, _ = ledger("none")

    assert found.exchange_rates(request("none", date(2026, 11, 20))).rows == ()


def test_a_share_named_as_a_money_is_the_ledgers_refusal_with_its_field() -> None:
    found, _ = ledger("not-currency")

    with pytest.raises(LedgerError) as caught:
        found.exchange_rates(request("not-currency", date(2026, 11, 20)))

    assert caught.value.code == "ASSET_IS_NOT_CURRENCY"
    assert sample("not-currency")["answer"]["content"]["field"] == "otherCurrencyAssetId"


def test_the_second_page_is_asked_with_the_token_as_handed_back() -> None:
    found, link = ledger("page-one", "page-two")

    listed = found.exchange_rates(request("page-one", date(2026, 9, 1)))

    assert len(listed.rows) == 51 and not listed.more
    token = sample("page-one")["answer"]["content"]["nextPageToken"]
    assert link.asked[1][1]["pageToken"] == token == sample("page-two")["arguments"]["pageToken"]


def test_a_page_reaching_the_earliest_day_is_the_last_one_read() -> None:
    found, link = ledger("page-one")

    listed = found.exchange_rates(request("page-one", date(2026, 11, 1)))

    assert len(link.asked) == 1 and len(listed.rows) == 50
