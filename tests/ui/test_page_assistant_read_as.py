"""Tests of the line under the person's words on the Assistant page: what they were read as.

The line is shown only when tidying changed the words, in the same bubble
as the words, never in the reply's container. The page runs headless with
a scripted model and the demo ledger. Every sentence, reply and trade is
invented.
"""

from __future__ import annotations

from ledger_hand.ports import ToolCall, ToolReply
from ledger_hand.ui.assistant_view import READ_AS, exchange_key, read_as_key
from tests.fakes.routed_model import RoutedModel
from tests.fakes.scripted_model import scripted_record
from tests.fakes.usdt_only import usdt_only_ledger
from tests.flows.scripted_flow import row, screened, table
from tests.ui.assistant_harness import captions, open_assistant, say_on_page

RECORD = ToolReply(
    text="", calls=(ToolCall(name="propose_trade_add", arguments={}),), record=scripted_record()
)
SAID = "今天上午九点四十分在币安买了0.02 BTC，价格九万四千九百，手续费2 USDT"
TIDIED = "今天上午9点40分在币安买了0.02 BTC，价格94900，手续费2 USDT"
PLAIN = "今天上午9:40在币安买了0.02 BTC，价格94900，手续费2 USDT"


def _model(time: str, price: str) -> RoutedModel:
    return RoutedModel(
        tools=[RECORD],
        screen=[screened(("spot_trade", "买了0.02 BTC"))],
        extraction=[
            table(
                row(
                    side="buy",
                    coin="BTC",
                    quantity="0.02 BTC",
                    price=price,
                    fee="2 USDT",
                    time=time,
                    platform="币安",
                )
            )
        ],
    )


def test_words_tidied_show_what_they_were_read_as_beside_them() -> None:
    page = open_assistant(_model("今天上午9点40分", "94900"), ledger=usdt_only_ledger())

    page = say_on_page(page, SAID)

    assert captions(page, read_as_key(1)) == [READ_AS + TIDIED]
    assert not any(line.startswith(READ_AS) for line in captions(page, exchange_key(1)))
    assert SAID in [str(text.value) for text in page.text]


def test_words_not_changed_show_no_such_line() -> None:
    page = open_assistant(_model("今天上午9:40", "94900"), ledger=usdt_only_ledger())

    page = say_on_page(page, PLAIN)

    assert not any(str(caption.value).startswith(READ_AS) for caption in page.caption)
