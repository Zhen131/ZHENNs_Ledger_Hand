"""A name matched by the program's table reaches the ledger page's link with its mark and reason.

The real plug (``LinkLedger``) is driven by a stand-in link that answers
the list of assets and the positions from the captured samples, says
``propose_trade_add`` takes cards, and turns the proposal down; what was
asked of it is kept. A scripted model stands in for the model. Every
sentence and figure is invented.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ledger_hand.flows.conversation import AssistantChat, say
from ledger_hand.ledger.invented_book import INVENTED_NOW, INVENTED_ZONE
from ledger_hand.ledger.link_client import ToolAnswer
from ledger_hand.ledger.link_ledger import LinkLedger
from tests.fakes.routed_model import RoutedModel
from tests.flows.scripted_flow import screened, table
from tests.flows.test_conversation_asset_pick import RECORD, row_of, said_as
from tests.ledger.test_link_ledger import MODEL, TODAY, sample, written_from_the_readme


class CardLink:
    """Answers the assets and the positions, takes cards, and turns any proposal down."""

    def __init__(self) -> None:
        self.asked: list[tuple[str, dict[str, Any]]] = []

    def tools(self) -> list[dict[str, Any]]:
        properties = {"trades": {"type": "array"}, "allowUnfinished": {"type": "boolean"}}
        schema = {"type": "object", "properties": properties}
        return [{"name": "propose_trade_add", "inputSchema": schema}]

    def call(self, name: str, arguments: Mapping[str, Any]) -> ToolAnswer:
        self.asked.append((name, dict(arguments)))
        if name == "list_assets":
            return sample("list-assets")
        if name == "get_positions":
            return sample("positions")
        return written_from_the_readme("PAGE_BUSY", "invented: the page is busy")


def test_a_name_of_the_table_goes_to_the_link_with_the_asset_marked_and_why() -> None:
    link = CardLink()
    ledger = LinkLedger(link, model_name=MODEL, today=lambda: TODAY)
    words = said_as("英伟达的股票")
    model = RoutedModel(
        tools=[RECORD],
        screen=[screened(("spot_trade", words.split("，")[0]))],
        extraction=[table(row_of("英伟达的股票"))],
    )

    said = say(
        AssistantChat(),
        words,
        model=model,
        ledger=ledger,
        now=INVENTED_NOW,
        zone=INVENTED_ZONE,
        max_steps=6,
    )

    assert model.questions.calls == []
    (proposed,) = [arguments for name, arguments in link.asked if name == "propose_trade_add"]
    (card,) = proposed["trades"]
    marks = {mark["field"]: mark for mark in card["fieldMarks"]}
    assert marks["assetId"]["kind"] == "inferred"
    assert marks["assetId"]["reason"] == (
        '"英伟达的股票" was taken as NVDA from the program\'s table of common company names'
    )
    assert said.recorded is not None
