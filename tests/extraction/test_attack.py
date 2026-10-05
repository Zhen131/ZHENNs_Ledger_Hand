"""Attacks on extraction: odd passages, odd phrases and odd replies, through the whole of it.

Every case must end in one of the four results, quickly, and never in an
exception. The random cases use a fixed seed, so every run feeds the same
inputs. Every passage is invented.
"""

from __future__ import annotations

import json
import random
import time
from decimal import Decimal

import pytest

from ledger_hand.core.ledger_limits import RAW_TEXT_MAX_LENGTH
from ledger_hand.core.trade import TradeDraft
from ledger_hand.extraction.extractor import (
    Extracted,
    ModelFailed,
    PassageRefused,
    ReplyUnreadable,
)
from ledger_hand.extraction.issues import IssueKind
from ledger_hand.extraction.reply_parser import MAX_REPLY_CHARACTERS, MAX_ROWS, ReplyProblem
from ledger_hand.extraction.reply_table import Field
from ledger_hand.ports import FinishReason, ModelReply, ReplyRecord
from tests.extraction.scripted_runs import row, run, table

OUTCOMES = (Extracted, PassageRefused, ReplyUnreadable, ModelFailed)
# Generous for a slow machine: every case below takes well under a second here.
TIME_ALLOWED_SECONDS = 5.0

ODD_CHARACTERS = [
    "\N{ZERO WIDTH SPACE}",
    "\N{ZERO WIDTH JOINER}",
    "\N{BYTE ORDER MARK}",
    "\N{COMBINING ACUTE ACCENT}",
    "\N{RIGHT-TO-LEFT OVERRIDE}",
    "\x00",
    "\x1b",
    "\N{GRINNING FACE}",
    "\N{MATHEMATICAL BOLD CAPITAL B}",
    "\N{ROMAN NUMERAL TWELVE}",
    "\N{CIRCLED DIGIT ONE}",
    "\N{ARABIC-INDIC DIGIT THREE}",
    "\N{HALFWIDTH KATAKANA LETTER KA}",
    "\N{FULLWIDTH DIGIT ZERO}",
    "\N{FULLWIDTH LATIN CAPITAL LETTER B}",
    "\N{IDEOGRAPHIC SPACE}",
    "\N{NO-BREAK SPACE}",
    "\U00020000",
    "豈",
    "\N{CYRILLIC CAPITAL LETTER VE}",
]
ALPHABET = (
    list(
        "0123456789.,:-+%$kKwWuU \t\n个枚刀万千百亿点零一二两三四五六七八九十买卖了比特币以太坊大饼"
        "BTCETHUSDTSOLbtc昨天今天晚上下午上午刚才周五lastFridaypm半多约"
    )
    + ODD_CHARACTERS
)


def timed(passage: str, *steps: object, **options: object) -> tuple[object, float]:
    started = time.monotonic()
    result, _ = run(passage, *steps, **options)  # type: ignore[arg-type]
    return result, time.monotonic() - started


def check_outcome(result: object) -> None:
    assert isinstance(result, OUTCOMES), result
    if isinstance(result, Extracted):
        assert all(isinstance(draft, TradeDraft) for draft in result.drafts)


# --- random passages and replies -------------------------------------------------------


class Fuzz:
    def __init__(self, seed: int) -> None:
        self.random = random.Random(seed)

    def text(self, longest: int) -> str:
        return "".join(self.random.choice(ALPHABET) for _ in range(self.random.randint(0, longest)))

    def value(self, depth: int = 0) -> object:
        pick = self.random.random()
        if depth > 3 or pick < 0.5:
            return self.text(12)
        if pick < 0.6:
            return self.random.choice([None, True, False, 0, -1, 1.5, 10**30])
        if pick < 0.8:
            return [self.value(depth + 1) for _ in range(self.random.randint(0, 3))]
        keys = [field.value for field in Field] + ["extra"]
        return {self.random.choice(keys): self.value(depth + 1) for _ in range(4)}

    def piece(self, passage: str) -> str:
        if not passage:
            return ""
        start = self.random.randrange(len(passage))
        return passage[start : start + self.random.randint(0, 12)]

    def row(self, passage: str) -> dict[str, object]:
        cells: dict[str, object] = {}
        for field in Field:
            pick = self.random.random()
            if field is Field.SIDE:
                cells[field.value] = self.random.choice(["buy", "sell", ""])
            elif pick < 0.6:
                cells[field.value] = self.piece(passage)
            elif pick < 0.85:
                cells[field.value] = self.text(8)
            elif pick < 0.95:
                cells[field.value] = self.value()
        return cells

    def reply(self, passage: str) -> str:
        pick = self.random.random()
        rows = [self.row(passage) for _ in range(self.random.randint(0, 6))]
        whole = json.dumps({"trades": rows}, ensure_ascii=self.random.random() < 0.5)
        if pick < 0.7:
            return whole
        if pick < 0.8:
            return json.dumps(self.value())
        if pick < 0.9:
            return whole[: self.random.randrange(len(whole) + 1)]
        return self.text(30)


