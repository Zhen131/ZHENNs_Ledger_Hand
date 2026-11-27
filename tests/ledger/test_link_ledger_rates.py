"""Tests of the real ledger's plug asking for the exchange rates the ledger keeps.

The answers are written from the ledger's ``assistant-link/README.md`` and
its code at dev 1b016ec ("list_exchange_rates"), by a stand-in that plays
them in order and keeps what the plug asked; a clock that only moves when
told stands in for the time. Every rate, day and identifier is invented.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from datetime import date
from typing import Any

import pytest

from ledger_hand.core.ledger_rate import NO_RATE_TOOL, RATE_TOOL, RateRequest
from ledger_hand.ledger.link_client import AnswerKind, ToolAnswer
from ledger_hand.ledger.link_failures import LedgerLinkError, LinkFailure
from ledger_hand.ledger.link_ledger import (
    CALL_FAILURES,
    MOST_RATE_PAGES,
    RATE_SECONDS,
    LinkLedger,
)
from ledger_hand.ports import LedgerError, LedgerErrorKind

TODAY = date(2026, 11, 27)
REQUEST = RateRequest(
    currency_id="asset-eur",
    other_id="asset-usd",
    last_day=date(2026, 11, 20),
    enough_day=date(2026, 11, 20),
)
TOOLS = [{"name": name} for name in ("list_assets", RATE_TOOL, "propose_trade_add")]


def row(rate: str, day: str, base: str = "EUR", quote: str = "USD", **extra: Any) -> dict[str, Any]:
    found = {
        "baseCurrencyAssetId": f"asset-{base.lower()}",
        "baseCurrencyCode": base,
        "quoteCurrencyAssetId": f"asset-{quote.lower()}",
        "quoteCurrencyCode": quote,
        "rate": rate,
        "rateDate": day,
        "source": "manual",
        "onlineSourceId": None,
    }
    return found | extra


def page(*rows: dict[str, Any], token: str | None = None) -> ToolAnswer:
    return ToolAnswer(
        kind=AnswerKind.RESULT,
        content={
            "kind": "exchange-rate-list",
            "todayDate": TODAY.isoformat(),
            "rates": list(rows),
            "pageSize": 50,
            "nextPageToken": token,
        },
    )


def error(code: str, message: str = "Invented words of the ledger.", **extra: Any) -> ToolAnswer:
    return ToolAnswer(
        kind=AnswerKind.ERROR,
        content={"code": code, "category": "invalid-arguments", "message": message, **extra},
    )


class Clock:
    """Seconds that pass only when an answer says it took them."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class RateLink:
    """Plays answers in order, each taking the seconds given; keeps what was asked and the wait."""

    def __init__(
        self,
        *script: tuple[ToolAnswer | Exception, float],
        clock: Clock,
        tools: list[dict[str, Any]] | None = TOOLS,
    ) -> None:
        self.script = list(script)
        self.clock = clock
        self.listed = tools
        self.asked: list[tuple[str, dict[str, Any], float]] = []

    def tools(self) -> list[dict[str, Any]]:
        if self.listed is None:
            raise LedgerLinkError(LinkFailure.NOT_STARTED)
        return self.listed

    def call(self, name: str, arguments: Mapping[str, Any]) -> ToolAnswer:
        return self.call_within(name, arguments, 60.0)

    def call_within(self, name: str, arguments: Mapping[str, Any], seconds: float) -> ToolAnswer:
        self.asked.append((name, copy.deepcopy(dict(arguments)), seconds))
        assert self.script, f"nothing left to answer {name}"
        answer, took = self.script.pop(0)
        if took > seconds:
            self.clock.now += seconds
            raise LedgerLinkError(LinkFailure.TIMED_OUT, "waiting for an answer")
        self.clock.now += took
        if isinstance(answer, Exception):
            raise answer
        return answer


def plug(*script: tuple[ToolAnswer | Exception, float], **kept: Any) -> tuple[LinkLedger, RateLink]:
    clock = Clock()
    link = RateLink(*script, clock=clock, **kept)
    return LinkLedger(link, model_name="qwen2.5:7b", today=lambda: TODAY, timer=clock), link


def test_it_asks_for_the_two_moneys_up_to_the_latest_day_and_keeps_every_row_as_text() -> None:
    online = row("0.925", "2026-11-19", "USD", "EUR", source="online", onlineSourceId="frankfurter")
    ledger, link = plug((page(row("1.08", "2026-11-20"), online), 0.1))

    listed = ledger.exchange_rates(REQUEST)

    assert link.asked == [
        (
            RATE_TOOL,
            {
                "currencyAssetId": "asset-eur",
                "otherCurrencyAssetId": "asset-usd",
                "endDate": "2026-11-20",
            },
            RATE_SECONDS,
        )
    ]
    assert listed.today == TODAY and not listed.more and listed.odd == 0
    assert [one.as_listed() for one in listed.rows] == [row("1.08", "2026-11-20"), online]


def test_pages_are_read_until_one_reaches_the_earliest_day() -> None:
    ledger, link = plug(
        (page(row("1.1", "2026-11-20"), token="t1"), 0.1),
        (page(row("1.09", "2026-11-19"), row("1.08", "2026-11-12"), token="t2"), 0.1),
    )
    request = RateRequest(
        currency_id="asset-eur",
        other_id="asset-usd",
        last_day=date(2026, 11, 20),
        enough_day=date(2026, 11, 15),
    )

    listed = ledger.exchange_rates(request)

    assert [arguments.get("pageToken") for _, arguments, _ in link.asked] == [None, "t1"]
    assert [one.rate for one in listed.rows] == ["1.1", "1.09", "1.08"]
    assert not listed.more


