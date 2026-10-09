"""Tests of putting the pieces of each trade back together into segments of the passage.

Every passage below is invented. Nothing is sent to a model.
"""

from __future__ import annotations

from ledger_hand.extraction.passage import Passage, PieceMiss
from ledger_hand.extraction.segments import SEPARATOR, PieceMissed, segments_of

THREE = (
    "今天在 Bybit 先买了 0.3 ETH 价格 2,350，又卖了 40 个 SOL 总共 6,200 U，"
    "还买了 2 个 BNB 价格 590，手续费都是 1 U"
)


def segments(passage: str, *trades: tuple[str, ...]) -> tuple[str, ...] | PieceMissed:
    return segments_of(Passage(passage), trades)


def test_each_trade_gets_its_pieces_and_the_shared_ones_as_the_passages_own_text() -> None:
    made = segments(
        THREE,
        ("今天在 Bybit", "先买了 0.3 ETH 价格 2,350", "手续费都是 1 U"),
        ("今天在 Bybit", "又卖了 40 个 SOL 总共 6,200 U", "手续费都是 1 U"),
        ("今天在 Bybit", "还买了 2 个 BNB 价格 590", "手续费都是 1 U"),
    )

    assert made == (
        "今天在 Bybit 先买了 0.3 ETH 价格 2,350，手续费都是 1 U",
        "今天在 Bybit，又卖了 40 个 SOL 总共 6,200 U，手续费都是 1 U",
        "今天在 Bybit，还买了 2 个 BNB 价格 590，手续费都是 1 U",
    )


def test_every_run_of_a_segment_is_a_piece_of_the_passage() -> None:
    made = segments(THREE, ("手续费都是 1 U", "今天在 Bybit", "又卖了 40 个 SOL"))

    assert isinstance(made, tuple)
    runs = made[0].split(SEPARATOR)
    assert runs == ["今天在 Bybit", "又卖了 40 个 SOL", "手续费都是 1 U"]
    assert all(run in THREE for run in runs)


def test_pieces_that_overlap_touch_or_stand_apart_by_spacing_become_one_run() -> None:
    passage = "Today on Kraken I sold 2 LTC at 72.4; fee 0.1 USDT"

    overlapping = segments(passage, ("Today on Kraken", "Kraken I sold"))
    touching = segments(passage, ("Today on", " Kraken"))
    spaced = segments(passage, ("sold 2 LTC at 72.4", "fee 0.1 USDT"))

    assert overlapping == ("Today on Kraken I sold",)
    assert touching == ("Today on Kraken",)
    assert spaced == ("sold 2 LTC at 72.4; fee 0.1 USDT",)


def test_pieces_apart_by_words_are_joined_by_the_separator() -> None:
    passage = "Today on Kraken I sold 2 LTC at 72.4 and 3 DOT at 4.1"

    assert segments(passage, ("Today on Kraken I sold", "3 DOT at 4.1")) == (
        "Today on Kraken I sold" + SEPARATOR + "3 DOT at 4.1",
    )


def test_a_piece_is_found_with_extractions_tidying_and_taken_as_the_passage_writes_it() -> None:
    passage = "昨天买了 ０.５ 个 ETH，价格 3,050"

    assert segments(passage, ("买了 0.5  个 ETH ",)) == ("买了 ０.５ 个 ETH",)


def test_a_piece_not_in_the_passage_is_reported_with_why() -> None:
    passage = "Sold 1 ETH at 2,980 and 300 ARB at 0.71"

    assert segments(passage, ("Sold 1 ETH at 2,980",), ("Sold 300 ARB",)) == PieceMissed(
        "Sold 300 ARB", PieceMiss.NOT_IN_PASSAGE
    )


def test_a_piece_that_cuts_a_number_is_reported_with_why() -> None:
    passage = "买了 2 个 BNB 价格 1,590"

    assert segments(passage, ("价格 1",)) == PieceMissed("价格 1", PieceMiss.CUTS_A_NUMBER)


def test_empty_pieces_are_left_out_and_a_trade_without_pieces_gives_no_segment() -> None:
    passage = "Sold 1 ETH at 2,980"

    assert segments(passage, ("", "  "), ("Sold 1 ETH",)) == ("Sold 1 ETH",)
    assert segments(passage) == ()


def test_a_piece_that_stands_twice_is_taken_where_it_first_stands() -> None:
    passage = "买了 1 个 OP，又买了 2 个 ARB"

    assert segments(passage, ("2 个 ARB", "买了")) == ("买了" + SEPARATOR + "2 个 ARB",)
