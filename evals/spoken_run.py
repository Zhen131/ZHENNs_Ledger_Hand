"""Measure recording the owner's way of speaking: each sentence of a tier's set, said once.

    .venv/bin/python -m evals.spoken_run --set evals/sets/spoken-r100-practice.json
    .venv/bin/python -m evals.spoken_run --set evals/sets/spoken-r70-hidden.json --model qwen2.5:7b

Run from the top of the repository. Each sentence is said once, in a chat
of its own, to the whole assistant (``flows.conversation.say``): the real
model, the system prompt a turn uses by default, a fresh fake ledger
holding the exam book (``exam_book``), the set's fixed moment and zone,
and the settings' steps and question tuning. The recording flow judges and
extracts with the prompt versions the assistant uses.

The ruler answers one question only: when the program asks which asset a
trade is (the asset itself, not its fee's money) and the gold asset of
that trade is in the exam book, it says the asset's code ("MSFT") once
for that trade, in the same chat, and goes on; anything asked after that,
or anything else, is left unanswered, and a question left waiting is what
came of it. Asking for the asset is what the program does while it does
not let the model pick assets from the ledger's list, so a trade saved
once the code was given is counted apart (①a).

What came of each sentence is judged trade by trade (``spoken_judge``)
and added up (``spoken_tally``). When the model cannot be reached, the
sentence is said again once, after a wait (three minutes, for another
process to let the model go); twice unreachable, it is not measured. When
more than a tenth of a file's sentences are not measured, the run says so
and should be run again.

The results go into ``evals/tool_results/``: a first line with the
conditions, one line for each sentence, and an ``end`` line with the
counts. A set whose file says it is the hidden half prints its counts
alone, never a sentence, and its run is added to the hidden-run log
(``hidden_runs``); a practice half prints one row a sentence as well.

Exit status: 0 the run finished; 2 it could not start.

Names defined here: ``RETRY_WAIT_SECONDS``, ``MOST_NOT_MEASURED``, ``Ports``,
``observe``, ``say_sentence``, ``run``, ``voided``, ``finish`` and ``main``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import TextIO

from evals.cells import issues_about
from evals.exam_book import exam_ledger
from evals.hidden_runs import log_hidden_run
from evals.run import Backend, local_backend
from evals.spoken_judge import Observed, SentTrade, Waiting, judge, local_minute
from evals.spoken_set import SpokenSentence, SpokenSet, load_spoken_set
from evals.spoken_tally import SentenceRow, markdown_sentences, markdown_totals, tally
from evals.tool_run import REPO_ROOT, TOOL_RESULTS_DIR, _git
from ledger_hand.assistant.outcome import Ending as TurnEnding
from ledger_hand.core.assets import AssetTable, MoneyReading
from ledger_hand.core.followup import AskCell, AskWhichCell, Cell, ConfirmCoin
from ledger_hand.core.ledger_records import TradeFacts
from ledger_hand.core.proposals import CheckOutcome
from ledger_hand.core.trade import Inferred, TradeDraft
from ledger_hand.extraction.issues import Issue
from ledger_hand.extraction.reply_table import Field
from ledger_hand.flows import assisting
from ledger_hand.flows.conversation import (
    ASSISTANT_EXTRACT_PROMPT,
    ASSISTANT_SCREEN_PROMPT,
    AssistantChat,
    Said,
    say,
)
from ledger_hand.flows.progress import Progress, Question, Tuning
from ledger_hand.flows.record_words import SPOKEN_REMINDERS, spoken_reminders
from ledger_hand.flows.recorded import Recorded, RecordEnding
from ledger_hand.flows.recording import tuning_from
from ledger_hand.ports import LedgerPort, ModelError, ModelPort
from ledger_hand.settings import SettingsError, load_assistant_steps, load_model_settings

# How long to wait before saying a sentence again when the model could not be reached.
RETRY_WAIT_SECONDS = 180
# More than this share of a file's sentences not measured voids the run.
MOST_NOT_MEASURED = Decimal("0.1")

_FIELD = {
    "side": Field.SIDE,
    "asset": Field.COIN,
    "quantity": Field.QUANTITY,
    "price": Field.PRICE,
    "total": Field.TOTAL,
    "quote": Field.PRICE_CURRENCY,
    "fee": Field.FEE,
    "fee_asset": Field.FEE_CURRENCY,
    "occurred": Field.TIME,
    "platform": Field.PLATFORM,
}
_CELL_NAME = {
    Cell.SIDE: "side",
    Cell.COIN: "asset",
    Cell.QUANTITY: "quantity",
    Cell.PRICE: "price",
    Cell.TOTAL: "total",
    Cell.FEE: "fee",
    Cell.FEE_COIN: "fee_asset",
    Cell.OCCURRED: "occurred",
    Cell.PLATFORM: "platform",
    Cell.NOTE: "note",
    Cell.QUOTE: "quote",
}
_GUESSED = {Inferred.QUOTE: "quote", Inferred.FEE_COIN: "fee_asset"}
_SENT_ENDINGS = frozenset({RecordEnding.SENT, RecordEnding.PARTLY_SENT, RecordEnding.MAYBE_SENT})


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --- what came of it ------------------------------------------------------------------


def _marked_by(issues: Sequence[Issue], position: int) -> frozenset[str]:
    """The cells of the trade at ``position`` that a reminder in ``issues`` is about."""
    return frozenset(
        name for name, field in _FIELD.items() if issues_about(field, position, issues)
    )


def _values(facts: TradeFacts, zone: str) -> dict[str, str | None]:
    return {
        "side": facts.side.value,
        "asset": facts.asset,
        "quantity": str(facts.quantity),
        "price": str(facts.price),
        "total": str(facts.total),
        "quote": facts.quote,
        "fee": str(facts.fee),
        "fee_asset": facts.fee_asset,
        "occurred": None if facts.date_only else local_minute(facts.occurred, zone),
        "platform": facts.platform,
    }


def _sent(recorded: Recorded, zone: str) -> tuple[SentTrade, ...]:
    if recorded.ending not in _SENT_ENDINGS:
        return ()
    checks = recorded.checks or (None,) * len(recorded.trades)
    reminders = spoken_reminders(recorded)
    progress = recorded.progress
    picked = {found.code for found in progress.picks if found.code is not None}
    sent: list[SentTrade] = []
    for number, facts, check in zip(recorded.numbers, recorded.trades, checks, strict=True):
        if check is not None and check.outcome is not CheckOutcome.PASSED:
            continue
        record = progress.trades[number - 1].record
        guessed = frozenset(_GUESSED[one] for one in record.inferred) if record else frozenset()
        said = _marked_by(reminders, number - 1) | guessed
        pick = frozenset({"asset"}) if facts.asset in picked else frozenset()
        sent.append(
            SentTrade(
                number=number,
                values=_values(facts, zone),
                marked=said | pick,
                picked_only=pick - said,
                inferred=guessed,
                day=facts.day.isoformat() if facts.date_only else None,
            )
        )
    return tuple(sent)


def _money(word: str | None, assets: AssetTable) -> str | None:
    if word is None:
        return None
    found = assets.money(word)
    if found.reading is MoneyReading.ONE and found.code is not None:
        return found.code
    coin = assets.find(word)
    return coin.symbol if coin is not None else None


def _draft_values(draft: TradeDraft, assets: AssetTable, zone: str) -> dict[str, str]:
    coin = assets.find(draft.coin) if draft.coin is not None else None
    moment = draft.occurred.value if draft.occurred is not None else None
    values: dict[str, str | None] = {
        "side": draft.side.value if draft.side is not None else None,
        "asset": coin.symbol if coin is not None else None,
        "quantity": None if draft.quantity is None else str(draft.quantity),
        "price": None if draft.price is None else str(draft.price),
        "total": None if draft.total is None else str(draft.total),
        "quote": _money(draft.quote, assets),
        "fee": None if draft.fee is None else str(draft.fee),
        "fee_asset": _money(draft.fee_coin, assets),
        "occurred": local_minute(moment, zone) if isinstance(moment, datetime) else None,
        "platform": draft.platform,
    }
    return {name: value for name, value in values.items() if value is not None}


def _asked_cells(question: Question) -> frozenset[str]:
    asked = question.asked
    if isinstance(asked, AskCell | ConfirmCoin):
        return frozenset({_CELL_NAME[asked.cell]})
    if isinstance(asked, AskWhichCell):
        return frozenset(_CELL_NAME[cell] for cell in asked.cells)
    return frozenset()


def _waiting(question: Question, progress: Progress, zone: str) -> Waiting:
    assets = progress.setting.assets
    reminders = [one for one in progress.reminders if one.kind in SPOKEN_REMINDERS]
    drafts: dict[int, dict[str, str]] = {}
    marked: dict[int, frozenset[str]] = {}
    for position, state in enumerate(progress.trades):
        drafts[position] = _draft_values(state.draft, assets, zone)
        guessed = frozenset(_GUESSED[one] for one in state.draft.inferred)
        marked[position] = _marked_by(reminders, position) | guessed
    return Waiting(
        trade=question.trade, cells=_asked_cells(question), drafts=drafts, draft_marked=marked
    )


def _unreachable(said: Said) -> bool:
    """Whether the model could not be asked: a failed call, not a reply that could not be read."""
    turn = said.turn
    if turn is not None and turn.ending is TurnEnding.MODEL_FAILED:
        return True
    recorded = said.recorded
    if recorded is None:
        return False
    failure = recorded.progress.failure
    if recorded.ending is RecordEnding.MODEL_FAILED and failure is not None:
        return failure.error is not None
    question = recorded.question
    return question is not None and question.model_failure is not None


def _reasons(said: Said) -> frozenset[str]:
    recorded = said.recorded
    if recorded is None:
        if said.turn is None:
            return frozenset({f"not recorded ({said.route.name.lower()})"})
        return frozenset({f"not recorded ({said.turn.ending.value})"})
    if recorded.ending is RecordEnding.NOTHING_TO_SEND:
        return frozenset(left.why.value for left in recorded.left_out)
    return frozenset({recorded.ending.value})


def observe(saids: Sequence[Said], answered: frozenset[int], zone: str) -> Observed:
    """What came of a sentence and the ruler's answers after it, in the shape the judge reads."""
    if any(_unreachable(said) for said in saids):
        return Observed(model_unreachable=True, answered=answered)
    last = saids[-1]
    recorded = last.recorded
    if recorded is None:
        return Observed(reasons=_reasons(last), answered=answered)
    question = recorded.question
    passage = any(one.draft is None for one in spoken_reminders(recorded))
    return Observed(
        sent=_sent(recorded, zone),
        waiting=_waiting(question, recorded.progress, zone) if question is not None else None,
        reasons=frozenset() if question is not None else _reasons(last),
        passage_reminders=passage,
        answered=answered,
    )


