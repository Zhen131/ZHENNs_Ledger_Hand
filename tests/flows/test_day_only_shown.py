"""A trade known only to its day is shown and kept with its day alone, never as 00:00.

The assistant sends such a trade with its day alone; the try-out script,
the assistant's record and the stocks measure's result line say the day
alone too, so that "bought at midnight" and "no time of day said" stay
apart. A scripted model and the demo ledger stand in; every sentence is
invented.
"""

from __future__ import annotations

import io

from evals.stock_run import _came, _line, outcome_of
from evals.stock_set import StockGold, StockSentence, Verdict
from ledger_hand.flows.assistant_record import entry_for
from ledger_hand.ledger.demo_book import demo_ledger
from ledger_hand.ledger.invented_book import INVENTED_NOW
from scripts import try_assistant
from tests.fakes.routed_model import RoutedModel
from tests.flows.scripted_flow import row, screened, table
from tests.flows.test_marks_examples import RECORD, send

WORDS = "11月22号买了0.5个ETH，成交价2650 USDT，手续费0"
CELLS = {
    "side": "buy",
    "coin": "ETH",
    "quantity": "0.5个ETH",
    "price": "2650 USDT",
    "fee": "0",
    "time": "11月22号",
}
TIMED = "今天上午10点买了0.5个ETH，成交价2650 USDT，手续费0"


def test_the_record_keeps_the_day_alone() -> None:
    said, _ = send(WORDS, CELLS)

    entry = entry_for(said, words=WORDS, at=INVENTED_NOW, model="invented-model")

    (trade,) = entry["trades"]
    assert trade["occurred"] == "2026-11-22"


def test_the_record_keeps_a_moment_as_before() -> None:
    said, _ = send(TIMED, CELLS | {"time": "今天上午10点"})

    entry = entry_for(said, words=TIMED, at=INVENTED_NOW, model="invented-model")

    (trade,) = entry["trades"]
    assert trade["occurred"] == "2026-11-24T10:00:00+01:00"


def test_the_try_out_script_prints_the_day_alone() -> None:
    model = RoutedModel(
        tools=[RECORD], screen=[screened(("spot_trade", "ETH"))], extraction=[table(row(**CELLS))]
    )
    out = io.StringIO()

    status = try_assistant.main([WORDS], out=out, model=model, ledger=demo_ledger(), max_steps=6)

    assert status == 0
    (line,) = [one for one in out.getvalue().splitlines() if one.startswith("  trade 1:")]
    assert line.startswith("  trade 1: 2026-11-22 buy 0.5 ETH at 2650 USDT")
    assert "00:00" not in line


def test_the_stocks_measure_says_day_only_not_midnight() -> None:
    said, _ = send(WORDS, CELLS)
    outcome = outcome_of(said)
    gold = StockGold(expect="asked", ask="time")
    sentence = StockSentence(id="X1", kind="record", text=WORDS, gold=gold)

    assert "day only" in _came(said, outcome)
    assert "00:00" not in _came(said, outcome)
    line = _line(sentence, said, outcome, next(iter(Verdict)), 1.0)
    assert line["sent"][0]["occurred"] == "2026-11-22"  # type: ignore[index]