@pytest.mark.parametrize("seed", range(10))
def test_random_passages_and_replies_always_end_in_one_of_the_four_results(seed: int) -> None:
    fuzz = Fuzz(seed)
    started = time.monotonic()

    for _ in range(300):
        passage = fuzz.text(60)
        result, _ = run(passage, fuzz.reply(passage), fuzz.reply(passage))
        check_outcome(result)

    assert time.monotonic() - started < TIME_ALLOWED_SECONDS


# --- odd passages ------------------------------------------------------------------------


@pytest.mark.parametrize("character", ODD_CHARACTERS)
def test_a_passage_of_odd_characters_with_odd_pieces_copied_out_of_it(character: str) -> None:
    passage = f"买了 0.1{character} BTC{character}，价格 6万{character}{character}，{character}"
    reply = table(
        row(
            side="buy",
            coin=f"BTC{character}",
            quantity=f"0.1{character} BTC",
            price=f"6万{character}",
            opinion=character,
            platform=f"{character}，",
            time=character * 3,
        )
    )

    result, took = timed(passage, reply)

    check_outcome(result)
    assert took < TIME_ALLOWED_SECONDS


@pytest.mark.parametrize(
    "passage",
    [
        ("买了 0.1 BTC，价格 6万；" * 2000)[:RAW_TEXT_MAX_LENGTH],
        "1" * RAW_TEXT_MAX_LENGTH,
        "1 " * (RAW_TEXT_MAX_LENGTH // 2),
        "一" * RAW_TEXT_MAX_LENGTH,
        "\N{GRINNING FACE}" * (RAW_TEXT_MAX_LENGTH // 2),
        "\N{ZERO WIDTH SPACE}" * (RAW_TEXT_MAX_LENGTH - 1) + "x",
        "\n" * (RAW_TEXT_MAX_LENGTH - 1) + "买",
    ],
    ids=["trades", "one-digit-run", "many-numbers", "chinese-ones", "emoji", "zero-width", "gaps"],
)
def test_the_longest_passages_with_the_most_rows_end_quickly(passage: str) -> None:
    pieces = [passage[:7], passage[-5:], passage[100:110]]
    rows = [
        row(side="buy", quantity=pieces[n % 3], opinion=pieces[(n + 1) % 3]) for n in range(200)
    ]

    result, took = timed(passage, table(*rows))

    check_outcome(result)
    assert took < TIME_ALLOWED_SECONDS


def test_every_field_copying_the_whole_long_passage_ends_quickly() -> None:
    passage = ("买了 0.1 BTC，价格 6万；" * 2000)[:15_000]
    every_field = {field.value: passage for field in Field if field is not Field.SIDE}

    result, took = timed(passage, table(*[every_field] * 6))

    assert isinstance(result, Extracted)
    assert len(result.drafts) == 6
    assert result.drafts[0].note == passage
    assert result.drafts[0].occurred is None
    assert took < TIME_ALLOWED_SECONDS


# --- odd phrases the core has to read ------------------------------------------------------


@pytest.mark.parametrize(
    "phrase",
    [
        "1e5",
        "NaN",
        "Infinity",
        "-5",
        "+5",
        "0",
        "0.0000000000000000001",
        "1" * 41,
        "１２３４５６７８９０" * 5,
        "\N{ARABIC-INDIC DIGIT THREE}",
        "\N{ROMAN NUMERAL TWELVE}",
        "\N{CIRCLED DIGIT ONE}",
        "5 个个个",
        "5 BTC BTC BTC",
        "5\N{ZERO WIDTH SPACE}",
        "5 \N{GRINNING FACE}",
        "两三千",
        "一亿五千",
        "零点零零零零零零零零零零零零零零零零零零零一",
    ],
)
@pytest.mark.parametrize("field", ["quantity", "price", "total", "fee"])
def test_a_number_phrase_the_core_will_not_read_leaves_the_field_empty(
    phrase: str, field: str
) -> None:
    passage = f"买了 BTC，{phrase}，就这样"

    result, _ = run(passage, table(row(side="buy", coin="BTC", **{field: phrase})))

    assert isinstance(result, Extracted)
    value = getattr(result.drafts[0], field)
    assert value is None or (isinstance(value, Decimal) and value.is_finite())
    if value is None:
        assert any(issue.field is Field(field) for issue in result.issues)


@pytest.mark.parametrize(
    "phrase",
    [
        "9999 年 1 月 1 号",
        "0001-01-01",
        "昨天" * 50,
        "\N{GRINNING FACE} 9 点",
        "25:61",
        "2 月 30 号",
        "last Fridayy",
        "9" * 200,
        "１０月２日",
    ],
)
def test_a_time_phrase_the_core_will_not_read_leaves_the_time_empty(phrase: str) -> None:
    passage = f"{phrase} 买了 BTC"

    result, _ = run(passage, table(row(side="buy", coin="BTC", time=phrase)))

    assert isinstance(result, Extracted)
    occurred = result.drafts[0].occurred
    if occurred is None:
        assert any(issue.field is Field.TIME for issue in result.issues)


@pytest.mark.parametrize(
    "coin", ["\N{GRINNING FACE}", "B T C", "BTC" * 20, "\x00", "USDT", "比特币现金经典", "𝐁𝐎𝐍𝐊"]
)
def test_an_odd_coin_goes_into_the_draft_for_the_check_to_judge(coin: str) -> None:
    passage = f"买了 5 {coin}"

    result, _ = run(passage, table(row(side="buy", coin=coin, quantity=f"5 {coin}")))

    assert isinstance(result, Extracted)
    assert result.drafts[0].coin


# --- odd replies -----------------------------------------------------------------------------


def _with_finish(text: str, finish: FinishReason) -> ModelReply:
    record = ReplyRecord(
        model="scripted", elapsed_seconds=0.0, prompt_tokens=None, reply_tokens=None, finish=finish
    )
    return ModelReply(text=text, record=record)


@pytest.mark.parametrize(
    ("reply", "problem"),
    [
        ("", ReplyProblem.NOT_JSON),
        ("\x00", ReplyProblem.NOT_JSON),
        ('{"trades": [{"coin": "\ud800"}]}', ReplyProblem.CELL_NOT_TEXT),
        ('{"trades": [], "x": ' + "[" * 200_000 + "]" * 200_000 + "}", None),
        (" " * (MAX_REPLY_CHARACTERS - 20) + '{"trades": []}', None),
        (" " * MAX_REPLY_CHARACTERS + '{"trades": []}', ReplyProblem.TOO_LONG),
        (json.dumps({"trades": [{}] * (MAX_ROWS + 1)}), ReplyProblem.TOO_MANY_ROWS),
        ('{"trades": [{"price": ' + "9" * 100_000 + "}]}", ReplyProblem.CELL_NOT_TEXT),
        ('{"trades": [{"opinion": "' + "买" * 900_000 + '"}]}', None),
        ('{"trades": [{"coin": "BTC", "coin": "BTC"}]}', ReplyProblem.REPEATED_KEY),
    ],
    ids=[
        "empty",
        "nul",
        "lone-surrogate",
        "deep-nesting-in-ignored-key",
        "just-within-length",
        "too-long",
        "too-many-rows",
        "huge-number",
        "huge-cell",
        "repeated-key",
    ],
)
def test_an_odd_reply_is_read_or_refused_and_never_raises(
    reply: str, problem: ReplyProblem | None
) -> None:
    result, took = timed("买了 BTC", reply, reply)

    check_outcome(result)
    assert took < TIME_ALLOWED_SECONDS
    if problem is not None:
        assert isinstance(result, ReplyUnreadable)
        assert result.problems == (problem, problem)


def test_a_cut_off_reply_whose_finish_is_not_reported_is_simply_not_json() -> None:
    cut = _with_finish('{"trades": [{"coin": "BT', FinishReason.NOT_REPORTED)

    result, _ = timed("买了 BTC", cut, cut)

    assert isinstance(result, ReplyUnreadable)
    assert result.problems == (ReplyProblem.NOT_JSON, ReplyProblem.NOT_JSON)


def test_the_same_row_given_the_most_times_is_kept_each_time() -> None:
    same = row(side="buy", coin="BTC", quantity="0.1 BTC")

    result, took = timed("买了 0.1 BTC", table(*[same] * MAX_ROWS))

    assert isinstance(result, Extracted)
    assert len(result.drafts) == MAX_ROWS
    repeats = [issue for issue in result.issues if issue.kind is IssueKind.SAME_AS_ANOTHER]
    assert len(repeats) == MAX_ROWS - 1
    assert all(issue.same_as == 0 for issue in repeats)
    assert took < TIME_ALLOWED_SECONDS


def test_every_row_empty_gives_no_drafts_and_one_issue_each() -> None:
    result, _ = timed("买了 0.1 BTC", table(*[row()] * 50))

    assert isinstance(result, Extracted)
    assert result.drafts == ()
    assert [issue.kind for issue in result.issues].count(IssueKind.EMPTY_ROW) == 50


def test_many_long_phrases_that_each_cut_thousands_of_numbers_end_quickly() -> None:
    passage = "12 " * 5461
    fields = [field for field in Field if field is not Field.SIDE]
    rows = [
        {field.value: "12 " * (10 * number + place) + "1" for place, field in enumerate(fields)}
        for number in range(70)
    ]

    result, took = timed(passage, table(*rows))

    assert isinstance(result, Extracted)
    assert all(issue.kind is not IssueKind.NOT_IN_PASSAGE for issue in result.issues)
    assert took < TIME_ALLOWED_SECONDS