# --- saying one sentence ------------------------------------------------------------


@dataclass(frozen=True)
class Ports:
    model: ModelPort
    ledger_of: Callable[[], LedgerPort]
    steps: int
    tuning: Tuning


def _asset_code_to_say(
    said: Said, sentence: SpokenSentence, codes: frozenset[str], answered: set[int]
) -> str | None:
    """The asset's code to answer with, when the program asks which asset a gold trade is."""
    recorded = said.recorded
    question = recorded.question if recorded is not None else None
    if question is None:
        return None
    asked = question.asked
    if not isinstance(asked, AskCell | ConfirmCoin) or asked.cell is not Cell.COIN:
        return None
    golds = sentence.gold.trades
    if question.trade in answered or question.trade >= len(golds):
        return None
    code = golds[question.trade].cells["asset"].value
    return code if code in codes else None


def say_sentence(
    sentence: SpokenSentence, spoken: SpokenSet, ports: Ports
) -> tuple[list[tuple[str, Said]], frozenset[int]]:
    """``sentence`` said in a chat of its own, with the asset's code answered once a trade."""
    ledger = ports.ledger_of()
    codes = frozenset(asset.code for asset in ledger.list_assets())
    answered: set[int] = set()
    words: str | None = sentence.text
    state = AssistantChat()
    saids: list[tuple[str, Said]] = []
    while words is not None:
        said = say(
            state,
            words,
            model=ports.model,
            ledger=ledger,
            now=spoken.now,
            zone=spoken.zone,
            max_steps=ports.steps,
            tuning=ports.tuning,
        )
        saids.append((words, said))
        state = said.state
        words = _asset_code_to_say(said, sentence, codes, answered)
        if words is not None:
            recorded = said.recorded
            assert recorded is not None and recorded.question is not None
            answered.add(recorded.question.trade)
    return saids, frozenset(answered)


