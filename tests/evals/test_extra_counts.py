"""Tests of the three more counts, on results files written by hand (no model, no runner).

Each case is worked out by hand in its comment. Every passage is invented.
"""

from __future__ import annotations

import io
from datetime import date
from pathlib import Path

from evals import extra_counts as counting
from evals.records import append_line, draft_to_json, issue_to_json, read_results
from evals.tables import summarize
from ledger_hand.core.trade import TradeDraft
from ledger_hand.extraction.issues import Issue, IssueKind
from ledger_hand.extraction.reply_table import Field
from tests.evals.builders import NOW, ZONE, draft, on_day

TOTAL_PASSAGE = "Bought 2 SOL for 300 USDT in total, 150 each"
TOTAL_GOLD = {
    "side": "buy",
    "coin": ["SOL", "SOL"],
    "quantity": ["2 SOL", "2"],
    "price": ["150", "150"],
    "total": ["300 USDT", "300"],
    "price_currency": ["USDT", "USDT"],
    "missing": ["FEE", "OCCURRED"],
}


def sentence_line(
    name: str,
    text: str,
    gold: list[dict[str, object]],
    drafts: list[TradeDraft],
    copied: list[dict[str, str]],
    issues: list[Issue] = (),  # type: ignore[assignment]
) -> dict[str, object]:
    return {
        "record": "sentence",
        "id": name,
        "text": text,
        "now": NOW,
        "zone": ZONE,
        "language": "en",
        "group": "scored",
        "kind": None,
        "features": [],
        "gold": gold,
        "result": "extracted",
        "drafts": [draft_to_json(made) for made in drafts],
        "copied": copied,
        "issues": [issue_to_json(issue) for issue in issues],
        "seconds": 1.0,
    }


def counts_of(tmp_path: Path, *lines: dict[str, object]) -> dict[str, object]:
    path = tmp_path / "run.jsonl"
    append_line(path, {"record": "run", "set": "debug", "prompt": "first"})
    for line in lines:
        append_line(path, line)
    append_line(path, {"record": "end", "finished_at": "x", "seconds_this_session": 1.0})
    return counting.extra_counts(read_results(path))


def sol(price: str | None, total: str | None = "300") -> TradeDraft:
    fields: dict[str, object] = {
        "side": "buy",
        "coin": "SOL",
        "quantity": "2",
        "price_currency": "USDT",
    }
    if price is not None:
        fields["price"] = price
    if total is not None:
        fields["total"] = total
    return draft(TOTAL_PASSAGE, **fields)


# --- a total put as the price ---------------------------------------------------------


def test_the_total_copied_as_the_price_counts_once(tmp_path: Path) -> None:
    # The model wrote "300 USDT" under price: the gold phrase of the total.
    # The draft's price is 300, the gold price 150: both ways say yes, one count.
    line = sentence_line(
        "a",
        TOTAL_PASSAGE,
        [TOTAL_GOLD],
        [sol("300")],
        [{"coin": "SOL", "quantity": "2 SOL", "price": "300 USDT", "total": "300 USDT"}],
    )

    counts = counts_of(tmp_path, line)

    assert counts["total_as_price"] == [
        {
            "id": "a",
            "text": TOTAL_PASSAGE,
            "draft": 1,
            "field": "price",
            "copied": "300 USDT",
            "got": "300",
            "gold_phrase": "300 USDT",
            "gold": "300",
        }
    ]


def test_the_total_value_as_the_price_counts_though_the_phrase_differs(tmp_path: Path) -> None:
    # The model wrote "300" (not the gold phrase "300 USDT"), and the draft's
    # price is 300, the gold total, while the gold price is 150: one count.
    line = sentence_line(
        "b", TOTAL_PASSAGE, [TOTAL_GOLD], [sol("300", None)], [{"price": "300", "coin": "SOL"}]
    )

    counts = counts_of(tmp_path, line)

    assert [case["copied"] for case in counts["total_as_price"]] == ["300"]  # type: ignore[union-attr]