def test_at_most_three_pages_are_read() -> None:
    pages = [(page(row("1.1", "2026-11-20"), token=f"t{n}"), 0.1) for n in range(5)]
    ledger, link = plug(*pages)
    request = RateRequest(
        currency_id="asset-eur",
        other_id="asset-usd",
        last_day=date(2026, 11, 20),
        enough_day=date(2026, 11, 1),
    )

    listed = ledger.exchange_rates(request)

    assert len(link.asked) == MOST_RATE_PAGES == 3
    assert listed.more and len(listed.rows) == 3


def test_a_ledger_that_changed_is_read_again_from_the_first_page_once_never_mixed() -> None:
    ledger, link = plug(
        (page(row("9.9", "2026-11-25"), token="t1"), 0.1),
        (error("LEDGER_CHANGED_START_FROM_FIRST_PAGE"), 0.1),
        (page(row("1.08", "2026-11-20")), 0.1),
    )

    listed = ledger.exchange_rates(REQUEST)

    assert [arguments.get("pageToken") for _, arguments, _ in link.asked] == [None, "t1", None]
    assert [one.rate for one in listed.rows] == ["1.08"]


@pytest.mark.parametrize("code", ["LEDGER_CHANGED_START_FROM_FIRST_PAGE", "INVALID_PAGE_TOKEN"])
def test_a_ledger_that_changes_twice_is_not_read(code: str) -> None:
    ledger, link = plug(
        (page(row("1.1", "2026-11-25"), token="t1"), 0.1),
        (error(code), 0.1),
        (page(row("1.1", "2026-11-25"), token="t2"), 0.1),
        (error(code), 0.1),
    )

    with pytest.raises(LedgerError) as caught:
        ledger.exchange_rates(REQUEST)

    assert caught.value.code == "LEDGER_CHANGED_START_FROM_FIRST_PAGE"
    assert len(link.asked) == 4


def test_a_ledger_whose_tools_lack_it_has_no_tool_and_is_not_asked() -> None:
    ledger, link = plug(tools=[{"name": "list_assets"}, {"name": "propose_trade_add"}])

    with pytest.raises(LedgerError) as caught:
        ledger.exchange_rates(REQUEST)

    assert (caught.value.code, caught.value.kind) == (NO_RATE_TOOL, LedgerErrorKind.OTHER)
    assert link.asked == []


def test_a_ledger_that_answers_unknown_tool_has_no_tool() -> None:
    ledger, _ = plug((error("UNKNOWN_TOOL"), 0.1), tools=None)

    with pytest.raises(LedgerError) as caught:
        ledger.exchange_rates(REQUEST)

    assert caught.value.code == NO_RATE_TOOL


def test_the_first_page_out_of_time_is_timed_out() -> None:
    ledger, link = plug((page(row("1.08", "2026-11-20")), RATE_SECONDS + 5))

    with pytest.raises(LedgerError) as caught:
        ledger.exchange_rates(REQUEST)

    assert caught.value.kind is LedgerErrorKind.TIMED_OUT
    assert caught.value.code == "HAND_RATES_TIMED_OUT"
    assert [seconds for _, _, seconds in link.asked] == [RATE_SECONDS]


def test_each_later_page_waits_only_for_the_time_left() -> None:
    ledger, link = plug(
        (page(row("1.1", "2026-11-25"), token="t1"), 20.0),
        (page(row("1.08", "2026-11-20")), 15.0),
    )

    with pytest.raises(LedgerError) as caught:
        ledger.exchange_rates(REQUEST)

    assert caught.value.kind is LedgerErrorKind.TIMED_OUT
    assert [seconds for _, _, seconds in link.asked] == [RATE_SECONDS, RATE_SECONDS - 20.0]


def test_a_row_lacking_a_field_is_passed_over_and_counted() -> None:
    broken = row("1.08", "2026-11-20")
    del broken["rateDate"]
    numeric = row("1.08", "2026-11-20") | {"rate": 1.08}
    ledger, _ = plug((page(broken, numeric, row("1.07", "2026-11-19")), 0.1))

    listed = ledger.exchange_rates(REQUEST)

    assert listed.odd == 2
    assert [one.rate for one in listed.rows] == ["1.07"]


@pytest.mark.parametrize(
    ("code", "kind"),
    [
        ("ASSET_IS_NOT_CURRENCY", LedgerErrorKind.OTHER),
        ("ASSET_NOT_FOUND", LedgerErrorKind.UNKNOWN_ASSET),
        ("LEDGER_NOT_READY", LedgerErrorKind.UNREACHABLE),
        ("UNEXPECTED_PROGRAM_ERROR", LedgerErrorKind.OTHER),
    ],
)
def test_the_ledgers_refusal_comes_back_with_its_code_and_words(
    code: str, kind: LedgerErrorKind
) -> None:
    ledger, _ = plug((error(code, "Its own words.", field="otherCurrencyAssetId"), 0.1))

    with pytest.raises(LedgerError) as caught:
        ledger.exchange_rates(REQUEST)

    assert (caught.value.code, caught.value.kind, caught.value.message) == (
        code,
        kind,
        "Its own words.",
    )


def test_the_new_code_is_on_the_table_of_call_failures() -> None:
    assert CALL_FAILURES["ASSET_IS_NOT_CURRENCY"] is LedgerErrorKind.OTHER
