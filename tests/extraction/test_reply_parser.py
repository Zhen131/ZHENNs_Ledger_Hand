"""Tests of reading the model's reply against the table's shape.

Every reply below is invented. A reply that has the shape gives rows; any
other reply gives one reason, and nothing ever raises.
"""

from __future__ import annotations

import json

import pytest

from ledger_hand.core.trade import Side
from ledger_hand.extraction.reply_parser import (
    MAX_REPLY_CHARACTERS,
    MAX_ROWS,
    ReplyProblem,
    ReplyRows,
    Unreadable,
    read_reply,
)
from ledger_hand.extraction.reply_table import COPIED_FIELDS, REPLY_TABLE, SIDE_WORDS, Field
from ledger_hand.ports import FinishReason, ModelReply, ReplyRecord

FULL_ROW = {
    "side": "buy",
    "coin": "BTC",
    "quantity": "0.02",
    "price": "94,900",
    "total": "",
    "price_currency": "",
    "fee": "2 USDT",
    "fee_currency": "",
    "time": "9:40",
    "platform": "",
    "opinion": "我觉得要涨",
}


def reply(text: str, finish: FinishReason = FinishReason.STOPPED) -> ModelReply:
    record = ReplyRecord(
        model="scripted",
        elapsed_seconds=0.0,
        prompt_tokens=None,
        reply_tokens=None,
        finish=finish,
    )
    return ModelReply(text=text, record=record)


def rows_of(text: str) -> ReplyRows:
    result = read_reply(reply(text))
    assert isinstance(result, ReplyRows), result
    return result


def problem_of(text: str, finish: FinishReason = FinishReason.STOPPED) -> ReplyProblem:
    result = read_reply(reply(text, finish))
    assert isinstance(result, Unreadable), result
    return result.problem


def table(*rows: object) -> str:
    return json.dumps({"trades": list(rows)}, ensure_ascii=False)


# --- the table itself -------------------------------------------------------


def test_the_table_is_a_list_of_flat_rows_of_text() -> None:
    row = REPLY_TABLE["properties"]["trades"]["items"]  # type: ignore[index]

    assert REPLY_TABLE["required"] == ["trades"]
    assert REPLY_TABLE["properties"]["trades"]["type"] == "array"  # type: ignore[index]
    assert list(row["properties"]) == [field.value for field in Field]
    assert row["required"] == [field.value for field in Field]
    assert row["additionalProperties"] is False
    for field in COPIED_FIELDS:
        assert row["properties"][field.value] == {"type": "string"}
    assert row["properties"]["side"] == {"type": "string", "enum": ["buy", "sell", ""]}


def test_the_field_names_are_plain_words() -> None:
    assert [field.value for field in Field] == [
        "side",
        "coin",
        "quantity",
        "price",
        "total",
        "price_currency",
        "fee",
        "fee_currency",
        "time",
        "platform",
        "opinion",
    ]
    assert set(SIDE_WORDS) == {"buy", "sell", ""}


# --- replies that have the shape ---------------------------------------------


def test_a_full_row_is_read_with_its_text_as_written() -> None:
    (row,) = rows_of(table(FULL_ROW)).rows

    assert row.side is Side.BUY
    assert row.cells == {
        Field.COIN: "BTC",
        Field.QUANTITY: "0.02",
        Field.PRICE: "94,900",
        Field.FEE: "2 USDT",
        Field.TIME: "9:40",
        Field.OPINION: "我觉得要涨",
    }


def test_an_empty_list_is_no_rows() -> None:
    assert rows_of('{"trades": []}').rows == ()


def test_rows_keep_their_order() -> None:
    rows = rows_of(table({"coin": "BTC", "side": "sell"}, {"coin": "ETH"}, {"coin": "SOL"})).rows

    assert [row.cells[Field.COIN] for row in rows] == ["BTC", "ETH", "SOL"]
    assert [row.side for row in rows] == [Side.SELL, None, None]


def test_a_missing_field_counts_as_empty() -> None:
    (row,) = rows_of(table({"coin": "BTC"})).rows

    assert row.side is None
    assert row.cells == {Field.COIN: "BTC"}


@pytest.mark.parametrize("blank", ["", " ", "\t\n", "\N{IDEOGRAPHIC SPACE}", "\N{NO-BREAK SPACE}"])
def test_text_of_nothing_but_whitespace_counts_as_empty(blank: str) -> None:
    (row,) = rows_of(table({"coin": blank, "price": "3,420"})).rows

    assert row.cells == {Field.PRICE: "3,420"}


def test_keys_the_table_does_not_have_are_ignored() -> None:
    row_with_more = {**FULL_ROW, "leverage": "10x", "Coin": "ETH", "notes": ["a"], "n": 5}
    reply_with_more = {"trades": [row_with_more], "comment": "done", "count": 1}

    (row,) = rows_of(json.dumps(reply_with_more)).rows

    assert row.cells[Field.COIN] == "BTC"
    assert set(row.cells) <= set(COPIED_FIELDS)


def test_an_empty_row_is_read_and_says_it_is_empty() -> None:
    (row,) = rows_of(table({field.value: "" for field in Field})).rows

    assert row.is_empty
    assert not rows_of(table({"side": "buy"})).rows[0].is_empty


def test_text_with_odd_characters_is_still_text() -> None:
    odd = "\N{ZERO WIDTH SPACE}BTC\N{GRINNING FACE}𝐁"

    (row,) = rows_of(table({"coin": odd})).rows

    assert row.cells == {Field.COIN: odd}


def test_the_reply_may_be_surrounded_by_whitespace() -> None:
    assert rows_of("\n  " + table(FULL_ROW) + "\n").rows


# --- replies that miss the shape --------------------------------------------


