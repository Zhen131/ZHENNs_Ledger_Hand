"""Capture what the real ledger answers through its assistant link, one sample file a case.

    LEDGER_HAND_LEDGER_DIR=path/to/LocalFirstTradingLedger \\
        .venv/bin/python scripts/capture_ledger_samples.py --out tests/ledger/samples

No model is used. The script starts the ledger's assistant link as
``try_ledger_link.py`` does (port and settings the same; the token printed
only to a terminal), and calls the eight tools in every case the next
part of the work needs to see: reading with and without filters, a second
page, every refusal of a filter, proposals taken, refused and partly taken,
times with and without a zone, changes and deletions that cannot be made,
and a proposal pending, saved, rejected, void and lost after a reload. Each
answer is written as it came into a file of its own in ``--out``, named
for its case, beside the tool and the arguments sent.

Some cases need the person on the ledger page: connecting, saving one
proposal, rejecting one, disconnecting, reloading, switching the page's
language. For each, the script prints one line starting ``PAGE ACTION``
with a name, the proposal it is about when there is one, and what to do,
and waits for Enter. The ledger page must hold an invented ledger only,
with at least: a deposit of USDT and one of USD; buys and a sell of coins;
a buy of a US stock in USD; one trade with a day and no time of day; one
with a platform and a note and one with neither (see ``--help``).

Every number sent is invented. The token and the ledger's folder are in no
sample. A case whose answer does not come is reported and left without a
file; nothing is written by hand in its place.

Exit status: 0 every case was captured; 1 some were not, or the link
failed; 2 the script could not start.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, TextIO

from try_ledger_link import Session, show_start, wait_for_page

from ledger_hand.ledger.link_client import AnswerKind, ToolAnswer
from ledger_hand.ledger.link_failures import LedgerLinkError
from ledger_hand.settings import LEDGER_DIRECTORY_VARIABLE, SettingsError
from ledger_hand.wiring import ledger_link

MODEL_NAME = "no model (sample capture)"
SOURCE_TEXT = "Ledger Hand sample capture: invented trades only"


@dataclass
class Capture:
    """Where samples go, what was learned on the way, and which cases were missed."""

    session: Session
    out: Path
    stdin: TextIO
    ids: dict[str, str] = field(default_factory=dict)
    proposals: dict[str, str] = field(default_factory=dict)
    missed: list[str] = field(default_factory=list)
    written: list[str] = field(default_factory=list)

    def sample(self, name: str, what: str, tool: str, arguments: Mapping[str, Any]) -> ToolAnswer:
        """Call ``tool`` and write its answer, as it came, into ``name``.json."""
        answer = self.session.call(tool, arguments)
        record = {
            "case": name,
            "what": what,
            "tool": tool,
            "arguments": dict(arguments),
            "answer": {"kind": answer.kind.value, "content": answer.content},
        }
        path = self.out / f"{name}.json"
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.written.append(name)
        code = answer.content.get("code") if answer.kind is AnswerKind.ERROR else None
        self.session.say(f"  {name}: {answer.kind.value}{f' {code}' if code else ''}")
        return answer

    def action(self, name: str, about: str, what: str) -> None:
        """Ask the person for one thing on the ledger page, and wait for Enter."""
        target = f" {about}" if about else ""
        self.session.say(f"PAGE ACTION {name}{target}: {what} Press Enter when done.")
        self.stdin.readline()

    def miss(self, name: str, why: str) -> None:
        self.missed.append(f"{name}: {why}")
        self.session.say(f"  {name}: NOT CAPTURED, {why}")


def trade(capture: Capture, side: str, asset: str, money: str, numbers: Sequence[str]) -> dict:
    """One trade to propose: quantity, price, total and fee in ``money``, dated from ``numbers``."""
    quantity, price, total, fee, day = numbers
    return {
        "occurredDate": day,
        "type": side,
        "assetId": capture.ids[asset],
        "quantity": quantity,
        "price": price,
        "totalValue": total,
        "quoteAssetId": capture.ids[money],
        "fee": fee,
        "feeAssetId": capture.ids[money],
    }


def proposed(capture: Capture, answer: ToolAnswer, names: Sequence[str]) -> None:
    """Keep the proposal id of every trade taken, under the names given in order."""
    if answer.kind is AnswerKind.ERROR:
        return
    for name, result in zip(names, answer.content.get("results", []), strict=False):
        if result.get("ok"):
            capture.proposals[name] = str(result["proposalId"])


def learn_ids(capture: Capture, answer: ToolAnswer) -> None:
    for asset in answer.content.get("assets", []):
        capture.ids.setdefault(str(asset["assetCode"]), str(asset["assetId"]))


def first_trade(capture: Capture, code: str, side: str) -> dict[str, Any] | None:
    answer = capture.session.call("list_trades", {"assetId": capture.ids[code], "side": side})
    trades = answer.content.get("trades", []) if answer.kind is AnswerKind.RESULT else []
    return trades[-1] if trades else None


# --- the cases, in the order they are run ---------------------------------------------


def reads(capture: Capture, today: str) -> None:
    learn_ids(capture, capture.sample("list-assets", "every asset", "list_assets", {}))
    capture.sample("list-trades-no-filter", "first page, no filter", "list_trades", {})
    dates = {"startDate": "2026-11-15", "endDate": "2026-11-16"}
    capture.sample("list-trades-dates", "two days, both included", "list_trades", dates)
    btc = {"assetId": capture.ids["BTC"]}
    capture.sample("list-trades-asset", "trades of one coin", "list_trades", btc)
    usdt = {"assetId": capture.ids["USDT"]}
    capture.sample("list-trades-asset-is-currency", "filtered by money", "list_trades", usdt)
    backwards = {"startDate": "2026-11-20", "endDate": "2026-11-01"}
    capture.sample("list-trades-dates-reversed", "end before start", "list_trades", backwards)
    nowhere = {"assetId": "asset-does-not-exist"}
    capture.sample("list-trades-asset-not-found", "no such asset", "list_trades", nowhere)
    whole = {"startDate": "1970-01-01", "endDate": today}
    capture.sample("period-summary-all-time", "1970-01-01 to today", "get_period_summary", whole)
    for day in ("2026-11-15", "2026-11-16"):
        one = {"startDate": day, "endDate": day}
        capture.sample(f"period-summary-{day}", f"the day {day}", "get_period_summary", one)
    capture.sample(
        "period-summary-dates-reversed",
        "end before start",
        "get_period_summary",
        backwards,
    )
    capture.sample("positions", "every position", "get_positions", {})


def proposals_add(capture: Capture) -> None:
    two = [
        trade(capture, "buy", "BTC", "USDT", ("0.01", "60000", "600", "0.6", "2026-11-18")),
        trade(capture, "buy", "ETH", "USDT", ("0.5", "3000", "1500", "1", "2026-11-18")),
    ]
    arguments = {"trades": two, "sourceText": SOURCE_TEXT, "modelName": MODEL_NAME}
    answer = capture.sample(
        "propose-add-two-taken", "two, both taken", "propose_trade_add", arguments
    )
    proposed(capture, answer, ["to-save", "to-reject"])
    too_much = trade(capture, "sell", "BTC", "USDT", ("50", "70000", "3500000", "1", "2026-11-18"))
    fine = trade(capture, "buy", "ADA", "USDT", ("100", "0.5", "50", "0.1", "2026-11-18"))
    arguments = {"trades": [too_much, fine], "sourceText": SOURCE_TEXT, "modelName": MODEL_NAME}
    answer = capture.sample(
        "propose-add-one-refused",
        "a sell beyond holdings, and a buy",
        "propose_trade_add",
        arguments,
    )
    proposed(capture, answer, ["refused", "to-void"])
    zoned = trade(capture, "buy", "ETH", "USDT", ("0.2", "3100", "620", "0.5", "2026-11-20"))
    zoned |= {"occurredTime": "22:30", "occurredTimeZone": "America/New_York"}
    arguments = {"trades": [zoned], "sourceText": SOURCE_TEXT, "modelName": MODEL_NAME}
    answer = capture.sample(
        "propose-add-time-with-zone", "22:30 New York", "propose_trade_add", arguments
    )
    proposed(capture, answer, ["zoned"])
    day_only = trade(capture, "buy", "ADA", "USDT", ("10", "0.5", "5", "0", "2026-11-19"))
    arguments = {"trades": [day_only], "sourceText": SOURCE_TEXT, "modelName": MODEL_NAME}
    capture.sample("propose-add-date-only", "a day, no time", "propose_trade_add", arguments)
    usd = trade(capture, "buy", "BTC", "USD", ("0.01", "61000", "610", "1", "2026-11-18"))
    arguments = {"trades": [usd], "sourceText": SOURCE_TEXT, "modelName": MODEL_NAME}
    capture.sample(
        "propose-add-other-money-no-rate",
        "BTC (priced in USDT) bought with USD, no costRate",
        "propose_trade_add",
        arguments,
    )


def as_write_side(saved: Mapping[str, Any]) -> dict[str, Any]:
    """A trade from list_trades, renamed for propose_trade_update, without its time."""
    written = {
        "type": saved["side"],
        "assetId": saved["assetId"],
        "quantity": saved["quantity"],
        "price": saved["price"],
        "totalValue": saved["tradeAmount"],
        "quoteAssetId": saved["tradeCurrencyAssetId"],
        "fee": saved["fee"],
        "feeAssetId": saved["feeAssetId"],
        "platform": saved["platform"],
        "note": saved["note"],
    }
    if saved.get("costRate") is not None:
        written["costRate"] = saved["costRate"]
    return written


def proposals_change(capture: Capture) -> None:
    eth = first_trade(capture, "ETH", "buy")
    if eth is None:
        capture.miss("propose-update-fee-only", "no saved ETH buy to change")
        return
    changed = as_write_side(eth) | {"fee": "1.5"}
    arguments = {"tradeId": eth["tradeId"], "trade": changed, "modelName": MODEL_NAME}
    arguments["sourceText"] = SOURCE_TEXT
    answer = capture.sample(
        "propose-update-fee-only", "only the fee, no time field", "propose_trade_update", arguments
    )
    proposed(capture, answer, ["update"])
    capture.sample(
        "propose-update-already-pending",
        "the same trade again while its change waits",
        "propose_trade_update",
        arguments | {"trade": changed | {"fee": "1.6"}},
    )
    missing = arguments | {"tradeId": "trade-does-not-exist"}
    capture.sample("propose-update-not-found", "no such trade", "propose_trade_update", missing)
    stock = first_trade(capture, "NVDA", "buy")
    if stock is not None:
        one = {"tradeId": stock["tradeId"], "sourceText": SOURCE_TEXT, "modelName": MODEL_NAME}
        capture.sample("propose-delete", "one trade", "propose_trade_delete", one)
    else:
        capture.miss("propose-delete", "no saved NVDA buy to delete")
    btc = first_trade(capture, "BTC", "buy")
    if btc is not None:
        one = {"tradeId": btc["tradeId"], "sourceText": SOURCE_TEXT, "modelName": MODEL_NAME}
        capture.sample(
            "propose-delete-breaks-timeline",
            "the first BTC buy, which a later sell needs",
            "propose_trade_delete",
            one,
        )
    capture.sample(
        "propose-delete-not-found",
        "no such trade",
        "propose_trade_delete",
        {"tradeId": "trade-does-not-exist", "modelName": MODEL_NAME},
    )


def status(capture: Capture, case: str, proposal: str, what: str) -> None:
    proposal_id = capture.proposals.get(proposal)
    if proposal_id is None:
        capture.miss(case, f"the proposal {proposal!r} was not taken")
        return
    capture.sample(case, what, "get_proposal_status", {"proposalId": proposal_id})


def statuses(capture: Capture) -> None:
    status(capture, "status-pending", "to-save", "waiting for the person")
    capture.action("save", capture.proposals.get("to-save", ""), "Click Save on this proposal.")
    status(capture, "status-saved", "to-save", "after Save on the page")
    capture.action("reject", capture.proposals.get("to-reject", ""), "Click Reject on it.")
    status(capture, "status-rejected", "to-reject", "after Reject on the page")
    capture.action("save", capture.proposals.get("zoned", ""), "Click Save on this proposal.")
    status(capture, "status-saved-time-with-zone", "zoned", "the 22:30 New York one, saved")
    for day in ("2026-11-20", "2026-11-21"):
        one = {"startDate": day, "endDate": day}
        capture.sample(
            f"list-trades-on-{day}-after-zoned-save",
            "which day the New York trade falls on",
            "list_trades",
            one,
        )
        capture.sample(f"period-summary-{day}-after-zoned-save", day, "get_period_summary", one)


def language(capture: Capture) -> None:
    capture.action("language", "en", "Switch the ledger page's language to English.")
    learn = trade(capture, "sell", "BTC", "USDT", ("50", "70000", "3500000", "1", "2026-11-18"))
    arguments = {"trades": [learn], "modelName": MODEL_NAME}
    capture.sample(
        "propose-add-refused-page-in-english", "page in English", "propose_trade_add", arguments
    )
    usdt = {"assetId": capture.ids["USDT"]}
    capture.sample(
        "list-trades-asset-is-currency-page-in-english", "page in English", "list_trades", usdt
    )
    capture.action("language", "zh", "Switch the ledger page's language back to Chinese.")


def pages(capture: Capture) -> None:
    """Fill the ledger past one page of list_trades: 20 at a time, saved on the page.

    Run while nothing else waits, since the pending list holds at most 20.
    """
    for round_number in range(3):
        for half in range(2):
            day = f"2026-10-{10 + round_number * 2 + half:02d}"
            batch = [
                trade(capture, "buy", "ADA", "USDT", ("1", "0.4", "0.4", "0", day))
                for _ in range(10)
            ]
            capture.session.call("propose_trade_add", {"trades": batch, "modelName": MODEL_NAME})
        if round_number == 0:
            extra = [trade(capture, "buy", "ADA", "USDT", ("1", "0.4", "0.4", "0", "2026-10-30"))]
            capture.sample(
                "propose-add-list-full",
                "a 21st proposal while 20 wait",
                "propose_trade_add",
                {"trades": extra, "modelName": MODEL_NAME},
            )
        capture.action("save-all", "", "Click Save all on the pending list.")
    first = capture.sample("list-trades-page-1", "first page", "list_trades", {})
    token = first.content.get("nextPageToken")
    if not token:
        capture.miss("list-trades-page-2", "the first page said there is no second one")
        return
    capture.sample("list-trades-page-2", "second page", "list_trades", {"pageToken": token})


def endings(capture: Capture) -> None:
    capture.action("disconnect", "", "Click Disconnect on the ledger page.")
    status(capture, "page-disconnected-call", "to-void", "a call after the page disconnected")
    capture.action("connect", "", "Connect the assistant again with the same port and token.")
    if not wait_for_page(capture.session.link, 120.0):
        capture.miss("status-void", "the page did not connect again")
        return
    status(capture, "status-void", "to-void", "pending when the page disconnected")
    capture.action("reload", "", "Reload the ledger page, open the ledger, connect again.")
    if not wait_for_page(capture.session.link, 180.0):
        capture.miss("status-not-found-after-reload", "the page did not connect again")
        return
    status(capture, "status-not-found-after-reload", "to-save", "a saved one, after a reload")


CASES: tuple[Callable[[Capture], None], ...] = (
    pages,
    proposals_add,
    proposals_change,
    statuses,
    language,
    endings,
)


def run(capture: Capture, wait_seconds: float) -> None:
    before = {"name": "page-not-connected", "what": "before any page connects"}
    capture.sample(before["name"], before["what"], "list_assets", {})
    capture.action("connect", "", "Connect the assistant on the ledger page.")
    if not wait_for_page(capture.session.link, wait_seconds):
        capture.miss("everything after connecting", "no page connected")
        return
    reads(capture, date.today().isoformat())
    for case in CASES:
        case(capture)


def options(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture the real ledger's answers as samples.")
    parser.add_argument("--out", type=Path, required=True, help="the folder samples go into")
    parser.add_argument("--wait-seconds", type=float, default=300.0)
    return parser.parse_args(argv)


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
    arguments.out.mkdir(parents=True, exist_ok=True)
    capture = Capture(Session(link, out), arguments.out, sys.stdin)
    failed = False
    try:
        with link:
            show_start(link, out)
            run(capture, arguments.wait_seconds)
    except LedgerLinkError as error:
        print(f"The link failed: {error}", file=out)
        failed = True
    print(
        f"\n{len(capture.written)} samples written; {len(capture.missed)} not captured:", file=out
    )
    for missed in capture.missed:
        print(f"  {missed}", file=out)
    return 1 if failed or capture.missed else 0


if __name__ == "__main__":
    raise SystemExit(main())
