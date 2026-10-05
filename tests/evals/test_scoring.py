"""Tests of the scores against cases worked out by hand.

Each case says, in its comment, the counts worked out by hand from the gold
trades and the drafts. Every passage is invented.
"""

from __future__ import annotations

import itertools
from datetime import date

import pytest

from evals.cells import CellOutcome, EmptyReason
from evals.scoring import Produced, ResultKind, Scores, add_up, score_sentence
from ledger_hand.core.trade import TradeDraft
from ledger_hand.extraction.issues import Issue, IssueKind
from ledger_hand.extraction.reply_table import Field
from tests.evals.builders import draft, on_day, sentence

ONE = "昨天在 OKX 买了 0.5 ETH，价格 3,200，手续费 1U"
ONE_GOLD = {
    "side": "buy",
    "coin": ["ETH", "ETH"],
    "quantity": ["0.5 ETH", "0.5"],
    "price": ["3,200", "3200"],
    "fee": ["1U", "1"],
    "fee_currency": ["U", "USDT"],
    "time": ["昨天", "2026-10-04", "day"],
    "platform": ["OKX", "OKX"],
}
YESTERDAY = on_day(date(2026, 10, 4))
TODAY = on_day(date(2026, 10, 5))


def one_right() -> TradeDraft:
    return draft(
        ONE,
        side="buy",
        coin="ETH",
        quantity="0.5",
        price="3200",
        fee="1",
        fee_currency="U",
        time=YESTERDAY,
        platform="OKX",
    )


def one_all_wrong() -> TradeDraft:
    return draft(
        ONE,
        side="sell",
        coin="BTC",
        quantity="2",
        price="100",
        total="5",
        price_currency="BTC",
        fee="9",
        fee_currency="BNB",
        time=on_day(date(2026, 10, 3)),
        platform="Kraken",
        opinion="随便买的",
    )


THREE = (
    "今天先买了 1 SOL，150 一个，又买了 2 ETH，价格 3,000，"
    "最后卖了 0.1 BTC，价格 60,000，手续费都是 0"
)
THREE_GOLD = [
    {
        "side": "buy",
        "coin": ["SOL", "SOL"],
        "quantity": ["1 SOL", "1"],
        "price": ["150", "150"],
        "fee": ["0", "0"],
        "time": ["今天", "2026-10-05", "day"],
    },
    {
        "side": "buy",
        "coin": ["ETH", "ETH"],
        "quantity": ["2 ETH", "2"],
        "price": ["3,000", "3000"],
        "fee": ["0", "0"],
        "time": ["今天", "2026-10-05", "day"],
    },
    {
        "side": "sell",
        "coin": ["BTC", "BTC"],
        "quantity": ["0.1 BTC", "0.1"],
        "price": ["60,000", "60000"],
        "fee": ["0", "0"],
        "time": ["今天", "2026-10-05", "day"],
    },
]


def three_right() -> list[TradeDraft]:
    return [
        draft(THREE, side="buy", coin="SOL", quantity="1", price="150", fee="0", time=TODAY),
        draft(THREE, side="buy", coin="ETH", quantity="2", price="3000", fee="0", time=TODAY),
        draft(THREE, side="sell", coin="BTC", quantity="0.1", price="60000", fee="0", time=TODAY),
    ]


def extracted(*drafts: TradeDraft, issues: tuple[Issue, ...] = ()) -> Produced:
    return Produced(ResultKind.EXTRACTED, tuple(drafts), issues)


def every_field(count: int) -> dict[Field, int]:
    return dict.fromkeys(Field, count)


def test_all_right() -> None:
    # 1 sentence, 1 gold trade, 1 draft, every field right. Gold-empty fields:
    # total, pricing currency, opinion = 3; none made up.
    score = score_sentence(sentence(ONE, ONE_GOLD), extracted(one_right()))
    total = add_up([score])

    assert (total.sentences, total.well_formed, total.gold_trades, total.pairs) == (1, 1, 1, 1)
    assert (total.whole_right, total.missed, total.extra) == (1, 0, 0)
    assert dict(total.field_right) == every_field(1)
    assert (total.made_up_fields, total.gold_empty_fields) == (0, 3)
    assert dict(total.outcomes) == {CellOutcome.RIGHT: 11}


