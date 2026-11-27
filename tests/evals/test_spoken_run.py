"""Tests of the ruler for sentences said the owner's way: each ending, through the whole assistant.

Each test says one invented sentence to the assistant against the exam
book, with a scripted model, and checks what the ruler made of it: the
ending of each gold trade, the columns kept apart, the one answer the
ruler gives (an asset's code), the sentences not enabled, a model that
cannot be reached, and what a hidden half prints and logs. Every
sentence, reply and figure is invented, and none is a sentence of the
exam.
"""

from __future__ import annotations

import io
import json
from collections.abc import Sequence
from pathlib import Path

import pytest

import evals.hidden_runs as hidden_runs
import evals.spoken_run as spoken_run
from evals.exam_book import EXAM_TRADES, exam_ledger
from evals.spoken_judge import (
    DisabledEnding,
    Ending,
    Observed,
    SentTrade,
    TradeResult,
    Waiting,
    judge,
)
from evals.spoken_judge import disabled_ending as disabled
from evals.spoken_run import Ports, observe, say_sentence
from evals.spoken_set import (
    CELLS,
    GoldCell,
    GoldTrade,
    SpokenGold,
    SpokenSentence,
    SpokenSet,
    load_spoken_set,
)
from evals.spoken_tally import SentenceRow, tally
from ledger_hand.flows import conversation
from ledger_hand.flows.progress import DEFAULT_TUNING
from ledger_hand.ledger.demo_book import DEMO_ASSETS, DEMO_MARKET_PRICES
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ports import ModelError, ModelErrorKind, ToolCall, ToolReply
from tests.fakes.routed_model import RoutedModel
from tests.fakes.scripted_model import Step, scripted_record
from tests.flows.scripted_flow import copied, row, screened, table

RECORD = ToolReply(
    text="", calls=(ToolCall(name="propose_trade_add", arguments={}),), record=scripted_record()
)
WHEN = "2026年11月20日14:43"
UNREACHABLE = ModelError(ModelErrorKind.UNREACHABLE, "no answer")


def _said(value: str, said: str) -> dict[str, object]:
    return {"value": value, "said": said}


NONE: dict[str, object] = {"none": True}
SKIP: dict[str, object] = {"skip": True}
ZERO: dict[str, object] = {"value": "0", "said": "手续费0", "zero": True}


def gold_trade(**cells: object) -> dict[str, object]:
    """A gold trade of 0.5 SOL at 200 USDT, unless ``cells`` says otherwise."""
    base: dict[str, object] = {
        "side": {"value": "buy"},
        "asset": _said("SOL", "SOL"),
        "quantity": _said("0.5", "0.5"),
        "price": _said("200", "200"),
        "total": _said("100", "100"),
        "quote": _said("USDT", "USDT"),
        "fee": ZERO,
        "fee_asset": SKIP,
        "occurred": {"value": "2026-11-20 14:43", "said": WHEN},
        "platform": {"value": ""},
    }
    return base | cells


def one_set(
    tmp_path: Path,
    text: str,
    trades: Sequence[dict[str, object]] = (),
    *,
    enabled: bool = True,
    half: str = "practice",
) -> SpokenSet:
    sentence: dict[str, object] = {
        "id": "R70-01" if half == "practice" else "R70-02",
        "kind": "invented",
        "language": "zh",
        "enabled": enabled,
        "text": text,
        "gold": {"expect": "send", "trades": list(trades)}
        if enabled
        else {"expect": "cannot_record", "why": ["money_not_in_ledger"]},
    }
    if not enabled:
        sentence["wait_for"] = "eur_payment"
    data = {
        "about": "invented",
        "tier": "r70",
        "half": half,
        "book": "exam",
        "now": "2026-11-24T23:55:00+01:00",
        "zone": "Europe/Budapest",
        "sentences": [sentence],
    }
    path = tmp_path / f"spoken-r70-{half}.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return load_spoken_set(path)


def model(
    text: str,
    rows: Sequence[dict[str, str]] = (),
    *,
    answers: Sequence[Step] = (),
    tools: Sequence[Step] = (RECORD,),
) -> RoutedModel:
    return RoutedModel(
        tools=tools,
        screen=[screened(("spot_trade", text[:8]))],
        extraction=[table(*rows)],
        answers=answers,
    )


