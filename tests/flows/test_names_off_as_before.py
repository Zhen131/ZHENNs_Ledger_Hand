"""With both ways of matching names off, the assistant does exactly what it did before them.

The same sentences (a name the table holds, answered with its code; a name
whose code the ledger lacks; a name with two codes; one with a tail word)
are said with the table off and no file of answers, and every message
each call to the model was sent, with every reply said, is hashed. The
hash was taken with the same function on the program as it stood before
names were matched (commit 9337a7e), so any byte sent or said that
differs shows here. A scripted model stands in; every sentence is
invented.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from ledger_hand.flows.conversation import AssistantChat, say
from ledger_hand.ledger.demo_book import demo_ledger
from ledger_hand.ledger.invented_book import INVENTED_NOW, INVENTED_ZONE
from tests.fakes.routed_model import RoutedModel
from tests.flows.scripted_flow import copied, screened, table
from tests.flows.test_conversation_asset_pick import RECORD, row_of, said_as

# The hash ``transcript`` gave before names were matched, at commit 9337a7e.
BEFORE_SHA256 = "05093c923cbfc82b1d78979267780431108d6debf895cc821c4cc410baf9f1ef"

# Each sentence's name, and the answers said after it.
SAID: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("微软", ("MSFT",)),
    ("特斯拉", ("TSLA",)),
    ("谷歌", ()),
    ("苹果的股票", ("AAPL",)),
)


def transcript(**switches: Any) -> str:
    """The hash of every message sent to the model and every reply, for ``SAID``."""
    seen: list[object] = []
    for coin, answers in SAID:
        words = said_as(coin)
        model = RoutedModel(
            tools=[RECORD],
            screen=[screened(("spot_trade", words.split("，")[0]))],
            extraction=[table(row_of(coin))],
            answers=[copied(answer) for answer in answers],
            # A reply that cannot be read: the call is kept, and the program's own words used.
            questions=["not a question"] * 4,
        )
        state = AssistantChat()
        for one in (words, *answers):
            said = say(
                state,
                one,
                model=model,
                ledger=demo_ledger(),
                now=INVENTED_NOW,
                zone=INVENTED_ZONE,
                max_steps=6,
                **switches,
            )
            seen.append(said.reply)
            state = said.state
        for call in model.tools.calls:
            seen.append(["tools", repr(call)])
        for kind in ("screen", "extraction", "questions", "answers", "picks"):
            for call in getattr(model, kind).calls:
                seen.append(
                    [kind, [[message.role.value, message.content] for message in call.messages]]
                )
    data = json.dumps(seen, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def test_with_both_off_every_byte_sent_and_said_is_as_before() -> None:
    assert transcript(name_table=False, names=None) == BEFORE_SHA256