def _first_tool(said: Said) -> str | None:
    turn = said.turn
    if turn is None or not turn.steps or not turn.steps[0].calls:
        return None
    return turn.steps[0].calls[0].call.name


def _came(observed: Observed) -> str:
    if observed.model_unreachable:
        return "not measured: the model could not be reached"
    if observed.sent:
        return f"sent {len(observed.sent)}"
    if observed.waiting is not None:
        cells = ", ".join(sorted(observed.waiting.cells))
        return f"asked trade {observed.waiting.trade + 1}: {cells}"
    return "nothing sent: " + ", ".join(sorted(observed.reasons))


def _line(
    row: SentenceRow, saids: Sequence[tuple[str, Said]], seconds: float, tries: int
) -> dict[str, object]:
    return {
        "record": "sentence",
        "id": row.sentence.id,
        "enabled": row.sentence.enabled,
        "said": [words for words, _ in saids],
        "routes": [said.route.name for _, said in saids],
        "endings": [said.recorded.ending.value if said.recorded else None for _, said in saids],
        "first_tool": row.first_tool,
        "asset_answered": bool(row.observed.answered),
        "replies": [said.reply for _, said in saids],
        "sent": [dict(one.values) for one in row.observed.sent],
        "asked": None
        if row.observed.waiting is None
        else {"trade": row.observed.waiting.trade, "cells": sorted(row.observed.waiting.cells)},
        "reasons": sorted(row.observed.reasons),
        "results": [
            {
                "trade": result.trade,
                "ending": result.ending.name,
                "wrong": sorted(result.wrong),
                "unmarked": sorted(result.unmarked),
                "guess_missing": sorted(result.guess_missing),
                "draft_unmarked": sorted(result.draft_unmarked),
                "asset_answered": result.answered,
            }
            for result in row.results
        ],
        "tries": tries,
        "seconds": round(seconds, 1),
    }


