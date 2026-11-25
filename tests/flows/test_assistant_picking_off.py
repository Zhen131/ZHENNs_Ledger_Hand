"""The assistant does not hand a name to the model to pick an asset: the step is off.

Measured on the names set, every prompt version picked a listed asset for
some name the ledger lacks, so the assistant keeps the step off
(``conversation.ASSISTANT_PICKS_ASSETS``). A Chinese name of a share is then
asked about, in the words for an asset, with the note to add it in the
ledger first; the code answered is recorded. A scripted model stands in.
"""

from __future__ import annotations

from ledger_hand.flows import conversation
from ledger_hand.flows.questions import ADD_IN_LEDGER_FIRST
from ledger_hand.flows.recorded import RecordEnding
from tests.flows.scripted_flow import copied
from tests.flows.test_conversation_asset_pick import model_for, pick, row_of, said_as, talk


def test_the_step_is_off_on_the_assistant() -> None:
    assert conversation.ASSISTANT_PICKS_ASSETS is False


def test_a_chinese_name_is_asked_about_and_the_code_answered_is_recorded() -> None:
    words = said_as("微软")
    model = model_for(
        words, [row_of("微软")], picks=[pick("微软", "MSFT")], answers=[copied("MSFT")]
    )

    first, last = talk(model, words, "MSFT")

    assert model.picks.calls == []
    assert first.recorded is not None and first.recorded.ending is RecordEnding.ASKING
    assert first.recorded.progress.picks == ()
    assert first.reply.startswith(
        "[Trade 1 of 1: asset] The ledger lists no asset by that name; which asset was it?"
    )
    assert ADD_IN_LEDGER_FIRST in first.reply
    assert "coin" not in first.reply.casefold()
    assert last.recorded is not None and last.recorded.ending is RecordEnding.SENT
    assert last.recorded.trades[0].asset == "MSFT"
    assert "Took " not in first.reply + last.reply
