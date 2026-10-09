"""Tests of what a ``Progress`` says may be done next: which trades can be removed, and saving.

An interface shows its controls from these and decides nothing itself, so
they must agree with what ``remove`` and ``finish`` accept. Every passage and
reply below is invented.
"""

from __future__ import annotations

import pytest

from ledger_hand.flows.progress import Progress, Stage
from ledger_hand.flows.recording import cancel, finish, remove
from tests.fakes.routed_model import RoutedModel
from tests.flows.scripted_flow import begin, row, screened, table, walk

SPOT = screened(("spot_trade", "买了 0.5 ETH"))
COMPLETE_TWO = "昨天买了 0.5 ETH，价格 3,420，手续费 0；卖了 2 SOL，价格 150，手续费 0.2 USDT"
COMPLETE_ROWS = table(
    row(side="buy", coin="ETH", quantity="0.5 ETH", price="3,420", fee="0", time="昨天"),
    row(side="sell", coin="SOL", quantity="2 SOL", price="150", fee="0.2 USDT", time="昨天"),
)
TWO_TRADES = "今天下午 3 点买了 0.5 ETH，又卖了 2 个 SOL，价格 150"
TWO_ROWS = table(
    row(side="buy", coin="ETH", quantity="0.5 ETH", time="今天下午 3 点"),
    row(side="sell", coin="SOL", quantity="2 个", price="150"),
)


def settled_two() -> Progress:
    return begin(COMPLETE_TWO, RoutedModel(screen=[SPOT], extraction=[COMPLETE_ROWS]))


def test_two_settled_records_can_each_be_removed_and_saved() -> None:
    progress = settled_two()

    assert progress.stage is Stage.REVIEWING
    assert progress.removable == (1, 2)
    assert progress.can_save


def test_a_removed_trade_is_no_longer_removable_and_the_rest_can_still_be_saved() -> None:
    progress = remove(settled_two(), 2)

    assert progress.removable == (1,)
    assert progress.can_save


def test_with_every_record_removed_nothing_can_be_saved() -> None:
    progress = remove(remove(settled_two(), 2), 1)

    assert progress.stage is Stage.REVIEWING
    assert progress.removable == ()
    assert not progress.can_save
    assert progress.can_cancel


def test_the_removable_numbers_are_exactly_those_remove_accepts() -> None:
    progress = remove(settled_two(), 1)

    for number in range(0, len(progress.trades) + 2):
        after = remove(progress, number)
        assert (after.note is None) == (number in progress.removable), number


def test_while_a_question_waits_nothing_can_be_removed_or_saved() -> None:
    model = RoutedModel(screen=[SPOT], extraction=[TWO_ROWS])
    progress = begin(TWO_TRADES, model)

    assert progress.stage is Stage.ASKING
    assert progress.removable == ()
    assert not progress.can_save
    assert progress.can_cancel


def test_a_skipped_trade_is_not_removable() -> None:
    model = RoutedModel(screen=[SPOT], extraction=[TWO_ROWS])
    seen = walk(begin(TWO_TRADES, model), model, "skip", "0.2 USDT", "昨天下午 4 点")

    last = seen[-1]
    assert last.stage is Stage.REVIEWING
    assert last.removable == (2,)
    assert last.can_save


@pytest.mark.parametrize("ending", [finish, cancel])
def test_once_the_passage_is_over_nothing_can_be_removed_or_saved(ending: object) -> None:
    progress = ending(settled_two())  # type: ignore[operator]

    assert progress.over
    assert progress.removable == ()
    assert not progress.can_save


def test_a_stopped_passage_offers_nothing() -> None:
    model = RoutedModel(screen=[screened(("plan", "打算明天买"))])
    progress = begin("打算明天买 1 个 ETH", model)

    assert progress.stage is Stage.STOPPED
    assert progress.removable == ()
    assert not progress.can_save
    assert not progress.can_cancel