def _one(
    sentence: SpokenSentence, spoken: SpokenSet, ports: Ports, wait: Callable[[], None]
) -> tuple[SentenceRow, list[tuple[str, Said]], int]:
    tries = 0
    while True:
        tries += 1
        saids, answered = say_sentence(sentence, spoken, ports)
        observed = observe([said for _, said in saids], answered, spoken.zone)
        if not observed.model_unreachable or tries == 2:
            break
        wait()
    row = SentenceRow(
        sentence=sentence,
        observed=observed,
        results=tuple(judge(sentence, observed, spoken.zone)),
        first_tool=_first_tool(saids[0][1]),
        came=_came(observed),
    )
    return row, saids, tries


def run(
    spoken: SpokenSet,
    ports: Ports,
    path: Path,
    wait: Callable[[], None] = lambda: time.sleep(RETRY_WAIT_SECONDS),
) -> list[SentenceRow]:
    """Say every sentence of the set, writing each sentence's line as it comes."""
    rows: list[SentenceRow] = []
    with path.open("a", encoding="utf-8") as out:
        for sentence in spoken.sentences:
            began = time.monotonic()
            row, saids, tries = _one(sentence, spoken, ports, wait)
            rows.append(row)
            line = _line(row, saids, time.monotonic() - began, tries)
            out.write(json.dumps(line, ensure_ascii=False) + "\n")
            out.flush()
    return rows


