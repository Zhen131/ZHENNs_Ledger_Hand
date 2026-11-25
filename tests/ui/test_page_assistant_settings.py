"""Tests of the Assistant page with the parts the wiring module builds: the demo ledger it makes,
how many steps it allows, and the demo ledger kept when a setting is changed.

The real wiring module builds the parts on a bare machine (``bare_machine``);
only the model is replaced by a scripted one, and the clock by the invented
book's fixed moment. Changing a setting on the Settings page builds every
part again; the demo ledger, and the proposals and trades in it, are carried
over. Every sentence, reply and trade is invented.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from ledger_hand.core.ledger_records import TradeFilter
from ledger_hand.flows.standing import LedgerKind
from ledger_hand.ledger.fake_ledger import FakeLedger
from ledger_hand.ledger.invented_book import INVENTED_NOW, INVENTED_ZONE
from ledger_hand.ports import ToolCall, ToolReply
from ledger_hand.settings import ASSISTANT_STEPS_VARIABLE, Variable
from ledger_hand.ui.assistant_cards import save_key
from ledger_hand.ui.session import BUILDER_KEY, PARTS_KEY
from ledger_hand.wiring import Parts, assemble
from tests.fakes.routed_model import RoutedModel
from tests.fakes.scripted_model import scripted_record
from tests.flows.scripted_flow import row, screened, table
from tests.ui.app_harness import APP_FILE
from tests.ui.assistant_harness import card_text, say_on_page, to_assistant
from tests.ui.page_harness import apply, set_setting, to_settings

RECORD = ToolReply(
    text="", calls=(ToolCall(name="propose_trade_add", arguments={}),), record=scripted_record()
)
SHARES = "今天15:30在IBKR买了2股MSFT，410美元一股，手续费1美元"
SHARES_ROW = row(
    side="buy",
    coin="MSFT",
    quantity="2股",
    price="410美元",
    fee="1美元",
    time="今天15:30",
    platform="IBKR",
)


class ScriptedBuilds:
    """Builds the parts with the real wiring module, then puts the scripted model in."""

    def __init__(self, model: RoutedModel) -> None:
        self.model = model
        self.built: list[Parts] = []

    def __call__(self, changes: Mapping[Variable, str]) -> Parts:
        parts = dataclasses.replace(
            assemble(changes), model=self.model, clock=lambda: INVENTED_NOW, zone=INVENTED_ZONE
        )
        self.built.append(parts)
        return parts


def test_the_wiring_module_builds_the_demo_ledger_and_the_steps(
    bare_machine: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(ASSISTANT_STEPS_VARIABLE, "4")

    parts = assemble()

    assert isinstance(parts.ledger, FakeLedger)
    assert parts.ledger_kind is LedgerKind.DEMO
    assert parts.assistant_steps == 4


def test_a_setting_changed_keeps_the_demo_ledger_its_proposal_and_its_saved_trade(
    bare_machine: Path,
) -> None:
    model = RoutedModel(
        tools=[RECORD],
        screen=[screened(("spot_trade", "今天15:30在IBKR买了2股MSFT"))],
        extraction=[table(SHARES_ROW)],
    )
    builds = ScriptedBuilds(model)
    page = AppTest.from_file(str(APP_FILE), default_timeout=30)
    page.session_state[BUILDER_KEY] = builds
    page = to_assistant(page.run())
    page = say_on_page(page, SHARES)
    ledger = builds.built[0].ledger
    assert isinstance(ledger, FakeLedger)
    page = page.button(key=save_key("proposal-1")).click().run()
    trades = len(ledger.list_trades(TradeFilter()))

    page = to_settings(page)
    page = set_setting(page, Variable.TIMEOUT_SECONDS, "45")
    page = apply(page)
    page = to_assistant(page)

    assert len(builds.built) == 2
    assert builds.built[1].ledger is not ledger
    assert page.session_state[PARTS_KEY].ledger is ledger
    assert "Status: saved" in card_text(page, "proposal-1")
    assert len(ledger.list_trades(TradeFilter())) == trades