def test_a_reply_cut_off_at_the_length_limit_is_not_read() -> None:
    assert problem_of(table(FULL_ROW), FinishReason.LENGTH_LIMIT) is ReplyProblem.CUT_OFF
    assert problem_of('{"trades": [{"coin": "BT', FinishReason.LENGTH_LIMIT) is (
        ReplyProblem.CUT_OFF
    )


def test_a_reply_whose_finish_is_not_reported_is_read() -> None:
    assert isinstance(read_reply(reply(table(FULL_ROW), FinishReason.NOT_REPORTED)), ReplyRows)


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "not json at all",
        '{"trades": [',
        '{"trades": []',
        "{'trades': []}",
        '{"trades": [],}',
        '```json\n{"trades": []}\n```',
        'Here you go: {"trades": []}',
        '{"trades": []} and more',
        '{"trades": [{"coin": NaN}]}',
        '{"trades": [{"coin": Infinity}]}',
        '{"trades": [{"coin": -Infinity}]}',
        "\N{BYTE ORDER MARK}" + '{"trades": []}',
    ],
)
def test_text_that_is_not_json_is_not_read(text: str) -> None:
    assert problem_of(text) is ReplyProblem.NOT_JSON


def test_lists_nested_beyond_the_parser_are_not_json() -> None:
    assert problem_of("[" * 100_000 + "]" * 100_000) is ReplyProblem.NOT_JSON
    assert problem_of('{"a":' * 50_000 + "1" + "}" * 50_000) is ReplyProblem.NOT_JSON


@pytest.mark.parametrize(
    "text",
    [
        '{"trades": [], "trades": []}',
        '{"trades": [{"coin": "BTC", "coin": "ETH"}]}',
        '{"trades": [{"coin": "BTC", "extra": {"a": 1, "a": 2}}]}',
    ],
)
def test_a_key_written_twice_is_not_read(text: str) -> None:
    assert problem_of(text) is ReplyProblem.REPEATED_KEY


@pytest.mark.parametrize(
    "text",
    [
        "[]",
        json.dumps([FULL_ROW]),
        "null",
        "true",
        "5",
        '"trades"',
        "{}",
        '{"Trades": []}',
        '{"trade": []}',
        '{"trades": null}',
        '{"trades": "none"}',
        '{"trades": {"coin": "BTC"}}',
        '{"trades": 0}',
        '{"rows": [{"coin": "BTC"}]}',
    ],
)
def test_anything_but_an_object_with_a_list_of_trades_is_not_read(text: str) -> None:
    assert problem_of(text) is ReplyProblem.NO_TRADES_LIST


def test_more_rows_than_the_limit_are_not_read() -> None:
    assert len(rows_of(table(*[FULL_ROW] * MAX_ROWS)).rows) == MAX_ROWS
    assert problem_of(table(*[FULL_ROW] * (MAX_ROWS + 1))) is ReplyProblem.TOO_MANY_ROWS
    assert problem_of(table(*[{}] * 5000)) is ReplyProblem.TOO_MANY_ROWS


@pytest.mark.parametrize("item", [None, "BTC", 5, 1.5, True, [], [FULL_ROW], ["buy", "BTC"]])
def test_a_row_that_is_not_an_object_is_not_read(item: object) -> None:
    assert problem_of(table(FULL_ROW, item)) is ReplyProblem.ROW_NOT_AN_OBJECT


@pytest.mark.parametrize("value", [None, 0, 0.02, -1, True, False, [], ["BTC"], {}, {"a": "b"}])
@pytest.mark.parametrize("field", list(Field))
def test_a_field_holding_anything_but_text_is_not_read(field: Field, value: object) -> None:
    assert problem_of(table({**FULL_ROW, field.value: value})) is ReplyProblem.CELL_NOT_TEXT


def test_a_number_of_thousands_of_digits_is_not_built() -> None:
    huge = "9" * 50_000

    assert problem_of('{"trades": [{"price": ' + huge + "}]}") is ReplyProblem.CELL_NOT_TEXT
    assert problem_of('{"trades": [{"price": 1e999999}]}') is ReplyProblem.CELL_NOT_TEXT


@pytest.mark.parametrize("escape", ["\\ud800", "\\udfff", "\\udc80abc"])
def test_text_with_a_lone_surrogate_is_not_valid_text(escape: str) -> None:
    text = '{"trades": [{"coin": "' + escape + '"}]}'

    assert problem_of(text) is ReplyProblem.CELL_NOT_TEXT


@pytest.mark.parametrize(
    "side", ["Buy", "BUY", "sell ", " buy", "买", "卖", "long", "short", "bought", "b", " "]
)
def test_a_side_other_than_the_three_words_is_not_read(side: str) -> None:
    assert problem_of(table({**FULL_ROW, "side": side})) is ReplyProblem.SIDE_NOT_ALLOWED


def test_one_bad_row_makes_the_whole_reply_unreadable() -> None:
    assert problem_of(table(FULL_ROW, FULL_ROW, {"coin": 5})) is ReplyProblem.CELL_NOT_TEXT


def test_a_reply_longer_than_the_limit_is_not_parsed() -> None:
    long_but_fine = table({"opinion": "x" * (MAX_REPLY_CHARACTERS - 100)})
    too_long = table({"opinion": "x" * MAX_REPLY_CHARACTERS})

    assert len(long_but_fine) <= MAX_REPLY_CHARACTERS
    assert isinstance(read_reply(reply(long_but_fine)), ReplyRows)
    assert problem_of(too_long) is ReplyProblem.TOO_LONG
    assert problem_of("[" * (MAX_REPLY_CHARACTERS + 1)) is ReplyProblem.TOO_LONG