def ports(scripted: RoutedModel, *, before: bool = False) -> Ports:
    """The ports for ``scripted``; ``before``, with a ledger that takes no card with empty
    cells, as every ledger was before 2026-11-25, so that the program asks each gap."""
    ledger_of = exam_ledger_before if before else exam_ledger
    return Ports(model=scripted, ledger_of=ledger_of, steps=6, tuning=DEFAULT_TUNING)


def exam_ledger_before() -> FakeLedger:
    """The exam book on a ledger that takes no card with empty cells."""
    return FakeLedger(assets=DEMO_ASSETS, trades=EXAM_TRADES, prices=DEMO_MARKET_PRICES)


def came(
    spoken: SpokenSet, scripted: RoutedModel, *, before: bool = False
) -> tuple[Observed, list[TradeResult]]:
    sentence = spoken.sentences[0]
    saids, answered = say_sentence(sentence, spoken, ports(scripted, before=before))
    observed = observe([said for _, said in saids], answered, spoken.zone)
    return observed, judge(sentence, observed, spoken.zone)


def endings(results: Sequence[TradeResult]) -> list[Ending]:
    return [result.ending for result in results]


SOL = f"{WHEN}买入0.5 SOL，成交价200 USDT，总额100 USDT，手续费0"
SOL_ROW = row(
    side="buy",
    coin="SOL",
    quantity="0.5 SOL",
    price="200 USDT",
    total="100 USDT",
    fee="0",
    time=WHEN,
)


# --- sent: ①, ①a, ②, ③ ------------------------------------------------------------


def test_every_cell_right_is_saved_with_no_cell_changed(tmp_path: Path) -> None:
    observed, results = came(one_set(tmp_path, SOL, [gold_trade()]), model(SOL, [SOL_ROW]))

    assert endings(results) == [Ending.CLEAN]
    assert observed.answered == frozenset()


def test_the_asset_code_is_answered_once_and_the_trade_saved_counts_apart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The program's table of company names would match "微软" first; turned off here.
    monkeypatch.setattr(conversation, "ASSISTANT_NAME_TABLE", False)
    text = f"{WHEN}买入1股微软，成交价400美元，总额400美元，手续费0"
    rows = [
        row(
            side="buy",
            coin="微软",
            quantity="1股",
            price="400美元",
            total="400美元",
            fee="0",
            time=WHEN,
        )
    ]
    gold = gold_trade(
        asset=_said("MSFT", "微软"),
        quantity=_said("1", "1"),
        price=_said("400", "400"),
        total=_said("400", "400"),
        quote=_said("USD", "美元"),
    )
    scripted = model(text, rows, answers=[copied("MSFT")])
    spoken = one_set(tmp_path, text, [gold])

    saids, answered = say_sentence(spoken.sentences[0], spoken, ports(scripted, before=True))
    observed = observe([said for _, said in saids], answered, spoken.zone)
    (result,) = judge(spoken.sentences[0], observed, spoken.zone)

    assert [words for words, _ in saids] == [text, "MSFT"]
    assert (result.ending, result.answered) == (Ending.CLEAN, True)
    assert (
        tally([SentenceRow(spoken.sentences[0], observed, (result,), None, "")])["clean_after_code"]
        == 1
    )


def test_a_wrong_cell_with_its_own_mark_is_marked(tmp_path: Path) -> None:
    text = f"{WHEN}买入1股MSFT，成交价400美金，总额400美金，手续费0"
    rows = [
        row(
            side="buy",
            coin="MSFT",
            quantity="1股",
            price="400美金",
            total="400美金",
            fee="0",
            time=WHEN,
        )
    ]
    # The gold money is set to USDT on purpose: the program guesses USD, and marks it.
    gold = gold_trade(
        asset=_said("MSFT", "MSFT"),
        quantity=_said("1", "1"),
        price=_said("400", "400"),
        total=_said("400", "400"),
        quote=_said("USDT", "美金"),
    )

    _, (result,) = came(one_set(tmp_path, text, [gold]), model(text, rows))

    assert (result.ending, result.wrong, result.unmarked) == (
        Ending.MARKED,
        frozenset({"quote"}),
        frozenset(),
    )


def test_a_wrong_figure_with_no_mark_is_silent(tmp_path: Path) -> None:
    text = f"{WHEN}买入0.6 SOL，成交价200 USDT，手续费0"
    rows = [row(side="buy", coin="SOL", quantity="0.6 SOL", price="200 USDT", fee="0", time=WHEN)]
    gold = gold_trade(total={"computed": True})

    _, (result,) = came(one_set(tmp_path, text, [gold]), model(text, rows))

    assert result.ending is Ending.SILENT
    assert result.unmarked == frozenset({"quantity", "total"})


