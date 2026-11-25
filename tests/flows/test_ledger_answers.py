"""Tests of the flows with what the real ledger answers: parts taken, words carried, failures.

The ledger's assistant link (68B2, 2026-11-25) keeps one proposal per trade
it takes and may take a sending in part; every proposal carries the
sentence said this time; a proposal it did not answer in time may still
have reached it; a proposal it forgot says nothing of whether it was saved;
a coin and a stock may share one code. The fake ledger answers the same
way, or is made to fail the way the real one can. Every sentence, figure
and trade is invented.
"""

from __future__ import annotations

import json
from datetime import date

from ledger_hand.assistant.lookups import CUT_WORDS, lookup_lines
from ledger_hand.assistant.outcome import Chat, TakenCall
from ledger_hand.core.ledger_records import Asset, AssetKind, Pricing, TradeFilter
from ledger_hand.core.ledger_table import same_codes
from ledger_hand.core.proposals import ProposalStatus
from ledger_hand.flows.conversation import AssistantChat, say
from ledger_hand.flows.editing import EditEnding
from ledger_hand.flows.recorded import LeftOut, RecordEnding
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ledger.invented_book import INVENTED_ASSETS, INVENTED_NOW, INVENTED_ZONE
from ledger_hand.ports import LedgerError, LedgerErrorKind
from tests.fakes.scripted_model import ScriptedModel
from tests.fakes.usdt_only import USDT_ONLY_ASSETS, usdt_only_ledger
from tests.flows.scripted_flow import row, table
from tests.flows.test_conversation import RECORD, SPOT, calls, talk
from tests.flows.test_editing import delete
from tests.flows.test_editing import talk as edit_talk

PARTLY = (
    "今天上午9:40在币安买了0.02 BTC，价格94900，手续费0.00002 BTC；"
    "下午2点又卖了5 ETH，价格2700，手续费1.35 USDT"
)
PARTLY_ROWS = table(
    row(
        side="buy",
        coin="BTC",
        quantity="0.02 BTC",
        price="94900",
        fee="0.00002 BTC",
        time="今天上午9:40",
    ),
    row(side="sell", coin="ETH", quantity="5 ETH", price="2700", fee="1.35 USDT", time="下午2点"),
)
ONE = "今天上午9:40在币安买了0.02 BTC，价格94900，手续费2 USDT"
ONE_ROWS = table(
    row(
        side="buy",
        coin="BTC",
        quantity="0.02 BTC",
        price="94900",
        fee="2 USDT",
        time="今天上午9:40",
        platform="币安",
    )
)


class TimingOut(FakeLedger):
    """The fake ledger, whose every proposal is answered by the page too late."""

    def _timed_out(self) -> LedgerError:
        return LedgerError(
            LedgerErrorKind.TIMED_OUT,
            "LEDGER_PAGE_TIMEOUT",
            "The ledger page did not answer in time.",
        )

    def propose_add(self, trades, said):  # type: ignore[no-untyped-def]
        self.calls.append("propose_add")
        raise self._timed_out()

    def propose_delete(self, trade_id, said):  # type: ignore[no-untyped-def]
        self.calls.append("propose_delete")
        raise self._timed_out()


class Forgetful(FakeLedger):
    """The fake ledger after its page was reloaded: it knows no proposal any more."""

    def proposal_status(self, proposal_id):  # type: ignore[no-untyped-def]
        raise LedgerError(LedgerErrorKind.RESULT_UNKNOWN, "PROPOSAL_NOT_FOUND", "找不到这条提议。")


# --- a sending taken in part (68B2, part 2) -----------------------------------


def test_one_trade_taken_and_one_turned_down_is_said_as_part_sent_never_all_or_none() -> None:
    ledger = usdt_only_ledger()

    (said,), _, _ = talk(
        PARTLY, tools=[RECORD], screen=[SPOT], extraction=[PARTLY_ROWS], ledger=ledger
    )

    assert said.recorded is not None
    assert said.recorded.ending is RecordEnding.PARTLY_SENT
    assert said.sent is not None and said.sent.proposals == ("proposal-1",)
    lines = said.reply.splitlines()
    assert lines[0].startswith("Only part of this was sent")
    assert "Trade 1 waits in the ledger to be confirmed (proposal-1)." in lines
    assert any(line.startswith("Trade 2: With this, a sell") for line in lines)
    assert said.state.chat.proposals == (("proposal-1",),)
    assert ledger.proposal_status("proposal-1").status is ProposalStatus.PENDING
    # The model is handed the new word for the ending, and no figure.
    handed = json.loads(said.turn.steps[-1].calls[0].result)  # type: ignore[union-attr]
    assert handed["status"] == "partly_sent"