def test_all_wrong() -> None:
    # Every field differs. The three gold-empty fields (total, pricing
    # currency, opinion) are made up: 3 of 3. The other 8 are wrong, with no
    # issue about them.
    score = score_sentence(sentence(ONE, ONE_GOLD), extracted(one_all_wrong()))
    total = add_up([score])

    assert (total.pairs, total.whole_right, total.missed, total.extra) == (1, 0, 0, 0)
    assert dict(total.field_right) == {}
    assert (total.made_up_fields, total.gold_empty_fields) == (3, 3)
    assert dict(total.outcomes) == {CellOutcome.MADE_UP: 3, CellOutcome.WRONG_SILENT: 8}


def test_a_missed_trade_counts_as_wrong() -> None:
    # 3 gold trades, 2 right drafts: 2 pairs, 2 whole of 3, 1 missed.
    drafts = three_right()
    score = score_sentence(sentence(THREE, *THREE_GOLD), extracted(drafts[0], drafts[2]))
    total = add_up([score])

    assert (total.gold_trades, total.drafts, total.pairs) == (3, 2, 2)
    assert (total.whole_right, total.missed, total.extra) == (2, 1, 0)
    assert dict(total.field_right) == every_field(2)
    assert [(pair.gold_at, pair.draft_at) for pair in score.pairs] == [(0, 0), (2, 1)]


def test_an_extra_draft() -> None:
    # 1 gold trade, 2 drafts: the right one is paired, 1 extra.
    score = score_sentence(sentence(ONE, ONE_GOLD), extracted(one_all_wrong(), one_right()))

    assert (len(score.pairs), score.whole_right, score.missed, score.extra) == (1, 1, 0, 1)
    assert score.pairs[0].draft_at == 1


def test_a_made_up_opinion() -> None:
    # Right in every field but the opinion, which the gold answer leaves
    # empty: 1 made up of 3 gold-empty fields, and the trade is not whole.
    made_up = draft(
        ONE,
        side="buy",
        coin="ETH",
        quantity="0.5",
        price="3200",
        fee="1",
        fee_currency="USDT",
        time=YESTERDAY,
        platform="OKX",
        opinion="感觉要涨",
    )
    total = add_up([score_sentence(sentence(ONE, ONE_GOLD), extracted(made_up))])

    assert (total.made_up_fields, total.gold_empty_fields) == (1, 3)
    assert total.whole_right == 0
    assert total.field_right[Field.OPINION] == 0
    assert total.field_right[Field.FEE_CURRENCY] == 1


def test_a_passage_with_no_trade() -> None:
    # No gold trade. No draft: right. One draft: 1 extra, not right.
    chatter = sentence("今天没交易，只看了看盘")

    right = score_sentence(chatter, extracted())
    wrong = score_sentence(chatter, extracted(one_right()))
    total = add_up([right, wrong])

    assert (total.no_trade_sentences, total.no_trade_right) == (2, 1)
    assert (total.gold_trades, total.extra, total.pairs) == (0, 1, 0)


@pytest.mark.parametrize(
    "kind", [ResultKind.REPLY_UNREADABLE, ResultKind.MODEL_FAILED, ResultKind.PASSAGE_REFUSED]
)
def test_no_table_read(kind: ResultKind) -> None:
    # Not well-formed; its one gold trade is missed.
    total = add_up([score_sentence(sentence(ONE, ONE_GOLD), Produced(kind))])

    assert (total.sentences, total.well_formed, total.whole_right) == (1, 0, 0)
    assert (total.missed, total.pairs) == (1, 0)


def test_no_table_read_on_a_passage_with_no_trade_is_not_right() -> None:
    total = add_up([score_sentence(sentence("今天没交易"), Produced(ResultKind.REPLY_UNREADABLE))])

    assert (total.no_trade_sentences, total.no_trade_right) == (1, 0)


