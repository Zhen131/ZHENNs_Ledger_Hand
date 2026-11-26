"""Tests of the exam book: what it adds to the demo book, and what it leaves as it was.

The demo book and the invented book stay byte for byte as they were; the
exam book only adds trades, each in the money the demo book prices its
asset in; and for every recording sentence of the exam, the money of the
asset's last trade (what a vague word for money is guessed from) is the
same against the exam book as against the demo book, and is the gold
money of every trade whose money the gold marks as a guess. Failures name
sentences by their identifiers only. No model is called.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from evals.exam_book import EXAM_ADDED, EXAM_TRADES, exam_ledger
from evals.spoken_set import load_spoken_set
from ledger_hand.flows.last_money import last_money_of
from ledger_hand.ledger.demo_book import DEMO_ASSETS, DEMO_TRADES, demo_ledger

REPO = Path(__file__).resolve().parents[2]
SETS = sorted((REPO / "evals" / "sets" / "spoken").glob("spoken-r*.json"))
# The two books' files: the invented book as it stood before the exam book
# was added; the demo book as it stands since five market prices were added
# to it (2026-11-25), its assets and trades as they were.
BOOK_FILES = {
    "src/ledger_hand/ledger/demo_book.py": (
        "a2d528ace7a011e642c8b38922e53c81dd930c46dcbe2a4983963e005f85504b"
    ),
    "src/ledger_hand/ledger/invented_book.py": (
        "ee5c36c5876b22f35d282cdda21079bb2f12aedde9d125385d97cb5d06aa4b63"
    ),
}


def test_the_demo_and_invented_books_are_unchanged() -> None:
    for name, pinned in BOOK_FILES.items():
        assert hashlib.sha256((REPO / name).read_bytes()).hexdigest() == pinned, name


# The demo book's assets and trades as they stood before the exam book was
# added, so that a new digest above cannot hide a change to either.
DEMO_ASSET_CODES = [
    "USDT", "USD", "BTC", "ETH", "ADA", "MSFT", "SOL", "INTC", "KO", "AAPL", "NVDA", "PEP", "DOT",
]  # fmt: skip
DEMO_TRADE_KEYS = [f"t-{number}" for number in range(12, 21)] + [
    f"t-{number:02d}" for number in range(1, 12)
]


def test_the_demo_books_assets_and_trades_are_as_they_were() -> None:
    assert [asset.code for asset in DEMO_ASSETS] == DEMO_ASSET_CODES
    assert [key for key, _ in DEMO_TRADES] == DEMO_TRADE_KEYS


def test_the_exam_book_is_the_demo_book_and_seven_trades_after_it() -> None:
    assert EXAM_TRADES[: len(DEMO_TRADES)] == DEMO_TRADES
    assert [key for key, _ in EXAM_ADDED] == [f"t-{number}" for number in range(21, 28)]
    assert len({key for key, _ in EXAM_TRADES}) == len(EXAM_TRADES)


def test_each_trade_added_uses_the_money_the_demo_book_prices_its_asset_in() -> None:
    demo_money = {facts.asset: facts.quote for _, facts in DEMO_TRADES}
    assert all(facts.quote == demo_money[facts.asset] for _, facts in EXAM_ADDED)


def test_the_ledger_takes_every_trade_added() -> None:
    ledger = exam_ledger()
    for key, facts in EXAM_ADDED:
        result = ledger.propose_add((facts,), "a copy, to see the book holds it")
        assert all(check.proposal_id is not None for check in result.checks), key


def test_every_recording_sentence_guesses_the_same_money_as_against_the_demo_book() -> None:
    assert len(SETS) == 6
    off: list[str] = []
    for path in SETS:
        spoken = load_spoken_set(path)
        exam = last_money_of(exam_ledger(), spoken.now)
        demo = last_money_of(demo_ledger(), spoken.now)
        for sentence in spoken.sentences:
            for trade in sentence.gold.trades:
                asset = trade.cells["asset"].value
                assert asset is not None
                found, before = exam(asset).found, demo(asset).found
                same = found is not None and before is not None and found.money == before.money
                guessed_right = "quote" not in trade.inferred or (
                    found is not None and found.money == trade.cells["quote"].value
                )
                if not (same and guessed_right):
                    off.append(sentence.id)
    assert off == []