def test_where_the_last_sending_stands_asks_every_proposal_it_left() -> None:
    ledger = usdt_only_ledger()
    (first,), _, _ = talk(
        PARTLY.replace("卖了5 ETH", "买了0.5 ETH"),
        tools=[RECORD],
        screen=[SPOT],
        extraction=[PARTLY_ROWS.replace('"sell"', '"buy"').replace('"5 ETH"', '"0.5 ETH"')],
        ledger=ledger,
    )
    assert first.sent is not None and first.sent.proposals == ("proposal-1", "proposal-2")
    ledger.save("proposal-1")
    ledger.calls.clear()

    said = say(
        first.state,
        "刚才那两笔怎么样了",
        model=ScriptedModel([calls("get_proposal_status"), "One saved, one waiting."]),
        ledger=ledger,
        now=INVENTED_NOW,
        zone=INVENTED_ZONE,
        max_steps=6,
    )

    assert ledger.calls == ["proposal_status", "proposal_status"]
    (taken,) = said.turn.steps[0].calls  # type: ignore[union-attr]
    assert isinstance(taken, TakenCall)
    handed = json.loads(taken.result)
    assert handed["proposal"] == "proposal-1"
    assert handed["status"] == "mixed"
    assert handed["proposals"] == [
        {"proposal": "proposal-1", "status": "saved"},
        {"proposal": "proposal-2", "status": "pending"},
    ]


# --- this time's words go with every proposal (part 3) -------------------------


def test_a_call_to_record_carries_the_users_words_once_as_said() -> None:
    ledger = usdt_only_ledger()

    talk(ONE, tools=[RECORD], screen=[SPOT], extraction=[ONE_ROWS], ledger=ledger)

    assert ledger.said == [ONE]


def test_a_deletion_carries_the_sentence_said_now_not_the_words_the_trade_came_from() -> None:
    sentence = "把9月25号那笔ADA删掉"

    (said,), _, ledger = edit_talk(sentence, steps=[delete(period="9月25号", asset="ADA")])

    assert said.edit_sent is not None
    assert ledger.said == [sentence]


def test_a_trade_picked_by_its_number_carries_the_sentence_that_asked_for_the_change() -> None:
    sentence = "把10月6号那笔删掉"
    ledger = FakeLedger()
    (first,), _, _ = edit_talk(sentence, steps=[delete(period="10月6号")], ledger=ledger)

    said = say(
        first.state,
        "2",
        model=ScriptedModel([]),
        ledger=ledger,
        now=INVENTED_NOW,
        zone=INVENTED_ZONE,
        max_steps=6,
    )

    assert said.edit_sent is not None
    assert ledger.said == [sentence]


# --- a proposal not answered in time is never sent again (part 14) -------------


def test_a_proposal_to_record_not_answered_in_time_may_be_waiting_and_is_not_sent_again() -> None:
    ledger = TimingOut(assets=USDT_ONLY_ASSETS)

    (said,), _, _ = talk(ONE, tools=[RECORD], screen=[SPOT], extraction=[ONE_ROWS], ledger=ledger)

    assert said.recorded is not None
    assert said.recorded.ending is RecordEnding.MAYBE_SENT
    assert ledger.calls.count("propose_add") == 1
    assert "may already be waiting there" in said.reply
    assert "pending list" in said.reply
    assert "Please try again" not in said.reply
    assert said.sent is None


def test_a_deletion_not_answered_in_time_is_not_sent_again_and_says_to_look() -> None:
    ledger = TimingOut()

    (said,), _, _ = edit_talk(
        "把9月25号那笔ADA删掉", steps=[delete(period="9月25号", asset="ADA")], ledger=ledger
    )

    assert said.edited is not None
    assert said.edited.ending is EditEnding.MAYBE_SENT
    assert ledger.calls.count("propose_delete") == 1
    assert "pending list" in said.reply


# --- a proposal the ledger forgot is not said to be unsaved (part 14) ---------