def test_a_suspect_cell_sent_without_a_mark_is_silent(tmp_path: Path) -> None:
    text = f"{WHEN}买入0.6 SOL，成交价200 USDT，总额100 USDT，手续费0"
    rows = [row(side="buy", coin="SOL", quantity="0.6 SOL", price="200 USDT", fee="0", time=WHEN)]
    gold = gold_trade(quantity=_said("0.6", "0.6"), suspect=["quantity", "price", "total"])

    observed, (result,) = came(one_set(tmp_path, text, [gold]), model(text, rows))

    assert result.ending is Ending.SILENT
    assert {"quantity", "price"} <= result.unmarked
    counts = tally(
        [SentenceRow(one_set(tmp_path, text, [gold]).sentences[0], observed, (result,), None, "")]
    )
    assert counts["silent_with_passage_reminder"] == int(observed.passage_reminders)


def test_a_none_cell_filled_without_a_mark_is_silent(tmp_path: Path) -> None:
    gold = gold_trade(fee=NONE, fee_asset=NONE)

    _, (result,) = came(one_set(tmp_path, SOL, [gold]), model(SOL, [SOL_ROW]))

    assert result.ending is Ending.SILENT
    assert "fee" in result.unmarked


def test_a_wrong_asset_with_no_mark_is_silent(tmp_path: Path) -> None:
    gold = gold_trade(asset=_said("ETH", "SOL"))

    _, (result,) = came(one_set(tmp_path, SOL, [gold]), model(SOL, [SOL_ROW]))

    assert (result.ending, result.unmarked) == (Ending.SILENT, frozenset({"asset"}))


def test_a_wrong_side_with_no_mark_is_silent(tmp_path: Path) -> None:
    gold = gold_trade(side={"value": "sell"})

    _, (result,) = came(one_set(tmp_path, SOL, [gold]), model(SOL, [SOL_ROW]))

    assert (result.ending, result.unmarked) == (Ending.SILENT, frozenset({"side"}))


def test_a_trade_sent_beyond_the_gold_ones_counts_every_cell_as_wrong(tmp_path: Path) -> None:
    text = f"{WHEN}买入0.5 SOL，成交价200 USDT，总额100 USDT，手续费0；{WHEN}又买入0.5 SOL"
    second = row(side="buy", coin="SOL", quantity="0.5 SOL", price="200 USDT", fee="0", time=WHEN)

    _, results = came(one_set(tmp_path, text, [gold_trade()]), model(text, [SOL_ROW, second]))

    assert endings(results) == [Ending.CLEAN, Ending.SILENT]
    assert results[1].trade is None


def test_a_money_that_should_be_marked_a_guess_and_is_not_is_counted(tmp_path: Path) -> None:
    text = f"{WHEN}买入1股MSFT，成交价400美元，总额400美元，手续费0"
    rows = [
        row(
            side="buy",
            coin="MSFT",
            quantity="1股",
            price="400美元",
            total="400美元",
            fee="0",
            time=WHEN,
        )
    ]
    gold = gold_trade(
        asset=_said("MSFT", "MSFT"),
        quantity=_said("1", "1"),
        price=_said("400", "400"),
        total=_said("400", "400"),
        quote=_said("USD", "美元"),
        inferred=["quote"],
    )

    _, (result,) = came(one_set(tmp_path, text, [gold]), model(text, rows))

    assert (result.ending, result.guess_missing) == (Ending.CLEAN, frozenset({"quote"}))


def test_only_the_picked_asset_line_keeping_it_out_of_silent_is_counted() -> None:
    skipped = GoldCell(skip=True)
    cells = {name: skipped for name in CELLS} | {"asset": GoldCell(value="AAPL")}
    gold = SpokenGold(expect="send", trades=(GoldTrade(cells=cells),))
    alone = SpokenSentence(id="R70-01", kind="", language="zh", enabled=True, text="", gold=gold)
    sent = SentTrade(
        number=1,
        values={"asset": "MSFT"},
        marked=frozenset({"asset"}),
        picked_only=frozenset({"asset"}),
    )

    (result,) = judge(alone, Observed(sent=(sent,)), "Europe/Budapest")

    assert (result.ending, result.picked_saved) == (Ending.MARKED, True)


