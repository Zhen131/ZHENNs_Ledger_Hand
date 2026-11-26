"""Tests of what the ruler of sentences said the owner's way added for euros paid for a share.

A sentence may name the exam book with a euro (``"book": "exam-euro"``),
and is then said against it; a gold trade may hold the rate it should be
sent with and the price said it is worked out from, which the gold checks
work out again; the rate sent is judged within a ten-thousandth of it, and
a trade whose gold answer holds no rate has none judged. Every sentence
and figure is invented, and none is a sentence of the exam.
"""

from __future__ import annotations

import json
from pathlib import Path

from evals.spoken_judge import RATE_CELL, Ending, Observed, SentTrade, judge
from evals.spoken_run import observe, say_sentence
from evals.spoken_set import GoldRate, SpokenSet, gold_problems, load_spoken_set
from tests.evals.test_spoken_run import _said, gold_trade, model, ports
from tests.flows.scripted_flow import row

TEXT = "2026年11月20日14:43花了128欧元买了2股KO，一股69.5美元，换汇费0.19欧元"
KO = gold_trade(
    asset=_said("KO", "KO"),
    quantity=_said("2", "2"),
    price={"computed": True},
    total=_said("128", "128"),
    quote=_said("EUR", "欧元"),
    fee=_said("0.19", "0.19"),
    fee_asset=_said("EUR", "欧元"),
)
RATE = {"value": "1.0859375", "from": "69.5"}
ROW = row(
    side="buy",
    coin="KO",
    quantity="2股",
    price="69.5美元",
    total="128欧元",
    fee="0.19欧元",
    time="2026年11月20日14:43",
)


def euro_set(tmp_path: Path, rate: dict[str, str] | None = RATE, *, book: bool = True) -> SpokenSet:
    trade = KO | ({"cost_rate": rate} if rate is not None else {})
    sentence: dict[str, object] = {
        "id": "R70-01",
        "kind": "invented",
        "language": "zh",
        "enabled": True,
        "text": TEXT,
        "gold": {"expect": "send", "trades": [trade]},
    }
    if book:
        sentence["book"] = "exam-euro"
    data = {
        "about": "invented",
        "tier": "r70",
        "half": "practice",
        "book": "exam",
        "now": "2026-11-24T23:55:00+01:00",
        "zone": "Europe/Budapest",
        "sentences": [sentence],
    }
    path = tmp_path / "spoken-r70-practice.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return load_spoken_set(path)


def test_a_gold_rate_is_read_with_the_price_it_comes_from(tmp_path: Path) -> None:
    spoken = euro_set(tmp_path)

    (sentence,) = spoken.sentences
    assert sentence.book == "exam-euro"
    assert sentence.gold.trades[0].cost_rate == GoldRate(value="1.0859375", said_price="69.5")
    assert gold_problems(spoken) == []


def test_a_gold_rate_that_is_not_worked_out_from_the_gold_figures_is_a_problem(
    tmp_path: Path,
) -> None:
    spoken = euro_set(tmp_path, {"value": "1.09", "from": "69.5"})

    assert [words for _, words in gold_problems(spoken)] == [
        "trade 1: cost_rate: is not quantity × the price said ÷ total, to ten places"
    ]


def test_said_against_the_euro_book_the_rate_sent_is_the_gold_one(tmp_path: Path) -> None:
    spoken = euro_set(tmp_path)
    (sentence,) = spoken.sentences

    saids, answered = say_sentence(sentence, spoken, ports(model(TEXT, [ROW])))
    observed = observe([said for _, said in saids], answered, spoken.zone)

    (sent,) = observed.sent
    assert (sent.values["quote"], sent.cost_rate) == ("EUR", "1.0859375")
    (result,) = judge(sentence, observed, spoken.zone)
    assert RATE_CELL not in result.wrong
    assert result.ending is Ending.CLEAN


def _judged(spoken: SpokenSet, cost_rate: str | None, marked: frozenset[str] = frozenset()):  # type: ignore[no-untyped-def]
    (sentence,) = spoken.sentences
    values = {
        "side": "buy",
        "asset": "KO",
        "quantity": "2",
        "price": "64",
        "total": "128",
        "quote": "EUR",
        "fee": "0.19",
        "fee_asset": "EUR",
        "occurred": "2026-11-20 14:43",
        "platform": "",
    }
    sent = SentTrade(number=1, values=values, marked=marked, cost_rate=cost_rate)
    (result,) = judge(sentence, Observed(sent=(sent,)), spoken.zone)
    return result


def test_no_rate_sent_where_the_gold_holds_one_is_a_wrong_figure_with_no_mark(
    tmp_path: Path,
) -> None:
    result = _judged(euro_set(tmp_path), None)

    assert result.wrong == {RATE_CELL}
    assert result.ending is Ending.SILENT


def test_a_rate_within_a_ten_thousandth_is_right_and_beyond_it_is_wrong(tmp_path: Path) -> None:
    spoken = euro_set(tmp_path)

    assert _judged(spoken, "1.0860").ending is Ending.CLEAN
    assert _judged(spoken, "1.0861").wrong == {RATE_CELL}


def test_a_wrong_rate_with_its_own_mark_is_marked_not_silent(tmp_path: Path) -> None:
    result = _judged(euro_set(tmp_path), "10.859375", marked=frozenset({RATE_CELL}))

    assert result.ending is Ending.MARKED


def test_a_trade_whose_gold_holds_no_rate_has_none_judged(tmp_path: Path) -> None:
    result = _judged(euro_set(tmp_path, None, book=False), None)

    assert RATE_CELL not in result.wrong
    assert result.ending is Ending.CLEAN
