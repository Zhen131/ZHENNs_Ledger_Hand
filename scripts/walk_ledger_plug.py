"""Walk the real ledger's plug through a ledger page, with no model: read, record, change, delete.

    LEDGER_HAND_LEDGER_DIR=path/to/LocalFirstTradingLedger \\
        .venv/bin/python scripts/walk_ledger_plug.py [--model-name NAME]

It starts the ledger's own assistant link as ``try_ledger_link.py`` does
(the port and the settings the same; the token printed only to a
terminal), waits for the person to connect the ledger page, and then does
everything through the ledger port's real plug (``ledger.link_ledger``),
printing what this program sees after the plug turned the ledger's answers
into its own shapes:

1. the assets; the trades of BTC in November 2026; the sums of all time and
   the sums of BTC alone; the holdings;
2. a call to record two invented trades, a buy of BTC and a sell of more
   ETH than is held: the ledger takes the first and turns the second down;
3. a change of one trade's fee alone, and a deletion of another;
4. where each proposal stands, after the person saved them on the page.

Some steps need the person on the ledger page; for each the script prints
one line starting ``PAGE ACTION`` with a name, the proposal it is about,
and what to do, and waits for Enter: connect, look at the pending list,
save one proposal, look at the change history. The ledger page must hold an
invented ledger only, with a BTC buy of 10 November 2026 at 09:30 in
Budapest (platform and note given), an ETH buy, and an NVDA buy of
14 November 2026 (the set-up of ``capture_ledger_samples.py``).

Every number sent is invented. The token is never written anywhere.

Exit status: 0 every step went as expected; 1 a step did not, or the link
failed; 2 the script could not start.
"""

from __future__ import annotations

import argparse
import dataclasses
import sys
from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import TextIO
from zoneinfo import ZoneInfo

from try_ledger_link import show_start, wait_for_page

from ledger_hand.assistant.lookups import when_text
from ledger_hand.core.ledger_records import (
    Figure,
    LedgerTrade,
    MoneyAmount,
    PeriodRequest,
    TradeFacts,
    TradeFilter,
)
from ledger_hand.core.proposals import ProposalResult
from ledger_hand.core.trade import Side
from ledger_hand.ledger.link_failures import LedgerLinkError
from ledger_hand.ledger.link_ledger import LinkLedger
from ledger_hand.ports import LedgerError
from ledger_hand.settings import LEDGER_DIRECTORY_VARIABLE, SettingsError
from ledger_hand.wiring import ledger_link, link_ledger

MODEL_NAME = "no model (plug walk-through)"
ZONE = "Europe/Budapest"
RECORD_WORDS = "今天10:15在币安买了0.002 BTC，64000一个，手续费0.5 USDT；又卖了50个ETH，3100一个"
CHANGE_WORDS = "把11月10号那笔BTC的手续费改成6 USDT"
DELETE_WORDS = "把11月14号那笔NVDA删掉"


