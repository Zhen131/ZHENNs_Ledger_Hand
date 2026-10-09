"""Tests of the record of every reply read, and a gate over the committed results files.

``reads_of`` and ``copied_from_reads`` are checked on cases worked out by
hand. The gate reads every committed results file: a line with the record
must hold, under ``copied``, exactly the phrases the record gives, one entry
per draft; a line without it (every run before the record was added) is
read from ``copied`` as before. No model is called.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from evals.reads import copied_from_reads, reads_of
from evals.records import produced_from_line, read_results
from evals.run import RESULTS_DIR
from ledger_hand.extraction.reply_table import Field
from ledger_hand.extraction.splitting import CallStep, Purpose
from ledger_hand.ports import FinishReason, ModelReply, ReplyRecord
from tests.extraction.scripted_runs import row, table

RUNS = sorted(RESULTS_DIR.glob("*.jsonl")) if RESULTS_DIR.is_dir() else []
WHOLE = CallStep(Purpose.EXTRACT, None)
SPLIT = CallStep(Purpose.SPLIT, None)


def reply(text: str) -> ModelReply:
    record = ReplyRecord(
        model="x",
        elapsed_seconds=0.0,
        prompt_tokens=None,
        reply_tokens=None,
        finish=FinishReason.STOPPED,
    )
    return ModelReply(text=text, record=record)


def test_one_call_after_an_unreadable_reply_gives_the_rows_of_the_last_reply() -> None:
    rows = table(row(side="buy", coin="ETH", quantity="1 ETH"), row(), row(coin="SOL"))

    reads = reads_of([reply("not json"), reply(rows)], [WHOLE, WHOLE], [1])

    assert reads == [
        {"call": 0, "step": "extract", "segment": None, "rows": None, "drafts": []},
        {
            "call": 1,
            "step": "extract",
            "segment": None,
            "rows": [{"coin": "ETH", "quantity": "1 ETH"}, {"coin": "SOL"}],
            "drafts": [0, 1],
        },
    ]
    assert copied_from_reads(reads) == (
        {Field.COIN: "ETH", Field.QUANTITY: "1 ETH"},
        {Field.COIN: "SOL"},
    )


def test_segments_give_their_rows_in_turn_and_the_split_none() -> None:
    first = table(row(coin="ETH"), row(coin="BTC"))
    second = table(row(coin="SOL"))
    steps = [SPLIT, CallStep(Purpose.EXTRACT, 0), CallStep(Purpose.EXTRACT, 1)]

    reads = reads_of([reply('{"trades": []}'), reply(first), reply(second)], steps, [1, 2])

    assert reads[0] == {"call": 0, "step": "split", "segment": None}
    assert [entry["drafts"] for entry in reads[1:]] == [[0, 1], [2]]
    assert [cells[Field.COIN] for cells in copied_from_reads(reads)] == ["ETH", "BTC", "SOL"]


def test_replies_the_drafts_were_not_made_from_give_no_draft() -> None:
    steps = [CallStep(Purpose.EXTRACT, 0), WHOLE]

    reads = reads_of([reply(table(row(coin="ETH"))), reply(table(row(coin="SOL")))], steps, [1])

    assert reads[0]["drafts"] == []
    assert copied_from_reads(reads) == ({Field.COIN: "SOL"},)


def test_no_draft_gives_no_phrases() -> None:
    assert copied_from_reads([]) == ()
    assert copied_from_reads(reads_of([reply("no")], [WHOLE], [])) == ()


@pytest.mark.parametrize(
    "reads",
    [
        "not a list",
        [{"call": 0, "rows": [{"coin": "A"}], "drafts": [1]}],
        [{"call": 0, "rows": [{"coin": "A"}, {"coin": "B"}], "drafts": [0]}],
    ],
)
def test_a_record_that_does_not_count_the_drafts_from_0_is_refused(reads: object) -> None:
    with pytest.raises(ValueError):
        copied_from_reads(reads)


def test_a_step_is_needed_for_every_reply() -> None:
    with pytest.raises(ValueError):
        reads_of([reply("x")], [], [])


@pytest.mark.parametrize("path", RUNS, ids=lambda path: path.name)
def test_a_committed_line_holds_the_phrases_its_record_gives_one_per_draft(path: Path) -> None:
    for line in read_results(path).sentences:
        copied = line.get("copied") or []
        as_written = tuple(
            {Field(name): text for name, text in entry.items()}
            for entry in copied  # type: ignore[union-attr]
        )
        produced = produced_from_line(line)
        assert produced.copied == as_written, line["id"]
        if "reads" in line:
            assert copied_from_reads(line["reads"]) == as_written
            assert len(as_written) == len(produced.drafts), line["id"]