def test_a_proposal_the_ledger_forgot_is_told_to_the_model_as_unknown_not_as_unsaved() -> None:
    ledger = Forgetful()

    said = say(
        AssistantChat(chat=Chat(proposals=(("proposal-4",),))),
        "刚才那笔保存了吗",
        model=ScriptedModel([calls("get_proposal_status"), "Please look at the ledger."]),
        ledger=ledger,
        now=INVENTED_NOW,
        zone=INVENTED_ZONE,
        max_steps=6,
    )

    (taken,) = said.turn.steps[0].calls  # type: ignore[union-attr]
    handed = json.loads(taken.result)
    assert handed["code"] == "PROPOSAL_NOT_FOUND"
    assert handed["message"] == "找不到这条提议。"
    assert "does not mean it was not saved" in handed["what_it_means"]


# --- two assets sharing one code (part 10) ------------------------------------

TWINS = (
    *INVENTED_ASSETS,
    Asset(id="asset-coin-ab", code="AB", name="Abacus coin", kind=AssetKind.CRYPTO,
          pricing=Pricing.CANNOT_PRICE),
    Asset(id="asset-stock-ab", code="AB", name="Abacus Inc", kind=AssetKind.STOCK,
          pricing=Pricing.CANNOT_PRICE),
)  # fmt: skip


def test_two_assets_sharing_a_code_are_both_kept_and_named() -> None:
    (same,) = same_codes(TWINS)

    assert same.code == "AB"
    assert [asset.id for asset in same.assets] == ["asset-coin-ab", "asset-stock-ab"]


def test_a_question_about_a_code_two_assets_share_looks_nothing_up_and_names_both() -> None:
    ledger = FakeLedger(assets=TWINS)

    said = say(
        AssistantChat(),
        "我10月的AB交易",
        model=ScriptedModel([calls("list_trades", period="10月", asset="AB")]),
        ledger=ledger,
        now=INVENTED_NOW,
        zone=INVENTED_ZONE,
        max_steps=6,
    )

    assert "list_trades" not in ledger.calls
    assert "Abacus coin (crypto) and Abacus Inc (stock)" in said.reply
    assert "cannot tell which one you mean" in said.reply


def test_a_trade_of_a_code_two_assets_share_is_not_sent_and_both_are_named() -> None:
    assets = tuple(asset for asset in TWINS if asset.code != "USD") + tuple(
        asset for asset in USDT_ONLY_ASSETS if asset.code == "USD"
    )
    ledger = FakeLedger(assets=assets)
    words = "今天上午9:40买了100个AB，价格2 USDT，手续费0.1 USDT"
    rows = table(
        row(side="buy", coin="AB", quantity="100个AB", price="2 USDT", fee="0.1 USDT",
            time="今天上午9:40")
    )  # fmt: skip

    (said,), _, _ = talk(words, tools=[RECORD], screen=[SPOT], extraction=[rows], ledger=ledger)

    assert said.recorded is not None
    assert "propose_add" not in ledger.calls
    assert [trade.why for trade in said.recorded.left_out] == [LeftOut.SAME_CODE]
    assert "Abacus coin (crypto) and Abacus Inc (stock)" in said.reply


# --- the most trades listed (part 9) ------------------------------------------


def test_a_list_cut_at_the_most_listed_says_so_to_the_user_and_to_the_model() -> None:
    ledger = FakeLedger(most_listed=3)

    said = say(
        AssistantChat(),
        "我所有的交易",
        model=ScriptedModel([calls("list_trades"), "Done."]),
        ledger=ledger,
        now=INVENTED_NOW,
        zone=INVENTED_ZONE,
        max_steps=6,
    )

    (lookup,) = said.turn.lookups  # type: ignore[union-attr]
    assert lookup.cut and lookup.trade_count == 3
    assert CUT_WORDS in lookup_lines(lookup)
    assert "2000" in CUT_WORDS
    handed = json.loads(said.turn.steps[0].calls[0].result)  # type: ignore[union-attr]
    assert handed["only_the_latest_taken"] == 2000
    assert handed["trade_count"] == 3


def test_a_list_in_full_has_no_cut_mark() -> None:
    found = FakeLedger().list_trades(
        TradeFilter(first_day=date(2026, 10, 6), last_day=date(2026, 10, 6))
    )

    assert not found.cut
    assert len(found.trades) == 2