def test_a_right_price_or_a_price_equal_to_the_total_by_the_gold_is_not_counted(
    tmp_path: Path,
) -> None:
    # "c": the price is 150, right: no count. "d": one coin, so the gold price
    # and the gold total are both 3000; the draft's price 3000 is the gold
    # price, and the model copied "3000", not the total's phrase "3000 USDT".
    one_coin = "Bought 1 ETH at 3000, 3000 USDT in all"
    gold = {
        "side": "buy",
        "coin": ["ETH", "ETH"],
        "quantity": ["1 ETH", "1"],
        "price": ["3000", "3000"],
        "total": ["3000 USDT", "3000"],
        "price_currency": ["USDT", "USDT"],
        "missing": ["FEE", "OCCURRED"],
    }
    eth = draft(one_coin, side="buy", coin="ETH", quantity="1", price="3000", total="3000")
    lines = [
        sentence_line("c", TOTAL_PASSAGE, [TOTAL_GOLD], [sol("150")], [{"price": "150"}]),
        sentence_line("d", one_coin, [gold], [eth], [{"price": "3000", "total": "3000 USDT"}]),
    ]

    assert counts_of(tmp_path, *lines)["total_as_price"] == []


def test_no_total_in_the_gold_answer_means_no_count(tmp_path: Path) -> None:
    passage = "Bought 2 SOL at 150"
    gold = {
        "side": "buy",
        "coin": ["SOL", "SOL"],
        "quantity": ["2 SOL", "2"],
        "price": ["150", "150"],
        "missing": ["FEE", "OCCURRED"],
    }
    made = draft(passage, side="buy", coin="SOL", quantity="2", price="150")
    line = sentence_line("e", passage, [gold], [made], [{"price": "150"}])

    assert counts_of(tmp_path, line)["total_as_price"] == []


# --- half copies, the second way ------------------------------------------------------

SHIB = "刚买了 100 万 SHIB，0.00001 一个"
SHIB_GOLD = {
    "side": "buy",
    "coin": ["SHIB", "SHIB"],
    "quantity": ["100 万 SHIB", "1000000"],
    "price": ["0.00001", "0.00001"],
    "missing": ["FEE", "OCCURRED"],
}
SPACED = "Bought 0.01 BTC at 94 900"
SPACED_GOLD = {
    "side": "buy",
    "coin": ["BTC", "BTC"],
    "quantity": ["0.01 BTC", "0.01"],
    "price": ["94 900", None],
    "missing": ["ONE_MORE_OF_QUANTITY_PRICE_TOTAL", "FEE", "OCCURRED"],
}


def test_a_half_copy_whose_field_came_out_right_counts_the_second_way_only(
    tmp_path: Path,
) -> None:
    # The model copied "100 万" of "100 万 SHIB": the draft holds 1000000, right.
    # The summary's way (only fields not right) counts 0; the second way 1.
    made = draft(SHIB, side="buy", coin="SHIB", quantity="1000000", price="0.00001")
    line = sentence_line(
        "f", SHIB, [SHIB_GOLD], [made], [{"coin": "SHIB", "quantity": "100 万", "price": "0.00001"}]
    )

    counts = counts_of(tmp_path, line)

    assert counts["half_copies_not_right"] == 0
    (case,) = counts["half_copies_any"]  # type: ignore[misc]
    assert (case["field"], case["copied"], case["gold_phrase"], case["right"]) == (
        "quantity",
        "100 万",
        "100 万 SHIB",
        True,
    )


def test_a_half_copy_left_empty_where_the_gold_is_empty_counts_the_second_way_only(
    tmp_path: Path,
) -> None:
    # The model copied "900" of "94 900"; the program left the price empty
    # (it cuts a number), and the gold price is empty too: right. Second way 1,
    # the summary's way 0.
    cut = Issue(kind=IssueKind.CUTS_A_NUMBER, draft=0, field=Field.PRICE, phrase="900")
    made = draft(SPACED, side="buy", coin="BTC", quantity="0.01")
    line = sentence_line(
        "g", SPACED, [SPACED_GOLD], [made], [{"quantity": "0.01 BTC", "price": "900"}], [cut]
    )

    counts = counts_of(tmp_path, line)

    assert counts["half_copies_not_right"] == 0
    assert [case["right"] for case in counts["half_copies_any"]] == [True]  # type: ignore[union-attr]


def test_a_half_copy_that_reached_the_draft_counts_both_ways(tmp_path: Path) -> None:
    # The model copied "900" and the draft holds 900 where the gold is empty:
    # made up, not right. Both ways count 1; the whole phrase or another
    # field's phrase does not count.
    made = draft(SPACED, side="buy", coin="BTC", quantity="0.01", price="900")
    line = sentence_line(
        "h", SPACED, [SPACED_GOLD], [made], [{"quantity": "0.01 BTC", "price": "900"}]
    )

    counts = counts_of(tmp_path, line)

    assert counts["half_copies_not_right"] == 1
    assert [case["field"] for case in counts["half_copies_any"]] == ["price"]  # type: ignore[union-attr]


