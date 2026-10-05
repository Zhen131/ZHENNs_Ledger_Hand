"""The live smoke test of extraction: four invented passages through the real model.

Marked ``live_model``, so ordinary runs leave it out; ``scripts/check.sh
live`` runs it, with the settings read from the environment as the program
reads them. It needs the model server running and the model there.

It checks only that the whole way runs and that what comes back has the
right shape: drafts and a list of issues. Whether the model read each
passage right is not judged here; that is what the experiments measure. It
prints everything it got, and how long each passage took, so the run
itself is the record. The current moment and the zone are fixed, so the
times in the passages always lie in the past.
"""

from __future__ import annotations

import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from ledger_hand.core.trade import TradeDraft
from ledger_hand.extraction.extractor import Extracted, ModelFailed, extract
from ledger_hand.extraction.issues import Issue
from ledger_hand.llm.local import connect_local_model
from ledger_hand.settings import load_model_settings
from scripts.try_extraction import show_result

pytestmark = pytest.mark.live_model

ZONE = "Europe/Budapest"
NOW = datetime(2026, 10, 5, 18, 30, tzinfo=ZoneInfo(ZONE))

# Invented passages, none of them a real trade.
PASSAGES = [
    pytest.param(
        "前天下午在 Bybit 买了 0.8 个以太坊，价格 3,150，手续费 0.6U，打算拿一阵", id="chinese-one"
    ),
    pytest.param(
        "sold 0.15 BTC at 68,200 on Coinbase yesterday evening, fee 4.1 USDT", id="english-one"
    ),
    pytest.param(
        "今天上午先卖了 300 个 ADA，0.42 一个；then bought 1.5 SOL at 151.3，手续费都是 0.2U",
        id="several",
    ),
    pytest.param("最近行情太闷了，周末打算去爬山，不看盘了", id="chatter"),
]


@pytest.mark.parametrize("passage", PASSAGES)
def test_a_passage_goes_the_whole_way_and_comes_back_as_drafts_and_issues(passage: str) -> None:
    model = connect_local_model(load_model_settings())

    started = time.monotonic()
    result = extract(passage, model, now=NOW, zone=ZONE)
    took = time.monotonic() - started

    print()
    show_result(result, passage, ZONE, sys.stdout)
    print(f"whole passage took {took:.2f} s")
    if isinstance(result, ModelFailed):
        pytest.fail(f"the live check could not talk to the model: {result.error}", pytrace=False)
    assert isinstance(result, Extracted), result
    assert all(isinstance(draft, TradeDraft) for draft in result.drafts)
    assert all(draft.raw_text == passage for draft in result.drafts)
    assert all(isinstance(issue, Issue) for issue in result.issues)
    assert result.calls
