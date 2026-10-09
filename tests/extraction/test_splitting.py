"""Tests of splitting a passage first and extracting each segment, with the scripted model.

Every passage and reply below is invented. The scripted model plays the
split's reply first and then one extraction reply per segment, in order.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from ledger_hand.extraction.extractor import (
    Extracted,
    ModelFailed,
    PassageProblem,
    PassageRefused,
    ReplyUnreadable,
    extract,
)
from ledger_hand.extraction.issues import Issue, IssueKind
from ledger_hand.extraction.prompts.first import FIRST_PROMPT
from ledger_hand.extraction.prompts.split import SPLIT_PROMPT
from ledger_hand.extraction.reply_parser import MAX_ROWS, ReplyProblem
from ledger_hand.extraction.reply_table import REPLY_TABLE, Field
from ledger_hand.extraction.segments import SEPARATOR
from ledger_hand.extraction.split_table import SPLIT_TABLE, SplitProblem
from ledger_hand.extraction.splitting import (
    CallStep,
    Purpose,
    Route,
    SplitExtraction,
    split_then_extract,
)
from ledger_hand.ports import Message, ModelError, ModelErrorKind, ModelParameters, Role
from tests.extraction.scripted_runs import NOW, ZONE, row, table
from tests.fakes.scripted_model import ScriptedModel, Step

THREE = (
    "今天在 Bybit 先买了 0.3 ETH 价格 2,350，又卖了 40 个 SOL 总共 6,200 U，"
    "还买了 2 个 BNB 价格 590，手续费都是 1 U"
)
SHARED = ("今天在 Bybit", "手续费都是 1 U")
OWN = ("先买了 0.3 ETH 价格 2,350", "又卖了 40 个 SOL 总共 6,200 U", "还买了 2 个 BNB 价格 590")
ONE = "昨天在 OKX 买了 0.5 个 ETH，价格 3,050，手续费 0.3U"
ONE_TABLE = table(
    row(
        side="buy",
        coin="ETH",
        quantity="0.5 个 ETH",
        price="3,050",
        fee="0.3U",
        time="昨天",
        platform="OKX",
    )
)


def split_reply(*trades: tuple[str, ...]) -> str:
    return json.dumps({"trades": [{"pieces": list(t)} for t in trades]}, ensure_ascii=False)


THREE_SPLIT = split_reply(*((SHARED[0], own, SHARED[1]) for own in OWN))


def shared_row(**cells: str) -> dict[str, str]:
    return row(platform="Bybit", fee="1 U", time="今天", **cells)


THREE_TABLES = (
    table(shared_row(side="buy", coin="ETH", quantity="0.3 ETH", price="2,350")),
    table(shared_row(side="sell", coin="SOL", quantity="40 个 SOL", total="6,200 U")),
    table(shared_row(side="buy", coin="BNB", quantity="2 个 BNB", price="590")),
)


def run(passage: str, *steps: Step, **options: object) -> tuple[SplitExtraction, ScriptedModel]:
    model = ScriptedModel(steps)
    settings: dict[str, object] = {"now": NOW, "zone": ZONE, **options}
    return split_then_extract(passage, model, **settings), model  # type: ignore[arg-type]


def test_a_passage_of_three_trades_is_cut_into_three_segments_of_its_own_text() -> None:
    done, model = run(THREE, THREE_SPLIT, *THREE_TABLES)

    assert done.route is Route.SEGMENTS
    assert done.trades_listed == 3
    assert done.segments == (
        "今天在 Bybit 先买了 0.3 ETH 价格 2,350，手续费都是 1 U",
        "今天在 Bybit，又卖了 40 个 SOL 总共 6,200 U，手续费都是 1 U",
        "今天在 Bybit，还买了 2 个 BNB 价格 590，手续费都是 1 U",
    )
    for segment in done.segments:
        assert all(run in THREE for run in segment.split(SEPARATOR))
    sent = [call.messages[-1].content for call in model.calls[1:]]
    assert sent == list(done.segments)


def test_the_shared_platform_and_fee_reach_every_draft_and_each_draft_holds_the_whole_passage() -> (
    None
):
    done, _ = run(THREE, THREE_SPLIT, *THREE_TABLES)

    assert isinstance(done.extraction, Extracted)
    drafts = done.extraction.drafts
    assert [d.coin for d in drafts] == ["ETH", "SOL", "BNB"]
    assert [d.price for d in drafts] == [Decimal("2350"), None, Decimal("590")]
    assert drafts[1].total == Decimal("6200")
    assert {d.platform for d in drafts} == {"Bybit"}
    assert {d.fee for d in drafts} == {Decimal("1")}
    assert {d.raw_text for d in drafts} == {THREE}
    assert done.extraction.issues == ()


def test_every_call_is_kept_with_what_it_was_for() -> None:
    done, model = run(THREE, THREE_SPLIT, *THREE_TABLES)

    assert isinstance(done.extraction, Extracted)
    assert len(done.extraction.calls) == len(model.calls) == 4
    assert done.steps == (
        CallStep(Purpose.SPLIT, None),
        CallStep(Purpose.EXTRACT, 0),
        CallStep(Purpose.EXTRACT, 1),
        CallStep(Purpose.EXTRACT, 2),
    )
    assert done.draft_calls == (1, 2, 3)
    assert model.calls[0].reply_schema is SPLIT_TABLE
    assert all(call.reply_schema is REPLY_TABLE for call in model.calls[1:])


def test_the_split_is_asked_with_its_instructions_and_examples() -> None:
    _, model = run(THREE, THREE_SPLIT, *THREE_TABLES)

    messages = model.calls[0].messages
    assert messages[0].role is Role.SYSTEM
    assert messages[0].content == SPLIT_PROMPT.instructions
    assert len(messages) == 2 + 2 * len(SPLIT_PROMPT.examples)
    assert messages[-1].content == THREE


def test_the_issues_count_the_drafts_of_all_segments_and_the_numbers_of_the_whole_passage() -> None:
    no_price = table(shared_row(side="buy", coin="BNB", quantity="2 个 BNB"))
    wrong_coin = table(shared_row(side="sell", coin="SOLANA", quantity="40 个 SOL"))

    done, _ = run(THREE, THREE_SPLIT, THREE_TABLES[0], wrong_coin, no_price)

    assert isinstance(done.extraction, Extracted)
    assert Issue(kind=IssueKind.NOT_IN_PASSAGE, draft=1, field=Field.COIN, phrase="SOLANA") in (
        done.extraction.issues
    )
    assert done.extraction.issues[-1] == Issue(
        kind=IssueKind.NUMBERS_LEFT_OVER, numbers=("6,200", "590")
    )


def test_a_phrase_that_runs_across_the_join_of_two_runs_is_left_empty_with_an_issue() -> None:
    across = "Bybit，又卖了"
    segment_table = table(
        row(side="sell", coin="SOL", quantity="40 个 SOL", total="6,200 U", platform=across)
    )

    done, _ = run(THREE, THREE_SPLIT, THREE_TABLES[0], segment_table, THREE_TABLES[2])

    assert across in done.segments[1]
    assert across not in THREE
    assert isinstance(done.extraction, Extracted)
    assert done.extraction.drafts[1].platform is None
    assert (
        Issue(kind=IssueKind.NOT_IN_PASSAGE, draft=1, field=Field.PLATFORM, phrase=across)
        in done.extraction.issues
    )


def test_a_row_two_segments_both_give_is_marked_as_given_twice() -> None:
    same = THREE_TABLES[0]

    done, _ = run(THREE, THREE_SPLIT, same, same, THREE_TABLES[2])

    assert isinstance(done.extraction, Extracted)
    assert Issue(kind=IssueKind.SAME_AS_ANOTHER, draft=1, same_as=0) in done.extraction.issues


@pytest.mark.parametrize("listed", [(), (("昨天在 OKX 买了 0.5 个 ETH",),)])
def test_fewer_than_two_trades_send_the_whole_passage_once_as_without_splitting(
    listed: tuple[tuple[str, ...], ...],
) -> None:
    done, model = run(ONE, split_reply(*listed), ONE_TABLE)
    alone = extract(ONE, ScriptedModel([ONE_TABLE]), now=NOW, zone=ZONE)

    assert done.route is Route.WHOLE
    assert done.trades_listed == len(listed)
    assert done.segments == ()
    assert isinstance(done.extraction, Extracted) and isinstance(alone, Extracted)
    assert (done.extraction.drafts, done.extraction.issues) == (alone.drafts, alone.issues)
    assert model.calls[1].messages == _messages_of_extract(ONE)
    assert len(done.extraction.calls) == 2
    assert done.steps == (CallStep(Purpose.SPLIT, None), CallStep(Purpose.EXTRACT, None))
    assert done.draft_calls == (1,)


def _messages_of_extract(passage: str) -> tuple[Message, ...]:
    model = ScriptedModel([ONE_TABLE])
    extract(passage, model, now=NOW, zone=ZONE)
    return model.calls[0].messages


def test_two_trades_whose_pieces_give_one_segment_go_whole() -> None:
    done, _ = run(ONE, split_reply(("昨天在 OKX",), ()), ONE_TABLE)

    assert done.route is Route.WHOLE
    assert done.trades_listed == 2
    assert done.segments == ("昨天在 OKX",)
    assert not done.route.fell_back


@pytest.mark.parametrize(
    ("split_steps", "route"),
    [
        ((split_reply(("bought 0.5 ETH",), ("sold 1 BTC",)),), Route.PIECE_NOT_IN_PASSAGE),
        ((split_reply(("价格 3",), ("手续费 0.3U",)),), Route.PIECE_CUTS_A_NUMBER),
        (("not json", "still not json"), Route.SPLIT_UNREADABLE),
        ((ModelError(ModelErrorKind.TIMED_OUT, "no reply in time"),), Route.SPLIT_FAILED),
    ],
)
def test_a_split_that_went_wrong_falls_back_to_the_whole_passage_and_says_why(
    split_steps: tuple[Step, ...], route: Route
) -> None:
    done, model = run(ONE, *split_steps, ONE_TABLE)
    alone = extract(ONE, ScriptedModel([ONE_TABLE]), now=NOW, zone=ZONE)

    assert done.route is route
    assert route.fell_back
    assert done.segments == ()
    assert isinstance(done.extraction, Extracted) and isinstance(alone, Extracted)
    assert (done.extraction.drafts, done.extraction.issues) == (alone.drafts, alone.issues)
    assert model.steps_left == 0
    assert done.draft_calls == (len(done.extraction.calls) - 1,)


def test_an_unreadable_split_is_asked_again_with_what_was_wrong() -> None:
    done, model = run(ONE, "not json", split_reply(), ONE_TABLE)

    assert done.route is Route.WHOLE
    again = model.calls[1].messages[-1].content
    assert SplitProblem.NOT_JSON.value in again
    assert done.steps[:2] == (CallStep(Purpose.SPLIT, None), CallStep(Purpose.SPLIT, None))


def test_a_segment_whose_reply_cannot_be_read_makes_the_passage_unreadable() -> None:
    done, model = run(THREE, THREE_SPLIT, THREE_TABLES[0], "not json", "still not json")

    assert done.route is Route.SEGMENTS
    assert done.extraction == ReplyUnreadable(
        (ReplyProblem.NOT_JSON, ReplyProblem.NOT_JSON),
        done.extraction.calls,  # type: ignore[union-attr]
    )
    assert len(done.extraction.calls) == 4  # type: ignore[union-attr]
    assert done.draft_calls == ()
    assert model.steps_left == 0


def test_a_model_failure_on_a_segment_fails_the_passage_and_sends_no_more() -> None:
    failure = ModelError(ModelErrorKind.UNREACHABLE, "nothing answers")

    done, model = run(THREE, THREE_SPLIT, failure)

    assert isinstance(done.extraction, ModelFailed)
    assert done.extraction.error is failure
    assert len(done.extraction.calls) == 1
    assert len(model.calls) == 2


def test_more_rows_than_one_reply_may_hold_go_the_one_list_way() -> None:
    half = MAX_ROWS // 2 + 1
    many = table(*[row(side="buy", coin="ETH", quantity="0.3 ETH")] * half)

    done, _ = run(THREE, split_reply(OWN[:1], OWN[1:2]), many, many, ONE_TABLE)

    assert done.route is Route.MERGED_TOO_LONG
    assert done.route.fell_back
    assert isinstance(done.extraction, Extracted)
    assert len(done.extraction.calls) == 4
    assert done.draft_calls == (3,)
    assert done.steps[-1] == CallStep(Purpose.EXTRACT, None)


def test_a_refused_passage_is_not_sent() -> None:
    done, model = run("   ")

    assert done == SplitExtraction(
        PassageRefused(PassageProblem.EMPTY), Route.REFUSED, None, (), (), ()
    )
    assert model.calls == []


def test_the_callers_prompt_parameters_and_asking_again_reach_every_call() -> None:
    parameters = ModelParameters(
        temperature=0.0, top_p=1.0, max_reply_tokens=64, context_tokens=512, timeout_seconds=5.0
    )

    done, model = run(
        THREE, "x", *THREE_TABLES, parameters=parameters, asks_again=0, prompt=FIRST_PROMPT
    )

    assert done.route is Route.SPLIT_UNREADABLE
    assert all(call.parameters is parameters for call in model.calls)


@pytest.mark.parametrize(
    ("options", "error"),
    [
        ({"now": NOW.replace(tzinfo=None)}, ValueError),
        ({"zone": "Not/AZone"}, ValueError),
        ({"asks_again": 9}, ValueError),
        ({"asks_again": True}, TypeError),
    ],
)
def test_a_mistake_of_the_calling_code_raises(options: dict[str, object], error: type) -> None:
    with pytest.raises(error):
        run(ONE, **options)
