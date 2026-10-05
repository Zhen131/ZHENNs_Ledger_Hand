"""Tests of judging one field: the same form on both sides, the six outcomes, half copies."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest

from evals.cells import (
    CellOutcome,
    EmptyReason,
    agrees,
    issues_about,
    judge_cell,
    shown,
    tidy_text,
)
from evals.gold import GoldCell
from ledger_hand.core.trade import Side
from ledger_hand.extraction.issues import Issue, IssueKind
from ledger_hand.extraction.reply_table import Field
from tests.evals.builders import at_minute, on_day


@pytest.mark.parametrize(
    ("field", "gold", "got"),
    [
        (Field.PRICE_CURRENCY, "USDT", "U"),
        (Field.PRICE_CURRENCY, "USDT", "刀"),
        (Field.FEE_CURRENCY, "USDT", "usdt"),
        (Field.COIN, "BTC", "比特币"),
        (Field.COIN, "BTC", "大饼"),
        (Field.COIN, "WIF", "WIF"),
        (Field.PRICE, Decimal("1200"), Decimal("1200.0")),
        (Field.QUANTITY, Decimal("0.5"), Decimal("0.50")),
        (Field.PLATFORM, "OKX", "ＯＫＸ"),
        (Field.PLATFORM, "OKX", " OKX "),
        (Field.OPINION, "感觉 还会涨", "感觉  还会涨"),
        (Field.SIDE, Side.BUY, Side.BUY),
        (Field.TIME, on_day(date(2026, 10, 4)), on_day(date(2026, 10, 4))),
        (
            Field.TIME,
            at_minute(datetime(2026, 10, 4, 21, 40)),
            at_minute(datetime(2026, 10, 4, 21, 40)),
        ),
    ],
)
def test_values_in_the_same_form_agree(field: Field, gold: object, got: object) -> None:
    assert agrees(field, gold, got)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("field", "gold", "got"),
    [
        (Field.PRICE_CURRENCY, "USDT", "BTC"),
        (Field.COIN, "BTC", "BCH"),
        (Field.PRICE, Decimal("94900"), Decimal("900")),
        (Field.PLATFORM, "OKX", "okx"),
        (Field.OPINION, "感觉还会涨", "感觉还会涨了"),
        (Field.SIDE, Side.BUY, Side.SELL),
        (Field.TIME, on_day(date(2026, 10, 4)), at_minute(datetime(2026, 10, 4, 0, 0))),
        (
            Field.TIME,
            at_minute(datetime(2026, 10, 4, 21, 40)),
            at_minute(datetime(2026, 10, 4, 9, 40)),
        ),
        (Field.FEE, Decimal("0"), None),
        (Field.FEE, None, Decimal("0")),
    ],
)
def test_other_values_do_not_agree(field: Field, gold: object, got: object) -> None:
    assert not agrees(field, gold, got)  # type: ignore[arg-type]


def test_two_empty_values_agree() -> None:
    assert agrees(Field.TOTAL, None, None)


def test_text_is_tidied_in_width_and_whitespace_only() -> None:
    assert tidy_text("　ＯＫＸ  app\t") == "OKX app"
    assert tidy_text("Okx") == "Okx"


def test_values_are_shown_as_text() -> None:
    assert shown(Decimal("94900.0")) == "94900.0"
    assert shown(Side.SELL) == "sell"
    assert shown(on_day(date(2026, 10, 4))) == "2026-10-04 (day)"
    assert shown(at_minute(datetime(2026, 10, 4, 21, 40))) == "2026-10-04T21:40:00+02:00 (minute)"
    assert shown(None) is None


def issue(kind: IssueKind, field: Field | None, draft: int | None = 0) -> Issue:
    return Issue(kind=kind, draft=draft, field=field)


PRICE = GoldCell("94,900", Decimal("94900"))


def test_the_right_value_is_right() -> None:
    result = judge_cell(Field.PRICE, PRICE, Decimal("94900"), (), "94,900")

    assert result.outcome is CellOutcome.RIGHT
    assert (result.gold, result.got, result.copied) == ("94900", "94900", "94,900")
    assert not result.half_copy


def test_both_empty_is_right() -> None:
    result = judge_cell(Field.TOTAL, GoldCell(None, None), None, (), None)

    assert result.outcome is CellOutcome.RIGHT


def test_a_value_where_the_gold_answer_is_empty_is_made_up() -> None:
    result = judge_cell(Field.OPINION, GoldCell(None, None), "感觉要涨", (), "感觉要涨")

    assert result.outcome is CellOutcome.MADE_UP


def test_empty_with_no_issue_is_left_empty_by_the_model() -> None:
    result = judge_cell(Field.PRICE, PRICE, None, (), None)

    assert result.outcome is CellOutcome.LEFT_EMPTY_BY_MODEL
    assert result.reason is None


@pytest.mark.parametrize(
    ("kind", "reason"),
    [
        (IssueKind.NOT_IN_PASSAGE, EmptyReason.NOT_IN_PASSAGE),
        (IssueKind.CUTS_A_NUMBER, EmptyReason.CUTS_A_NUMBER),
        (IssueKind.NUMBER_UNSURE, EmptyReason.NUMBER_NOT_READ),
        (IssueKind.NOT_A_NUMBER, EmptyReason.NUMBER_NOT_READ),
        (IssueKind.UNIT_NAMES_SEVERAL, EmptyReason.OTHER),
    ],
)
def test_empty_with_an_issue_is_left_empty_with_its_reason(
    kind: IssueKind, reason: EmptyReason
) -> None:
    about = (issue(kind, Field.PRICE),)

    result = judge_cell(Field.PRICE, PRICE, None, about, "94")

    assert result.outcome is CellOutcome.LEFT_EMPTY_WITH_REASON
    assert result.reason is reason
    assert result.issues == (kind,)


@pytest.mark.parametrize("kind", [IssueKind.TIME_REFUSED, IssueKind.TWO_TIMES])
def test_a_time_left_empty_by_the_time_reader(kind: IssueKind) -> None:
    gold = GoldCell("昨天", on_day(date(2026, 10, 4)))

    result = judge_cell(Field.TIME, gold, None, (issue(kind, Field.TIME),), "昨天")

    assert result.reason is EmptyReason.TIME_NOT_READ


def test_a_wrong_value_with_an_issue_about_it() -> None:
    gold = GoldCell("昨天晚上 9 点 40", at_minute(datetime(2026, 10, 4, 21, 40)))
    got = at_minute(datetime(2026, 10, 5, 9, 40))
    about = (issue(IssueKind.TIME_CAUTION, Field.TIME),)

    result = judge_cell(Field.TIME, gold, got, about, "9 点 40")

    assert result.outcome is CellOutcome.WRONG_WITH_ISSUE
    assert result.half_copy


def test_a_wrong_value_with_no_issue_is_silent() -> None:
    result = judge_cell(Field.PRICE, PRICE, Decimal("94"), (), "94,9")

    assert result.outcome is CellOutcome.WRONG_SILENT


def test_half_copies_let_through_and_caught() -> None:
    gold = GoldCell("9万 4900", Decimal("94900"))
    caught = (issue(IssueKind.CUTS_A_NUMBER, Field.PRICE),)

    through = judge_cell(Field.PRICE, gold, Decimal("4900"), (), "4900")
    stopped = judge_cell(Field.PRICE, gold, None, caught, "4900")

    assert (through.outcome, through.half_copy) == (CellOutcome.WRONG_SILENT, True)
    assert (stopped.outcome, stopped.half_copy) == (CellOutcome.LEFT_EMPTY_WITH_REASON, True)


def test_a_half_copy_of_a_number_the_rules_leave_empty() -> None:
    gold = GoldCell("3 w", None)

    result = judge_cell(Field.QUANTITY, gold, Decimal("3"), (), "3")

    assert (result.outcome, result.half_copy) == (CellOutcome.MADE_UP, True)


def test_a_shorter_copy_that_comes_out_right_is_no_half_copy() -> None:
    gold = GoldCell("0.5 ETH", Decimal("0.5"))

    result = judge_cell(Field.QUANTITY, gold, Decimal("0.5"), (), "0.5")

    assert (result.outcome, result.half_copy) == (CellOutcome.RIGHT, False)


def test_a_longer_or_other_copy_is_no_half_copy() -> None:
    gold = GoldCell("94,900", Decimal("94900"))

    longer = judge_cell(Field.PRICE, gold, None, (), "价格 94,900 刀")
    other = judge_cell(Field.PRICE, gold, Decimal("95000"), (), "95000")

    assert not longer.half_copy
    assert not other.half_copy


def test_issues_about_a_field_include_those_of_the_fields_that_fill_it() -> None:
    issues = (
        issue(IssueKind.UNIT_NOT_THE_PRICE_CURRENCY, Field.PRICE),
        issue(IssueKind.UNIT_NOT_THE_PRICE_CURRENCY, Field.TOTAL),
        issue(IssueKind.UNIT_NOT_THE_FEE_CURRENCY, Field.FEE),
        issue(IssueKind.UNIT_NOT_THE_COIN, Field.QUANTITY),
        issue(IssueKind.NUMBER_CAUTION, Field.QUANTITY),
        issue(IssueKind.NOT_IN_PASSAGE, Field.PRICE, draft=1),
        issue(IssueKind.NUMBERS_LEFT_OVER, None, draft=None),
        issue(IssueKind.SAME_AS_ANOTHER, None),
    )

    assert [i.field for i in issues_about(Field.PRICE_CURRENCY, 0, issues)] == [
        Field.PRICE,
        Field.TOTAL,
    ]
    assert [i.field for i in issues_about(Field.FEE_CURRENCY, 0, issues)] == [Field.FEE]
    assert [i.kind for i in issues_about(Field.COIN, 0, issues)] == [IssueKind.UNIT_NOT_THE_COIN]
    assert len(issues_about(Field.QUANTITY, 0, issues)) == 2
    assert [i.draft for i in issues_about(Field.PRICE, 1, issues)] == [1]
    assert issues_about(Field.OPINION, 0, issues) == ()