# --- asked: ④, and the drafts ------------------------------------------------------

MSFT_NO_FEE = f"{WHEN}买入1股MSFT，成交价400美元，总额400美元"


def _msft(**cells: object) -> dict[str, object]:
    msft: dict[str, object] = {
        "asset": _said("MSFT", "MSFT"),
        "quantity": _said("1", "1"),
        "price": _said("400", "400"),
        "total": _said("400", "400"),
        "quote": _said("USD", "美元"),
    }
    return gold_trade(**(msft | cells))


MSFT_ROW = row(side="buy", coin="MSFT", quantity="1股", price="400美元", total="400美元", time=WHEN)


def test_a_question_about_a_cell_the_gold_lets_be_asked_is_asked_rightly(tmp_path: Path) -> None:
    gold = _msft(fee=NONE, fee_asset=NONE)

    observed, (result,) = came(
        one_set(tmp_path, MSFT_NO_FEE, [gold]), model(MSFT_NO_FEE, [MSFT_ROW]), before=True
    )

    assert result.ending is Ending.ASKED_OK
    assert observed.waiting is not None and observed.waiting.cells == frozenset({"fee"})


def test_a_question_about_a_cell_the_gold_has_is_not_asked_rightly(tmp_path: Path) -> None:
    gold = _msft(fee={"value": "0", "said": "400"})

    _, (result,) = came(
        one_set(tmp_path, MSFT_NO_FEE, [gold]), model(MSFT_NO_FEE, [MSFT_ROW]), before=True
    )

    assert result.ending is Ending.ASKED_NOT_OK


def test_the_other_trade_waits_its_turn_and_a_wrong_draft_cell_is_counted(tmp_path: Path) -> None:
    text = f"{MSFT_NO_FEE}；{WHEN}又买入2股MSFT，成交价400美元"
    second = row(side="buy", coin="MSFT", quantity="2股", price="400美元", time=WHEN)
    golds = [
        _msft(fee=NONE, fee_asset=NONE),
        _msft(quantity=_said("3", "2"), total={"computed": True}, fee=NONE, fee_asset=NONE),
    ]

    observed, results = came(
        one_set(tmp_path, text, golds), model(text, [MSFT_ROW, second]), before=True
    )

    assert endings(results) == [Ending.ASKED_OK, Ending.NOT_ITS_TURN]
    assert results[1].draft_unmarked == frozenset({"quantity"})
    assert observed.waiting is not None and observed.waiting.trade == 0


def test_a_question_after_the_asset_code_is_left_unanswered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The program's table of company names would match "微软" first; turned off here.
    monkeypatch.setattr(conversation, "ASSISTANT_NAME_TABLE", False)
    text = f"{WHEN}买入1股微软，成交价400美元，总额400美元"
    rows = [
        row(side="buy", coin="微软", quantity="1股", price="400美元", total="400美元", time=WHEN)
    ]
    gold = _msft(asset=_said("MSFT", "微软"), fee=NONE, fee_asset=NONE)
    scripted = model(text, rows, answers=[copied("MSFT")])
    spoken = one_set(tmp_path, text, [gold])

    saids, answered = say_sentence(spoken.sentences[0], spoken, ports(scripted, before=True))
    observed = observe([said for _, said in saids], answered, spoken.zone)
    (result,) = judge(spoken.sentences[0], observed, spoken.zone)

    assert len(saids) == 2
    assert (result.ending, result.answered) == (Ending.ASKED_OK, True)


def test_a_question_about_the_fee_money_is_not_answered(tmp_path: Path) -> None:
    text = f"{WHEN}买入0.5 SOL，成交价200 USDT，总额100 USDT，手续费0.1"
    rows = [
        row(
            side="buy",
            coin="SOL",
            quantity="0.5 SOL",
            price="200 USDT",
            total="100 USDT",
            fee="0.1",
            time=WHEN,
        )
    ]
    gold = gold_trade(fee=_said("0.1", "0.1"), fee_asset=_said("USDT", "USDT"))
    spoken = one_set(tmp_path, text, [gold])

    saids, answered = say_sentence(spoken.sentences[0], spoken, ports(model(text, rows)))

    assert len(saids) == 1
    assert answered == frozenset()


# --- not sent, not measured, not enabled --------------------------------------------