def _conditions(
    backend: Backend, started: datetime, set_file: Path, spoken: SpokenSet, steps: int
) -> dict[str, object]:
    prompt = assisting.DEFAULT_PROMPT
    results = TOOL_RESULTS_DIR.relative_to(REPO_ROOT).as_posix()
    return {
        "record": "run",
        "set_file": set_file.resolve().relative_to(REPO_ROOT).as_posix(),
        "set_sha256": _sha256(set_file.read_bytes()),
        "tier": spoken.tier,
        "half": spoken.half,
        "book": spoken.book,
        "prompt": prompt.name,
        "prompt_words_sha256": _sha256(prompt.words.encode("utf-8")),
        "screen_prompt": ASSISTANT_SCREEN_PROMPT.name,
        "extraction_prompt": ASSISTANT_EXTRACT_PROMPT.name,
        "commit": _git("rev-parse", "HEAD"),
        "worktree_clean": not _git("status", "--porcelain", "--", ".", f":(exclude){results}"),
        "model": backend.name,
        "model_fingerprint": backend.fingerprint,
        "server_version": backend.server_version,
        "base_url": backend.base_url,
        "parameters": dict(backend.parameters),
        "max_steps": steps,
        "now": spoken.now.isoformat(),
        "zone": spoken.zone,
        "started_at": started.isoformat(timespec="seconds"),
    }


def voided(counts: dict[str, object]) -> bool:
    """Whether more than a tenth of the sentences were not measured, so the run does not count."""
    measured = int(str(counts["sentences_enabled"])) + int(str(counts["sentences_disabled"]))
    missing = int(str(counts["sentences_not_measured"]))
    return measured > 0 and Decimal(missing) > MOST_NOT_MEASURED * measured


def finish(
    rows: Sequence[SentenceRow],
    head: dict[str, object],
    spoken: SpokenSet,
    set_file: Path,
    path: Path,
    out: TextIO,
) -> None:
    """The ``end`` line, the hidden-run log for a hidden half, and the tables printed."""
    counts = tally(rows)
    end = {"record": "end", **counts, "void": voided(counts)}
    with path.open("a", encoding="utf-8") as tail:
        tail.write(json.dumps(end, ensure_ascii=False) + "\n")
    if spoken.hidden:
        log_hidden_run(
            set_file,
            path,
            counts,
            extraction_prompt=str(head["extraction_prompt"]),
            prompt=str(head["prompt"]),
        )
    print(f"results: {path.relative_to(REPO_ROOT).as_posix()}", file=out)
    if end["void"]:
        print("more than a tenth of the sentences were not measured: run it again", file=out)
    print(markdown_totals(counts, head), file=out)
    if not spoken.hidden:
        print("", file=out)
        print(markdown_sentences(rows), file=out)


def main(arguments: Sequence[str] = (), *, out: TextIO = sys.stdout) -> int:
    """Run the measure; print the counts, and for a practice half the sentences."""
    parser = argparse.ArgumentParser(prog="evals.spoken_run")
    parser.add_argument("--model", default=None)
    parser.add_argument("--set", required=True, help="the set of sentences to run")
    options = parser.parse_args(arguments)
    set_file = Path(options.set).resolve()
    try:
        spoken = load_spoken_set(set_file)
        backend = local_backend(options.model)
        steps = load_assistant_steps()
        tuning = tuning_from(load_model_settings())
    except (SettingsError, ModelError, ValueError) as error:
        print(f"cannot start: {error}", file=out)
        return 2
    started = datetime.now(UTC)
    TOOL_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = started.strftime("%Y%m%dT%H%M%SZ")
    prompts = f"{ASSISTANT_EXTRACT_PROMPT.name}-{assisting.DEFAULT_PROMPT.name}"
    name = f"spoken-{stamp}-{set_file.stem}-{prompts}"
    path = TOOL_RESULTS_DIR / f"{name}.jsonl"
    head = _conditions(backend, started, set_file, spoken, steps)
    path.write_text(json.dumps(head, ensure_ascii=False) + "\n", encoding="utf-8")
    ports = Ports(model=backend.model, ledger_of=exam_ledger, steps=steps, tuning=tuning)
    rows = run(spoken, ports, path)
    finish(rows, head, spoken, set_file, path, out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
