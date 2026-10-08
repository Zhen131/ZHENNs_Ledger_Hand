"""Tests of the samples the ledger tier adds: where the zone databases agree, and the flow's file.

No ledger is run here. The samples where the two time zone databases agree
are built from what both sides said, so here a comparison is made up to see
which trades are left out; what the ledger then says is the tier's to check.
"""

from __future__ import annotations

import json
from datetime import date

from scripts import ledger_check
from scripts.ledger_check import Accepted, Sample, ZoneDataComparison, ZoneGap, agreed_samples
from tests.ledger_check import cases


def test_each_agreed_case_comes_from_a_sample_that_allows_for_the_gap() -> None:
    light = {case.name: case for case in cases.light_cases()}
    agreed = cases.zone_agreed_cases()

    assert [case.source for case in agreed] == [
        "attack-last-days.json",
        "attack-every-zone-on-the-day.json",
    ]
    for case in agreed:
        assert light[case.source].expect is cases.Expect.ACCEPTED_EXCEPT_ZONE_DATA
        assert light[case.source].today == case.today
        assert case.name not in light
    assert {
        case.name
        for case in light.values()
        if case.expect is cases.Expect.ACCEPTED_EXCEPT_ZONE_DATA
    } == {case.source for case in agreed}


def source_sample() -> Sample:
    case = next(
        case for case in cases.light_cases() if case.name == "attack-every-zone-on-the-day.json"
    )
    return Sample(case.name, case.build(), ledger_check.AcceptedExceptZoneData(), case.today)


def test_the_trades_the_databases_disagree_on_are_left_out_and_the_rest_must_be_accepted() -> None:
    source = source_sample()
    written = json.loads(source.text)["ledgerData"]["trades"]
    gaps = {
        1: ZoneGap(written[1]["occurredTimeZone"], written[1]["occurredAt"], "+01:00", "+00:00"),
        4: ZoneGap(written[4]["occurredTimeZone"], written[4]["occurredAt"], "-06:00", "-07:00"),
    }

    derived, lines = agreed_samples([source], ZoneDataComparison("ours", "theirs", (gaps,)))

    (sample,) = derived
    assert sample.name == "attack-every-zone-on-the-day-where-zone-data-agree.json"
    assert sample.expected == Accepted()
    assert sample.today == date(2026, 10, 5)
    kept = [trade["id"] for trade in json.loads(sample.text)["ledgerData"]["trades"]]
    assert kept == [trade["id"] for place, trade in enumerate(written) if place not in gaps]
    assert lines[0].endswith("left out 2")
    assert written[1]["id"] in lines[1] and written[1]["occurredTimeZone"] in lines[1]
    assert written[4]["id"] in lines[2]


def test_with_no_disagreement_the_same_trades_are_judged_strictly() -> None:
    source = source_sample()

    (sample,), lines = agreed_samples([source], ZoneDataComparison("a", "a", ({},)))

    assert (
        json.loads(sample.text)["ledgerData"]["trades"]
        == json.loads(source.text)["ledgerData"]["trades"]
    )
    assert lines[0].endswith("left out 0")


def test_a_case_whose_source_is_not_checked_adds_nothing() -> None:
    other = Sample("edges.json", "{}", Accepted(), date(2026, 10, 4))

    assert agreed_samples([other], ZoneDataComparison("a", "a", ({},))) == ([], [])


def test_the_flow_writes_a_file_with_every_trade_and_the_confirmed_coins_card() -> None:
    (case,) = [case for case in cases.light_cases() if case.name == "flow-export.json"]
    trades, _ = cases.flow_trades()

    written = json.loads(case.build())

    assert case.expect is cases.Expect.ACCEPTED
    assert case.today.isoformat() == written["exportedAt"][:10] == "2026-10-04"
    assert sorted(trade["id"] for trade in written["ledgerData"]["trades"]) == sorted(
        trade.id for trade in trades
    )
    assert "PIKA" in {card["symbol"] for card in written["ledgerData"]["assets"]}