def test_several_sentences_add_up() -> None:
    # All right (1 trade) + three with one missed + one unreadable:
    # sentences 3, well-formed 2, gold trades 1 + 3 + 1 = 5, pairs 1 + 2 = 3,
    # whole 3, missed 0 + 1 + 1 = 2. Gold-empty fields: 3 in the first pair;
    # 5 in each pair of the second (total, pricing currency, fee currency,
    # platform, opinion) = 13.
    drafts = three_right()
    scores = [
        score_sentence(sentence(ONE, ONE_GOLD), extracted(one_right())),
        score_sentence(sentence(THREE, *THREE_GOLD), extracted(drafts[1], drafts[2])),
        score_sentence(sentence(ONE, ONE_GOLD), Produced(ResultKind.REPLY_UNREADABLE)),
    ]
    total = add_up(scores)

    assert (total.sentences, total.well_formed, total.gold_trades, total.pairs) == (3, 2, 5, 3)
    assert (total.whole_right, total.missed, total.extra) == (3, 2, 0)
    assert (total.gold_empty_fields, total.made_up_fields) == (13, 0)
    assert dict(total.field_right) == every_field(3)


def test_the_reasons_and_half_copies_are_counted() -> None:
    # The price is left empty because the model's phrase cut a number; the
    # fee holds a wrong value with no issue. Both phrases are parts of the
    # gold phrases.
    cut = draft(
        ONE,
        side="buy",
        coin="ETH",
        quantity="0.5",
        fee="0.1",
        fee_currency="U",
        time=YESTERDAY,
        platform="OKX",
    )
    produced = Produced(
        ResultKind.EXTRACTED,
        (cut,),
        (Issue(kind=IssueKind.CUTS_A_NUMBER, draft=0, field=Field.PRICE, phrase="200"),),
        ({Field.PRICE: "200", Field.FEE: "1"},),
    )
    total = add_up([score_sentence(sentence(ONE, ONE_GOLD), produced)])

    assert total.outcomes[CellOutcome.LEFT_EMPTY_WITH_REASON] == 1
    assert total.outcomes[CellOutcome.WRONG_SILENT] == 1
    assert dict(total.empty_reasons) == {EmptyReason.CUTS_A_NUMBER: 1}
    assert dict(total.half_copies) == {
        CellOutcome.LEFT_EMPTY_WITH_REASON: 1,
        CellOutcome.WRONG_SILENT: 1,
    }


def summary(total: Scores) -> tuple[object, ...]:
    return (
        total.pairs,
        total.whole_right,
        total.missed,
        total.extra,
        total.made_up_fields,
        total.gold_empty_fields,
        tuple(sorted((f.value, n) for f, n in total.field_right.items())),
        tuple(sorted((o.value, n) for o, n in total.outcomes.items())),
    )


def test_three_trades_in_any_order_score_the_same() -> None:
    # The second draft has a wrong price; every order of the three drafts
    # pairs each with its own gold trade.
    drafts = three_right()
    drafts[1] = draft(THREE, side="buy", coin="ETH", quantity="2", price="300", fee="0", time=TODAY)
    gold = sentence(THREE, *THREE_GOLD)
    results = set()
    for order in itertools.permutations(drafts):
        score = score_sentence(gold, extracted(*order))
        paired = {pair.gold_at: order[pair.draft_at] for pair in score.pairs}
        assert paired == dict(enumerate(drafts))
        results.add(summary(add_up([score])))

    assert len(results) == 1
    (only,) = results
    assert only[:4] == (3, 2, 0, 0)


def test_a_tie_between_two_pairings_is_settled_the_same_in_any_order() -> None:
    # Gold: SOL 1 at 150, SOL 2 at 160. Drafts: SOL 2 at 150, SOL 1 at 160.
    # Pairing by price agrees on 10 + 10 fields, and so does pairing by
    # quantity; whichever is taken must not depend on the drafts' order.
    text = "买了 1 SOL，150 一个，又买了 2 SOL，160 一个"
    gold = sentence(
        text,
        {
            "side": "buy",
            "coin": ["SOL", "SOL"],
            "quantity": ["1 SOL", "1"],
            "price": ["150", "150"],
        },
        {
            "side": "buy",
            "coin": ["SOL", "SOL"],
            "quantity": ["2 SOL", "2"],
            "price": ["160", "160"],
        },
    )
    one = draft(text, side="buy", coin="SOL", quantity="2", price="150")
    two = draft(text, side="buy", coin="SOL", quantity="1", price="160")

    forward = summary(add_up([score_sentence(gold, extracted(one, two))]))
    backward = summary(add_up([score_sentence(gold, extracted(two, one))]))

    assert forward == backward
    assert forward[:2] == (2, 0)