def options(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model-name", default=MODEL_NAME, help="the model name sent along")
    parser.add_argument("--wait-seconds", type=float, default=300.0)
    return parser.parse_args(argv)


class Walk:
    """The plug and where to print, and the person to ask on the page."""

    def __init__(self, ledger: LinkLedger, out: TextIO, stdin: TextIO) -> None:
        self.ledger = ledger
        self.out = out
        self.stdin = stdin
        self.problems: list[str] = []

    def say(self, line: str = "") -> None:
        print(line, file=self.out, flush=True)

    def action(self, name: str, about: str, what: str) -> None:
        target = f" {about}" if about else ""
        self.say(f"PAGE ACTION {name}{target}: {what} Press Enter when done.")
        self.stdin.readline()

    def expect(self, what: str, *, holds: bool) -> None:
        self.say(f"  {'as expected' if holds else 'NOT AS EXPECTED'}: {what}")
        if not holds:
            self.problems.append(what)


def figure(value: Figure | None) -> str:
    if value is None:
        return "-"
    if isinstance(value, MoneyAmount):
        return f"{format(value.amount, 'f')} {value.currency}"
    return f"not worked out ({value.reason})"


def trade_line(trade: LedgerTrade) -> str:
    facts = trade.facts
    words = "none" if facts.raw_text is None else repr(facts.raw_text)
    line = (
        f"{trade.id[:8]} {when_text(facts)} ({facts.zone or 'no zone'}) {facts.side.value} "
        f"{format(facts.quantity, 'f')} {facts.asset} at {format(facts.price, 'f')} "
        f"{facts.quote}, fee {format(facts.fee, 'f')} {facts.fee_asset}, platform "
        f"{facts.platform or '-'}, note {facts.note or '-'}, words {words}"
    )
    if trade.realized is not None:
        line += f", realized {figure(trade.realized)}"
    return line


def checks_lines(walk: Walk, result: ProposalResult) -> list[str]:
    ids: list[str] = []
    for number, check in enumerate(result.checks, start=1):
        if check.proposal_id is not None:
            walk.say(f"  trade {number}: waits in the ledger as {check.proposal_id}")
            ids.append(check.proposal_id)
        else:
            walk.say(f"  trade {number}: turned down, {check.code}: {check.message}")
    return ids


def reading(walk: Walk) -> list[LedgerTrade]:
    ledger = walk.ledger
    walk.say("\n1. Reading")
    assets = ledger.list_assets()
    walk.say(f"list_assets: {len(assets)} assets")
    for asset in assets:
        walk.say(
            f"  {asset.code} ({asset.kind.value}, {asset.pricing.value}, "
            f"priced in {asset.price_currency or '-'})"
        )
    november = TradeFilter(first_day=date(2026, 11, 1), last_day=date(2026, 11, 30), asset="BTC")
    listed = ledger.list_trades(november)
    walk.say(f"list_trades of BTC, 2026-11-01 to 2026-11-30: {len(listed.trades)} trades")
    for trade in listed.trades:
        walk.say(f"  {trade_line(trade)}")
    walk.expect("the list is whole, not cut", holds=not listed.cut)
    for request, what in ((PeriodRequest(), "all time"), (PeriodRequest(asset="BTC"), "BTC")):
        summary = ledger.period_summary(request)
        walk.say(f"period_summary, {what}: {summary.trade_count} trades")
        for group in summary.by_currency:
            walk.say(
                f"  {group.currency}: {group.buy_count} buys, {group.sell_count} sells, "
                f"spent {figure(group.spent)}, received {figure(group.received)}, "
                f"fees {', '.join(figure(fee) for fee in group.fees) or '-'}, "
                f"realized {figure(group.realized)} (sells {figure(group.realized_from_sells)}, "
                f"transfers {figure(group.realized_from_transfers)})"
            )
    held = ledger.positions()
    walk.say(f"positions: {len(held)} holdings, none sold out, no cash")
    for position in held:
        walk.say(
            f"  {position.asset}: {format(position.quantity, 'f')}, cost {figure(position.cost)}, "
            f"on paper {figure(position.unrealized)}"
        )
    walk.expect("no holding of 0 is shown", holds=all(position.quantity > 0 for position in held))
    return list(ledger.list_trades(TradeFilter()).trades)


def recording(walk: Walk) -> list[str]:
    walk.say("\n2. Recording two trades in one call")
    today = datetime.now(ZoneInfo(ZONE)).replace(hour=10, minute=15, second=0, microsecond=0)
    common = {
        "occurred": today,
        "quote": "USDT",
        "fee_asset": "USDT",
        "note": "",
        "raw_text": RECORD_WORDS,
        "zone": ZONE,
        "date_only": False,
        "cost_rate": None,
    }
    buy = TradeFacts(
        side=Side.BUY,
        asset="BTC",
        quantity=Decimal("0.002"),
        price=Decimal("64000"),
        total=Decimal("128"),
        fee=Decimal("0.5"),
        platform="Binance",
        **common,  # type: ignore[arg-type]
    )
    sell = TradeFacts(
        side=Side.SELL,
        asset="ETH",
        quantity=Decimal("50"),
        price=Decimal("3100"),
        total=Decimal("155000"),
        fee=Decimal("0"),
        platform="",
        **common,  # type: ignore[arg-type]
    )
    result = walk.ledger.propose_add((buy, sell), RECORD_WORDS)
    ids = checks_lines(walk, result)
    walk.expect("one trade taken, one turned down", holds=len(ids) == 1 and not result.all_passed)
    if ids:
        walk.action("pending", ids[0], "Look at the pending list.")
        walk.action("save", ids[0], "Click Save on this proposal.")
    return ids


def changing(walk: Walk, before: list[LedgerTrade]) -> list[str]:
    walk.say("\n3. Changing one fee, deleting one trade")
    ids: list[str] = []
    bought = next(
        (t for t in before if t.facts.asset == "BTC" and t.facts.platform == "Binance"), None
    )
    if bought is None:
        walk.expect("a BTC buy on Binance is in the ledger", holds=False)
        return ids
    walk.say(f"before: {trade_line(bought)}")
    changed = dataclasses.replace(bought.facts, fee=Decimal("6"))
    result = walk.ledger.propose_update(bought.id, changed, CHANGE_WORDS)
    found = checks_lines(walk, result)
    walk.expect("the change waits in the ledger", holds=len(found) == 1)
    if found:
        walk.action("change", found[0], "Look at the change, before and after.")
        walk.action("save", found[0], "Click Save on this proposal.")
        ids += found
    nvda = next((t for t in before if t.facts.asset == "NVDA"), None)
    if nvda is None:
        walk.expect("an NVDA buy is in the ledger", holds=False)
        return ids
    walk.say(f"to delete: {trade_line(nvda)}")
    found = checks_lines(walk, walk.ledger.propose_delete(nvda.id, DELETE_WORDS))
    walk.expect("the deletion waits in the ledger", holds=len(found) == 1)
    if found:
        walk.action("save", found[0], "Click Save on this proposal.")
        ids += found
    after = {t.id: t for t in walk.ledger.list_trades(TradeFilter()).trades}
    kept = after.get(bought.id)
    if kept is not None:
        walk.say(f"after: {trade_line(kept)}")
        same = dataclasses.replace(kept.facts, fee=bought.facts.fee) == bought.facts
        walk.expect("only the fee changed", holds=kept.facts.fee == Decimal("6") and same)
    walk.expect("the NVDA buy is gone", holds=nvda.id not in after)
    return ids


def standing(walk: Walk, ids: Sequence[str]) -> None:
    walk.say("\n4. Where each proposal stands")
    for proposal in ids:
        state = walk.ledger.proposal_status(proposal)
        extra = f", wrote {state.trade_id}" if state.trade_id else ""
        walk.say(f"  {proposal}: {state.status.value}{extra}")
        walk.expect(f"{proposal} is saved", holds=state.status.value == "saved")
    walk.action("history", "", "Open the change history.")


def run(walk: Walk) -> bool:
    before = reading(walk)
    ids = recording(walk)
    ids += changing(walk, before)
    standing(walk, ids)
    walk.say(f"\n{len(walk.problems)} step(s) not as expected")
    return not walk.problems


def main(argv: Sequence[str] | None = None, out: TextIO = sys.stdout) -> int:
    arguments = options(argv)
    try:
        link = ledger_link()
    except SettingsError as error:
        print(f"A setting was refused: {error}", file=out)
        return 2
    if link is None:
        print(f"Name the ledger's folder in {LEDGER_DIRECTORY_VARIABLE} first.", file=out)
        return 2
    try:
        with link:
            show_start(link, out)
            print("PAGE ACTION connect: Connect the assistant there.", file=out, flush=True)
            if not wait_for_page(link, arguments.wait_seconds):
                print("No ledger page connected in time.", file=out)
                return 1
            print("A ledger page is connected.", file=out, flush=True)
            walk = Walk(link_ledger(link, arguments.model_name), out, sys.stdin)
            done = run(walk)
    except (LedgerLinkError, LedgerError) as error:
        print(f"The ledger failed: {error}", file=out)
        return 1
    return 0 if done else 1


if __name__ == "__main__":
    raise SystemExit(main())