def test_nothing_sent_and_nothing_waiting_is_not_sent(tmp_path: Path) -> None:
    words = ToolReply(text="I cannot do that.", calls=(), record=scripted_record())

    observed, (result,) = came(one_set(tmp_path, SOL, [gold_trade()]), model(SOL, tools=[words]))

    assert result.ending is Ending.NOT_SENT
    assert observed.reasons


def test_a_model_unreachable_twice_is_not_measured_after_one_wait(tmp_path: Path) -> None:
    spoken = one_set(tmp_path, SOL, [gold_trade()])
    scripted = model(SOL, tools=[UNREACHABLE, UNREACHABLE])
    waits: list[int] = []

    rows = spoken_run.run(
        spoken, ports(scripted), tmp_path / "out.jsonl", wait=lambda: waits.append(1)
    )

    assert waits == [1]
    assert endings(rows[0].results) == [Ending.NOT_MEASURED]
    counts = tally(rows)
    assert counts["not_measured"] == 1
    assert counts["clean_share_of"] == 0
    assert spoken_run.voided(counts)


def test_a_model_unreachable_once_is_measured_on_the_second_try(tmp_path: Path) -> None:
    spoken = one_set(tmp_path, SOL, [gold_trade()])
    scripted = RoutedModel(
        tools=[UNREACHABLE, RECORD],
        screen=[screened(("spot_trade", SOL[:8]))],
        extraction=[table(SOL_ROW)],
    )

    rows = spoken_run.run(spoken, ports(scripted), tmp_path / "out.jsonl", wait=lambda: None)

    assert endings(rows[0].results) == [Ending.CLEAN]
    line = json.loads((tmp_path / "out.jsonl").read_text("utf-8").splitlines()[0])
    assert line["tries"] == 2


EURO = f"{WHEN}花了9欧元买入0.1股KO，股价80美元，手续费0"


def _not_enabled(
    tmp_path: Path, rows: Sequence[dict[str, str]], *, before: bool = False, **options: object
) -> DisabledEnding | None:
    spoken = one_set(tmp_path, EURO, enabled=False)
    observed, results = came(spoken, model(EURO, rows, **options), before=before)  # type: ignore[arg-type]
    if observed.sent:
        assert endings(results) == [Ending.SILENT] * len(observed.sent)
    return disabled(spoken.sentences[0], observed)


def test_a_sentence_not_enabled_said_to_be_unrecordable_is_told(tmp_path: Path) -> None:
    euro = row(side="buy", coin="KO", quantity="0.1股", total="9欧元", fee="0", time=WHEN)
    assert _not_enabled(tmp_path, [euro]) is DisabledEnding.TOLD


def test_a_sentence_not_enabled_asked_about_is_asked(tmp_path: Path) -> None:
    asked = row(side="buy", coin="KO", quantity="0.1股", price="80美元", time=WHEN)
    assert _not_enabled(tmp_path, [asked], before=True) is DisabledEnding.ASKED


def test_a_sentence_not_enabled_that_sends_counts_every_trade_as_silent(tmp_path: Path) -> None:
    sent = row(side="buy", coin="KO", quantity="0.1股", price="80美元", fee="0", time=WHEN)
    assert _not_enabled(tmp_path, [sent]) is DisabledEnding.SENT


def test_a_sentence_not_enabled_answered_in_words_is_something_else(tmp_path: Path) -> None:
    words = ToolReply(text="Noted.", calls=(), record=scripted_record())
    assert _not_enabled(tmp_path, [], tools=[words]) is DisabledEnding.OTHER


# --- what a hidden half prints and logs -----------------------------------------------


def test_a_hidden_half_prints_its_counts_alone_and_is_logged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spoken = one_set(tmp_path, SOL, [gold_trade()], half="hidden")
    set_file = tmp_path / "spoken-r70-hidden.json"
    log = tmp_path / "hidden-runs.log"
    root = tmp_path
    results = tmp_path / "spoken-run-hidden.jsonl"
    results.write_text("", encoding="utf-8")
    monkeypatch.setattr(spoken_run, "REPO_ROOT", root)
    monkeypatch.setattr(hidden_runs, "REPO_ROOT", root)
    monkeypatch.setattr(spoken_run, "log_hidden_run", _logging_to(log))
    rows = spoken_run.run(spoken, ports(model(SOL, [SOL_ROW])), results, wait=lambda: None)
    out = io.StringIO()
    head = {
        "extraction_prompt": "first-3",
        "prompt": "assistant-4",
        "tier": "r70",
        "half": "hidden",
    }

    spoken_run.finish(rows, head, spoken, set_file, results, out)

    printed = out.getvalue()
    assert "R70-02" not in printed
    assert SOL not in printed and "0.5" not in printed
    assert "| Sentence |" not in printed
    (line,) = log.read_text("utf-8").splitlines()
    logged = json.loads(line)
    assert logged["results"] == results.name
    assert logged["totals"]["clean"] == 1


