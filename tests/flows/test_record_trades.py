"""Tests of the command-line script that records trades, with fake models standing in.

The script's own work is reading the passage and the answers, showing each
question and the records, and its exit status; the flow itself is tested
elsewhere. It writes nothing: each run here takes place in an empty
directory that must still be empty afterwards. Every passage below is
invented.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
import tzlocal

from ledger_hand.flows.progress import Tuning
from scripts import record_trades
from tests.fakes.routed_model import RoutedModel
from tests.flows.scripted_flow import NOW, ZONE, row, screened, table

TWO_TRADES = "今天下午 3 点买了 0.5 ETH，又卖了 2 个 SOL，价格 150"
TWO_ROWS = table(
    row(side="buy", coin="ETH", quantity="0.5 ETH", time="今天下午 3 点"),
    row(side="sell", coin="SOL", quantity="2 个", price="150"),
)
SPOT = screened(("spot_trade", "买了 0.5 ETH"))
ANSWERS = ["3420", "none", "0.2 USDT", "昨天下午 4 点"]


def two_trades() -> RoutedModel:
    return RoutedModel(screen=[SPOT], extraction=[TWO_ROWS])


def run(
    arguments: list[str], stdin: str, model: RoutedModel, *, zone: str | None = ZONE
) -> tuple[int, str]:
    out = io.StringIO()
    status = record_trades.main(
        arguments,
        stdin=io.StringIO(stdin),
        out=out,
        model=model,
        tuning=Tuning(),
        now=NOW,
        zone=zone,
    )
    return status, out.getvalue()


@pytest.fixture
def empty_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An empty working directory for the run, checked to be empty still afterwards."""
    where = tmp_path / "run"
    where.mkdir()
    monkeypatch.chdir(where)
    return where


def test_each_question_and_the_records_are_shown_and_nothing_is_written(
    empty_directory: Path,
) -> None:
    status, shown = run(["--answers", "-", TWO_TRADES], "\n".join(ANSWERS) + "\n", two_trades())

    assert status == record_trades.DONE == 0
    for expected in [
        f"passage: {TWO_TRADES!r}",
        "[Trade 1 of 2: price] What was the price of one coin, in USDT?",
        "> 3420",
        "[Trade 1 of 2: fee]",
        "    Answer 'none' if there was no fee.",
        "[Trade 2 of 2: fee]",
        "[Trade 2 of 2: time] When did this trade happen?",
        "Records:",
        "    1. buy 0.5 ETH at 3420, total 1710 (total worked out), fee 0 USDT,",
        "    2. sell 2 SOL at 150, total 300 (total worked out), fee 0.2 USDT,",
        "> done",
        "2 record(s); nothing is saved yet.",
        "calls to the model: ",
    ]:
        assert expected in shown, expected
    assert list(empty_directory.iterdir()) == []


def test_a_record_can_be_removed_without_a_terminal(empty_directory: Path) -> None:
    answers = [*ANSWERS, "remove 2", "done"]

    status, shown = run(["--answers", "-", TWO_TRADES], "\n".join(answers), two_trades())

    assert status == 0
    final = shown[shown.index("> done") :]
    assert "1. buy 0.5 ETH" in final
    assert "2. skipped" in final
    assert "1 record(s); nothing is saved yet." in final
    assert list(empty_directory.iterdir()) == []


def test_the_whole_passage_can_be_dropped_without_a_terminal(empty_directory: Path) -> None:
    status, shown = run(["--answers", "-", TWO_TRADES], "3420\ncancel\n", two_trades())

    assert status == record_trades.NOTHING_KEPT == 1
    assert "cancelled: the whole passage was dropped; nothing is kept" in shown
    assert list(empty_directory.iterdir()) == []


def test_answers_that_run_out_before_the_end_stop_the_script(empty_directory: Path) -> None:
    status, shown = run(["--answers", "-", TWO_TRADES], "3420\n", two_trades())

    assert status == record_trades.RAN_OUT == 3
    assert "the answers ran out before every trade was settled" in shown
    assert list(empty_directory.iterdir()) == []


def test_answers_can_come_from_a_file_and_the_passage_from_the_first_line(
    tmp_path: Path, empty_directory: Path
) -> None:
    answers = tmp_path / "answers.txt"
    answers.write_text("\n".join(ANSWERS) + "\n", encoding="utf-8")

    status, shown = run(["--answers", str(answers)], TWO_TRADES + "\n", two_trades())

    assert status == 0
    assert f"passage: {TWO_TRADES!r}" in shown
    assert list(empty_directory.iterdir()) == []


def test_typed_answers_are_prompted_for_and_the_end_of_input_stops_the_script(
    empty_directory: Path,
) -> None:
    status, shown = run([TWO_TRADES], "3420\nnone\n", two_trades())

    assert status == 3
    assert shown.count("> ") >= 3
    assert list(empty_directory.iterdir()) == []


def test_a_passage_that_is_stopped_says_why_and_keeps_nothing(empty_directory: Path) -> None:
    passage = "昨天开了 5 倍杠杆做多 ETH"
    model = RoutedModel(screen=[screened(("futures_or_leverage", "5 倍杠杆做多"))])

    status, shown = run(["--answers", "-", passage], "", model)

    assert status == 1
    assert "stopped: the passage reports only things the ledger does not record" in shown
    assert "futures_or_leverage '5 倍杠杆做多': this looks like futures" in shown
    assert model.extraction.calls == []


def test_without_a_zone_the_program_takes_the_script_cannot_start(
    monkeypatch: pytest.MonkeyPatch, empty_directory: Path
) -> None:
    monkeypatch.setattr(tzlocal, "get_localzone_name", lambda: "Not/AZone")

    status, shown = run(["--answers", "-", TWO_TRADES], "", RoutedModel(), zone=None)

    assert status == record_trades.CANNOT_START == 2
    assert "time zone" in shown


def test_a_setting_that_is_refused_stops_the_script(
    monkeypatch: pytest.MonkeyPatch, empty_directory: Path
) -> None:
    monkeypatch.setenv("LEDGER_HAND_MODEL_QUESTION_TEMPERATURE", "warm")
    out = io.StringIO()

    status = record_trades.main(
        ["--answers", "-", TWO_TRADES], stdin=io.StringIO(""), out=out, now=NOW, zone=ZONE
    )

    assert status == 2
    assert "setting refused" in out.getvalue()
