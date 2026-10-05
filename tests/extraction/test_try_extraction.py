"""Tests of the script for trying extraction by hand, with the scripted model standing in.

The script's own work is reading the passage, the machine's zone and the
settings, and printing; extraction itself is tested elsewhere. Every
passage below is invented.
"""

from __future__ import annotations

import io

import pytest
import tzlocal

from ledger_hand.ports import ModelError, ModelErrorKind
from scripts import try_extraction
from tests.extraction.scripted_runs import NOW, ZONE, row, table
from tests.fakes.scripted_model import ScriptedModel

PASSAGE = "9:40 买了 0.02 BTC，价格 94,900，手续费 2 USDT，还买了 1 ETH"
ROW = row(side="buy", coin="BTC", quantity="0.02 BTC", price="94,900", fee="2 USDT", time="9:40")


def run_script(
    arguments: list[str], *steps: object, stdin: str = "", zone: str | None = ZONE
) -> tuple[int, str, ScriptedModel]:
    model = ScriptedModel(steps)  # type: ignore[arg-type]
    out = io.StringIO()
    status = try_extraction.main(
        arguments, read_input=lambda: stdin, out=out, model=model, now=NOW, zone=zone
    )
    return status, out.getvalue(), model


def test_the_drafts_issues_and_calls_are_printed() -> None:
    status, shown, model = run_script([PASSAGE], table(ROW))

    assert status == 0
    assert len(model.calls) == 1
    for expected in [
        "trade 1",
        "  side            buy",
        "  coin            BTC",
        "  quantity        0.02",
        "  price           94900",
        "  total           -",
        "  fee             2",
        "  fee currency    USDT",
        "  time            2026-10-05T09:40:00+02:00 (minute)",
        "trade 1, time: the time was read and kept, with a caution",
        "passage: numbers in the passage that no trade used; a trade may be missing: 1",
        "call 1: scripted, 0.00 s, None tokens read, None written, stopped",
    ]:
        assert expected in shown, expected


def test_the_arguments_are_joined_and_standard_input_is_the_fallback() -> None:
    _, _, from_arguments = run_script(["卖了", "2", "ETH"], '{"trades": []}')
    _, _, from_input = run_script([], '{"trades": []}', stdin="卖了 2 ETH\n")

    assert from_arguments.calls[0].messages[-1].content == "卖了 2 ETH"
    assert from_input.calls[0].messages[-1].content == "卖了 2 ETH\n"


def test_no_trade_is_said_and_is_still_a_success() -> None:
    status, shown, _ = run_script(["今天没交易"], '{"trades": []}')

    assert status == 0
    assert "no trade" in shown
    assert "issues: none" in shown


@pytest.mark.parametrize(
    ("steps", "expected"),
    [
        ((ModelError(ModelErrorKind.UNREACHABLE, "invented"),), "model failed: unreachable"),
        (("not JSON", "still not"), "no reply could be read: the reply is not valid JSON"),
    ],
)
def test_a_failure_is_said_and_ends_with_status_one(
    steps: tuple[object, ...], expected: str
) -> None:
    status, shown, _ = run_script([PASSAGE], *steps)

    assert status == 1
    assert expected in shown


def test_a_refused_passage_is_not_sent() -> None:
    status, shown, model = run_script(["   "])

    assert status == 1
    assert "not sent: the passage is empty" in shown
    assert model.calls == []


@pytest.mark.parametrize("name", ["localtime", "europe/budapest", "Factory", ""])
def test_a_machine_zone_the_program_does_not_take_stops_the_script(
    monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    monkeypatch.setattr(tzlocal, "get_localzone_name", lambda: name)

    status, shown, model = run_script([PASSAGE], zone=None)

    assert status == 2
    assert "cannot tell the machine's time zone" in shown
    assert model.calls == []


def test_a_machine_zone_that_cannot_be_read_stops_the_script(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unreadable() -> str:
        raise LookupError("no zone")

    monkeypatch.setattr(tzlocal, "get_localzone_name", unreadable)

    status, _, _ = run_script([PASSAGE], zone=None)

    assert status == 2


def test_the_machine_zone_is_used_as_tzlocal_names_it(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tzlocal, "get_localzone_name", lambda: "Asia/Shanghai")

    status, shown, _ = run_script([PASSAGE], '{"trades": []}', zone=None)

    assert status == 0
    assert "zone:    Asia/Shanghai" in shown