def _logging_to(log: Path):  # type: ignore[no-untyped-def]
    def logging(*arguments: object, **options: object) -> None:
        hidden_runs.log_hidden_run(*arguments, log=log, **options)  # type: ignore[arg-type]

    return logging


def test_a_practice_half_prints_one_row_a_sentence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spoken = one_set(tmp_path, SOL, [gold_trade()])
    results = tmp_path / "out.jsonl"
    results.write_text("", encoding="utf-8")
    monkeypatch.setattr(spoken_run, "REPO_ROOT", tmp_path)
    rows = spoken_run.run(spoken, ports(model(SOL, [SOL_ROW])), results, wait=lambda: None)
    out = io.StringIO()
    head = {
        "extraction_prompt": "first-3",
        "prompt": "assistant-4",
        "tier": "r70",
        "half": "practice",
    }

    spoken_run.finish(rows, head, spoken, tmp_path / "spoken-r70-practice.json", results, out)

    assert "| R70-01 |" in out.getvalue()
    end = json.loads(results.read_text("utf-8").splitlines()[-1])
    assert (end["record"], end["clean"], end["first_tool_right"]) == ("end", 1, 1)


class _WordsOnly:
    """A stand-in model that answers every turn in words, so nothing is ever recorded."""

    def chat_with_tools(
        self, items: object, tools: object, *, parameters: object = None
    ) -> ToolReply:
        return ToolReply(text="Noted.", calls=(), record=scripted_record())


HIDDEN = sorted(
    (Path(__file__).resolve().parents[2] / "evals" / "sets" / "spoken").glob(
        "spoken-r*-hidden.json"
    )
)