def test_half_copy_any() -> None:
    assert counting.half_copy_any("900", "94 900")
    assert counting.half_copy_any(" 3 ", "3 w DOGE")
    assert not counting.half_copy_any("94 900", "94　900")
    assert not counting.half_copy_any("", "94 900")
    assert not counting.half_copy_any(None, "94 900")
    assert not counting.half_copy_any("1900", "94 900")


# --- a time written in another language -------------------------------------------------


def test_an_english_time_written_in_chinese_and_the_other_way_round_count(
    tmp_path: Path,
) -> None:
    english = "Sold 3 ETH at 2,400 yesterday"
    chinese = "昨天卖了 3 ETH，2,400 一个"

    def gold(time: str) -> dict[str, object]:
        return {
            "side": "sell",
            "coin": ["ETH", "ETH"],
            "quantity": ["3 ETH", "3"],
            "price": ["2,400", "2400"],
            "time": [time, "2026-10-04", "day"],
            "missing": ["FEE"],
        }

    def made(text: str) -> TradeDraft:
        return draft(text, side="sell", coin="ETH", quantity="3", price="2400")

    def missed(phrase: str) -> Issue:
        return Issue(kind=IssueKind.NOT_IN_PASSAGE, draft=0, field=Field.TIME, phrase=phrase)

    copied = {"coin": "ETH", "quantity": "3 ETH", "price": "2,400"}
    lines = [
        # "i": an English time written in Chinese: counts.
        sentence_line(
            "i",
            english,
            [gold("yesterday")],
            [made(english)],
            [{**copied, "time": "昨天"}],
            [missed("昨天")],
        ),
        # "j": a Chinese time written in English: counts.
        sentence_line(
            "j",
            chinese,
            [gold("昨天")],
            [made(chinese)],
            [{**copied, "time": "yesterday"}],
            [missed("yesterday")],
        ),
        # "k": not a piece of the passage, but English both: no count.
        sentence_line(
            "k",
            english,
            [gold("yesterday")],
            [made(english)],
            [{**copied, "time": "yday"}],
            [missed("yday")],
        ),
    ]
    right = draft(
        english, side="sell", coin="ETH", quantity="3", price="2400", time=on_day(date(2026, 10, 4))
    )
    # "l": the time is right: no issue, no count.
    lines.append(
        sentence_line("l", english, [gold("yesterday")], [right], [{**copied, "time": "yesterday"}])
    )

    counts = counts_of(tmp_path, *lines)

    cases = counts["time_in_another_language"]
    assert isinstance(cases, list)
    assert [(case["id"], case["copied"], case["gold_phrase"]) for case in cases] == [
        ("i", "昨天", "yesterday"),
        ("j", "yesterday", "昨天"),
    ]


def test_has_chinese() -> None:
    assert counting.has_chinese("昨天 18:20")
    assert not counting.has_chinese("yesterday at 18:20")


# --- the tables -------------------------------------------------------------------------


def test_the_tables_hold_each_count_and_every_case(tmp_path: Path) -> None:
    line = sentence_line(
        "a",
        TOTAL_PASSAGE,
        [TOTAL_GOLD],
        [sol("300")],
        [{"coin": "SOL", "quantity": "2 SOL", "price": "300 USDT", "total": "300 USDT"}],
    )
    counts = counts_of(tmp_path, line)

    text = counting.extra_markdown(counts)

    assert "| A total put as the price | 1 |" in text
    assert "| Half copies, any field whose phrase is part of the gold phrase | 0 |" in text
    assert "| A time written in another language | 0 |" in text
    assert f"| a: {TOTAL_PASSAGE} | 1 | price | 300 USDT | 300 | 300 USDT | 300 |" in text


def test_the_counts_leave_the_summary_as_it_is(tmp_path: Path) -> None:
    line = sentence_line("a", TOTAL_PASSAGE, [TOTAL_GOLD], [sol("300")], [{"price": "300 USDT"}])
    counts_of(tmp_path, line)
    results = read_results(tmp_path / "run.jsonl")
    before = summarize(results)

    counting.extra_counts(results)

    assert summarize(results) == before
    assert "total_as_price" not in before


def test_the_script_prints_the_tables(tmp_path: Path) -> None:
    line = sentence_line("a", TOTAL_PASSAGE, [TOTAL_GOLD], [sol("300")], [{"price": "300 USDT"}])
    counts_of(tmp_path, line)
    out = io.StringIO()

    assert counting.main([str(tmp_path / "run.jsonl")], out=out) == 0
    assert "#### Three more counts" in out.getvalue()
    assert counting.main([str(tmp_path / "missing.jsonl")], out=io.StringIO()) == 2
