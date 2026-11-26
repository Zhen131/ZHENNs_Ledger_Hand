"""Tests of the Assistant page's way to your ledger page: the kept link's plug and cards.

The plug the keeper hands out reaches the link through the keeper, so it
asks the running link for its list of tools there. The link is the
stand-in of ``fake_link.py`` (the "samples" scenario, playing the
ledger's answers in order), so nothing reaches a real ledger page. When
the list says ``propose_trade_add`` takes ``allowUnfinished``, a trade
with no fee said is sent as a card, the fee empty; when it does not, the
fee is asked about, as before. The card's answer is written from the
ledger's ``assistant-link/README.md``; every figure is invented.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Iterator
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from ledger_hand.flows.conversation import AssistantChat, Said, say
from ledger_hand.flows.recorded import RecordEnding
from ledger_hand.ledger.invented_book import INVENTED_NOW, INVENTED_ZONE
from ledger_hand.ledger.link_client import LedgerLink
from ledger_hand.ledger.link_failures import LinkToken
from ledger_hand.ledger.link_keeper import LinkKeeper
from ledger_hand.ledger.link_ledger import LinkLedger, ToolCaller
from ledger_hand.ports import LedgerPort, ToolCall, ToolReply
from tests.fakes.routed_model import RoutedModel
from tests.fakes.scripted_model import scripted_record
from tests.flows.scripted_flow import row, screened, table
from tests.ledger.test_link_client import ledger_folder, node, setup

__all__ = ["ledger_folder", "node"]  # the stand-in link's fixtures, used below

SAMPLES = Path(__file__).resolve().parent / "samples"
RECORD = ToolReply(
    text="", calls=(ToolCall(name="propose_trade_add", arguments={}),), record=scripted_record()
)
WORDS = "今天上午10点买了0.1个ETH，价格2600 USDT"
CELLS = row(side="buy", coin="ETH", quantity="0.1个ETH", price="2600 USDT", time="今天上午10点")
# One card taken, its fee and the fee's money empty, as the README writes the answer.
CARD_TAKEN = {
    "kind": "result",
    "content": {
        "results": [
            {
                "ok": True,
                "proposalId": "p-invented-1",
                "readyToSave": False,
                "missingFields": ["fee", "feeAssetId"],
                "ledgerProblem": None,
            }
        ]
    },
}


def sample(name: str) -> dict[str, Any]:
    answer: dict[str, Any] = json.loads((SAMPLES / f"{name}.json").read_text("utf-8"))["answer"]
    return answer


def plug_for(caller: ToolCaller, model_name: str) -> LedgerPort:
    return LinkLedger(caller, model_name=model_name, today=lambda: date(2026, 11, 24))


@pytest.fixture
def keeper(ledger_folder: Path, node: str, tmp_path: Path) -> Iterator[LinkKeeper]:
    played = tmp_path / "played.json"
    answers = [
        sample("list-assets"),  # recording begins
        sample("positions"),  # the market prices ...
        sample("list-assets"),  # ... by the assets' identifiers
        sample("list-assets"),  # the card's identifiers
        CARD_TAKEN,
    ]
    played.write_text(json.dumps(answers), encoding="utf-8")
    base = setup(ledger_folder, node, "samples", FAKE_LINK_SAMPLES=str(played))
    kept = LinkKeeper(lambda: LedgerLink(replace(base, token=LinkToken("K" * 32))), plug_for)
    yield kept
    kept.stop()


def said_through(keeper: LinkKeeper) -> Said:
    model = RoutedModel(
        tools=[RECORD], screen=[screened(("spot_trade", "ETH"))], extraction=[table(CELLS)]
    )
    return say(
        AssistantChat(),
        WORDS,
        model=model,
        ledger=keeper.plug("invented-model"),
        now=INVENTED_NOW,
        zone=INVENTED_ZONE,
        max_steps=6,
    )


def taking_cards(link: LedgerLink) -> list[dict[str, Any]]:
    """The stand-in link's list of tools, ``propose_trade_add`` taking ``allowUnfinished``."""
    tools = copy.deepcopy(link.tools())
    for tool in tools:
        if tool["name"] == "propose_trade_add":
            schema = tool["inputSchema"]
            schema.setdefault("properties", {})["allowUnfinished"] = {"type": "boolean"}
    return tools


def test_a_ledger_page_whose_tools_take_cards_is_sent_a_card_with_the_fee_empty(
    keeper: LinkKeeper, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert keeper.start() is None
    link = keeper.running_link()
    assert link is not None
    listed = taking_cards(link)
    monkeypatch.setattr(link, "tools", lambda: listed)

    said = said_through(keeper)

    assert said.recorded is not None and said.recorded.ending is RecordEnding.SENT, said.reply
    (card,) = said.recorded.trades
    assert (card.fee, card.fee_asset) == (None, None)
    (check,) = said.recorded.checks
    assert check.ready is False and check.missing == ("fee", "feeAssetId")
    assert "with empty fields: fee, feeAssetId" in said.reply


def test_a_ledger_page_whose_tools_take_no_card_is_asked_the_fee_as_before(
    keeper: LinkKeeper,
) -> None:
    assert keeper.start() is None

    said = said_through(keeper)

    assert said.recorded is not None and said.recorded.ending is RecordEnding.ASKING, said.reply
    assert "fee" in said.reply
    assert said.sent is None


def test_the_plug_asks_the_kept_link_for_its_tools_and_keeps_no_answer_while_none_runs(
    keeper: LinkKeeper, monkeypatch: pytest.MonkeyPatch
) -> None:
    plug = keeper.plug("invented-model")
    assert plug.takes_unfinished() is False  # no link runs: not read, not kept
    assert keeper.start() is None
    link = keeper.running_link()
    assert link is not None
    listed = taking_cards(link)
    monkeypatch.setattr(link, "tools", lambda: listed)

    assert plug.takes_unfinished() is True  # the same plug reads it now
    assert keeper.plug("invented-model").takes_unfinished() is True