@pytest.mark.parametrize("path", HIDDEN, ids=lambda path: path.name)
def test_a_hidden_file_prints_no_sentence_identifier_or_piece(
    path: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spoken = load_spoken_set(path)
    results = tmp_path / "out.jsonl"
    results.write_text("", encoding="utf-8")
    monkeypatch.setattr(spoken_run, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(spoken_run, "log_hidden_run", _logging_to(tmp_path / "log"))
    stand_in = Ports(model=_WordsOnly(), ledger_of=exam_ledger, steps=6, tuning=DEFAULT_TUNING)  # type: ignore[arg-type]
    rows = spoken_run.run(spoken, stand_in, results, wait=lambda: None)
    out = io.StringIO()
    head = {
        "extraction_prompt": "first-3",
        "prompt": "assistant-4",
        "tier": spoken.tier,
        "half": "hidden",
    }

    spoken_run.finish(rows, head, spoken, path, results, out)

    printed = out.getvalue()
    leaked = [
        sentence.id
        for sentence in spoken.sentences
        if sentence.id in printed
        or sentence.text in printed
        or any(
            len(piece) >= 4 and piece in printed
            for trade in sentence.gold.trades
            for cell in trade.cells.values()
            for piece in cell.said
        )
    ]
    assert leaked == []


def test_a_silent_trade_of_a_reply_with_a_passage_reminder_is_counted_apart(
    tmp_path: Path,
) -> None:
    sentence = one_set(tmp_path, SOL, [gold_trade()]).sentences[0]
    silent = TradeResult(trade=0, ending=Ending.SILENT, unmarked=frozenset({"fee"}))
    with_reminder = SentenceRow(sentence, Observed(passage_reminders=True), (silent,), None, "")
    without = SentenceRow(sentence, Observed(), (silent,), None, "")

    assert tally([with_reminder, without])["silent_with_passage_reminder"] == 1
    assert tally([with_reminder, without])["silent"] == 2


# --- once the ledger takes a card with empty cells --------------------------------------------


def test_a_fee_not_said_is_sent_empty_and_counts_as_left_empty(tmp_path: Path) -> None:
    gold = _msft(fee=NONE, fee_asset=NONE)

    observed, (result,) = came(
        one_set(tmp_path, MSFT_NO_FEE, [gold]), model(MSFT_NO_FEE, [MSFT_ROW])
    )

    assert observed.cards is True and observed.waiting is None
    (sent,) = observed.sent
    assert (sent.values["fee"], sent.values["fee_asset"]) == (None, None)
    assert result.ending is Ending.EMPTY_LEFT


def test_three_figures_that_disagree_are_marked_on_the_card_not_silent(tmp_path: Path) -> None:
    text = f"{WHEN}买入0.5 SOL，成交价200 USDT，总额300 USDT，手续费0"
    rows = [
        row(side="buy", coin="SOL", quantity="0.5 SOL", price="200 USDT", total="300 USDT",
            fee="0", time=WHEN)
    ]  # fmt: skip
    gold = gold_trade(total=_said("300", "300"), suspect=["quantity", "price", "total"])
    gold.pop("suspect")
    trade = {**gold, "suspect": ["quantity", "price", "total"]}

    observed, (result,) = came(one_set(tmp_path, text, [trade]), model(text, rows))

    (sent,) = observed.sent
    assert sent.values["total"] == "300"
    assert {"quantity", "price", "total"} <= sent.marked
    assert result.ending is Ending.MARKED


@pytest.mark.parametrize(
    ("cells", "ask_ok", "ending"),
    [
        (frozenset({"side"}), (), Ending.ASKED_OK),
        (frozenset({"asset"}), (), Ending.ASKED_OK),
        (frozenset({"fee"}), (), Ending.ASKED_NOT_OK),
        (frozenset({"quote"}), (), Ending.ASKED_NOT_OK),
        (frozenset({"quote"}), ("quote",), Ending.ASKED_OK),
    ],
)
def test_once_cards_are_taken_only_the_asset_and_side_are_rightly_asked_by_default(
    tmp_path: Path, cells: frozenset[str], ask_ok: tuple[str, ...], ending: Ending
) -> None:
    trade = _msft(fee=NONE, fee_asset=NONE) | ({"ask_ok": list(ask_ok)} if ask_ok else {})
    sentence = one_set(tmp_path, MSFT_NO_FEE, [trade]).sentences[0]

    with_cards = Observed(waiting=Waiting(trade=0, cells=cells), cards=True)
    before = Observed(waiting=Waiting(trade=0, cells=frozenset({"fee"})), cards=False)

    (result,) = judge(sentence, with_cards, "Europe/Budapest")
    assert result.ending is ending
    if not ask_ok:
        # Before cards were taken, a question about the fee no one said was rightly asked.
        (asked_before,) = judge(sentence, before, "Europe/Budapest")
        assert asked_before.ending is Ending.ASKED_OK


# --- a reply that came back empty is measured, not "not reached" ------------------------------


def test_a_reply_that_came_back_empty_is_not_sent_with_why_not_unmeasured(tmp_path: Path) -> None:
    empty = ModelError(ModelErrorKind.MALFORMED_REPLY, "the reply was empty")
    spoken = one_set(tmp_path, SOL, [gold_trade()])
    scripted = model(SOL, tools=[empty, empty])
    waits: list[int] = []

    rows = spoken_run.run(
        spoken, ports(scripted), tmp_path / "out.jsonl", wait=lambda: waits.append(1)
    )

    assert waits == []
    (result,) = rows[0].results
    assert result.ending is Ending.NOT_SENT
    lines = [json.loads(one) for one in (tmp_path / "out.jsonl").read_text("utf-8").splitlines()]
    (line,) = [one for one in lines if "reasons" in one]
    assert any("malformed_reply" in reason for reason in line["reasons"]), line


def test_a_cell_said_but_sent_empty_on_a_card_is_marked_not_silent(tmp_path: Path) -> None:
    text = f"{WHEN}买入0.5 SOL，成交价200 USDT，总额100 USDT，手续费是零"
    rows = [
        row(side="buy", coin="SOL", quantity="0.5 SOL", price="200 USDT", total="100 USDT",
            time=WHEN)
    ]  # fmt: skip
    gold = gold_trade(fee={"value": "0", "said": "零", "zero": True})

    observed, (result,) = came(one_set(tmp_path, text, [gold]), model(text, rows))

    (sent,) = observed.sent
    assert sent.values["fee"] is None and "fee" in sent.marked
    assert result.ending is Ending.MARKED
    assert result.wrong == frozenset({"fee"}) and result.unmarked == frozenset()
